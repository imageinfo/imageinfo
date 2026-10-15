"""Author the bounded public ledger; updating a hash never qualifies evidence."""
import hashlib
import json
from pathlib import Path

from admission import CONFIGURATION, PROFILE, SECONDARY_CONFIGURATION

ROOT = Path(__file__).resolve().parents[2]


def evidence(*names):
    return [{'path': f'docs/write-safety/{name}',
             'sha256': hashlib.sha256((ROOT/'docs/write-safety'/name).read_bytes()).hexdigest()}
            for name in names]


def build():
    cells = []

    def cell(identifier, status, scope, finding, *sources):
        cells.append({'id': identifier, 'status': status, 'scope': scope, 'finding': finding,
                      'evidence': evidence(*sources)})

    cell('exact-configuration', 'missing', 'declared-system-volume-candidate',
         'Known build, architecture, q35/SATA and writeback image settings are declared. Exact host storage/cache stack and complete OS servicing revision are not qualified.',
         'windows-guest.md', 'namespace-receipt-guest.json')
    cell('byte-name-guards', 'observed', 'marker-live-only',
         'Held default-stream/object/name guards and no-replacement publication have bounded live evidence. This is not a complete production format/backend guard profile.',
         'ordinary-output.md', 'namespace-receipt-native.json')
    cell('property-policy', 'counterexample', 'OD-11-boundary-observations',
         'Ordinary private owner editing follows option A. Two receipt-written emulator/NMI cells have timestamp drift and guarded inspection refusal; cause unproven.',
         'namespace-receipt-guest.json', 'practical-output-policy.md')
    cell('namespace-ack', 'unqualified', 'system-SATA-QCOW2-writeback',
         'Flush returns and matching survivors do not qualify a namespace persistence acknowledgement. Earlier mode-specific NMI output-name loss is retained as historical evidence, not asserted as a current F869 receipt-sequence outcome.',
         'namespace-receipt-guest.json', 'windows-persistence.md', 'windows-guest.md')
    cell('receipt-ack', 'unqualified', 'unqualified-observational-receipt',
         'The F869 marker receipt binds observations, not its own future durability. Qualified receipt-phase acknowledgements and restart survivor rules remain absent.',
         'namespace-receipt-marker.md', 'namespace-receipt-guest.json', 'namespace-receipt-protocol.md')
    cell('caller-custody', 'unqualified', 'external-explicit-caller-history',
         'Accepted #44 guest observations cover bounded captured/fenced/stopped/renewed histories. They do not supply automatic durable current caller authority or freshness; same-byte replacement is accepted.',
         'windows-custody-guest.json', 'windows-custody.md')
    cell('native-storage-errors', 'unqualified', 'separate-secondary-USB-raw-NTFS',
         '#48 audits one control plus four actual worker storage-full os-error112 cells: empty/32768-byte candidate, pre-prepared-record and pre-receipt failure. Sources and inspection inventories remain unchanged, with no removals. Read/device-flush and isolated metadata-only errors are unrun. This distinct secondary volume cannot qualify the system SATA/QCOW2 candidate or a merged profile.',
         'native-storage-failures-native.json', 'native-storage-failures.md')
    cell('cumulative-resources', 'observed', 'one-live-fresh-supervisor',
         '#49 charges 655360 logical bytes and one operation before constructions; 15 native cells pass. No persistent global quota, reservation or free-space guarantee follows.',
         'cumulative-budget-native.json', 'cumulative-budget.md')
    cell('physical-power', 'missing', 'no-qualified-physical-fixture',
         '#50 is unscoped. Process/emulator termination and guest NMI preserve host caches; none substitutes for physical power loss.',
         'namespace-receipt-guest.md')
    cell('restart-actions', 'unqualified', 'caller-directed-marker-actions-only',
         'Narrow caller-attested unpublished owned-handle prune and read-only inspection do not qualify automatic finalization, general cleanup, replay or rollback.',
         'windows-restart-actions.md', 'windows-custody-guest.json')
    cell('runtime-workflow', 'missing', 'production-plan-apply-and-outcomes',
         'No production backend adapter implements this ledger. Explicit current plan authorization, complete integration, reporting and independent applicability checks remain required.',
         'README.md')
    cell('independent-format-admission', 'unqualified', 'RAW-and-XMP-separate',
         'Authored markers are not a RAW or XMP writer. CR3 opaque/checksum and coupled-effect refusals remain; format preservation, authenticity, privacy and operation scope are independent gates.',
         'write-admission.md')

    trace = {}

    def rows(prefix, mapping):
        for number, (ids, obligation, separate) in enumerate(mapping, 1):
            trace[f'{prefix}-{number:03}'] = {
                'cells': ids.split(','), 'disposition': 'separate-required-scope' if separate else 'required-unqualified',
                'obligation': obligation}

    rows('WS', [
        ('runtime-workflow', 'Explicit current apply authorization; preview does not mutate targets.', False),
        ('runtime-workflow,caller-custody', 'Bound revisions/read/write identities; imported plans cannot grant authority.', False),
        ('runtime-workflow', 'Whole-request preflight and explicit partial-request policy precede effects.', False),
        ('independent-format-admission', 'Exact scalar/list/structure/date semantics remain independently required.', True),
        ('independent-format-admission,runtime-workflow', 'No-op detection and explicit implicit/coupled changes remain independently required.', True),
        ('independent-format-admission', 'Exact format/capability admission refuses unsupported operations and variants.', True),
        ('independent-format-admission', 'Preserve sensor/decoding data, unknown structures and references.', True),
        ('independent-format-admission,restart-actions', 'Validate the complete candidate and all pre/post preservation checks before publication; preserve originals and recoverability.', False),
        ('byte-name-guards,property-policy', 'Continuous default-stream/object/name guards plus option-A relevant property checkpoints.', False),
        ('byte-name-guards,property-policy', 'No-clobber/link/reparse/case policy and checked topology at declared boundaries.', False),
        ('property-policy', 'Private ordinary-owner output and explicit property policy; source properties unchanged.', False),
        ('restart-actions,cumulative-resources', 'Existing-target original/backup recovery before replacement is excluded and independently required; no-backup cannot waive temporary recovery.', True),
        ('namespace-ack,caller-custody,cumulative-resources', 'Bounded persisted candidate/prepared/intent evidence and release-fence ordering.', False),
        ('byte-name-guards,namespace-ack,receipt-ack', 'One guarded publication; installed verification and qualified phase acknowledgements precede commit.', False),
        ('restart-actions,receipt-ack,caller-custody', 'Fresh actual-state bindings and current trusted history; uncertain restart retains artifacts.', False),
        ('restart-actions,runtime-workflow', 'Cancellation/interruption before and after possible publication have distinct truthful outcomes.', False),
        ('runtime-workflow,receipt-ack', 'Per-unit group dependencies, partial outcomes and receipt-based resume remain separate production work.', True),
        ('byte-name-guards,runtime-workflow', 'Rename, cycles and cross-volume copy/publish/delete workflows are excluded and remain independently required.', True),
        ('restart-actions,caller-custody', 'Restore is a fresh authorized mutation; prune only proven owned eligible held objects.', False),
        ('independent-format-admission,runtime-workflow', 'Privacy scope/residual copies and no secure-erasure claim remain independently required.', True),
        ('independent-format-admission', 'Affected authenticity-bearing structures refuse without a qualified workflow.', True),
        ('runtime-workflow,receipt-ack', 'Truthful per-unit identities/effects/recovery/cleanup and uncertainty precedence remain required.', False),
        ('cumulative-resources,native-storage-errors,property-policy', 'Private bounded recovery; storage/error/property failures stop unsafe publication.', False),
        ('exact-configuration,namespace-ack,receipt-ack,physical-power,native-storage-errors', 'Qualify exact OS/FS/storage/failure model before enabling any backend.', False),
    ])
    rows('SAF', [
        ('runtime-workflow,caller-custody', 'Preview/imported fabricated authorization cannot mutate a target.', False),
        ('independent-format-admission,property-policy', 'Paired XMP editing/no-op/creation preservation is excluded and separately required.', True),
        ('independent-format-admission', 'CR3 growth/shrink/maker-note/sensor/opaque preservation remains unqualified.', True),
        ('independent-format-admission', 'Read-only/unsupported preview/C-RAW/DPRAW operations refuse explicitly.', True),
        ('byte-name-guards,property-policy,caller-custody', 'Source/stage/parent substitution and property-check conflicts preserve the publication boundary.', False),
        ('byte-name-guards,property-policy', 'Reparse/link/case/collision policy and option-A topology observations remain required.', False),
        ('property-policy', 'Property failure refuses; ordinary owner-editable private output and explicit carry-through policy.', False),
        ('native-storage-errors,cumulative-resources,namespace-ack', 'Space/copy/flush failure retains originals and prevents unsafe release; no-backup cannot waive it.', False),
        ('namespace-ack,receipt-ack,physical-power,restart-actions', 'Distinct kill/cancel/OS/power and phase failures; no guessed rollback or fabricated commit.', False),
        ('runtime-workflow,receipt-ack', 'Pair/group partial failures and duplicate-free resume remain separate required implementation.', True),
        ('byte-name-guards,runtime-workflow', 'Pair/case/cycle rename and cross-volume source-removal safety are excluded, independently required.', True),
        ('restart-actions,caller-custody', 'Fresh authorized restore; refuse unresolved/unowned/path-injected prune.', False),
        ('independent-format-admission,runtime-workflow', 'Privacy residual and unknown coverage remains independently required.', True),
        ('independent-format-admission', 'Signature/provenance affected writes refuse until their own qualified policy.', True),
        ('restart-actions,receipt-ack,caller-custody', 'Qualified commit plus pending cleanup is distinct from uncertainty; no replay or pattern deletion.', False),
        ('exact-configuration,runtime-workflow', 'Unverified network/cloud/removable/replacement profiles refuse before publication.', False),
    ])
    return {'schemaVersion': 1, 'profile': PROFILE, 'domain': 'actual-observations-only',
            'configuration': CONFIGURATION, 'cells': cells, 'criteriaTrace': trace,
            'combinations': {
                'supportedActualProfiles': [],
                'secondaryObservationConfiguration': SECONDARY_CONFIGURATION,
                'refusedCandidates': [PROFILE, 'secondary-USB-raw-NTFS-native-error-fixture'],
                'excludedOperations': ['replacement', 'cross-volume', 'network', 'cloud',
                                       'removable-production', 'batch-pair-publication',
                                       'RAW-mutation', 'XMP-publication', 'automatic-recovery',
                                       'restore', 'broad-prune'],
                'supportedModelInput': 'exact declared candidate for refusal inspection only'},
            'limitations': [
                'All required actual cells are nonqualifying; accepted child work does not qualify its parent.',
                'System SATA/QCOW2 and secondary USB/raw evidence cannot be combined into a storage profile.',
                'Physical power, exact host storage, durable caller freshness and qualified acknowledgements remain absent.',
                'This read-only model has no target mutation API and never authorizes a backend, RAW or recovery action.',
            ]}


if __name__ == '__main__':
    path = ROOT/'docs/write-safety/profile-admission-ledger.json'
    path.write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Wrote nonqualifying actual-observation ledger')
