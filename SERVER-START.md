# Clone and set up the training server without sudo

This private branch includes current source and the frozen completed XSMN/XSMT modeling snapshot (75,424 eligible prize targets), retained source exports and eligibility decisions. The snapshot is compressed into about 13 MB of checksummed Git chunks; no Git LFS is required. It does not rescrape or alter the raw collector archives. Training outputs, environments, credentials and old runs are excluded.

Authenticate to this private repository using your own GitHub credentials/SSH setup. Never put a token into a command or commit:

```bash
git clone --branch codex/past-only-prediction --single-branch https://github.com/bendoantran/loto.git
cd loto
bash setup-server.sh
./loto doctor --device cuda
./loto pilot --device cuda
```

Setup requires Linux x86_64 with glibc, Bash, tar, sha256sum, curl or wget, and a writable executable persistent directory. Allow at least 20 GiB free plus training outputs/backups. The first setup downloads Python 3.12.15 and about 3.3 GB of pinned wheels over HTTPS from GitHub, PyPI and the official PyTorch CUDA 12.4 index. It uses no sudo, compiler, system Python, systemd or system package installation. It verifies hashes, restores the frozen snapshot and creates an isolated `.server-runtime` directory. Repeating setup verifies/reuses the same version. After pulling changed source, preserve the old runtime/run before preparing another version; a pending run requires its original source/environment.

If the server cannot download dependencies, use the separately prepared 3.5 GB offline transfer bundle instead. This branch includes data and source; it does not put multi-gigabyte dependency wheels into Git.

The NVIDIA kernel driver, OpenCL driver library and GPU-device permissions must already be provided by the server. Missing drivers require administrator support. If CUDA is unavailable, explicitly use `--device cpu` with doctor, pilot and preparation. The doctor performs readiness checks; the pilot fits only eight tree rounds/one tiny Transformer epoch on the 2007 subset. Setup starts no training, and the full development job below is separate and explicit.

```bash
./loto prepare --name development-001 --profile development --device cuda
cat .server-runtime/number_prediction/runs/development-001.launch/command.json
cat .server-runtime/number_prediction/runs/development-001.launch/params.json
# Only when ready to launch the reviewed longer job:
./loto start development-001
./loto status development-001
tail -f .server-runtime/number_prediction/runs/development-001.launch/process.log
```

Stop with `./loto stop development-001`, wait until both running fields are false, then explicitly `./loto resume development-001`. Keep this directory at its installed path. Detached jobs survive ordinary SSH disconnects, subject to server policy. After reboot, resume manually unless an allowed scheduler/user service starts it. Do not delete locks, reset checkpoints or change the environment/GPU allocation during a pending run. Back up entire stopped run and launch directories, including hidden recovery files, onto separate persistent storage.

See [number_prediction/SERVER.md](number_prediction/SERVER.md) and [number_prediction/RECOVERY.md](number_prediction/RECOVERY.md) for recovery and portability details. When using this Git-clone setup, the installed environment's root is `.server-runtime/`, so paths in the offline-bundle guide are relative to that directory. Local acceptance passed 78 regressions and 22 small GPU predictor/prize checks before this clone packaging; actual server, Windows, full-size resource acceptance and predictive advantage remain unverified. No full training or reserved final-test scoring has run.
