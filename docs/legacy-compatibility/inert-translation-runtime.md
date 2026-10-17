# Finite inert translation runtime

2026-10-17, #0130. `imageinfo compat translate` reads one UTF-8 JSON invocation
object from stdin and writes one JSON report followed by LF to stdout. The
[#0129 contract](inert-translation.md), schemas and twelve frozen MIG forms
remain the profile authority. This operation owns its JSON transport; omit
`--output`. Contextual help is available through `compat translate help`.

The production module checks the encoded 131,072-byte document bound and
container depth of eight before JSON decoding. Stdin reads at most the document
bound plus one sentinel byte. The typed decoder rejects duplicate/unknown
members, malformed JSON, wrong field types, invalid UTF-8/surrogates, BOM, NUL,
wrong version/kind, unsupported directory syntax and the frozen string/argument
bounds. Argument decoding stops before retaining a 129th entry. No validated
prefix is translated after a preflight failure. Decoded allocations are bounded
by the already checked document length; this is not a process memory quota.

The twelve report templates are immutable compiled data extracted from the
frozen authored reports, independently compared to those original reports by
actual library and executable tests. Only literal operand positions vary;
separate option values and attached assignment values keep their exact frozen
spelling. MIG-001 permits any nonempty literal input, including dash-prefixed
spelling, and places it after native `--`. The other eleven forms withhold a
suggestion. Unrecognized values, orders, options and combinations also withhold
it. Duplicate options never receive first/last-wins handling. Known missing
operations remain explicit prerequisites in combined refusals.

Every validated source argument is accounted separately in source order, with
Unicode scalar substring offsets, explicit attached empty values and separate
value ownership. The request is echoed at JSON value level. One complete
encoded report, including its final LF, is limited to 1,048,576 bytes before
writing. Report status is 0 for complete-with-differences, 1 for needs-input or
unsupported, and 2 for malformed. Actual read/write/flush failures propagate as
transport errors; the executable returns 1 and does not claim report completion.
A broken output transport may of course already contain a partial report.

The implementation accepts caller-owned input/output streams and has no
filesystem, environment, process-launch or native metadata-request boundary.
It never opens, stats or follows media/config/import/argument paths, changes the
working directory, expands shell text or dispatches suggestions. The command
accepts no document filename; shell redirection is the caller's own transport.

Verification includes all twelve actual CLI reports compared to the frozen
vectors, authored sentinel content/inventory preservation, malformed/unknown/
order/duplicate cases, exact byte/count/Unicode/path controls, and actual faulting
input/output streams. Sentinel preservation shows no writes; absence of reads
also rests on the reviewed module boundary, rather than an OS access trace.
The finite cases establish neither arbitrary legacy parsing nor compatibility
parity, successful media reads, writer/storage admission or automatic application.
