# Stage 3: PyTorch causal Transformer

Status: implementation and local pilot verified; full stage acceptance remains pending the work below.

The reference architecture remains 256 dimensions, 8 heads, 6 layers, dropout .1, sequence 128. The implementation supports masked G.8/G.ĐB heads, province/region embeddings, position/calendar information, causal attention, missing/start/padding tokens, early stopping, scheduling, clipping and optional CUDA mixed precision.

## Actual validation

Causality test changes future/padded tokens without changing earlier predictions. Masked training, empty histories and CPU weight round trips pass. The pilot uses d_model=16, two heads, one layer, sequence length eight, one epoch. CPU benchmark measured 1.4585 s load and 0.9393 ms median for its one-query probe; peak whole-process memory 327663616 bytes. This does not estimate the reference model or Windows cost.

## Remaining acceptance

Run reference-size server experiments and actual GPU/mixed-precision/Windows benchmarks.

Code and data hashes, measured metrics, environment and limitations are recorded in `local-evidence.json`. No GPU, Windows, final-test or future result is claimed.
