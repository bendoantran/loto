"""Region isolation, malformed-source and XSMT control regression tests."""
import gzip
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import history
from tools import control, monitor
from tools.install_service import units

REPO = Path(__file__).resolve().parent


def raw(day="2026-10-21"):
    return gzip.decompress((REPO / f"reference/xsmt/raw/{day}.html.gz").read_bytes())


class RegionTests(unittest.TestCase):
    def test_retry_backoff_and_rate_limit_minimum(self):
        for errors, expected in [([URLError('offline')] * 5, [5, 10, 20, 40, 60]),
                                 ([HTTPError('https://xosodaiphat.com', 429, 'rate limited', {}, None)], [60])]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                db = history.connect(root, '2026-10-21', '2026-10-21', 'xsmt')
                clock, waits = [1000.0], []
                def wait(seconds, stop):
                    waits.append(seconds)
                    clock[0] += seconds + 0.1
                    return True
                with patch.object(history, 'fetch', side_effect=errors + [raw()]), \
                     patch.object(history.time, 'time', side_effect=lambda: clock[0]), \
                     patch.object(history, 'interruptible_wait', side_effect=wait):
                    history.collect(root, db, interval=0, region='xsmt')
                self.assertEqual(waits[:-1], expected)
                self.assertEqual(db.execute('SELECT attempts,status FROM days').fetchone()[:], (len(errors)+1, 'saved'))
                db.close()

    def test_wrong_region_both_directions_and_wrong_date(self):
        southern = gzip.decompress((REPO / "tests/fixtures/modern.html.gz").read_bytes())
        for data, region, day in [(southern, "xsmt", "2026-10-21"),
                                  (raw(), "xsmn", "2026-10-21"),
                                  (raw(), "xsmt", "2026-10-20")]:
            with self.subTest(region=region, day=day), self.assertRaises(ValueError):
                history.parse_day(data, day, region)

    def test_partial_captcha_empty_missing_and_duplicate_tiers(self):
        for data in [b'<html>captcha login access denied</html>',
                     raw().replace(b'044743', b'...'),
                     raw().replace(b'G.8', b'G.7', 1),
                     raw().replace(b'G.8', b'unknown', 1)]:
            with self.assertRaises(ValueError):
                history.parse_day(data, "2026-10-21", "xsmt")

    def test_anomalies_flagged_without_fixing_numbers(self):
        result = history.parse_day(raw().replace(b'044743', b'04474'), "2026-10-21", "xsmt")
        self.assertEqual(result['status'], 'flagged')
        self.assertEqual(result['draws'][1]['prizes']['G.ĐB'], ['04474'])
        self.assertTrue(result['draws'][1]['quality_flags'])

    def test_province_order_is_read_from_source(self):
        data = raw().replace('Đà Nẵng'.encode(), b'FIRST').replace('Khánh Hòa'.encode(), b'SECOND')
        result = history.parse_day(data, "2026-10-21", "xsmt")
        self.assertEqual([d['province'] for d in result['draws']], ['FIRST', 'SECOND'])
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(result['draws'][1]['loto_by_head']['0'].count('04'), 2)

    def test_unrelated_loto_before_real_tables_is_ignored(self):
        sidebar = b'<table class="table-loto"><tr><th>Wrong<th>Sidebar<tr><td>0<td>00</table>'
        data = raw().replace(b'<p class=padding10>Loto ', sidebar + b'<p class=padding10>Loto ', 1)
        self.assertEqual(history.parse_day(data, "2026-10-21", "xsmt")['draws'],
                         history.parse_day(raw(), "2026-10-21", "xsmt")['draws'])

    def test_synthetic_notices_are_region_and_date_specific(self):
        # Synthetic wording tests; no claim that these dates were actually cancelled.
        cancelled = '<p>Kết quả XSMT ngày 21/10/2026 không mở thưởng do nghỉ dịch.</p>'.encode()
        missing = '<div class="block-no-result info-result">Kết quả XSMT Thứ 4 ngày 21/10/2026 không được lưu trữ.</div>'.encode()
        for data, status in [(cancelled, 'no_draw'), (missing, 'unavailable')]:
            self.assertEqual(history.parse_day(data, '2026-10-21', 'xsmt')['status'], status)
            with self.assertRaises(ValueError):
                history.parse_day(data, '2026-10-21', 'xsmn')
            with self.assertRaises(ValueError):
                history.parse_day(data, '2026-10-20', 'xsmt')

    def test_checkpoint_mismatch_refused_without_database_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = history.connect(root, '2026-10-21', '2026-10-21')
            db.close()
            before = hashlib.sha256((root / 'history.sqlite3').read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                history.connect(root, region='xsmt')
            result = subprocess.run([sys.executable, str(REPO / 'history.py'), 'export',
                                     '--region', 'xsmt', '--root', str(root)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, hashlib.sha256((root / 'history.sqlite3').read_bytes()).hexdigest())
            self.assertFalse((root / 'years').exists())

    def test_fresh_xsmt_requires_explicit_range_and_reverse_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                history.connect(root, region='xsmt')
            self.assertFalse((root / 'history.sqlite3').exists())
            db = history.connect(root, '2026-10-21', '2026-10-21', 'xsmt')
            self.assertEqual(dict(db.execute('SELECT key,value FROM settings'))['region'], 'xsmt')
            self.assertIn('/xsmt-', db.execute('SELECT source_url FROM days').fetchone()[0])
            with self.assertRaises(ValueError):
                history.collect(root, db)
            with self.assertRaises(ValueError):
                history.export_year(root, db, 2026)
            db.close()
            with self.assertRaises(ValueError):
                history.connect(root)
            with self.assertRaises(ValueError):
                history.connect(root, '2026-10-20', region='xsmt')

    def test_xsmt_stop_monitor_and_separate_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = history.connect(root, '2026-10-21', '2026-10-21', 'xsmt')
            history.write_progress(root, db, 'running')
            db.close()
            control.request_stop(root, region='xsmt')
            with patch.object(monitor, 'start') as start:
                self.assertIsNone(monitor.check(root, notify=False, region='xsmt'))
                self.assertIsNone(monitor.check(root, notify=False, region='xsmt'))
                start.assert_not_called()
            self.assertTrue((root / 'STOP').exists())
            generated = units(REPO, root, Path(sys.executable), 'xsmt')
            self.assertEqual(set(generated), {'loto-xsmt-history.service', 'loto-xsmt-monitor.service', 'loto-xsmt-monitor.timer'})
            self.assertIn('--region xsmt', generated['loto-xsmt-history.service'])
            self.assertIn('--region xsmt', generated['loto-xsmt-monitor.service'])
            self.assertIn('WorkingDirectory=' + str(root) + '\n', generated['loto-xsmt-history.service'])


if __name__ == '__main__':
    unittest.main()
