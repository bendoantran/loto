"""Tiny subprocess fixture: abrupt exit bypasses Python cleanup, like a dead worker."""
import os
from pathlib import Path
import sys
import time
import numpy as np


def main():
    kind, destination, mode = sys.argv[1:4]
    device = sys.argv[4] if len(sys.argv) > 4 else "cpu"
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(71)
    if kind == "transformer":
        from number_prediction.transformer import TransformerModel
        sequence = rng.integers(1, 100, (32, 8, 3))
        sequence[:, 0, :2] = 102
        sequence[:, :, 2] = np.arange(8)
        inputs = [sequence, np.full(32, 7), np.zeros(32, dtype=int),
                  np.arange(32) % 2, np.column_stack((np.arange(32), np.ones(32, dtype=int)))]
        labels = np.column_stack((np.arange(32) % 5, np.arange(32) % 7))
        def fault(progress):
            if mode == "crash" and progress["steps"] == 2:
                os._exit(23)
        model = TransformerModel(1, device=device, d_model=16, nhead=2, layers=1, sequence_length=8, dropout=.2)
        model.fit([x[:24] for x in inputs], labels[:24], ([x[24:] for x in inputs], labels[24:]),
                  epochs=1 if device == "cuda" else 3, batch_size=6, checkpoint=destination / "checkpoint", checkpoint_every=1,
                  after_checkpoint=fault)
        np.savez(destination / "result.npz", probabilities=model.predict_proba(inputs),
                 resumed=model.resumed_from_step, losses=model.training_report["validation_losses"],
                 training_device=str(next(model.model.parameters()).device), mixed_precision=model.training_report["mixed_precision"])
        import torch
        torch.save(model.model.state_dict(), destination / "final.pt")
        if not (destination / "native").exists():
            model.save(destination / "native")
    else:
        from number_prediction.trees import TreeModel
        midfit = kind == "catboost-midfit"
        x = rng.normal(size=(16384, 64)).astype("float32") if midfit else rng.normal(size=(128, 6))
        y = np.arange(len(x)) % 100 if midfit else (x[:, 0] > .1).astype(int) + (x[:, 1] > .5).astype(int)
        def fault(progress):
            if mode == "crash":
                if kind == "catboost":
                    if progress["rounds"] == 2:
                        time.sleep(1.1)
                    if progress["rounds"] >= 4 and progress["native_snapshot"]:
                        os._exit(23)
                elif progress["rounds"] == 3:
                    os._exit(23)
        model = TreeModel("catboost" if midfit else kind, iterations=8, depth=2, threads=2, device=device,
                          catboost_logging_level="Debug" if midfit else "Silent")
        model.fit(x, y, checkpoint=destination / "checkpoint", checkpoint_every=1, after_checkpoint=fault)
        np.savez(destination / "result.npz", probabilities=model.predict_proba(x[:128] if midfit else x), resumed=model.resumed_from_round,
                 training_device=model.training_device,
                 trees=model.model.tree_count_ if midfit else -1)
        if not (destination / "native").exists():
            model.save(destination / "native")


if __name__ == "__main__":
    main()
