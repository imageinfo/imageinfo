# Installed component binding for #0075

This research wrapper acquires no tool, imports no media and adds no root
dependency. The operational interpreter and library locations belong in private
attempt records. `runtime.py` derives them from the explicitly selected installed
interpreter, checks Windows x64 LLP64 and CPython 3.12.14, and hashes components
before importing the authored encoder or loading TurboJPEG.

The immutable [#0111 profile](../0111-warning-jpeg/profile.json) records its exact
historical interpreter, native codec, non-OS module closure, encoder sources,
metadata, notices and manifest. The #0075 profile is separate. A package version
string is insufficient to substitute changed component bytes. Until the new
component binding and authored technical profile are reviewed and actually
qualified, the new profile is a candidate and confers no camera assertion result.

The current discovered installation differs from the historical #0111 component
bytes. Its separate [component profile](component-profile.json) records the
current installed identities and actual inventory-only loaded closure. This is
neither reproduction of #0111 nor entropy qualification. The wrapper requires
the separately frozen canonical component-profile hash before any native load.

The finite envelope is selected independently of private camera values: stored
input at most 32 MiB; each dimension at most 8192; packed RGB at most 256 MiB;
three-component 8-bit Huffman baseline with one interleaved scan and no restart;
all-zero suffix length from 0 through 32 bytes inclusive. These are logical allocation and process
bounds, not an OS memory quota. An unsupported syntax or extent refuses before
native decoder access.

The actual decoder adapter binds `tjDecompressHeader3`, `tjDecompress2`, error
severity/diagnostics and destruction with explicit C signatures. Full native RGB
decoding uses `TJFLAG_STOPONWARNING` (8192). Zero return is required; the stored
extent policy remains a separate necessary condition. The native component and
Pillow encoder belong to the same codec family. Independence here is from
imageinfo's extraction/parser, not from Pillow's underlying codec.

The local package manifest identifies `libjpeg-turbo=3.1.4.1=hfd05255_0` inside
the libheif package. This is installed-component provenance, not proof that the
binary reproducibly corresponds to an upstream source tree. The historical
review's upstream source references are retained in the immutable #0111 profile.
No separate notice file accompanied the installed TurboJPEG DLL; pinned Pillow
notices identify the corresponding codec family/version and include its notices.
The wrapper redistributes neither native implementation nor upstream binary.

Module checks enumerate actual loaded non-OS modules and require the reviewed
closure, including byte identities. Modules under the actual Windows directory
are excluded. That exclusion is an explicit OS provenance limit; component hashes
are a local binding rather than a sandbox or complete runtime trust proof.
