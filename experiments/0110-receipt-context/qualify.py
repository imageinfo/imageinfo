"""Eleven retained native checked-flush context cells; authored markers only."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent/'0022-ordinary-output'))
from qualify import Process, inventory, invoke
from restart_qualify import close, flags, load_actor

MODE = 'ordinary-receipt-checked-flush'
FLAGS = ('committed', 'namespaceAcknowledged', 'productionPublicationAllowed', 'repairAllowed')
MATRIX = [
    ('normal', None, None, 'receipt-written', 'receipt.record'),
    ('cancel-pre-context', 'cancel', None, 'receipt-written', 'receipt.record'),
    ('fail-pre-context', 'fail', None, 'receipt-written', 'receipt.record'),
    ('terminate-pre-context', 'kill', None, 'receipt-written', 'receipt.record'),
    ('receipt-mtime-pre-context', None, 'mtime', 'receipt-written', 'receipt.record'),
    ('receipt-ads-pre-context', None, 'ads', 'receipt-written', 'receipt.record'),
    ('held-default-write', None, 'write', 'receipt-written', 'receipt.record'),
    ('held-name-rename', None, 'rename', 'receipt-written', 'receipt.record'),
    ('later-stale-context', None, 'mtime', 'receipt-file-flushed', 'receipt.record'),
    ('source-property-pre-context', None, 'mtime', 'receipt-written', 'source.marker'),
]

def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def binding(binary):
    paths = list((REPO/'experiments/0032-windows-publication/src').glob('*.rs'))
    paths += list((REPO/'experiments/0028-recovery-evidence/src').glob('*.rs'))
    paths += [REPO/p for p in ('rust-toolchain.toml',
        'experiments/0032-windows-publication/Cargo.toml', 'experiments/0032-windows-publication/Cargo.lock',
        'experiments/0028-recovery-evidence/Cargo.toml', 'experiments/0028-recovery-evidence/Cargo.lock',
        'experiments/0038-staging-cleanup/src/staging.rs', 'experiments/0038-staging-cleanup/src/disposition.rs')]
    return {'workerSha256':sha(binary), 'mode':MODE,
            'sources':{p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sorted(paths)}}

def trial(binary, root, spec):
    name, stop, action, phase, role = spec
    folder = root/name
    folder.mkdir()
    transaction = folder/'transaction.marker'
    code, _ = invoke(binary, transaction, 'ordinary-prepare', folder/'prepare')
    assert code == 0
    before = inventory(transaction)
    worker = Process([binary, transaction, MODE], folder/'worker')
    actors = []
    try:
        while True:
            event = worker.next()
            flags([event])
            if event.get('barrier') == phase:
                if action:
                    try:
                        load_actor().act(action, transaction/role)
                        result = {'allowed':True, 'winError':None}
                    except OSError as error:
                        result = {'allowed':False, 'winError':error.winerror}
                    actors.append({'action':action, 'role':role, 'eventOrdinal':len(worker.lines)-1, **result})
                    assert result['allowed'] == (action not in ('write', 'rename'))
                if stop == 'kill':
                    worker.stop()
                    break
                if stop:
                    worker.controls.append(stop)
                    worker.proc.stdin.write(stop+'\n')
                    worker.proc.stdin.flush()
                    continue
            if 'barrier' in event:
                worker.send()
            if 'outcome' in event:
                break
        code = worker.finish()
        events = [json.loads(line) for line in worker.lines]
        contexts = [e['receiptContext'] for e in events if 'receiptContext' in e]
        terminal = next((e for e in reversed(events) if 'outcome' in e), None)
        after = inventory(transaction)
        write(folder/'inventories.private.json', {'before':before, 'after':after})
        row = {'id':name, 'mode':MODE, 'phase':phase, 'stop':stop, 'actors':actors,
               'exitCode':code, 'terminal':terminal, 'contextCount':len(contexts),
               'contextOrdinals':[i for i,e in enumerate(events) if 'receiptContext' in e],
               'retained':True}
        write(folder/'case.private.json', row)
        if contexts:
            write(folder/'context.private.json', contexts[0])
        return row
    finally:
        close(worker)

def inspect_stale(inspector, root):
    spec = importlib.util.spec_from_file_location('receipt110_legacy', HERE.parent/'0046-namespace-receipt/qualify.py')
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    prior = root/'later-stale-context'
    transaction = prior/'transaction.marker'
    context = json.loads((prior/'context.private.json').read_text())
    folder = root/'unchanged-inspector-stale-refusal'
    folder.mkdir()
    before = inventory(transaction)
    result = legacy.inspect(inspector, transaction, context, folder/'inspect')
    after = inventory(transaction)
    write(folder/'inventories.private.json', {'before':before, 'after':after})
    row = {'id':folder.name, 'inspectorSha256':sha(inspector), 'contextSource':'later-stale-context',
           'transactionSource':'later-stale-context', **result}
    write(folder/'case.private.json', row)
    return row

def run(binary, inspector, output):
    if os.name != 'nt' or not __debug__:
        raise RuntimeError('Native Windows assertions required')
    output.mkdir(parents=True, exist_ok=False)
    who = subprocess.run(['whoami','/user','/fo','csv','/nh'], capture_output=True, check=True, timeout=15)
    sid = next(csv.reader(who.stdout.decode(errors='replace').splitlines()))[-1]
    assert sid.startswith('S-1-5-')
    policy = subprocess.run(['icacls',str(output),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],capture_output=True,check=True,timeout=15)
    (output/'root-policy.private.txt').write_bytes(policy.stdout+policy.stderr)
    frozen = binding(binary)
    write(output/'source-binding.private.json', frozen)
    harness = list(HERE.glob('*.py'))+[HERE.parent/p for p in (
        '0022-ordinary-output/qualify.py','0022-ordinary-output/restart_qualify.py',
        '0034-source-oplocks/qualify.py','0033-owner-rights/actor.py',
        '0046-namespace-receipt/qualify.py')]
    write(output/'harness-binding.private.json', {p.relative_to(REPO).as_posix():sha(p) for p in harness})
    for path in harness:
        target=output/'harness-sources.private'/path.relative_to(REPO)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    rows = []
    try:
        for spec in MATRIX:
            rows.append(trial(binary, output, spec))
        rows.append(inspect_stale(inspector, output))
        assert binding(binary) == frozen
        write(output/'source-binding-after.private.json', binding(binary))
        report = {'caseCount':len(rows), 'cases':rows, 'workerSha256':sha(binary),
                  'inspectorSha256':sha(inspector), 'mode':MODE, 'enabledProfiles':0, **dict.fromkeys(FLAGS,False)}
        write(output/'report.private.json', report)
        print(json.dumps({'caseCount':len(rows), 'output':str(output)}))
    except BaseException as error:
        write(output/'failed-report.private.json', {'cases':rows,'diagnostic':str(error)})
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',required=True,type=Path)
    parser.add_argument('--inspector',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    run(args.binary.resolve(), args.inspector.resolve(), args.output.resolve())
