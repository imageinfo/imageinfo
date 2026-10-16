# WSL-native Linux new-output boundary: accepted deferral

**#0177, option A explicitly selected by Terry on 2026-10-16.** Positive
Linux new-output support is deferred from the initial new-output milestone.
That milestone's new-output scope is Windows-only; its remaining Windows
implementation, qualification and admission gates still apply. WSL-native Linux
new-output support remains separate future scope under its full continuous
byte/object/name guarantee, with ordinary owner-editable output and no clobber.
Windows-mounted paths inside WSL are a distinct, unsupported configuration.
The [Windows contract](new-output-contract.md) and Windows implementation evidence
do not qualify either Linux location. Linux reads are unchanged. This scope
decision enables no mutation capability and does not remove future Linux support
from the product scope.

## Concrete missing mechanism

The retained requirement is continuous source/candidate default-stream byte,
object and name protection, including applicable parent/ancestor bindings,
through publication and final verification, with an ordinary owner-editable private
output and no clobber of a foreign output. [Option A](practical-output-policy.md)
relaxes continuous same-owner **property** exclusion only. It does not permit
cooperative writers, a hash/check/reopen race or a temporarily unguarded name.

The accepted [#0029 evidence](object-guards.md) and actual
[Linux anonymous-stage code](../../experiments/0029-object-guards/src/linux.rs)
justify these separate conclusions:

| Existing mechanism | What it supplies | What remains missing |
| --- | --- | --- |
| Source read lease | Tested rejection of prior writable handles/maps; a new writer blocks and signals a pending break. | A lease can break and the measured rename succeeds. It supplies no continuous source-name/ancestor binding or complete publication interval. |
| Anonymous candidate plus descriptor-sourced conditional link | The selected inode supplies the publication bytes; an occupied output name refuses the link rather than replacing the winner. | Anonymous staging supplies no source guard; post-link output writes remain possible. The held directory/root identity and pathname rechecks do not continuously exclude a parent/name change. |
| Private owner modes and descriptor-relative operations | Bounded creation/access policy and reference to held objects. | These do not establish exclusion against unrelated permitted same-owner writers or preserve the original path spelling continuously. Ordinary owner editability after release must remain available. |
| #0031 marker sequence and restart inspection | Bounded Linux research observations with authored in-memory producer bytes. | It does not integrate an existing mutable source or supply a complete continuous guard. Actual admit/finalize/prune refuse. |

The [actual guest research code](../../experiments/0031-guest-durability/src/linux.rs)
uses an immutable authored memory producer, anonymous staging and live snapshot
checks before its conditional link. Its `admit`, `finalize` and `prune` branches
return before opening the operand. Those branches are safe refusal, not positive
Linux publication or recovery implementations. Its research `worker` can create
artifacts and is not a production apply path or a supported fallback.

No complete native Linux mechanism meeting the retained continuous guarantee has
been justified by this preparation. This is a statement about the selected code
and available evidence, not a proof that every possible Linux design is impossible.
A new mechanism would need a concrete primitive argument for all the missing
intervals before an implementable profile/evidence plan can be honestly scoped.
Repeating the accepted lease or anonymous-stage probes cannot supply that argument.

## Options presented and decision history

The following options were independently reviewed before Terry selected the first
option (option A). The alternatives remain historical, unselected choices.

| Choice | Exact consequence |
| --- | --- |
| **A — Defer positive Linux new-output support for the initial delivery (selected 2026-10-16).** | Change the initial new-output milestone acceptance to Windows new-output only. Preserve Linux new-output as a separately deferred future scope with its current continuous guarantee. WSL-native and Windows-mounted Linux mutation requests remain unsupported; Linux reads are unchanged. This does not declare Linux implemented or erase the future gap. |
| **Remove positive Linux new-output support from the retained product scope.** | Explicitly remove the Linux new-output requirement from #0022 and its requirement/dependency trace. Keep honest unsupported refusal and historical Linux evidence. Read-only Linux scope remains separate. Reintroducing Linux writes later would require a new scope decision and justified mechanism. |
| **Retain the current positive Linux requirement.** | Keep #0022's Linux acceptance open and unsupported. A concrete continuous guard/backend mechanism is still needed before scheduling an executable implementation increment; no fully scoped successor is claimed here. Neither #0177 refusal evidence nor Windows completion can satisfy it. |

Terry selected deferral, not removal or a weaker guarantee. A cooperative-writer
restriction or weaker continuous byte/name promise would require an explicit
different contract; neither is included in the accepted decision. The future
Linux requirement retains the full guarantee described above.

Record this choice in #0022, the requirement/acceptance trace and remaining-work
inventory: positive Linux support is no longer an initial-milestone prerequisite,
but remains explicitly deferred future scope. No positive Linux implementation or
fully scoped successor is claimed. This decision introduces no writer, profile,
automatic custody, RAW admission or new power-testing requirement. Historical
Linux observations and the refusal evidence below retain their original limits.

## Bounded verification and limits

The new [refusal-only checker](../../scripts/verify_linux_scope_refusal.py) ran the
provenance-bound retained #0031 Linux executable on WSL2 native ext4 and, separately,
Windows-mounted 9p. Each location covered `admit`, `finalize`, `prune` against an
absent operand and authored foreign output/invalid-record fixtures: **12 cases
passed**. Commands reported no authorized action, commitment or production
publication permission; absent operands remained absent, and foreign entries,
object identities, bytes, modes, owners, links, sizes and modification times
matched. The harness itself created and retained its fixtures. Access-time effects
from inspection are outside these comparisons.

The executable digest matches the prior #0031 retained run ledger; this is a
refusal rerun of that frozen research binary, not a new production build or native
Linux profile admission. Current source dispatch agrees with those branches.
The root production package exposes no Linux storage backend: the Windows backend
is conditionally compiled and runtime execution remains crate-private with no
admitted public apply caller. The saved-plan profile remains
`unavailable-production`. Static source inspection establishes those boundaries;
the 12 executable cases test the research refusal dispatcher only.

No lease/anonymous-stage experiment, writer, guest, interruption or power operation
ran. No Windows evidence is transferred to Linux; mounted-path refusal does not
qualify a mounted filesystem. These finite cases do not prove arbitrary-writer
exclusion or complete filesystem-property preservation.

Primary API references rechecked **2026-10-16**: Linux man-pages 6.19
[fcntl](https://man7.org/linux/man-pages/man2/fcntl.2.html),
[open](https://man7.org/linux/man-pages/man2/open.2.html) and
[link](https://man7.org/linux/man-pages/man2/link.2.html).
They document distinct descriptor, anonymous-file and conditional-link operations;
the accepted actual observations above, not API names alone, determine the current
qualification disposition. No upstream source or documentation is imported.
