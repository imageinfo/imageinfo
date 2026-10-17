"""Independent #0146 retained frame, request isolation, timing and telemetry audit."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import re

from audit_read_telemetry import audit as resource_audit

ROOT=Path(__file__).resolve().parents[1]


def audit_bindings(record, prepared):
    expected={str(Path(prepared['binary']))} | {str(ROOT/name) for name in (
        'scripts/measure_session_resources.py','scripts/audit_session_resources.py',
        'scripts/read_telemetry.py','scripts/audit_read_telemetry.py','scripts/read_benchmark.py',
        'scripts/check_read_arguments.py','tests/support/mod.rs')}
    require(set(record['bindings'])==expected, 'exact required tool inventory')
    require(record['bindingsUnchanged'] and all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in record['bindings'].items()), 'frozen build/tools')
    require(record['bindings'][prepared['binary']]==prepared['binarySha256'], 'prepared executable binding')
    source=prepared['sourceBinding']
    require(record['sourceBinding']==source and record['sourceBindingUnchanged'], 'frozen source binding')
    require(re.fullmatch('[0-9a-f]{40}',source['revision']) is not None, 'source revision')
    paths=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',ROOT/'rust-toolchain.toml']+[p for p in (ROOT/'src').rglob('*') if p.is_file()]
    current={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    require(source['files']==current, 'exact frozen source inventory')


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    data = Path(path).read_bytes()
    require(len(data) <= 256*1024*1024, 'audit input cap')
    return json.loads(data)


def normalize(value):
    value = copy.deepcopy(value)
    identity = value['requestId']
    require(value['request']['requestId'] == identity == value['summary']['requestId'], 'inner ID isolation')
    for key in (value, value['request'], value['summary']):
        key['requestId'] = 'request'
    for issue in value['request']['issues']:
        issue['message'] = issue['message'].replace('imageinfo.exe', 'imageinfo')
    for file in value['files']:
        require(file['requestId'] == identity, 'file request ID')
        file['requestId'] = 'request'
        if file['snapshot']:
            require(file['snapshot']['id'].startswith(identity+'-snapshot-'), 'snapshot ID')
            file['snapshot']['id'] = 'request'+file['snapshot']['id'][len(identity):]
    return value


def schedule():
    cells = []
    for count in (1, 64, 255):
        for repeat in range(3):
            expected = ['selected'] if count == 1 else [
                ('usage', 'selected', 'missing', 'all', 'invalid', 'selected', 'all')[i % 7]
                for i in range(count)]
            cells.append((f'reads-{count}-{repeat}', expected, 'close', 0, None))
    cells.extend((name, cases, reason, status, error) for name, cases, reason, status, error in (
        ('id-128', [], 'close', 0, None), ('id-129', [], 'protocol-error', 2, 'FRAME_SCHEMA'),
        ('duplicate-id', ['selected'], 'protocol-error', 2, 'DUPLICATE_ID'),
        ('frame-lf-cap', [], 'close', 0, None), ('frame-crlf-cap', [], 'close', 0, None),
        ('frame-over', [], 'protocol-error', 2, 'FRAME_TOO_LARGE'),
        ('auto-256', ['selected' if i % 2 == 0 else 'all' for i in range(256)], 'limit', 0, None)))
    return cells


def distribution(values):
    return dict(count=len(values), min=min(values) if values else None,
                median=statistics.median(values) if values else None, max=max(values) if values else None)


def input_expectations(name, cases):
    """Independent exact UTF-8 serialization oracle, including delimiters."""
    def encoded(kind, identity, case=None):
        value=dict(protocolVersion=1,kind=kind,id=identity)
        if case:
            common=['metadata','read','--max-bytes','8388608']
            suffix={'usage':['--bogus'],'missing':['--','missing.cr3'],
                    'invalid':['--','invalid.cr3'],
                    'selected':['--tag','ISO','--values','raw','--','s\u00e9ssion.cr3'],
                    'all':['--values','all','--','s\u00e9ssion.cr3']}[case]
            value['tokens']=common+suffix
        return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n'
    wires=[]
    for i,case in enumerate(cases):
        identity='same' if name=='duplicate-id' else f'r{i:03}'+'a'*124 if name=='auto-256' else f'r{i}'
        wires.append(encoded('read',identity,case))
    if name=='auto-256':
        return wires
    if name.startswith('frame-'):
        if name=='frame-over':
            return [b' '*524288]
        end=b'\r\n' if name=='frame-crlf-cap' else b'\n'
        prefix=encoded('close','cap')[:-1]
        return [prefix+b' '*(524288-len(prefix)-len(end))+end]
    identity='a'*int(name.split('-')[1]) if name.startswith('id-') else 'same' if name=='duplicate-id' else 'done'
    return wires+[encoded('close',identity)]


def audit_cell(root, row, expectation, oracles):
    name, cases, reason, status, error = expectation
    require(row['name'] == name, 'cell order')
    raw = (root/'captures'/f'{name}.stdout').read_bytes()
    stderr = (root/'captures'/f'{name}.stderr').read_bytes()
    for channel, data in (('stdout', raw), ('stderr', stderr)):
        require(len(data) == row[channel+'CapturedBytes'] <= min(row[channel+'Bytes'], 32*1024*1024), 'capture bounds')
        require(hashlib.sha256(data).hexdigest() == row[channel+'Sha256'], 'capture hash')
    pieces = raw.splitlines(keepends=True)
    require(len(row['received']) <= len(pieces), 'phantom frames')
    previous = -1
    for data, observation in zip(pieces, row['received']):
        require(observation['bytes'] == len(data) and observation['sha256'] == hashlib.sha256(data).hexdigest(), 'LF frame binding')
        require(observation['completeLf'] == data.endswith(b'\n'), 'LF completeness')
        require(previous <= observation['endOffsetNs'] <= row['elapsedNs'], 'frame timing')
        previous = observation['endOffsetNs']
    probe = dict(row, index=0, phase='sample', eligible=False, correctness='fail')
    if row['censored'] and row['outcome'] not in ('timeout','output-limit','consumer-error','cancelled','telemetry-limit'):
        probe['outcome']='consumer-error'
    # Telemetry helper is reused, while its existing independent auditor checks
    # all arithmetic, alignment, null reasons, membership and final observations.
    resource_audit(dict(schemaVersion=2, purpose='authored-child-qualification', telemetry=[row['telemetry']],
                        elapsedRecord=dict(attempts=[probe], configuration=dict(warmups=0, repeats=1, captureBytes=32*1024*1024),
                                           status='cancelled' if row['outcome']=='cancelled' else 'completed',
                                           sourceUnchanged=True, binaryUnchanged=True)))
    expected_inputs=input_expectations(name,cases)
    def check_point(index, unavailable, lower, upper):
        if index is None:
            require(unavailable in ('process-exited', 'sample-unavailable'), 'missing checkpoint reason')
            return
        samples=row['telemetry']['samples']
        require(type(index) is int and 0 <= index < len(samples), 'checkpoint index bounds')
        sample=samples[index]
        require(not sample['final'] and unavailable is None, 'post-exit/final checkpoint')
        live=row['checkpointLiveness'].get(str(index))
        require(isinstance(live,dict) and live['liveBefore'] is True and live['liveAfter'] is True, 'checkpoint live observations')
        require(lower <= live['beforeOffsetNs'] <= sample['beginOffsetNs'] <= sample['endOffsetNs'] <= live['afterOffsetNs'] <= upper, 'live checkpoint alignment')
    if row['readyLatencyNs'] is not None:
        require(row['received'] and row['readyLatencyNs']==row['received'][0]['endOffsetNs'], 'ready timing')
        check_point(row['readyCheckpoint'], row['readyCheckpointUnavailable'], row['readyLatencyNs'],
                    row['requests'][0]['sendOffsetNs'] if row['requests'] else row['elapsedNs'])
    for i, request in enumerate(row['requests']):
        require(i<len(expected_inputs) and request['inputBytes']==len(expected_inputs[i]) and
                request['inputSha256']==hashlib.sha256(expected_inputs[i]).hexdigest(),'encoded UTF-8 input binding')
        require(0 <= request['sendOffsetNs'] <= row['elapsedNs'], 'send time')
        if request['completeOffsetNs'] is None:
            require(request['latencyNs'] is None and row['censored'], 'uncensored missing request')
            continue
        require(request['completeOffsetNs'] == row['received'][i+1]['endOffsetNs'], 'request/result alignment')
        require(request['latencyNs'] == request['completeOffsetNs']-request['sendOffsetNs'] >= 0, 'latency arithmetic')
        check_point(request['checkpoint'], request['checkpointUnavailable'], request['completeOffsetNs'],
                    row['requests'][i+1]['sendOffsetNs'] if i+1<len(row['requests']) else row['elapsedNs'])
    # Every complete retained frame is semantic evidence even if a later request
    # was censored, or the supervisor did not dequeue a final captured frame.
    require(all(p.endswith(b'\n') for p in pieces[:-1]), 'interior incomplete frame')
    if pieces and not pieces[-1].endswith(b'\n'):
        require(row['censored'], 'uncensored truncated output')
    frames=[json.loads(p) for p in pieces if p.endswith(b'\n')]
    ready_expected=dict(protocolVersion=1,kind='session-ready',allowApply=False,limits=dict(
        maxInputFrameBytes=524288, maxOutputFrameBytes=16777728, maxFrames=256, maxQueuedRequests=0,
        maxTokens=128, maxTokenBytes=32768, maxTotalTokenBytes=65536, maxInputs=4,
        maxMetadataBytes=8388608, maxResultBytes=16777216))
    expected_close = None
    if reason=='close':
        expected_close = 'a'*128 if name=='id-128' else 'cap' if name.startswith('frame-') else 'done'
    total = len(cases) + (0 if reason=='limit' else 1)
    completion=dict(protocolVersion=1,kind='session-complete',reason=reason,exitStatus=status,
                    frames=total,results=len(cases),closeId=expected_close)
    expected_count=len(cases)+2+int(error is not None)
    require(len(frames)<=expected_count, 'unexpected complete frame suffix')
    statuses=dict(usage=2,missing=1,invalid=1,selected=0,all=0)
    for position,value in enumerate(frames):
        if position==0:
            require(value==ready_expected, 'ready frame/caps')
            if 'ready' in row:
                require(value==row['ready'], 'retained ready value')
        elif position<=len(cases):
            i=position-1
            case=cases[i]
            identity='same' if name=='duplicate-id' else f'r{i:03}'+'a'*124 if name=='auto-256' else f'r{i}'
            require(value['kind']=='read-result' and value['protocolVersion']==1 and value['id']==identity, 'request IDs/order')
            require(value['result']['requestId']==identity, 'outer/inner ID')
            require(value['result']['summary']['exitStatus']==statuses[case], 'authored expected status')
            require(normalize(value['result'])==normalize(oracles[case]), 'exact independent standalone oracle / request isolation')
            require(i<len(row['requests']) and row['requests'][i]['case']==case, 'request case order')
        elif error and position==len(cases)+1:
            require(value==dict(protocolVersion=1,kind='protocol-error',id=None,code=error), 'protocol refusal')
        else:
            require(value==completion, 'complete final frame')
    if row['censored']:
        return dict(name=name,eligible=False,outcome=row['outcome'],retainedRequests=len(row['requests']),
                    completeRequests=sum(r['completeOffsetNs'] is not None for r in row['requests']),
                    semanticCompleteFrames=len(frames))
    require(row['outcome']=='exited' and row['exitCode']==status and not stderr and not row['faults'], 'session outcome')
    require(len(row['received'])==len(pieces)==len(frames)==expected_count, 'complete frame denominator')
    require(len(row['requests'])==total, 'request denominator')
    if name.startswith('frame-'):
        require(row['requests'][0]['inputBytes']==524288, 'exact frame boundary')
    first = row['readyCheckpoint']
    last = row['requests'][len(cases)-1]['checkpoint'] if cases else first
    growth = {}
    for metric in ('workingSetBytes', 'privateCommitBytes'):
        values = row['telemetry']['samples']
        a = values[first]['values'][metric] if first is not None else None
        b = values[last]['values'][metric] if last is not None else None
        growth[metric] = dict(ready=a, lastResult=b, delta=None if a is None or b is None else b-a, unavailableReason=None if a is not None and b is not None else 'live endpoint unavailable; post-exit memory excluded')
    return dict(name=name, eligible=row['telemetry']['valid'], reads=len(cases), outputBytes=len(raw),
                readyLatencyNs=row['readyLatencyNs'], totalExitNs=row['elapsedNs'],
                requestLatencyNs=distribution([r['latencyNs'] for r in row['requests'][:len(cases)]]),
                retainedState=growth, telemetryValid=row['telemetry']['valid'])


def audit(root):
    r, p = load(root/'record.private.json'), load(root/'prepared.private.json')
    require(r['status']=='completed' and r['revision']=='session-resources-146-v1', 'campaign completion')
    require(r['sourceBefore']==r['sourceAfter']==p['fixtureBefore'], 'no source byte/stat/name effects')
    audit_bindings(r,p)
    require(hashlib.sha256((root/'oracles.private.json').read_bytes()).hexdigest()==p['oracleSha256'], 'oracle binding')
    require(len(r['cells'])==len(schedule())==16, 'fixed cell denominator')
    reports = [audit_cell(root, row, expected, load(root/'oracles.private.json')) for row,expected in zip(r['cells'],schedule())]
    return dict(cells=reports, attempted=16, eligible=sum(x['eligible'] for x in reports),
                scope='Authored single-host sequential sessions; cache uncontrolled; direct process logical I/O; sampled state is not leak proof or policy')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    args=parser.parse_args()
    root=args.run_root.resolve()
    result=audit(root)
    with (root/'audit.private.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
