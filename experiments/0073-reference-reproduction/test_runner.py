"""Authored refusal test: an invalid destination must remain untouched."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class OutputRefusal(unittest.TestCase):
    def test_existing_directory_is_not_used_for_failure_artifacts(self):
        scratch = Path(__file__).resolve().parents[2] / ".local"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="0073-refusal-", dir=scratch) as directory:
            root = Path(directory)
            sentinel = root / "keep.txt"
            sentinel.write_bytes(b"authored sentinel")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("reproduce.py")),
                                     "--repository", str(root), "--output", str(root)],
                                    capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(root.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b"authored sentinel")


if __name__ == "__main__":
    unittest.main()
