import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from tools.restore_prediction_transfer import restore


class CloneTransferTests(unittest.TestCase):
    def test_restore_reuse_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = b'00 G.\xc4\x90B'
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode='w:gz') as archive:
                member = tarfile.TarInfo('snapshot/records.jsonl')
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            part = raw.getvalue()
            (root / 'part').write_bytes(part)
            manifest = {'data_version': 'test', 'archive_sha256': hashlib.sha256(part).hexdigest(),
                'parts': [{'name': 'part', 'sha256': hashlib.sha256(part).hexdigest()}],
                'files': {'snapshot/records.jsonl': hashlib.sha256(data).hexdigest()}}
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            restored = root / 'restored'
            restore(path, restored)
            restore(path, restored)
            self.assertEqual((restored / 'snapshot/records.jsonl').read_bytes(), data)
            (restored / 'snapshot/records.jsonl').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'changed'):
                restore(path, restored)
            (root / 'part').write_bytes(b'bad chunk')
            with self.assertRaisesRegex(ValueError, 'chunk changed'):
                restore(path, root / 'other')
