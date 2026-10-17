"""Finite authored native byte-budget campaign; run only in serialized freeze slot."""
import argparse
import json
import os
from pathlib import Path
import platform
import read_benchmark as b
from read_telemetry import Observer

ROOT = Path(__file__).resolve().parent.parent
CELLS = [(a, d) for a in ('metadata', 'block') for d in (-1, 0, 1)]
TOOL_FILES = ['examples/reader_byte_boundaries.rs', 'tests/support/mod.rs',
              'tests/support/byte_boundaries.rs', 'tests/support/byte_budget_fixtures.rs',
              'scripts/reader_byte_boundary_campaign.py', 'scripts/audit_reader_byte_boundaries.py',
              'scripts/read_benchmark.py', 'scripts/read_telemetry.py',
              'scripts/check_reader_byte_boundary_tools.py', 'tests/reader_byte_boundaries.rs',
              'Cargo.toml', 'Cargo.lock']


def frozen_binding(binary):
    files = set(TOOL_FILES)
    for directory in ('src', 'crates'):
        files.update(p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob('*.rs'))
        files.update(p.relative_to(ROOT).as_posix() for p in (ROOT / directory).rglob('Cargo.toml'))
    return {'schemaVersion': 1, 'binary': str(Path(binary).resolve()),
            'binarySha256': b.digest(binary),
            'files': {name: b.digest(ROOT / name) for name in sorted(files)}}


def collect(binary, freeze, freeze_sha256, output):
    binary = Path(binary).resolve()
    if b.digest(freeze) != freeze_sha256:
        raise ValueError('external freeze witness mismatch')
    binding = json.loads(Path(freeze).read_text(encoding='utf-8'))
    if frozen_binding(binary) != binding:
        raise ValueError('binary/tool/source freeze mismatch')
    output = Path(output).resolve()
    output.mkdir(exist_ok=False)
    attempts = []
    result = {'schemaVersion': 1, 'scope': 'six authored native default-byte-boundary cells',
              'freezeSha256': freeze_sha256, 'binding': binding,
              'platform': platform.platform(), 'attempts': attempts,
              'limits': {'metadataBytes': 8388608, 'blockBytes': 1048576},
              'limitsOfEvidence': ['in-memory source; logical requests are source Read calls',
                  'direct-process counters include fixture construction, hashing and JSON output',
                  'source read timing excludes fixture construction and hashing',
                  'sampled working-set maximum is not a memory quota or allocation peak',
                  'physical I/O and attempted allocation are unavailable',
                  'one retained attempt per cell; no regression/noise budget adopted']}
    for index, (axis, delta) in enumerate(CELLS):
        if frozen_binding(binary) != binding:
            raise ValueError('binary/tool/source changed between attempts')
        observer = Observer(1)
        argv = [str(binary), axis, str(delta)]
        record, stdout, stderr = b.run_process(argv, str(binary.parent), os.environ.copy(),
                                              10000, 262144, observer)
        stem = f'{index:02d}-{axis}-{delta}'
        (output / (stem + '.stdout')).write_bytes(stdout)
        (output / (stem + '.stderr')).write_bytes(stderr)
        attempts.append({'axis': axis, 'delta': delta, 'process': record, 'argv': argv,
                         'telemetry': observer.report(), 'captureStem': stem})
        (output / 'campaign.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        if frozen_binding(binary) != binding:
            result['freezeFailure'] = 'binary/tool/source changed during attempt'
            (output / 'campaign.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            raise ValueError('binary/tool/source changed during attempt; all attempt records retained')
    (output / 'campaign.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', required=True)
    p.add_argument('--prepare-freeze', help='write exact pre-campaign binding manifest, then exit')
    p.add_argument('--freeze')
    p.add_argument('--freeze-sha256')
    p.add_argument('--output')
    a = p.parse_args()
    if a.prepare_freeze:
        with Path(a.prepare_freeze).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(frozen_binding(a.binary), indent=2) + '\n')
        return 0
    if not all((a.freeze, a.freeze_sha256, a.output)):
        p.error('--freeze, --freeze-sha256 and --output required for campaign')
    result = collect(a.binary, a.freeze, a.freeze_sha256, a.output)
    return 0 if all(x['process']['outcome'] == 'exited' and x['process']['exitCode'] == 0
                    and x['telemetry']['valid'] for x in result['attempts']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
