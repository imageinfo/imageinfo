"""Closed, read-only #0051 profile ledger model. Never authorizes target effects."""
import hashlib
import json
from pathlib import Path

PROFILE = 'win26300-ntfs-sata-qcow2-writeback-marker-f869-v1'
REQUIRED = (
    'exact-configuration', 'byte-name-guards', 'property-policy', 'namespace-ack',
    'receipt-ack', 'caller-custody', 'native-storage-errors', 'cumulative-resources',
    'restart-actions', 'runtime-workflow', 'independent-format-admission',
)
STATUSES = {'observed', 'unqualified', 'counterexample', 'missing', 'pending', 'excluded'}
CRITERIA = {f'WS-{n:03}' for n in range(1, 25)} | {f'SAF-{n:03}' for n in range(1, 17)}
CONFIGURATION = {
    'architecture': 'x86_64', 'os': 'Windows 11 EnterpriseEval', 'build': '26300',
    'filesystem': 'NTFS', 'volume': 'guest-system-C', 'controller': 'SATA',
    'qemuMachine': 'q35,accel=kvm,smm=on', 'qemuDriveIf': 'ide',
    'imageFormat': 'QCOW2', 'qemuCache': 'writeback',
    'hostCaches': 'alive-through-observed-faults',
    'workerSha256': 'f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa',
    'mode': 'ordinary-receipt', 'outputPolicy': 'OD-11-option-A',
    'source': 'authored-65536-byte-marker-only', 'publication': 'held-same-volume-no-replacement',
}
SECONDARY_CONFIGURATION = {
    'os': 'Windows 11 Enterprise Evaluation', 'version': '10.0.26300',
    'volume': 'guest-secondary-D', 'filesystem': 'NTFS', 'diskCapacityBytes': 134217728,
    'partitionStartLBA': 2048, 'partitionSectors': 260096,
    'partitionBytes': 133169152, 'filesystemReportedBytes': 133165056,
    'qmpBlockDriver': 'raw', 'qmpBackingDriver': 'file', 'device': 'usb-storage',
    'controller': 'existing-qemu-xhci-bus-auto-selected',
    'cacheFlags': 'not-explicitly-supplied-defaults-only',
    'queryBlockCache': 'writeback=false,direct=false,no-flush=false',
    'namedBlockNodeCaches': 'file:writeback=true,direct=false,no-flush=false;raw:writeback=true,direct=false,no-flush=false',
    'scope': 'native-error-observations-only',
}


class Refused(ValueError):
    pass


def exact_configuration(value, expected):
    return (type(value) is dict and set(value) == set(expected)
            and all(type(value[key]) is type(item) and value[key] == item
                    for key, item in expected.items()))


def members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Refused('duplicate JSON member')
        result[key] = value
    return result


def _validate(ledger):
    if type(ledger) is not dict:
        raise Refused('ledger object required')
    if set(ledger) != {'schemaVersion', 'profile', 'domain', 'configuration', 'cells',
                       'criteriaTrace', 'combinations', 'limitations'}:
        raise Refused('ledger fields')
    if type(ledger['schemaVersion']) is not int or ledger['schemaVersion'] != 1:
        raise Refused('schema version')
    if ledger['domain'] != 'actual-observations-only' or ledger['profile'] != PROFILE:
        raise Refused('profile or evidence domain')
    if not exact_configuration(ledger['configuration'], CONFIGURATION):
        raise Refused('exact configuration mismatch')
    if type(ledger['cells']) is not list:
        raise Refused('cells required')
    ids = []
    for cell in ledger['cells']:
        if set(cell) != {'id', 'status', 'scope', 'finding', 'evidence'}:
            raise Refused('cell fields')
        ids.append(cell['id'])
        # This revision has no qualified actual profile cell. A caller cannot
        # promote an editable status to qualification by changing JSON.
        if cell['status'] not in STATUSES:
            raise Refused('unsupported actual qualification claim')
        if not all(type(cell[key]) is str and cell[key] for key in ('scope', 'finding')):
            raise Refused('cell explanation required')
        if type(cell['evidence']) is not list:
            raise Refused('evidence references required')
        for evidence in cell['evidence']:
            if set(evidence) != {'path', 'sha256'}:
                raise Refused('evidence fields')
            if (type(evidence['path']) is not str or not evidence['path'].startswith('docs/')
                    or '..' in Path(evidence['path']).parts):
                raise Refused('nonpublic evidence reference')
            digest = evidence['sha256']
            if type(digest) is not str or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise Refused('evidence digest')
    if len(ids) != len(set(ids)) or set(ids) != set(REQUIRED):
        raise Refused('missing, duplicate or unknown required cell')
    trace = ledger['criteriaTrace']
    if type(trace) is not dict or set(trace) != CRITERIA:
        raise Refused('complete WS/SAF trace required')
    for value in trace.values():
        if set(value) != {'cells', 'disposition', 'obligation'}:
            raise Refused('criterion trace fields')
        if (not value['cells'] or not set(value['cells']) <= set(REQUIRED)
                or value['disposition'] not in {'required-unqualified', 'separate-required-scope'}
                or type(value['obligation']) is not str or not value['obligation']):
            raise Refused('criterion obligation missing')
    combinations = ledger['combinations']
    if type(combinations) is not dict or set(combinations) != {
            'supportedActualProfiles', 'refusedCandidates', 'excludedOperations', 'supportedModelInput',
            'secondaryObservationConfiguration'}:
        raise Refused('combination fields')
    if combinations['supportedActualProfiles'] != []:
        raise Refused('this revision supports no actual profile')
    if not exact_configuration(combinations['secondaryObservationConfiguration'], SECONDARY_CONFIGURATION):
        raise Refused('secondary observation configuration mismatch')
    for key in ('refusedCandidates', 'excludedOperations'):
        values = combinations[key]
        if type(values) is not list or not values or any(type(value) is not str or not value for value in values):
            raise Refused('combination lists')
    if type(combinations['supportedModelInput']) is not str or not combinations['supportedModelInput']:
        raise Refused('model scope required')
    if type(ledger['limitations']) is not list or not ledger['limitations'] or any(
            type(value) is not str or not value for value in ledger['limitations']):
        raise Refused('limitations required')


def validate(ledger):
    try:
        _validate(ledger)
    except (TypeError, AttributeError, KeyError) as error:
        raise Refused('malformed ledger structure') from error


def inspect(ledger, requested_configuration, evidence_root):
    """Return refusal before any target API. Only public evidence reads occur."""
    validate(ledger)
    if not exact_configuration(requested_configuration, CONFIGURATION):
        raise Refused('requested configuration is outside exact declared candidate')
    root = Path(evidence_root).resolve()
    for cell in ledger['cells']:
        for evidence in cell['evidence']:
            path = (root / evidence['path']).resolve()
            if not path.is_relative_to(root / 'docs'):
                raise Refused('evidence escapes public docs')
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != evidence['sha256']:
                raise Refused('missing or changed bound evidence')
    blockers = [{'cell': cell['id'], 'status': cell['status']} for cell in ledger['cells']]
    return {'outcome': 'refused-before-target-effects', 'profile': PROFILE,
            'blockingCells': blockers, 'targetEffects': 0, 'profileAdmitted': False,
            'productionPublicationAllowed': False, 'rawAdmissionAllowed': False,
            'repairAllowed': False, 'automaticRecoveryAllowed': False}


def hypothetical_conjunction(premises):
    """Test-only logical sufficiency; this function consumes no actual ledger."""
    if type(premises) is not dict or set(premises) != set(REQUIRED):
        return False
    return all(type(value) is bool and value for value in premises.values())


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=members)
