# One explicit XMP OwnerName removal contract (#0188)

Specified **2026-10-16**, contract revision **`xmp-owner-removal-2026-10-16.1`**.
This finishes the engineering selection and effect-report contract for one future
in-memory removal. It implements no XML removal, file mutation, publication or
privacy certification. #0190 owns the actual bounded mechanism; #0189 owns its
inherited known-provenance refusal. Their positive capabilities require their own
evidence. No renewed catalog-adoption decision is required for this selected slice.

## Frozen catalog and exact operation

The denominator is [r5-gps-owner-serial-core revision 1](r5-catalog.v1.json),
**31 exact selectors, 59 selector/location templates**, as committed in
`631529a01d9dca515d60fe298f7dc0d61010dc36`. The catalog file's SHA-256 is
`2c40f81340730fc169bd5e62b25d20e43ba32b7b37427324c00662d69019b25c`.
The [catalog rules](r5-catalog.md), occurrence identities, protected rendering
data, unknown-data preservation and exclusions remain intact. This operation
does not rename, add or retire selectors or change the catalog's historical
`proposal-only` label. It selects one already authorized engineering slice.

The only requested removal is **R5P-026 at `sidecar.xmp`**, expanded name
**`{http://ns.adobe.com/exif/1.0/aux/}OwnerName`** in one explicitly supplied
immutable sidecar snapshot. It selects no RAW field and no preview XMP occurrence.
Prefix spelling is irrelevant; URI spelling and local-name case are exact.
Same-stem pairing, namespace repair, alias folding and text searching cannot
select a target. Other namespaces' `OwnerName` remain unchanged residuals.

The contract accepts the bounded supported XML subset only after fresh inspection
of the actual input; caller-provided counts or coverage flags grant no technical
admission. One direct scalar description attribute or simple property element is
the selected shape. Unknown but supported siblings remain preserved. Lists,
nested/qualified targets, multiple descriptions, malformed or unsupported XML,
DTD/entity policy failures and exhausted limits refuse. The actual parser and
whole-property lexical range rules must be independently reviewed and qualified
before #0190 can claim implementation. The [existing XML component](../sidecars/xmp-component.md)
is bounded read-only evidence, not deletion qualification.

| Complete supported target inventory | Required result |
| --- | --- |
| Zero exact occurrences | `unchanged_absent`: return the entire original byte slice unchanged, with zero removals. This is scoped absence in this sidecar snapshot only. |
| Exactly one supported scalar occurrence | A future mechanism may prepare a separate derivative deleting that whole property, including its value. Empty text is still an occurrence. Return one exact original occurrence identity and deletion range. |
| Two or more exact occurrences | Refuse before derivative creation, including equal values or an attribute/element pair. No first-match selection or remove-all fallback. |
| Incomplete or unsupported inventory | Refuse; report `uninspectable`, never absence. No partial successful list may grant removal. |

The selected occurrence retains its document ID, original ordinal, exact expanded
name, form and original byte range. A derivative's remaining ordinals may shift;
compare the ordered sibling sequence with the original target removed rather
than treating ordinal renumbering as a second semantic edit. Independently check
that the derivative is the original prefix and suffix with exactly the selected
whole-property range omitted, and that a fresh supported semantic parse has
exactly the original non-target properties, values, forms and relative order.
Whitespace outside the declared deletion range, namespace declarations, packet
instructions, unknown siblings and all other bytes remain exact. No document
reserialization, property insertion, second-field edit or padding repair is implied.
Failure of either check refuses with no usable candidate returned. These checks
prove a bounded lexical/model effect, not absence of unknown semantic dependencies.

## Requested and actual effects by artifact

Each artifact receives its own stable opaque document ID and report row; do not
merge repeated previews or equal-valued occurrences. Record `requestedEffects`
separately from `actualEffects`. A request is intent, never evidence of removal.
Actual state needs the mechanism result and an observer tied to the exact input,
derivative and source revisions. Until those exist, use `unrun` rather than
manufacturing an actual `removed` result from this contract's model.

| Artifact | Requested effect | Actual/report obligation |
| --- | --- | --- |
| RAW original | None | Retained immutable input; no native removal. Native catalog cells remain uninspectable where exact namespace interpretation is unavailable. RAW embedded XMP and opaque data remain residual. |
| Every recognized stored preview | None | Distinct retained document/range and uninspectable nested metadata unless independently inspected. No decode, pixel rewrite, metadata stripping or whole-preview drop. Unknown preview inventory is an explicit uninspectable inventory residual. |
| Explicit sidecar original | Read and retain | Original bytes remain retained even if the separate derivative succeeds. Never describe the original's OwnerName as removed. |
| Separate sidecar derivative | Remove one R5P-026 occurrence | `removed` only after exact deletion and target-only semantic checks; `unchanged_absent` only after complete supported absence inspection; otherwise refusal/unrun. Every non-target remains retained or explicitly uninspectable. |
| Retained originals/backups | None | Retained copies may still contain the target. Record their known scope as residual; do not imply a privacy scrub of the retained original. |
| Recovery/staging/observation artifacts | None in this in-memory slice | No artifact is created by this contract. A future file path must inventory actual artifacts and their states, including partial failures, before reporting. Unknown existence/content is uninspectable. |
| External copies, snapshots, journals, logs and visible pixels | None | Explicit residual outside the operation. No absence, deletion, anonymity or secure-erasure assertion. |

`removed` means one exact occurrence was present in the input and absent from the
checked derivative, with the declared complement preserved. `retained` means a
known object or occurrence remains; it is not a claim that all its contents were
inspected. `residual` names known retained or excluded privacy exposure, including
known target-bearing originals. `uninspectable` means the mechanism cannot resolve
existence/content/identity completely within its supported bounds. These labels
can coexist in separate fields: a retained RAW can contain uninspectable metadata
and a known residual. Unselected documents are `unexamined`, not absent. Only a
complete inventory can establish a narrowly scoped artifact-absent result.

The other **30 selectors** and R5P-026's preview location are never implied removed.
Keep the whole **59-template** denominator visible even though just one template
is requested. Expansion remains the read reporter's **18 native RAW + 13 sidecar
+ 28 per recognized preview** cells. This arithmetic is not an inventory-completeness
or occurrence-count claim. Preserve the [read report's limits](read-coverage.md).
No overall clean/private Boolean or summed removal percentage is permitted.

Protected sensor samples, additional planes, rendering interpretation, previews,
ICC, maker-note rendering parameters, unknown pointers/checksums and all unrelated
metadata remain protected under [WS-020/021/022](../write-safety/README.md).
Catalog selection cannot waive format, dependency, identity/guard, filesystem,
recovery or publication admission. Known provenance follows inherited refusal;
there is no force switch or provenance-loss operation in this contract.

## Operation-specific rights and review before actual media work

[FXP-029](../fixture-plan/case-plan.v1.json),
[GAP-011](../inventory/README.md) and
[PROV-001 through PROV-012](../provenance/README.md) require separate scoped
evidence for the exact assets and intended operations. This is an admission
record requirement, not a newly invented product-adoption gate. Before any private
media execution, bind exact lawful input identities and historical fixture lineage,
the applicable permission overlay, users/location, retention and audience limits,
the removal implementation and observer revisions, and the following dispositions:

| Use | Evidence required / current disposition |
| --- | --- |
| Private source analysis and proposed OwnerName removal | Explicit applicable permission for this privacy purpose and these exact sources. Existing reference/read-only reviews alone do not establish it. Actual privacy media use is **unrun** pending exact rights evidence; Terry/rightsholder supplies missing permission, and the operation reviewer verifies its scope. |
| Separately named modified sidecar and retained/recovery copies | Permission for these particular derivatives, storage and retention, with source/recipe lineage and inherited restrictions. No original mutation is implied. Missing or denied scope refuses execution. |
| Independent observer/tool execution | Review exact tool/component terms, permitted local execution and processing of these inputs/outputs, notices and any derivative/report restrictions. An external upload or service needs its own access permission; none is authorized here. |
| Privacy review | Authorized reviewer records identifying owner/serial/GPS fields, embedded and visible content, opaque/uninspected regions and permitted users/storage. Lawful modification is not a privacy clearance. |
| Reports, fixtures, CI and release | Independently review the actual assembled artifacts and intended audience. Local private permission grants no publication, upload, CI artifact or redistribution permission. Keep camera-derived values, counts, flags, hashes, paths, reports and logs private unless separately allowed. |

The #0164 permission for one selected private PreviewImage's structural preflight
and JPEG decode, including separately named decoded pixels, is purpose-limited.
It **does not authorize OwnerName/privacy removal**, its media evidence, unrelated
derivatives or reports. Do not apply the PreviewImage phase extension to this path.
If existing private grants already explicitly cover the exact new purpose and
operations, record that supported conclusion instead of requesting redundant
permission. Otherwise only the missing rights need Terry/rightsholder action;
authored engineering and conservative refusal do not wait for renewed adoption.

## Finite authored contract verification

[Authored vectors](xmp-owner-removal-vectors.v1.json) and the
[independent checker](../../scripts/check_xmp_owner_contract.py) freeze catalog
bytes/counts and test the abstract singleton/absent/refusal table plus separation
of requested and actual effects. Run `python scripts/check_xmp_owner_contract.py`.
The checker is a contract model over invented observations, with no XML parser,
media input, filesystem mutation or oracle invocation. It cannot qualify #0190 or
prove the truth of a caller's claimed inventory, rights, checks or occurrence list.

Current status: operation/effect/rights contract **specified**; authored model
**verified when its checker passes**; actual private privacy media evidence,
independent removal assertion, storage publication and production removal **unrun**.
No anonymity, all-GPS/all-personal-data removal, secure erasure, native mutation,
broader RAW/firmware scope or guarantee reduction is delivered.
