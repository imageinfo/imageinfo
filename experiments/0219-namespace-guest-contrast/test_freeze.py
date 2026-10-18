"""Authored exact-byte/source and current-parent freeze controls.

Only temporary inert files and local temporary Git repositories are used. No
worker, native probe, guest, QMP or QGA endpoint is started by these tests.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import freeze


class AuthoredTree(unittest.TestCase):
    """A real Git tree with raw LF blobs, unrelated to the production checkout."""

    def setUp(self):
        parent = Path(__file__).resolve().parents[2] / ".local" / "0219-authored-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="freeze-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write(self, name, data=b"authored source\n"):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def git(self, *args):
        result = subprocess.run(["git", "--no-optional-locks", *args], cwd=self.root,
                                capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, "temporary authored Git command failed")
        return result.stdout

    def publish(self):
        self.git("init", "--quiet")
        self.git("config", "user.name", "Authored control")
        self.git("config", "user.email", "authored@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "Authored inert controls")
        return self.git("rev-parse", "HEAD").strip().decode("ascii")


class GitBlobControls(AuthoredTree):
    def setUp(self):
        super().setUp()
        self.write(".gitattributes", b"* text eol=lf\n")
        self.source = self.write("source.rs", b"authored raw LF bytes\n")
        self.commit = self.publish()

    def test_exact_current_git_blobs_accept_without_mutation(self):
        before = self.source.read_bytes()
        self.assertEqual(freeze._published_sources(self.root, ["source.rs"]), self.commit)
        self.assertEqual(self.source.read_bytes(), before)

    def test_changed_worktree_or_crlf_refuses(self):
        for raw in (b"different LF bytes\n", b"authored raw LF bytes\r\n"):
            with self.subTest(raw=repr(raw)):
                self.source.write_bytes(raw)
                with self.assertRaises(freeze.FreezeError):
                    freeze._published_sources(self.root, ["source.rs"])

    def test_untracked_source_and_wrong_git_commit_refuse(self):
        self.write("new.rs")
        with self.assertRaises(freeze.FreezeError):
            freeze._published_sources(self.root, ["source.rs", "new.rs"])
        with self.assertRaises(freeze.FreezeError):
            freeze._published_sources(self.root, ["source.rs"], "0" * 40)

    def test_wrong_case_git_path_refuses_even_on_case_insensitive_host(self):
        with self.assertRaises(freeze.FreezeError):
            freeze._published_sources(self.root, ["SOURCE.rs"])

    def test_index_only_changes_do_not_replace_current_head_binding(self):
        self.source.write_bytes(b"new index bytes\n")
        self.git("add", "source.rs")
        with self.assertRaises(freeze.FreezeError):
            freeze._published_sources(self.root, ["source.rs"])


class ManifestControls(AuthoredTree):
    def setUp(self):
        super().setUp()
        # Complete tiny authored trees exercise inventory discovery as well as
        # SDK/runtime/collector/controller source changes without executing them.
        names = ["Cargo.toml", "Cargo.lock", ".gitattributes", "build.rs",
                 ".cargo/config.toml", "rust-toolchain.toml",
                 "src/storage/namespace_diagnostic.rs", "src/storage/namespace_guest_diagnostic.rs",
                 "src/storage/windows.rs",
                 "src/storage/runtime.rs", "crates/imageinfo-windows-storage/Cargo.toml",
                 "crates/imageinfo-windows-storage/src/lib.rs",
                 "crates/imageinfo-windows-storage/src/native.rs",
                 "crates/imageinfo-windows-storage/src/windows.rs"]
        for number, components in ((218, ("freeze", "protocol", "controller", "run", "audit", "fixtures", "probe")),
                                   (219, ("freeze", "protocol", "host_controller", "guest_collector", "audit", "fixtures", "authored_child"))):
            directory = "0218-namespace-observer" if number == 218 else "0219-namespace-guest-contrast"
            names.extend("experiments/" + directory + "/" + name + ".py" for name in components)
        names.append("experiments/0219-namespace-guest-contrast/guest_bootstrap.ps1")
        for name in names:
            self.write(name)
        self.commit = self.publish()
        self.worker = self.write("inert-worker.exe", b"inert authored executable bytes")
        self.build_path = self.root / "build.private.json"
        self.build = {"source_commit": self.commit, "worker_sha256": hashlib.sha256(self.worker.read_bytes()).hexdigest(),
                      "argv": ["cargo", "build", "--release"], "target": "authored-target", "compiler": "authored compiler"}
        self.build_path.write_bytes(json.dumps(self.build).encode())
        self.runtime_path = self.write("runtime.private.json", b'{"authored":"runtime"}\n')
        self.disk_path = self.write("disk.private.json", b'{"authored":"disk"}\n')
        self.controller_path = self.write("resident-source.py", b"authored source\n")
        self.plan_path = self.root / "plan.private.json"
        self.plan = {
            "schema": freeze.PLAN_SCHEMA,
            "worker_test_name": "storage::namespace_guest_diagnostic::guest_namespace_diagnostic_worker",
            "argv": ["C:\\runtime\\worker.exe", "--exact",
                     "storage::namespace_guest_diagnostic::guest_namespace_diagnostic_worker",
                     "--ignored", "--nocapture", "--test-threads=1"],
            "cases": [{"case": "persistent-write-error", "unit": "fresh-error", "root": "C:\\fresh\\error"},
                      {"case": "no-error", "unit": "fresh-control", "root": "C:\\fresh\\control"}],
            "bounds": {"deadline_seconds": 120, "stdout_bytes": 4194304, "stderr_bytes": 4194304,
                       "line_bytes": 32768, "events": 128, "command_bytes": 1024, "commands": 128},
            "marker": {"source_bytes": 16777216, "source_fill": 83, "candidate_bytes": 4194304, "candidate_fill": 24},
            "fault": {"event": "write_aio", "iotype": "write", "errno": 28, "once": False,
                      "sector": None, "arm_stage": "create-Candidate", "arm_seq": 9},
            "freeze_inputs": {"build_record": str(self.build_path), "runtime_inventory": str(self.runtime_path),
                              "disk_configuration": str(self.disk_path), "controller_source": str(self.controller_path)},
            "resident_expected": {
                "controller": {
                    "persistent-write-error": {"controller_epoch": "f" * 32, "code_sha256": "a" * 64, "python": {"authored": True}},
                    "no-error": {"controller_epoch": "1" * 32, "code_sha256": "a" * 64, "python": {"authored": True}}},
                "guest": {"implementation": "cpython", "version": "authored-v", "platform": "win32",
                          "stat_profile": "authored-stat-profile", "code_sha256": "b" * 64,
                          "files": {"C:\\runtime\\python.exe": "c" * 64,
                                    "C:\\runtime\\worker.exe": hashlib.sha256(self.worker.read_bytes()).hexdigest(),
                                    "C:\\runtime\\collector.py": "e" * 64}}},
            "identities": {"guest": {"authored": True},
                           "disk": {"disk_path": "/authored/disposable.qcow2", "raw_node": "authored-raw",
                                    "file_node": "authored-file", "filter_node": "authored-filter",
                                    "device_id": "authored-device", "device_serial": "authored-serial"},
                           "volume": {"volume_serial": "authored-volume"}}}
        self.plan.update({key: False for key in freeze.FLAGS})
        self.disk_path.write_bytes(json.dumps({"identities": self.plan["identities"]}).encode())
        self.runtime_inventory = {"guest": self.plan["resident_expected"]["guest"],
                                  "controller_python": {case: value["python"] for case, value in
                                                        self.plan["resident_expected"]["controller"].items()}}
        self.runtime_path.write_bytes(json.dumps(self.runtime_inventory).encode())
        self.plan_path.write_bytes(json.dumps(self.plan).encode())
        self.manifest = freeze.build_manifest(self.root, self.worker, self.plan_path)
        self.freeze_path = self.root / "freeze.private.json"
        self.freeze_path.write_bytes(json.dumps(self.manifest).encode())
        self.decision = freeze.ParentDecision(self.manifest["plan"]["sha256"],
                                               hashlib.sha256(self.freeze_path.read_bytes()).hexdigest(),
                                               "authored current parent choice")
        self.verify()

    def verify(self, **kwargs):
        return freeze.verify_current(self.plan_path, self.freeze_path,
                                     parent_decision=kwargs.get("decision", self.decision))

    def observed(self, case="persistent-write-error"):
        selected = next(item for item in self.plan["cases"] if item["case"] == case)
        controller = copy.deepcopy(self.plan["resident_expected"]["controller"][case])
        controller.update(plan_sha256=self.manifest["plan"]["sha256"],
                          source_sha256=self.manifest["inputs"]["controller_source"]["sha256"],
                          source_bytes=self.manifest["inputs"]["controller_source"]["bytes"], pid=219,
                          binding={**self.plan["identities"]["disk"], **self.plan["identities"]["volume"],
                                   "case": case, "unit": selected["unit"], "root": selected["root"]})
        return {"plan_sha256": self.manifest["plan"]["sha256"], "controller": controller,
                "guest": copy.deepcopy(self.plan["resident_expected"]["guest"])}

    def verify_resident(self, observed, case="persistent-write-error"):
        return freeze.verify_resident(self.manifest, observed, case=case)

    def test_exact_complete_manifest_and_current_decision_accept(self):
        result = self.verify()
        self.assertEqual(result["worker_sha256"], hashlib.sha256(self.worker.read_bytes()).hexdigest())
        self.assertNotIn("approved", self.manifest)
        self.assertNotIn("parent_decision", self.manifest)
        self.assertEqual(self.verify_resident(self.observed())["plan"], self.plan)
        self.verify_resident(self.observed("no-error"), case="no-error")
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file() and ".git" not in path.parts}
        self.assertEqual(freeze.build_manifest(self.root, self.worker, self.plan_path), self.manifest)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_changed_worker_plan_build_runtime_disk_controller_inputs_refuse(self):
        for path in (self.worker, self.plan_path, self.build_path, self.runtime_path,
                     self.disk_path, self.controller_path):
            with self.subTest(name=path.name):
                raw = path.read_bytes()
                path.write_bytes(raw + b" ")
                with self.assertRaises(freeze.FreezeError):
                    self.verify()
                path.write_bytes(raw)

    def test_changed_sdk_runtime_build_and_transport_sources_refuse(self):
        names = ("src/storage/runtime.rs", "src/storage/namespace_guest_diagnostic.rs",
                 "crates/imageinfo-windows-storage/src/windows.rs",
                 "build.rs", ".cargo/config.toml", "rust-toolchain.toml",
                 "experiments/0218-namespace-observer/run.py",
                 "experiments/0219-namespace-guest-contrast/host_controller.py",
                 "experiments/0219-namespace-guest-contrast/guest_bootstrap.ps1")
        bound = {entry["path"] for entry in self.manifest["sources"]}
        self.assertTrue(set(names) <= bound)
        for name in names:
            with self.subTest(name=name):
                path = self.root / name
                raw = path.read_bytes()
                path.write_bytes(b"changed source\n")
                with self.assertRaises(freeze.FreezeError):
                    self.verify()
                path.write_bytes(raw)

    def test_inventory_omission_duplicate_new_source_wrong_case_refuse(self):
        for mutate in (lambda names: names.pop(), lambda names: names.append(names[0]),
                       lambda names: names[0].update(path=names[0]["path"].upper())):
            changed = copy.deepcopy(self.manifest)
            mutate(changed["sources"])
            with self.assertRaises(freeze.FreezeError):
                freeze.verify_manifest(changed)
        self.write("experiments/0219-namespace-guest-contrast/unreviewed.py")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_resident_epoch_code_interpreter_plan_and_guest_must_match(self):
        changes = (("controller", "controller_epoch", "0" * 32),
                   ("controller", "code_sha256", "0" * 64),
                   ("controller", "python", {"authored": "other interpreter"}),
                   ("guest", "code_sha256", "0" * 64),
                   ("guest", "version", "other runtime"),
                   ("guest", "files", {"C:\\other.py": "0" * 64}))
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                observed = self.observed()
                observed[section][key] = value
                with self.assertRaises(freeze.FreezeError):
                    self.verify_resident(observed)
        observed = self.observed()
        observed["plan_sha256"] = "0" * 64
        with self.assertRaises(freeze.FreezeError):
            self.verify_resident(observed)
        for key in ("case", "root", "unit", "disk_path", "volume_serial"):
            with self.subTest(binding=key):
                observed = self.observed()
                observed["controller"]["binding"][key] += "-changed"
                with self.assertRaises(freeze.FreezeError):
                    self.verify_resident(observed)

    def test_disk_controller_equality_never_substitutes_for_stale_resident(self):
        self.assertEqual(self.controller_path.read_bytes(), b"authored source\n")
        stale = self.observed()
        stale["controller"]["code_sha256"] = "0" * 64
        with self.assertRaises(freeze.FreezeError):
            self.verify_resident(stale)
        stale = self.observed()
        stale["controller"]["controller_epoch"] = "0" * 32
        with self.assertRaises(freeze.FreezeError):
            self.verify_resident(stale)
        with self.assertRaises(freeze.FreezeError):
            self.verify_resident(self.observed("no-error"))

    def test_saved_decision_dictionary_and_wrong_current_choice_refuse(self):
        saved = dict(self.decision.__dict__)
        for decision in (saved, json.loads(json.dumps(saved)), None,
                         freeze.ParentDecision("0" * 64, self.decision.freeze_sha256, "reviewer"),
                         freeze.ParentDecision(self.decision.plan_sha256, "0" * 64, "reviewer"),
                         freeze.ParentDecision(self.decision.plan_sha256, self.decision.freeze_sha256, ""),
                         freeze.ParentDecision(self.decision.plan_sha256, self.decision.freeze_sha256, "reviewer", "all-cells")):
            with self.subTest(decision_type=type(decision).__name__):
                with self.assertRaises(freeze.FreezeError):
                    self.verify(decision=decision)

    def test_case_order_freshness_fault_bounds_and_flags_are_exact(self):
        mutations = (
            lambda plan: plan["cases"].reverse(),
            lambda plan: plan["cases"][0].update(case="Persistent-write-error"),
            lambda plan: plan["cases"][1].update(unit="fresh-error"),
            lambda plan: plan["cases"][1].update(root="c:\\FRESH\\ERROR"),
            lambda plan: plan["fault"].update(once=True),
            lambda plan: plan["fault"].update(sector=0),
            lambda plan: plan["fault"].update(arm_seq=True),
            lambda plan: plan["bounds"].update(deadline_seconds=float("nan")),
            lambda plan: plan["bounds"].update(events=True),
            lambda plan: plan.update(committed=True))
        for index, mutate in enumerate(mutations):
            with self.subTest(control=index):
                plan = copy.deepcopy(self.plan)
                mutate(plan)
                with self.assertRaises(freeze.FreezeError):
                    freeze._validate_plan(plan)

    def test_exact_guest_entry_filter_and_worker_argv_are_required(self):
        # The positive fixture already passes full manifest/current-decision
        # checks. Each change below alters only the selected guest execution.
        mutations = (
            lambda plan: plan.pop("worker_test_name"),
            lambda plan: plan.update(worker_test_name="storage::namespace_diagnostic::namespace_diagnostic_worker"),
            lambda plan: plan["argv"].__setitem__(2, "storage::namespace_diagnostic::namespace_diagnostic_worker"),
            lambda plan: plan["argv"].remove("--exact"),
            lambda plan: plan["argv"].append("--skip=other"),
            lambda plan: plan["argv"].__setitem__(3, "--include-ignored"),
            lambda plan: plan["argv"].__setitem__(5, "--test-threads=2"),
            lambda plan: plan["argv"].__setitem__(0, "worker.exe"))
        for index, mutate in enumerate(mutations):
            with self.subTest(control=index):
                plan = copy.deepcopy(self.plan)
                mutate(plan)
                with self.assertRaises(freeze.FreezeError):
                    freeze._validate_plan(plan)

    def test_guest_worker_argv_path_must_bind_frozen_worker_bytes(self):
        for path in ("C:\\runtime\\python.exe", "C:\\runtime\\WORKER.exe", "C:\\runtime\\unbound.exe"):
            with self.subTest(path=path):
                plan = copy.deepcopy(self.plan)
                plan["argv"][0] = path
                self.plan_path.write_bytes(json.dumps(plan).encode())
                with self.assertRaises(freeze.FreezeError):
                    freeze.build_manifest(self.root, self.worker, self.plan_path)

    def test_required_guest_diagnostic_source_cannot_be_omitted(self):
        path = self.root / "src/storage/namespace_guest_diagnostic.rs"
        path.unlink()
        with self.assertRaises(freeze.FreezeError):
            freeze.source_inventory(self.root)

    def test_wrong_case_loaded_guest_paths_refuse(self):
        observed = self.observed()
        files = observed["guest"]["files"]
        key = next(iter(files))
        files[key.upper()] = files.pop(key)
        with self.assertRaises(freeze.FreezeError):
            self.verify_resident(observed)

    def test_different_selected_plan_and_changed_saved_freeze_refuse(self):
        other = self.write("other-plan.private.json", self.plan_path.read_bytes())
        with self.assertRaises(freeze.FreezeError):
            freeze.verify_current(other, self.freeze_path, parent_decision=self.decision)
        self.freeze_path.write_bytes(self.freeze_path.read_bytes() + b" ")
        with self.assertRaises(freeze.FreezeError):
            self.verify()

    def test_build_request_cannot_claim_different_source_or_worker(self):
        for key, value in (("source_commit", "0" * 40), ("worker_sha256", "0" * 64),
                           ("argv", []), ("compiler", "")):
            with self.subTest(key=key):
                build = dict(self.build, **{key: value})
                self.build_path.write_bytes(json.dumps(build).encode())
                with self.assertRaises(freeze.FreezeError):
                    freeze.build_manifest(self.root, self.worker, self.plan_path)
        self.build_path.write_bytes(json.dumps(self.build).encode())

    def test_runtime_and_disk_declarations_must_match_plan_even_when_newly_frozen(self):
        runtime = copy.deepcopy(self.runtime_inventory)
        runtime["guest"]["version"] = "different runtime"
        self.runtime_path.write_bytes(json.dumps(runtime).encode())
        with self.assertRaises(freeze.FreezeError):
            freeze.build_manifest(self.root, self.worker, self.plan_path)
        self.runtime_path.write_bytes(json.dumps(self.runtime_inventory).encode())
        disk = {"identities": copy.deepcopy(self.plan["identities"])}
        disk["identities"]["volume"]["volume_serial"] = "different-volume"
        self.disk_path.write_bytes(json.dumps(disk).encode())
        with self.assertRaises(freeze.FreezeError):
            freeze.build_manifest(self.root, self.worker, self.plan_path)

    def test_duplicate_nonfinite_nonobject_json_refuse(self):
        for raw in (b'{"duplicate":1,"duplicate":2}', b'{"value":NaN}', b'[]'):
            with self.subTest(raw=repr(raw)):
                with self.assertRaises(freeze.FreezeError):
                    freeze._json(raw)

    def test_preparse_loader_captures_exact_bytes_used_for_execution(self):
        raw = b"def authored_value():\n    return 'captured-A'\n"
        path = self.write("inert-loader.py", raw)
        digest = hashlib.sha256(raw).hexdigest()
        module = freeze.load_controller_source(path, digest)
        self.addCleanup(sys.modules.pop, module.__name__, None)
        self.assertEqual(module.authored_value(), "captured-A")
        self.assertEqual(module.__resident_source_sha256__, digest)
        self.assertEqual(module.__resident_source_bytes_count__, len(raw))
        path.write_bytes(b"def authored_value():\n    return 'disk-B'\n")
        self.assertEqual(module.authored_value(), "captured-A")
        with self.assertRaises(freeze.FreezeError):
            freeze.load_controller_source(path, digest)

    def test_preparse_loader_never_executes_mismatched_or_crlf_bytes(self):
        raw = b"raise AssertionError('must not execute')\n"
        path = self.write("inert-refusal.py", raw)
        with self.assertRaises(freeze.FreezeError):
            freeze.load_controller_source(path, "0" * 64)
        path.write_bytes(raw.replace(b"\n", b"\r\n"))
        with self.assertRaises(freeze.FreezeError):
            freeze.load_controller_source(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_resident_requires_preparse_source_capture_and_actual_pid(self):
        for key, value in (("source_sha256", "0" * 64), ("source_bytes", True), ("pid", 0), ("pid", True)):
            observed = self.observed()
            observed["controller"][key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(freeze.FreezeError):
                    self.verify_resident(observed)

    def test_unrelated_head_advance_preserves_exact_immutable_source_pin(self):
        self.write("unrelated.txt", b"unrelated later commit\n")
        self.git("add", "unrelated.txt")
        self.git("commit", "--quiet", "-m", "Unrelated authored change")
        self.assertNotEqual(self.git("rev-parse", "HEAD").strip().decode(), self.commit)
        self.verify()


if __name__ == "__main__":
    unittest.main()
