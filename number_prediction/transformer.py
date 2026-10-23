"""Causal, province-isolated dual-prize Transformer with explicit missing tokens."""
import copy
import json
import random
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .baselines import probabilities


class CausalTransformer(nn.Module):
    def __init__(self, identities, d_model=256, nhead=8, layers=6, dropout=.1, sequence_length=128):
        super().__init__()
        self.config = dict(identities=identities, d_model=d_model, nhead=nhead, layers=layers,
                           dropout=dropout, sequence_length=sequence_length)
        self.g8 = nn.Embedding(103, d_model, padding_idx=0)
        self.db = nn.Embedding(103, d_model, padding_idx=0)
        self.position = nn.Embedding(sequence_length, d_model)
        self.province = nn.Embedding(identities, d_model)
        self.region = nn.Embedding(2, d_model)
        self.calendar = nn.Linear(1, d_model, bias=False)
        self.query = nn.Linear(2, d_model)
        layer = nn.TransformerEncoderLayer(d_model, nhead, d_model * 4, dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.heads = nn.ModuleList([nn.Linear(d_model, 100), nn.Linear(d_model, 100)])

    def forward(self, sequence, lengths, identities, regions, query):
        length = sequence.shape[1]
        positions = torch.arange(length, device=sequence.device)
        x = self.g8(sequence[:, :, 0]) + self.db(sequence[:, :, 1]) + self.position(positions)[None]
        x = x + self.calendar(sequence[:, :, 2:3].float() / 10000)
        x = x + self.province(identities)[:, None] + self.region(regions)[:, None]
        padding = sequence[:, :, 0] == 0
        causal = torch.triu(torch.ones(length, length, dtype=torch.bool, device=x.device), diagonal=1)
        hidden = self.encoder(x, mask=causal, src_key_padding_mask=padding)
        last = hidden[torch.arange(len(x), device=x.device), lengths]
        last = last + self.query(query.float() / torch.tensor([10000., 5.], device=x.device))
        return torch.stack([head(last) for head in self.heads], dim=1)


class TransformerModel:
    def __init__(self, identities, seed=1729, device="cpu", shrink=.01, **architecture):
        self.seed, self.device, self.shrink = seed, device, shrink
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; select CPU explicitly or use the training server")
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.set_num_threads(2)
        # Fail instead of silently using nondeterministic attention on CUDA.
        # The launcher sets CUBLAS_WORKSPACE_CONFIG before importing torch.
        torch.use_deterministic_algorithms(True)
        self.model = CausalTransformer(identities, **architecture).to(device)
        self.training_report = {}

    def fit(self, inputs, labels, validation, epochs=30, batch_size=64, learning_rate=1e-3,
            patience=5, checkpoint=None, checkpoint_every=100, stop_check=None, after_checkpoint=None):
        """Resume committed batches, including optimizer, scheduler, AMP and RNG state."""
        from .recovery import CheckpointStore, StopRequested, array_signature, ensure_context
        val_inputs, val_labels = validation
        labels = np.asarray(labels)
        if epochs < 1 or batch_size < 1 or checkpoint_every < 1:
            raise ValueError("Epochs, batch size and checkpoint interval must be positive")
        if labels.ndim != 2 or labels.shape[1] != 2 or not np.any(labels >= 0):
            raise ValueError("Expected two masked prize targets; missing targets use -1")
        store = None
        if checkpoint is not None:
            ensure_context(checkpoint, {"architecture": self.model.config, "seed": self.seed,
                "device": self.device, "torch": str(torch.__version__), "numpy": np.__version__,
                "epochs": epochs, "batch_size": batch_size, "learning_rate": learning_rate, "patience": patience,
                "arrays": array_signature([*inputs, labels, *val_inputs, val_labels])})
            store = CheckpointStore(Path(checkpoint) / "batches")
        tensors = [torch.as_tensor(x, device=self.device) for x in inputs]
        vt = [torch.as_tensor(x, device=self.device) for x in val_inputs]
        target = torch.as_tensor(labels, dtype=torch.long, device=self.device)
        vy = torch.as_tensor(val_labels, dtype=torch.long, device=self.device)
        if not (vy >= 0).any():
            raise ValueError("Validation has no eligible target labels")
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=2, factor=.5)
        amp = self.device.startswith("cuda")
        scaler = torch.amp.GradScaler("cuda", enabled=amp)
        best, best_state, stale = float("inf"), None, 0
        rng = np.random.default_rng(self.seed)
        losses, epoch, cursor, order, steps, complete = [], 0, 0, None, 0, False
        saved = store.load() if store else None
        if saved:
            state = torch.load(saved[0], map_location=self.device, weights_only=True)
            self.model.load_state_dict(state["model"])
            optimizer.load_state_dict(state["optimizer"])
            scheduler.load_state_dict(state["scheduler"])
            scaler.load_state_dict(state["scaler"])
            best, best_state, stale = state["best"], state["best_state"], state["stale"]
            losses, epoch, cursor, order = state["losses"], state["epoch"], state["cursor"], state["order"]
            steps, complete = state["steps"], state["complete"]
            random.setstate(state["python_rng"])
            nr = state["numpy_rng"]
            np.random.set_state((nr[0], np.asarray(nr[1], dtype=np.uint32), *nr[2:]))
            rng.bit_generator.state = state["shuffle_rng"]
            torch.set_rng_state(state["torch_rng"].cpu())
            if amp:
                torch.cuda.set_rng_state_all([v.cpu() for v in state["cuda_rng"]])
        self.resumed_from_step = steps

        def commit():
            if store:
                nr = np.random.get_state()
                state = {"model": self.model.state_dict(), "optimizer": optimizer.state_dict(),
                    "scheduler": scheduler.state_dict(), "scaler": scaler.state_dict(),
                    "best": best, "best_state": best_state, "stale": stale, "losses": losses,
                    "epoch": epoch, "cursor": cursor, "order": order, "steps": steps, "complete": complete,
                    "python_rng": random.getstate(), "numpy_rng": (nr[0], nr[1].tolist(), *nr[2:]),
                    "shuffle_rng": rng.bit_generator.state, "torch_rng": torch.get_rng_state(),
                    "cuda_rng": torch.cuda.get_rng_state_all() if amp else []}
                store.commit(lambda path: torch.save(state, path), ".pt",
                    {"epoch": epoch, "batch": cursor, "steps": steps, "complete": complete}, after_checkpoint)
            if stop_check:
                stop_check()

        if not saved:
            commit()
        while epoch < epochs and not complete:
            self.model.train()
            if order is None:
                order = rng.permutation(len(labels)).tolist()
                cursor = 0
            batches = np.array_split(np.asarray(order), max(1, int(np.ceil(len(labels) / batch_size))))
            for batch in range(cursor, len(batches)):
                ix = batches[batch]
                if (target[ix] >= 0).any():
                    optimizer.zero_grad(set_to_none=True)
                    with torch.autocast(device_type="cuda" if amp else "cpu", enabled=amp):
                        logits = self.model(*[t[ix] for t in tensors])
                        loss = nn.functional.cross_entropy(logits.reshape(-1, 100), target[ix].reshape(-1), ignore_index=-1)
                    scaler.scale(loss).backward()
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(self.model.parameters(), 1.)
                    scaler.step(optimizer)
                    scaler.update()
                cursor, steps = batch + 1, steps + 1
                if steps % checkpoint_every == 0:
                    commit()
                elif stop_check:
                    try:
                        stop_check()
                    except StopRequested:
                        commit()
                        raise
            self.model.eval()
            with torch.no_grad():
                total_loss, target_count = 0., 0
                for start in range(0, len(vy), batch_size):
                    sl = slice(start, start + batch_size)
                    total_loss += nn.functional.cross_entropy(self.model(*[x[sl] for x in vt]).reshape(-1, 100),
                        vy[sl].reshape(-1), ignore_index=-1, reduction="sum").item()
                    target_count += int((vy[sl] >= 0).sum())
                score = total_loss / target_count
            scheduler.step(score)
            losses.append(score)
            if score < best:
                best, best_state, stale = score, copy.deepcopy(self.model.state_dict()), 0
            else:
                stale += 1
            epoch, cursor, order = epoch + 1, 0, None
            complete = epoch >= epochs or stale >= patience
            commit()
        if best_state is None:
            raise ValueError("No training epochs completed")
        self.model.load_state_dict(best_state)
        self.training_report = {"epochs": len(losses), "validation_losses": losses,
                                "best_validation_loss": best, "mixed_precision": amp}
        return self

    def predict_proba(self, inputs, prize=1, batch_size=128):
        self.model.eval()
        output = []
        with torch.no_grad():
            for start in range(0, len(inputs[0]), batch_size):
                batch = [torch.as_tensor(x[start:start + batch_size], device=self.device) for x in inputs]
                logits = self.model(*batch)[:, prize]
                output.append(logits.softmax(-1).cpu().numpy())
        p = np.concatenate(output)
        return probabilities(p * (1 - self.shrink) + self.shrink / 100)

    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "metadata.json").write_text(json.dumps({"architecture": self.model.config, "seed": self.seed,
            "shrink": self.shrink, "training_report": self.training_report}), encoding="utf-8")
        torch.save({k: v.cpu() for k, v in self.model.state_dict().items()}, folder / "weights.pt")

    @classmethod
    def load(cls, folder, device="cpu"):
        folder = Path(folder)
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        obj = cls(**meta["architecture"], seed=meta["seed"], shrink=meta["shrink"], device=device)
        obj.model.load_state_dict(torch.load(folder / "weights.pt", map_location=device, weights_only=True))
        obj.training_report = meta["training_report"]
        return obj


def sequence_inputs(builder, queries, sequence_length=128):
    sequences, lengths = zip(*(builder.sequence(q, sequence_length) for q in queries))
    identities = [builder.identities.index((q["region"], q["province"])) for q in queries]
    regions = [int(q["region"] == "xsmt") for q in queries]
    from .data import day_index
    known = [[day_index(q["date"]), q.get("horizon", 1)] for q in queries]
    return [np.stack(sequences), np.asarray(lengths), np.asarray(identities), np.asarray(regions), np.asarray(known)]
