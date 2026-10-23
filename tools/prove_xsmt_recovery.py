"""Reproducible OFFLINE fault injection using frozen raw HTML, never live data."""
import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import history
from tools import monitor


def fixture(day):
    return gzip.decompress((REPO / f"reference/xsmt/raw/{day}.html.gz").read_bytes())


def worker(root, mode, limit=None):
    def transport(url, timeout):
        assert timeout == 20
        day = history.datetime.strptime(url.rsplit('/', 1)[1][5:-5], '%d-%m-%Y').date().isoformat()
        with (root / 'requests.jsonl').open('a') as f:
            f.write(json.dumps({'date': day, 'url': url, 'transport': 'frozen fixture'}) + '\n')
        # A resumed year transition must first reconcile the earlier year export.
        if day == '2026-01-01':
            assert (root / 'years/2025/results.jsonl').exists()
        return fixture(day)

    original_atomic = history.atomic_write
    def atomic(path, content):
        original_atomic(path, content)
        if mode == 'after_raw' and str(path).endswith('.html.gz'):
            os._exit(71)

    original_progress = history.write_progress
    def progress(root, db, *args, **kwargs):
        if mode == 'after_commit' and history.summary(db)['processed_days']:
            os._exit(72)
        return original_progress(root, db, *args, **kwargs)

    db = history.connect(root, region='xsmt')
    with history.WorkerLock(root), patch.object(history, 'fetch', side_effect=transport), \
         patch.object(history, 'atomic_write', side_effect=atomic), \
         patch.object(history, 'write_progress', side_effect=progress):
        history.collect(root, db, interval=0, limit=limit, region='xsmt')
    db.close()


def run_worker(root, mode='normal', limit=None, expected=0):
    command = [sys.executable, str(Path(__file__).resolve()), 'worker', '--root', str(root), '--mode', mode]
    if limit:
        command += ['--limit', str(limit)]
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=30)
    if result.returncode != expected:
        raise AssertionError(f'Worker code {result.returncode}, expected {expected}: {result.stderr}')


def request_dates(root):
    return [json.loads(line)['date'] for line in (root / 'requests.jsonl').read_text().splitlines()]


def prepare(root, first, last):
    if root.exists():
        raise ValueError('Evidence roots are never reset; select a new root: ' + str(root))
    db = history.connect(root, first, last, region='xsmt')
    db.close()


def prove(base):
    base.mkdir(parents=True, exist_ok=True)
    report = {'transport': 'OFFLINE frozen fixture responses; not live requests',
              'retry_clock': 'mocked; production defaults unchanged', 'physical_reboot_tested': False}
    root = base / 'resume'
    prepare(root, '2026-10-16', '2026-10-18')
    run_worker(root, limit=2)
    first_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('years/*/raw/*.gz')}
    run_worker(root)
    run_worker(root)
    assert request_dates(root) == ['2026-10-16', '2026-10-17', '2026-10-18']
    assert all(hashlib.sha256(next(root.glob('years/*/raw/' + name)).read_bytes()).hexdigest() == digest for name, digest in first_hashes.items())
    report['restart_after_two_commits'] = {'passed': True, 'request_dates': request_dates(root), 'first_hashes_unchanged': first_hashes}

    root = base / 'raw-crash'
    prepare(root, '2026-10-21', '2026-10-21')
    run_worker(root, 'after_raw', expected=71)
    with sqlite3.connect(root / 'history.sqlite3') as db:
        assert db.execute('SELECT status FROM days').fetchone()[0] == 'pending'
    run_worker(root)
    assert request_dates(root) == ['2026-10-21']
    report['crash_after_raw_before_commit'] = {'passed': True, 'exit_code': 71, 'requests_total': 1, 'cached_response_reused': True}

    root = base / 'commit-crash'
    prepare(root, '2025-12-31', '2026-01-01')
    run_worker(root, 'after_commit', expected=72)
    with sqlite3.connect(root / 'history.sqlite3') as db:
        assert db.execute("SELECT status FROM days WHERE date='2025-12-31'").fetchone()[0] == 'saved'
    assert not (root / 'years/2025/results.jsonl').exists()
    run_worker(root)
    assert request_dates(root) == ['2025-12-31', '2026-01-01']
    assert len((root / 'years/2025/results.jsonl').read_text().splitlines()) == 1
    report['crash_after_commit_before_export'] = {'passed': True, 'exit_code': 72, 'request_dates': request_dates(root),
                                                 'previous_year_export_rebuilt_before_next_request': True}

    root = base / 'outage'
    prepare(root, '2026-10-21', '2026-10-21')
    db = history.connect(root, region='xsmt')
    clock, waits, calls = [1000.0], [], []
    def wait(seconds, stop):
        waits.append(seconds)
        clock[0] += seconds + 0.1
        return True
    def transport(url, timeout):
        calls.append(url)
        assert history.summary(db)['processed_days'] == 0
        if len(calls) <= 2:
            raise URLError('Injected offline transport')
        return fixture('2026-10-21')
    with patch.object(history, 'fetch', side_effect=transport), \
         patch.object(history.time, 'time', side_effect=lambda: clock[0]), \
         patch.object(history, 'interruptible_wait', side_effect=wait):
        history.collect(root, db, interval=0, region='xsmt')
    row = db.execute('SELECT * FROM days').fetchone()
    assert len(calls) == 3 and row['status'] == 'saved' and row['attempts'] == 3
    assert waits[:2] == [5, 10]
    report['two_failures_then_recovery'] = {'passed': True, 'attempts': row['attempts'], 'retry_delays_seconds': waits[:2], 'numbers': row['number_count']}
    db.close()

    root = base / 'stop'
    prepare(root, '2026-10-21', '2026-10-21')
    db = history.connect(root, region='xsmt')
    history.write_progress(root, db, 'running')
    db.close()
    (root / 'STOP').write_text('Intentional offline test stop\n')
    run_worker(root)
    assert not (root / 'requests.jsonl').exists()
    with patch.object(monitor, 'start') as start:
        monitor.check(root, notify=False, region='xsmt')
        monitor.check(root, notify=False, region='xsmt')
        start.assert_not_called()
    assert (root / 'STOP').exists()
    report['durable_stop'] = {'passed': True, 'separate_process_restart_requests': 0, 'monitor_restart_calls': 0, 'stop_persists': True}

    code = "import sys;from pathlib import Path;import history;\nwith history.WorkerLock(Path(sys.argv[1])):\n print('READY',flush=True);sys.stdin.readline()"
    holder = subprocess.Popen([sys.executable, '-c', code, str(root)], cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'READY'
        contender = subprocess.run([sys.executable, str(REPO / 'history.py'), 'run', '--region', 'xsmt', '--root', str(root)], capture_output=True, text=True)
        assert contender.returncode != 0 and 'already running' in contender.stderr
        report['linux_cross_process_lock'] = {'passed': True, 'second_process_returncode': contender.returncode, 'refusal': 'A collector is already running for this project'}
    finally:
        holder.communicate('release\n', timeout=10)
    report['passed'] = True
    history.atomic_write(base / 'recovery.json', json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['worker', 'prove'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--mode', default='normal')
    p.add_argument('--limit', type=int)
    args = p.parse_args()
    if args.command == 'worker':
        worker(args.root, args.mode, args.limit)
    else:
        print(json.dumps(prove(args.root.resolve()), indent=2))
