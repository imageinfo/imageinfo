"""Portable refusal checks; VM interruption evidence is a separate opt-in suite."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile


def run(binary, parent):
    binary = Path(binary).resolve()
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='refusal-', dir=parent))
    cases = []
    for mode in ['admit','finalize','prune','inspect']:
        missing = root/(mode+'-absent')
        proc = subprocess.run([str(binary),mode,str(missing)], capture_output=True, text=True, timeout=20)
        result = json.loads(proc.stdout if proc.returncode == 0 else proc.stderr)
        assert result['committed'] is False and not missing.exists()
        if platform.system() == 'Linux':
            assert proc.returncode == 0
            assert result['authorizedActions'] == []
            if mode == 'inspect':
                assert result['classification'] == 'invalid-or-uninspectable-evidence'
            else:
                assert result['outcome'] == 'refused-before-mutation'
        else:
            assert proc.returncode == 5 and result['issue'] == 'GUEST_LINUX_PROFILE_UNVERIFIED'
        cases.append({'mode':mode,'artifactsCreated':False,'committed':False})
    existing = root/'foreign'; existing.mkdir(mode=0o700)
    marker = existing/'output.bin'; marker.write_bytes(b'foreign marker retained')
    before = hashlib.sha256(marker.read_bytes()).hexdigest()
    for mode in ['finalize','prune','admit']:
        subprocess.run([str(binary),mode,str(existing)], capture_output=True, timeout=20)
        assert sorted(p.name for p in existing.iterdir()) == ['output.bin']
        assert hashlib.sha256(marker.read_bytes()).hexdigest() == before
        cases.append({'mode':mode,'foreignArtifactRetained':True,'committed':False})
    report = {'platform':platform.system(),'cases':cases,'caseCount':len(cases),
              'vmCrashRuns':0,'productionPublicationAllowed':False,'enabledProfiles':0}
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Qualification requires Python without -O')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',required=True)
    parser.add_argument('--parent',required=True)
    args = parser.parse_args()
    run(args.binary,args.parent)
