"""Executable admission and native marker integration cells; retains all scratch."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from supervisor import BLOCK, Budget, OPERATION_BYTES, Refused, Supervisor, U64_MAX, add, wire


def refuses(call):
    try:
        call()
    except (Refused, FileExistsError):
        return
    raise AssertionError('expected refusal')


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def qualify(binary, parent):
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='budget49-', dir=parent)).resolve()
    cells = []

    def cell(name, **observations):
        cells.append({'name': name, 'passed': True, **observations})

    for invalid in (-1, U64_MAX + 1, True, 1.0):
        refuses(lambda: Budget(invalid, 1))
    cell('invalid-u64-limits')
    refuses(lambda: add(U64_MAX, 1))
    b = Budget(U64_MAX, U64_MAX)
    b.charged = U64_MAX - OPERATION_BYTES + 1
    refuses(b.admit)
    assert b.operations == 0
    cell('checked-byte-overflow-before-charge')
    b = Budget(U64_MAX, U64_MAX)
    b.operations = U64_MAX
    refuses(b.admit)
    assert b.charged == 0
    cell('checked-operation-overflow-before-charge')
    assert len(wire('x' * (BLOCK - 3))) == BLOCK
    refuses(lambda: wire('x' * (BLOCK - 2)))
    cell('actual-serialized-request-exact-and-over-bound')

    wrong = root/'wrong-worker.exe'
    wrong.write_bytes(b'not the reviewed worker')
    refuses(lambda: Supervisor(root/'wrong-worker-root', wrong, OPERATION_BYTES, 1))
    assert not (root/'wrong-worker-root').exists()
    cell('unsupported-stable-worker-refuses-before-root-creation')

    s = Supervisor(root/'below', binary, OPERATION_BYTES - 1, 1)
    refuses(s.run)
    assert not list(s.root.iterdir()) and s.budget.charged == 0
    cell('one-byte-below-refuses-before-operation-directory')
    s = Supervisor(root/'zero-operations', binary, OPERATION_BYTES, 0)
    refuses(s.run)
    assert not list(s.root.iterdir()) and s.budget.charged == 0
    cell('operation-cap-refuses-before-effects')

    unknown = root/'unknown'
    unknown.mkdir()
    (unknown/'foreign').write_bytes(b'unowned-marker')
    before = hashes(unknown)
    refuses(lambda: Supervisor(unknown, binary, OPERATION_BYTES, 1))
    assert before == hashes(unknown)
    cell('preexisting-unknown-root-retained')

    s = Supervisor(root/'exact', binary, OPERATION_BYTES, 1)
    result = s.run()
    assert result['outcome'] == 'observed-receipt-recovery-required'
    assert result['observedFiles'] == 10 and result['custodySnapshots'] == 4
    assert result['chargedBytes'] == OPERATION_BYTES
    before = hashes(s.root)
    refuses(s.run)
    assert before == hashes(s.root)
    cell('exact-full-receipt-four-custody-snapshots-and-retained-charge', **result)

    s = Supervisor(root/'multiple', binary, OPERATION_BYTES * 2, 2)
    first = s.run(control_at='before-namespace-call', control='fail')
    before = hashes(s.root/'1')
    second = s.run(mode='ordinary-short-source')
    assert before == hashes(s.root/'1') and second['chargedBytes'] == OPERATION_BYTES * 2
    assert (s.root/'2/transaction.marker/candidate.marker').stat().st_size == BLOCK - 1
    before = hashes(s.root)
    refuses(s.run)
    assert before == hashes(s.root)
    cell('two-incomplete-operations-failed-control-short-copy-third-refused',
         first=first, second=second)

    s = Supervisor(root/'cancel', binary, OPERATION_BYTES, 2)
    result = s.run(control_at='before-namespace-call', control='cancel')
    assert result['outcome'] == 'cancelled-before-publication'
    assert result['chargedBytes'] == OPERATION_BYTES
    before = hashes(s.root)
    refuses(s.run)
    assert before == hashes(s.root)
    cell('cancel-retains-full-charge-after-worker-owned-cleanup', **result)

    s = Supervisor(root/'short-record', binary, OPERATION_BYTES, 1)
    result = s.run(mode='ordinary-receipt-short-record')
    assert result['outcome'] != 'observed-receipt-recovery-required'
    assert result['custodySnapshots'] == 4 and result['chargedBytes'] == OPERATION_BYTES
    cell('short-receipt-retains-candidate-records-and-custody', **result)

    class Interrupted(Supervisor):
        def _call(self, root, mode, request=None, callback=None):
            result = super()._call(root, mode, request, callback)
            if mode == 'ordinary-prepare':
                raise OSError('labeled supervisor interruption after prepare')
            return result

    s = Interrupted(root/'interrupted', binary, OPERATION_BYTES * 2, 2)
    try:
        s.run()
    except OSError:
        pass
    else:
        raise AssertionError('expected labeled interruption')
    assert s.poisoned and s.budget.charged == OPERATION_BYTES
    before = hashes(s.root)
    assert len(before) == 1
    refuses(s.run)
    assert before == hashes(s.root) and s.budget.charged == OPERATION_BYTES
    cell('supervisor-exception-after-real-source-construction-poisons-and-retains-charge')

    s = Supervisor(root/'foreign-after-run', binary, OPERATION_BYTES * 2, 2)
    s.run(mode='ordinary-short-source')
    (s.root/'unowned.marker').write_bytes(b'foreign-retained')
    before = hashes(s.root)
    refuses(s.run)
    assert before == hashes(s.root) and s.budget.operations == 1 and s.poisoned
    cell('late-unknown-entry-poisons-without-removal-or-second-charge')

    s = Supervisor(root/'worker-failure', binary, OPERATION_BYTES * 2, 2)
    # Unknown preexisting namespace refuses before admission or worker creation.
    (s.root/'1').mkdir()
    (s.root/'1/foreign').write_bytes(b'retain')
    before = hashes(s.root)
    refuses(s.run)
    assert before == hashes(s.root) and s.poisoned and s.budget.charged == 0
    cell('foreign-operation-directory-refuses-before-charge')

    repo = Path(__file__).resolve().parents[2]
    paths = list((repo/'experiments/0032-windows-publication/src').glob('*.rs'))
    paths += [repo/'experiments/0038-staging-cleanup/src/staging.rs',
              Path(__file__).with_name('supervisor.py'), Path(__file__)]
    return {'ticket': 49, 'observed': '2026-10-15', 'operationBoundBytes': OPERATION_BYTES,
            'perFileBoundBytes': BLOCK, 'maximumFilesPerOperation': 10,
            'workerSha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            'sourceSha256': {str(p.relative_to(repo)).replace('\\', '/'):
                             hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'cells': cells, 'cellCount': len(cells), 'allPassed': True,
            'logicalByteAdmissionOnly': True, 'diskReservation': False,
            'physicalAllocationQuota': False, 'freeSpaceQualified': False,
            'automaticCustody': False, 'productionPublicationAllowed': False,
            'rawAdmissionAllowed': False, 'repairAllowed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--public', type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.binary.resolve(), args.parent.resolve())
    args.public.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'allPassed': True, 'cellCount': result['cellCount']}))
