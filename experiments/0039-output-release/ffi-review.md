# Existing boundary reuse for owned output policy

Reviewed **2026-10-13**, Rust **1.99.0**, `windows-sys` **0.61.2**. New worker code
uses safe Rust. The unchanged [#0032/#0033 SDK boundary](../0032-windows-publication/ffi-review.md)
supplies exclusive creation, policy checks, held rename, stream inspection and
`apply_to_owned_marker`. No OS API, SDK feature, ABI declaration or unsafe block is
added. Root production unsafe policy and dependency graph remain unchanged.

The only policy application targets a newly created marker through its original
owned handle. The descriptor stays alive through the synchronous call; the existing
helper checks its non-null DACL, passes only DACL/protected-DACL flags, keeps owner
unchanged, and returns actual OS failure before exact post-checking. No original,
imported path, reopened handle, elevated token, SACL or NULL DACL enters that path.
Requested masks retain READ_CONTROL for inspection and compare WRITE_DAC/full control;
requesting those bits is not evidence of their effective authorization.

The measured sealed calls return error 5. The unsealed control's helper instead
returns its own exact-policy mismatch after the setter returned success. Private
Get-Acl observations record a protected, auto-inherited descriptor with one explicit
FullControl allow entry, no inherited entries. The helper continues to reject that
representation; this experiment neither changes normalization nor enables it as
a product policy. Actor success on the control is separately captured.

Primary Microsoft references observed **2026-10-13**:

- [SetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setsecurityinfo),
  updated 2021-10-13: handle-directed changes, nonzero error contract, supplied DACL
  and propagation behavior. The helper changes only the protected DACL.
- [Automatic propagation of inheritable ACEs](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces),
  updated 2021-01-07: the API's inheritance model and auto-inherited control bits.
  This informs the control observation; it does not prove a cause for access denied.

No claim is made about the internal reason for Windows denying the sealed setter,
the impossibility of other APIs/strategies, malicious privileged actors or persistence
after OS/power loss. This is a scoped source/API review and executable qualification,
not independent signoff or a complete storage-profile admission.
