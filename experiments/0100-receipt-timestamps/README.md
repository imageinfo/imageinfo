# Receipt timestamp completion diagnostic (#0100)

This isolated research experiment narrows one storage prerequisite for #0078:
whether ordinary native write-handle completion reproduces the receipt timestamp
drift seen in two [#0047 guest cells](../../docs/write-safety/namespace-receipt-guest.md).
The [actual finite findings](../../docs/write-safety/receipt-timestamp-completion.md)
are native observations, not a historical crash explanation or profile admission.

The worker and historical captures remain frozen. Required worker SHA-256:
`f86918a7fb3880cf8e09590fcc7d58155ef64d98c95cf9c2a6afc541c5b040fa`,
from source `b819f54533c495b332c3d4dbb0caccef49923036`.

## Fixed twelve-cell schedule

- Six frozen-worker cells: `receipt-written`, `receipt-file-flushed`,
  `final-checked`, each with normal continuation or direct process termination.
- Six authored marker cells: buffered/write-through handles, each binding after
  the write, explicit file flush, or writer close. Every marker is 65,536 authored
  bytes. The creation/write separation and repeated post-close observation each
  have one declared 20 ms wait; this is not a timing benchmark.

The read-only observer has access `GENERIC_READ | READ_CONTROL` (`0x80020000`),
sharing `FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE` (`7`),
`OPEN_EXISTING` and `FILE_FLAG_OPEN_REPARSE_POINT`. It remains open across writer
completion, then is replaced by a fresh read-only observer. Each observation
queries retained metadata, opens a separate fresh read-only path handle, queries
its metadata/security, reads at most 65,537 bytes, and queries retained metadata
again. Last-access time is not part of the claimed invariant.

Frozen-worker inspectors receive only actual emitted phase/latest receipt
contexts. Twelve before/after inspection inventories preserve byte/name/security
checks. The authored actor alone evaluates fresh property binding after writer
close. There is no timestamp setter, ACL change, privilege change, source media,
cleanup, OS crash, VM operation or adjustment to the frozen worker's checks.

## Reproduce

Use a fresh private root on Windows. Do not reuse or delete retained runs:

```powershell
python experiments/0100-receipt-timestamps/qualify.py --binary EXACT-FROZEN-WORKER.exe --root .local/receipt-timestamps-new-run
python experiments/0100-receipt-timestamps/audit.py --root .local/receipt-timestamps-new-run --output .local/receipt-timestamps-new-audit.json
```

The driver exclusively creates the root and evidence; the auditor exclusively
creates its output. The process harness has a 60-second supervisor timer and
bounded line/exit waits. These are research harness limits, not qualified native
I/O cancellation. All transaction objects and raw captures stay private and
retained. The public ledger binds the exact controller, auditor, native adapter
and existing capture harness. Record the actual filesystem separately using a
read-only volume query; results do not generalize to another filesystem or OS.

## Native boundary review

`native.py` declares the SDK ABI explicitly with Windows pointer-sized handles,
32-bit `DWORD`/`BOOL`, UTF-16 paths and the 52-byte
`BY_HANDLE_FILE_INFORMATION` structure (checked before effects). Every opened
handle is closed in `finally`. `GetSecurityInfo` and descriptor-to-SDDL conversion
are read-only; their separate OS allocations use `LocalFree`. The bounded native
read avoids Python runtime sharing defaults conflicting with the held writer.

The only native operations are `CreateFileW`, `CloseHandle`, `ReadFile`,
`WriteFile`, `FlushFileBuffers`, `GetFileInformationByHandle`, `GetSecurityInfo`,
`ConvertSecurityDescriptorToStringSecurityDescriptorW` and `LocalFree`. Creation
uses `CREATE_NEW` for the authored marker; write/flush calls use only that handle.
These research bindings introduce no Rust API, dependency, production helper or
root unsafe-policy change. The auditor runs portably on retained JSON without
loading the native adapter.
