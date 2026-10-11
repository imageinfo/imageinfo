"""Owned marker actors against handle-bound Windows publication. No media input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import subprocess
import tempfile
import threading

BARRIERS = ['root-created', 'candidate-flushed', 'prepared-record-flushed',
            'intent-record-flushed', 'validated-before-publish', 'published',
            'output-file-flushed', 'directory-flush-attempted', 'observation-record-flushed']
MARKER = b'2' * 65536


def run(binary, parent):
    binary = str(Path(binary).resolve())
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='imageinfo-bound-', dir=parent))
    cases = []
    if os.name != 'nt':
        result = subprocess.run([binary, str(scratch/'root'), 'absolute'], capture_output=True, text=True, timeout=30)
        assert result.returncode == 5 and 'WINDOWS_BACKEND_UNVERIFIED' in result.stderr
        assert not list(scratch.iterdir())
        return {'caseCount': 1, 'cases': [{'id': 'unsupported-platform', 'workerArtifacts': 0}],
                'productionPublicationAllowed': False, 'enabledProfiles': 0}
    shell = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')

    def actor(script, path):
        env = dict(os.environ, IMAGEINFO_BOUND_ACTOR=str(path))
        result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command',
                                 "$ErrorActionPreference='Stop'; " + script], env=env,
                                text=True, capture_output=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr[:256]

    def rejected(action):
        try:
            action()
        except OSError:
            return True
        return False

    def stream_actor(path):
        # Reviewed actor-only SDK boundary. CRT stream opens do not share DELETE
        # and therefore cannot test this holder's actual alternate-stream policy.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        kernel.WriteFile.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.CreateFileW(str(path)+':extra', 0x40000000, 7, None, 1, 128, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        data = ctypes.create_string_buffer(b'marker-only')
        count = wintypes.DWORD()
        try:
            # Live typed buffers, bounded authored bytes, synchronous handle and
            # NULL OVERLAPPED. No callback, privileged access or path from media.
            if not kernel.WriteFile(handle, data, 11, ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            assert count.value == 11
        finally:
            assert kernel.CloseHandle(handle)

    def execute(name, mode='absolute', action=None, stop=None, command='continue', operand=None):
        root = Path(operand) if operand is not None else scratch/name
        capture = scratch/(name+'-captures')
        capture.mkdir()
        argv = [binary, str(root), mode]
        (capture/'argv.json').write_text(json.dumps(argv), encoding='utf-8')
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        messages = queue.Queue()

        def read():
            for line in process.stdout:
                messages.put(line)
            messages.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        timer = threading.Timer(120, lambda: process.kill() if process.poll() is None else None)
        timer.start()
        events, controls, identity = [], [], None
        try:
            while True:
                line = messages.get(timeout=30)
                if line is None:
                    break
                event = json.loads(line)
                events.append(event)
                assert not event['productionPublicationAllowed']
                if 'barrier' not in event:
                    continue
                barrier = event['barrier']
                if barrier == 'candidate-flushed':
                    identity = event['candidate']['identity']
                if action:
                    action(barrier, root)
                if barrier == stop and command == 'kill':
                    process.kill()  # This owned child only; never the host/distro.
                    break
                reply = command if barrier == stop else 'continue'
                controls.append(reply)
                process.stdin.write(reply+'\n')
                process.stdin.flush()
            process.wait(timeout=30)
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
            reader.join(timeout=5)
        stderr = process.stderr.read()
        if stderr:
            diagnostic = json.loads(stderr)
            assert not diagnostic['committed'] and not diagnostic['productionPublicationAllowed']
        (capture/'stdout.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events), encoding='utf-8')
        (capture/'stdin.txt').write_text(''.join(c+'\n' for c in controls), encoding='utf-8')
        (capture/'stderr.json').write_text(stderr, encoding='utf-8')
        final = next((e for e in reversed(events) if 'outcome' in e), {})
        assert not final.get('committed', False)
        owned = root.is_absolute() and root.is_relative_to(scratch)
        facts = {'id': name, 'barriers': [e['barrier'] for e in events if 'barrier' in e],
                 'exitCode': process.returncode, 'outputExists': owned and (root/'output.bin').exists(),
                 'outcome': final.get('outcome', 'interrupted-or-refused'),
                 'errorCode': final.get('errorCode'),
                 'diagnostic': json.loads(stderr)['diagnostic'] if stderr else None}
        if facts['outputExists']:
            facts['completeMarkerVisible'] = (root/'output.bin').is_file() and (root/'output.bin').read_bytes() == MARKER
        if final.get('heldCandidateIdentityStable'):
            assert identity and final['rootIdentityStable']
            facts['liveHeldCandidateAndParentStable'] = True
        for event in events:
            if event.get('barrier') == 'directory-flush-attempted':
                facts['directoryFlushCallSucceeded'] = event['callSucceeded']
                facts['directoryFlushError'] = event['errorCode']
                assert not event['namespaceAcknowledged']
        cases.append(facts)
        return root, facts

    root, baseline = execute('bound-publication')
    assert baseline['barriers'] == BARRIERS and baseline['completeMarkerVisible']
    assert baseline['liveHeldCandidateAndParentStable']
    for name in ['prepared.record', 'intent.record', 'observation.record']:
        envelope = json.loads((root/name).read_text())
        assert hashlib.sha256(envelope['body'].encode()).hexdigest() == envelope['sha256']
        body = json.loads(envelope['body'])
        assert body['observationOnly'] and not body['committed'] and not body['namespaceAcknowledged']
    root, rooted = execute('win32-directory-relative', mode='rooted')
    assert rooted['errorCode'] == 87 and not rooted['outputExists']
    root, admission = execute('strict-admission', mode='admit')
    assert admission['outcome'] == 'refused-before-effects' and not root.exists()

    def root_binding(barrier, root):
        if barrier == 'root-created':
            assert rejected(lambda: root.rename(root.with_name(root.name+'-moved')))
            assert rejected(root.rmdir)
    _, facts = execute('atomic-root-held-before-payload', action=root_binding)
    assert facts['completeMarkerVisible'] and facts['liveHeldCandidateAndParentStable']
    def candidate_winner(barrier, root):
        if barrier == 'root-created':
            (root/'candidate.bin').write_bytes(b'foreign-candidate-winner')
    root, facts = execute('candidate-creation-race', action=candidate_winner)
    assert not facts['outputExists'] and (root/'candidate.bin').read_bytes() == b'foreign-candidate-winner'

    def junction(link, target):
        result = subprocess.run([os.environ['COMSPEC'], '/d', '/c', 'mklink', '/J', str(link), str(target)],
                                text=True, capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0
    foreign = scratch/'junction-target'
    foreign.mkdir()
    (foreign/'foreign.bin').write_bytes(b'foreign-retained')
    link = scratch/'existing-root-junction'
    junction(link, foreign)
    _, facts = execute('existing-root-junction-refusal', operand=link)
    assert not facts['barriers'] and (foreign/'foreign.bin').read_bytes() == b'foreign-retained'
    assert list(foreign.iterdir()) == [foreign/'foreign.bin']
    link = scratch/'parent-junction'
    junction(link, foreign)
    _, facts = execute('parent-junction-refusal', operand=link/'new-root')
    assert not facts['barriers'] and not (foreign/'new-root').exists()

    for phase in ['validated-before-publish', 'published']:
        for kind in ['write', 'truncate', 'delete', 'rename', 'alias', 'case-write']:
            def mutation(barrier, root, phase=phase, kind=kind):
                if barrier != phase:
                    return
                path = root/('candidate.bin' if phase != 'published' else 'output.bin')
                operations = {'write': lambda: path.write_bytes(b'foreign'),
                              'truncate': lambda: os.truncate(path, 1), 'delete': path.unlink,
                              'rename': lambda: path.rename(root/'moved.bin'),
                              'alias': lambda: os.link(path, root/'alias.bin'),
                              'case-write': lambda: path.with_name(path.name.upper()).write_bytes(b'foreign')}
                if kind == 'alias':
                    os.link(path, root/'alias.bin')
                    assert rejected(lambda: (root/'alias.bin').write_bytes(b'foreign'))
                    # A distinct link can be removed even though deletion of the
                    # held original name is excluded. Retain a new alias so the
                    # actual link-count drift is detected by the worker.
                    assert not rejected((root/'alias.bin').unlink)
                    os.link(path, root/'alias.bin')
                else:
                    assert rejected(operations[kind]), kind
            _, facts = execute(kind+'-'+phase, action=mutation)
            assert facts['completeMarkerVisible']
            if kind == 'alias':
                facts['newAliasCreateDeleteAllowedContentWriteExcluded'] = True
                assert facts['exitCode'] == 5 and 'STAGE_PROPERTY_OR_CONTENT_CHANGED' in facts['diagnostic']
            else:
                assert facts['liveHeldCandidateAndParentStable']
        def parent_move(barrier, root, phase=phase):
            if barrier == phase:
                assert rejected(lambda: root.rename(root.with_name(root.name+'-moved')))
        _, facts = execute('parent-rename-'+phase, action=parent_move)
        assert facts['completeMarkerVisible']

    def reader(barrier, root):
        if barrier == 'published':
            actor("$f=[IO.FileStream]::new($env:IMAGEINFO_BOUND_ACTOR,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)); "
                  "try {$b=[byte[]]::new(65537); $n=0; while($n -lt $b.Length){$k=$f.Read($b,$n,$b.Length-$n); if($k -eq 0){break}; $n+=$k}; "
                  "if($n -ne 65536 -or @($b[0..65535] | Where-Object {$_ -ne 50}).Count -ne 0){throw 'partial marker'}} finally {$f.Dispose()}", root/'output.bin')
    _, facts = execute('compatible-reader', action=reader)
    assert facts['completeMarkerVisible']
    def child_entry(barrier, root):
        if barrier == 'validated-before-publish':
            (root/'unrelated.bin').write_bytes(b'unrelated-retained')
    root, facts = execute('directory-entry-writes-allowed', action=child_entry)
    assert facts['completeMarkerVisible'] and (root/'unrelated.bin').read_bytes() == b'unrelated-retained'

    changes = {
        'timestamp': None,
        'readonly': "[IO.File]::SetAttributes($env:IMAGEINFO_BOUND_ACTOR,[IO.FileAttributes]::ReadOnly)",
        'acl': "$p=$env:IMAGEINFO_BOUND_ACTOR; $s=[IO.File]::GetAccessControl($p); "
               "$r=[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-1-0'),[Security.AccessControl.FileSystemRights]::Read,[Security.AccessControl.AccessControlType]::Allow); "
               "$s.AddAccessRule($r); [IO.File]::SetAccessControl($p,$s)",
        'stream': 'python-stream'}
    for phase in ['intent-record-flushed', 'published']:
        for kind, script in changes.items():
            def change(barrier, root, phase=phase, script=script):
                if barrier == phase:
                    path = root/('candidate.bin' if phase != 'published' else 'output.bin')
                    if script is None:
                        os.utime(path, (1000000000, 1000000000))
                    elif script == 'python-stream':
                        stream_actor(path)
                    else:
                        actor(script, path)
            _, facts = execute(kind+'-'+phase, action=change)
            assert facts['outputExists'] == (phase == 'published')
            assert facts['diagnostic'] and facts['exitCode'] == 5

    def late_substitute(barrier, root):
        if barrier == 'validated-before-publish':
            assert rejected(lambda: (root/'candidate.bin').rename(root/'held-original.bin'))
            assert rejected(lambda: (root/'candidate.bin').write_bytes(b'late-foreign'))
    _, facts = execute('late-substitution-excluded', action=late_substitute)
    assert facts['completeMarkerVisible']
    for kind in ['record-write', 'record-delete']:
        def records(barrier, root, kind=kind):
            if barrier == 'validated-before-publish':
                for name in ['prepared.record', 'intent.record']:
                    path = root/name
                    assert rejected((lambda: path.write_bytes(b'forged')) if kind == 'record-write' else path.unlink)
        _, facts = execute(kind, action=records)
        assert facts['completeMarkerVisible']

    for case_name, spelling in [('collision-existing', 'output.bin'), ('collision-case-alias', 'OUTPUT.BIN')]:
        def collision(barrier, root, spelling=spelling):
            if barrier == 'validated-before-publish':
                (root/spelling).write_bytes(b'foreign-winner')
        root, facts = execute(case_name, action=collision)
        assert facts['outputExists'] and not facts['completeMarkerVisible']
        assert (root/spelling).read_bytes() == b'foreign-winner' and (root/'candidate.bin').read_bytes() == MARKER
    def directory_collision(barrier, root):
        if barrier == 'validated-before-publish':
            (root/'output.bin').mkdir()
            (root/'output.bin'/'foreign.bin').write_bytes(b'foreign-retained')
    # Directory observation does not try to read the directory as marker content.
    root, facts = execute('directory-collision', action=directory_collision)
    assert (root/'output.bin'/'foreign.bin').read_bytes() == b'foreign-retained'

    for barrier in BARRIERS:
        for command in ['fail', 'kill', 'cancel']:
            root, facts = execute(command+'-'+barrier, stop=barrier, command=command)
            assert facts['outputExists'] == (BARRIERS.index(barrier) >= BARRIERS.index('published'))
            if facts['outputExists']:
                assert facts['completeMarkerVisible']
            if (root/'candidate.bin').exists():
                assert (root/'candidate.bin').read_bytes() == MARKER
    existing = scratch/'existing'
    existing.mkdir()
    (existing/'foreign.bin').write_bytes(b'keep')
    _, facts = execute('existing-root-refusal', operand=existing)
    assert not facts['barriers'] and (existing/'foreign.bin').read_bytes() == b'keep'
    for name, operand in [('relative-path', 'relative-unverified'), ('unc-path', r'\\localhost\unverified\root'),
                          ('device-path', r'\\?\C:\unverified'), ('stream-root', str(scratch/'root')+':extra'),
                          ('traversal-path', str(scratch)+r'\child\..\root'),
                          ('control-character-root', str(scratch)+'\\bad\nroot'),
                          ('reserved-device-root', str(scratch/'NUL'))]:
        _, facts = execute(name, operand=operand)
        assert not facts['barriers']
    _, facts = execute('unknown-mode', mode='unknown')
    assert not facts['barriers']
    _, facts = execute('overlong-control', stop='candidate-flushed', command='x'*40)
    assert not facts['outputExists'] and facts['exitCode'] == 5
    _, facts = execute('unicode-root', operand=scratch/'unicode-文-é')
    assert facts['completeMarkerVisible']
    report = {'schemaVersion': 1, 'platform': platform.platform(), 'cases': cases, 'caseCount': len(cases),
              'productionPublicationAllowed': False, 'enabledProfiles': 0, 'namespaceAcknowledged': False,
              'OSCrashRuns': 0, 'powerLossRuns': 0, 'mediaInputs': 0,
              'data': 'authored 64 KiB marker; no source media or metadata edits',
              'storage': 'ordinary local NTFS, unchanged DOS mapping; privileges/providers excluded'}
    (scratch/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--parent', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.binary, args.parent), indent=2))
