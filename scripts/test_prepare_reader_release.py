"""Adversarial source-archive and exact-source CI checks (authored bytes only)."""
import hashlib
import io
import tarfile
import unittest

from prepare_reader_release import MATRIX, inspect_archive, validate_ci


def tar(name="README.md", payload=b"authored source\n", kind=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        if kind is not None:
            member.type = kind
            member.size = 0
            member.linkname = "outside"
        archive.addfile(member, io.BytesIO(payload))
    return data.getvalue()


class ReleaseChecks(unittest.TestCase):
    def test_exact_source_and_substitution(self):
        payload = b"authored source\n"
        oid = hashlib.sha1(b"blob 16\0" + payload).hexdigest()
        expected = {"README.md": oid}
        self.assertEqual(inspect_archive(tar(), expected), {"README.md": payload})
        with self.assertRaises(ValueError):
            inspect_archive(tar(payload=b"changed\n"), expected)
        with self.assertRaises(ValueError):
            inspect_archive(tar(), {**expected, "missing": oid})

    def test_unsafe_paths_and_links(self):
        for path in ["../escape", "/escape", "C:/escape", "a/../../escape", "a\\escape", ".local/private", "target/tool.exe"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                inspect_archive(tar(path), {})
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                inspect_archive(tar(kind=kind), {})

    def test_ci_requires_all_exact_source_jobs(self):
        record = {"headSha": "a" * 40, "status": "completed", "conclusion": "success",
                  "workflowName": "Rust foundation", "url": "https://github.com/imageinfo/imageinfo/actions/runs/1",
                  "databaseId": 1, "jobs": [{"name": os, "conclusion": "success"} for os in sorted(MATRIX)]}
        self.assertEqual(validate_ci(record, "a" * 40), record)
        with self.assertRaises(ValueError):
            validate_ci(record, "b" * 40)
        for jobs in [record["jobs"][:-1], record["jobs"] + [record["jobs"][0]],
                     [{"name": os, "conclusion": "skipped"} for os in MATRIX]]:
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                validate_ci({**record, "jobs": jobs}, "a" * 40)


if __name__ == "__main__":
    unittest.main()
