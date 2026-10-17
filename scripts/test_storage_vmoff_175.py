"""Authored controller controls; no VM/process/native device actions."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

import storage_vmoff_175 as controller


class Controls(unittest.TestCase):
    def setUp(self):
        self.root = controller.BASE / 'production-0175-authored'
        self.manifest = {'tools': '/opt/imageinfo-qemu'}
        self.args = ['qemu-system-x86_64', '-drive',
            f'if=pflash,format=raw,unit=0,readonly=on,file={Path("/opt/imageinfo-qemu")}/usr/share/OVMF/OVMF_CODE_4M.ms.fd',
            '-drive', f'if=pflash,format=raw,unit=1,file={self.root}/vars.fd', '-drive',
            f'file={self.root}/windows.qcow2,if=ide,format=qcow2,cache=writeback', '-qmp',
            f'unix:{self.root}/qmp,server=on,wait=off']
        self.blocks = [{'inserted': {'file': str(self.root / 'windows.qcow2'), 'image': {
            'filename': str(self.root / 'windows.qcow2'), 'format': 'qcow2',
            'full-backing-filename': str(controller.BASE / 'windows.qcow2'),
            'backing-image': {'filename': str(controller.BASE / 'windows.qcow2'), 'format': 'qcow2'}}}}]

    def test_exact_args_and_backing_pass(self):
        controller.validate_emulator_args(self.root, self.manifest, self.args, self.args)
        controller.validate_backing(self.blocks, self.root)

    def test_live_argv_changed_refuses_even_if_disk_matches(self):
        with self.assertRaises(ValueError):
            controller.validate_emulator_args(self.root, self.manifest, self.args + ['-snapshot'], self.args)

    def test_additional_disk_refuses_even_with_matching_launch_receipt(self):
        changed = self.args + ['-drive', 'file=/mnt/c/unrelated.vhd,format=raw']
        with self.assertRaises(ValueError):
            controller.validate_emulator_args(self.root, self.manifest, changed, changed)

    def test_shared_folder_refuses_even_with_matching_launch_receipt(self):
        changed = self.args + ['-fsdev', 'local,id=share,path=/mnt/c,security_model=none']
        with self.assertRaises(ValueError):
            controller.validate_emulator_args(self.root, self.manifest, changed, changed)

    def test_forged_backing_path_refuses(self):
        self.blocks[0]['inserted']['image']['full-backing-filename'] = '/var/tmp/foreign.qcow2'
        with self.assertRaises(ValueError): controller.validate_backing(self.blocks, self.root)

    def test_extra_backing_level_refuses(self):
        self.blocks[0]['inserted']['image']['backing-image']['backing-image'] = {'filename': '/dev/sda'}
        with self.assertRaises(ValueError): controller.validate_backing(self.blocks, self.root)

    def test_ambiguous_live_overlay_refuses(self):
        with self.assertRaises(ValueError): controller.validate_backing(self.blocks * 2, self.root)

    def test_live_added_disk_refuses(self):
        changed = self.blocks + [{'inserted': {'file': '/mnt/c/unrelated.vhd'}}]
        with self.assertRaises(ValueError): controller.validate_backing(changed, self.root)

    def test_preserve_previous_capture(self):
        with tempfile.TemporaryDirectory(dir=controller.REPO / '.local') as temporary:
            path = Path(temporary) / 'capture.json'
            controller.save(path, {'retained': 'original'})
            with self.assertRaises(FileExistsError): controller.save(path, {'retained': 'replacement'})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'retained': 'original'})

    def test_bytes_retained_exactly_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=controller.REPO / '.local') as temporary:
            path = Path(temporary) / 'events'
            encoded = base64.b64encode(b'line\npartial').decode('ascii')
            controller.retain_bytes(path, encoded)
            self.assertEqual(path.read_bytes(), b'line\npartial')
            with self.assertRaises(FileExistsError): controller.retain_bytes(path, encoded)

    def test_fixed_matrix_matches_method(self):
        ledger = json.loads((controller.REPO / 'docs/write-safety/production-vmoff-cells.json').read_text(encoding='utf-8'))
        rows = [(row['id'], row['mode'], {'normal': 'none'}.get(row['kind'], row['kind']), row['checkpoint']) for row in ledger['cells']]
        self.assertEqual(rows, list(controller.MATRIX))

    def test_transport_initializes_with_pinned_payloads(self):
        with tempfile.TemporaryDirectory(dir=controller.REPO / '.local') as temporary:
            root = Path(temporary); worker = root / 'authored.exe'; worker.write_bytes(b'not executable; transport control only')
            output = root / 'capture'
            server = mock.Mock()
            with mock.patch.object(controller, 'scoped', return_value=self.root), mock.patch.object(controller, 'ThreadingHTTPServer', return_value=server):
                controller.serve(output, worker, self.root)
            server.serve_forever.assert_called_once()
            binding = json.loads((output / 'transport-binding.private.json').read_text(encoding='utf-8'))
            self.assertEqual(binding['workerSha256'], controller.digest(worker))
            self.assertTrue((output / 'transport-history.private.jsonl').is_file())

    def test_quit_lost_response_still_checks_exit_without_resend(self):
        with tempfile.TemporaryDirectory(dir=controller.REPO / '.local') as temporary:
            folder=Path(temporary); qmp=mock.Mock(); qmp.call.side_effect=EOFError('expected lost response')
            with mock.patch.object(controller, 'process_binding', return_value={'pid': 987654321}), \
                    mock.patch.object(controller, 'load_legacy', return_value=SimpleNamespace(Qmp=lambda _root: qmp)), \
                    mock.patch.object(controller, 'host_boot', return_value='authored-host-boot'):
                controller.off(self.root,folder,'vmoff-completed-predicate','a'*64)
            qmp.call.assert_called_once_with('quit')
            result=json.loads((folder/'off-completed.private.json').read_text(encoding='utf-8'))
            self.assertTrue(result['vm_process_exit_confirmed'])
            self.assertIn('EOFError', result['quit_error'])

    def test_freeze_retains_actual_baseline_review_bytes(self):
        with tempfile.TemporaryDirectory(dir=controller.REPO / '.local') as temporary:
            root=Path(temporary); output=root/'output'; output.mkdir()
            worker=root/'worker.exe';worker.write_bytes(b'authored nonexecuting worker')
            baseline=root/'baseline.json';baseline.write_text('{"authored":true}\n',encoding='utf-8')
            review=root/'review.json';review.write_text('{"review":"authored"}\n',encoding='utf-8')
            spec={'workerSha256':controller.digest(worker),'sources':{'Cargo.toml':controller.digest(controller.REPO/'Cargo.toml')},
                  'native_baseline_evidence_path':str(baseline),'native_baseline_evidence_sha256':controller.digest(baseline),
                  'freeze_review_evidence_path':str(review),'freeze_review_evidence_sha256':controller.digest(review)}
            manifest=root/'source.json';controller.save(manifest,spec)
            refs=controller.freeze(output,worker,manifest)
            self.assertEqual((output/refs['native_baseline_evidence']['path']).read_bytes(),baseline.read_bytes())
            self.assertEqual((output/refs['freeze_review_evidence']['path']).read_bytes(),review.read_bytes())

    def test_freeze_rejects_naked_or_false_baseline_hash(self):
        with tempfile.TemporaryDirectory(dir=controller.REPO / '.local') as temporary:
            root=Path(temporary);output=root/'output';output.mkdir()
            worker=root/'worker.exe';worker.write_bytes(b'authored nonexecuting worker')
            spec={'workerSha256':controller.digest(worker),'sources':{'Cargo.toml':controller.digest(controller.REPO/'Cargo.toml')},
                  'native_baseline_evidence_sha256':'0'*64}
            manifest=root/'source.json';controller.save(manifest,spec)
            with self.assertRaisesRegex(ValueError,'Required retained evidence path/hash'):
                controller.freeze(output,worker,manifest)


if __name__ == '__main__': unittest.main()
