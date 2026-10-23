"""Exercise actual child-process crashes and durable restart using frozen HTML."""
import tempfile
import unittest
from pathlib import Path

from tools.prove_xsmt_recovery import prove


class RecoveryProofTests(unittest.TestCase):
    def test_recorded_xsmt_fault_injection_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = prove(Path(tmp))
            self.assertTrue(report['passed'])
            self.assertEqual(report['restart_after_two_commits']['request_dates'],
                             ['2026-10-16', '2026-10-17', '2026-10-18'])
            self.assertFalse(report['physical_reboot_tested'])


if __name__ == '__main__':
    unittest.main()
