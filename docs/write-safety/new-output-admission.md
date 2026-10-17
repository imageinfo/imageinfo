# Exact new-output admission boundary — #0176

The production selector and intended caller now return a concrete unsupported
result for the selected Windows new-output candidate. No exact profile is
admitted. This is the explicit unsupported branch of #0176's acceptance; the
positive storage outcome tracked by #0022 and the downstream RAW/XMP operations
remain unfulfilled.

## Implemented caller boundary

[`new_output::prepare`](../../src/storage/new_output.rs) receives the intended
operation paths, an existing cumulative resource owner, cancellation and a deferred
builder. It invokes the [code-defined selector](../../src/storage/admission.rs)
before source/candidate/backend construction, resource charges or worker release.
The builder also requires the sealed admission token. The preparation exposes
neither a token extractor nor a positive executor.

Requested OS/filesystem/controller/cache/operation labels are hints, not live
observations. Exact field and operation mismatches refuse; even matching labels
cannot manufacture a grant. Receipts, imported plans, status booleans and editable
qualification records are not admission inputs. The token has no inhabitant or
constructor, including in test builds. A positive path requires a reviewed code
change plus actual evidence, independent format validation and explicit apply.

The existing internal unqualified protocol remains available for bounded
qualification. Its successful protocol execution does not call or bypass this
intended production admission boundary and cannot mint a token.

## Concrete unresolved predicates

| Predicate | Actual disposition | Corrective implementation owner and work |
|---|---|---|
| Prepared-source namespace preservation on native failure | Contrary #0174 staged-error observation | Bot storage integration under #0022/#0176: resolve the prepared-source/transaction name loss and substantiate preservation on the exact proposed configuration. Original bytes at an earlier fixture name are insufficient; cause remains unproven. |
| Candidate-file native flush error | Not produced | Bot native-adapter/qualification integration: establish actual candidate flush-failure behavior and retained artifacts for the exact profile. |
| Installed-namespace native flush error | Not produced | Bot native-adapter/qualification integration: establish actual postpublication namespace-flush failure and uncertainty/preservation behavior. |
| Receipt-file native flush error | Not produced | Bot native-adapter/qualification integration: establish actual receipt-flush failure, rather than substituting survival or a successful flush return. |
| Exact live configuration and implementation binding | Not implemented | Bot admission implementation: bind actual OS/servicing, volume/filesystem, controller/cache, executable and held operation facts before any positive grant. A requested descriptor is not that binding. |

#0174's actual source-read1117 and compound candidate-create433 observations
remain separate from the unproduced flush classes. #0175's twelve actual
system-volume/QMP-quit cells do not qualify the separate USB/raw fixture or erase
its contrary observation. Software-injected errors and emulator drain failures
do not become actual returned native flush errors.

Physical power, dedicated hardware, new NMI campaigns, automatic durable custody,
encryption/key services and renewed product approval are not added gates.
The accepted ordinary-owner option-A property boundaries and VM-off-only
best-effort limits remain unchanged.

## Evidence and verification

- [WS trace](new-output-admission-ws.json): twelve exact storage clauses and the
  full retained #0022 acceptance mapping, with explicit evidence kinds and owners.
- [SAF trace](new-output-admission-saf.json): all sixteen original scenarios,
  applicable mechanism evidence and their remaining full-operation obligations.
- [Selector controls](../../src/storage/admission/tests.rs): exact descriptor,
  operation, imported-claim, host and owned-filesystem refusals.
- [Intended caller controls](../../src/storage/new_output/tests.rs): zero deferred
  constructors, unchanged prior cumulative accounting and actual namespace/bytes
  on exact and mismatched requests, even with missing source, cancellation or
  exhausted resource state.
- Existing actual native normal protocol control remains unqualified and
  preserves its explicit refusal/retained-artifact result.

`python scripts/check_new_output_admission.py` checks trace integrity and its
negative controls offline. It neither executes the storage protocol nor grants
authority. Relevant root Rust/native tests and cross-platform refusal/build
checks are retained separately. None of these checks completes a RAW/XMP SAF
scenario or enables replacement, move, grouping, privacy mutation or repair.
