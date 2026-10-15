# Clean hosted contributor verification

**#0065 / GOV-OPEN-06 subset, observed 2026-10-15.** Procedure
`clean-machine-v1` maps the pinned Rust contribution checks to actual fresh hosted
jobs at source revision
[`5f7a86eca8e36b48d8334c8e754e3859dd9bb213`](https://github.com/imageinfo/imageinfo/commit/5f7a86eca8e36b48d8334c8e754e3859dd9bb213).
All three jobs in [run 38749270366](https://github.com/imageinfo/imageinfo/actions/runs/38749270366)
passed. The [sanitized evidence](clean-machine-evidence.json) records exact source
file hashes, runner images, toolchain targets, command mapping and permission scope.

Here, **clean** means a fresh GitHub-hosted VM and newly initialized public
checkout with no private corpus or local board prerequisite. The hosted images
already contain Git, rustup, native compiler/linker prerequisites and Python.
This does not demonstrate installation from a bare OS or a hermetic build.
GitHub documents the [fresh VM behavior and hosted privileges](https://docs.github.com/en/actions/reference/runners/github-hosted-runners);
the run's setup and checkout logs witness the actual image and source revision.
The existing CI was reused; this ticket adds no duplicate workflow.

## Declared setup and checks

Start with Git, rustup and the host's native linker prerequisites from the
[foundation setup](../foundation/README.md). Python 3.10 or newer with pip must be available
as `python` for documentation/schema QA. The observed images supply these
prerequisites; their installation on a bare contributor OS was not tested.
Clone the public repository, select the revision to review and work at its root.

```console
git clone https://github.com/imageinfo/imageinfo.git
cd imageinfo
git checkout 5f7a86eca8e36b48d8334c8e754e3859dd9bb213
rustup toolchain install 1.99.0 --profile minimal --component clippy,rustfmt
python -m pip install jsonschema==4.26.0
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
python scripts/check_output_schemas.py
cargo build --locked --release
python scripts/check_docs.py
```

The Git clone/checkout commands describe the equivalent contributor operation;
the hosted jobs used the immutable checkout action, fresh initialization and
depth-one fetch of that exact commit. The remaining commands above ran directly
in all three jobs. CI installs the Python QA dependency in its disposable image;
on an existing workstation, use an isolated Python environment if the package
manager requires it. `jsonschema` is QA tooling, not an imageinfo runtime or Cargo
dependency. Only its top-level version is pinned here; this is not a locked
Python dependency graph. The pinned package's `Requires-Python: >=3.10`
metadata sets that installation minimum; every Python version above the minimum
has not been qualified by these jobs.

`rust-toolchain.toml` activates Rust 1.99.0 with clippy/rustfmt from the repository
root, and `--locked` preserves the committed Cargo dependency resolution.
Initial toolchain and package acquisition needs network access. No dependency
cache restoration step appears in this frozen workflow; image-provided tools
and upstream caches still prevent a claim that every byte was obtained anew.

## Observed environments and outcomes

| Job | Setup log OS / image version | Rust target | Root tests |
| --- | --- | --- | --- |
| [Windows](https://github.com/imageinfo/imageinfo/actions/runs/38749270366/job/116471054132) | Server 2025, 10.0.26100; `windows-2025-vs2026` / `20261007.264.1` | `x86_64-pc-windows-msvc` | 80 passed, none failed/ignored |
| [Ubuntu](https://github.com/imageinfo/imageinfo/actions/runs/38749270366/job/116471054342) | 24.04.5 LTS; `ubuntu-24.04` / `20261004.327.1` | `x86_64-unknown-linux-gnu` | 82 passed, none failed/ignored |
| [macOS](https://github.com/imageinfo/imageinfo/actions/runs/38749270366/job/116471053742) | 15.7.9, build 24G830; `macos-15-arm64` / `20260907.0337.1` | `aarch64-apple-darwin` | 82 passed, none failed/ignored |

The Rust installer logs report `rustc 1.99.0 (b940084d7 2026-09-28)` on each
target. The extra Unix tests cover native path/case behavior. Formatting, clippy,
release build and documentation checks pass on every row. Each actual-output
schema check validates 12 emitted records and rejects six altered observations.
The workflow's separate research checks also pass or take their declared
platform skip/refusal branch; a successful job does not make a skipped Windows
probe a macOS/Linux qualification.

The image manifests linked by the setup logs declare
[Windows native tools and SDKs](https://github.com/actions/runner-images/blob/win25-vs2026/20261007.264/images/windows/Windows2025-VS2026-Readme.md),
[Ubuntu C/C++ tools](https://github.com/actions/runner-images/blob/ubuntu24/20261004.327/images/ubuntu/Ubuntu2404-Readme.md),
and [macOS Xcode/Python tooling](https://github.com/actions/runner-images/blob/macos-15-arm64/20260907.0337/images/macos/macos-15-arm64-Readme.md).
These are the supplied image inventories, not independently measured compiler or
Python version selections. No standalone `python --version` step was logged.

A separate frozen Git archive on the existing Windows developer host also passes
the documented debug build, root/metadata help and JSON version commands, public
docs checker, and all 31 published notice hash comparisons across 30 packages.
That host check is supplemental; the parent host was not clean or disposable.

## Sanitized CI permission inspection

The exact workflow source grants `contents: read`, with no job override, OIDC,
publication step, explicit secret reference or `pull_request_target` trigger.
It pins `actions/checkout` to
`d23441a48e516b6c34aea4fa41551a30e30af803` and sets
`persist-credentials: false`. All three setup logs report only **Contents: read**
and **Metadata: read** for `GITHUB_TOKEN`; checkout logs show authentication
cleanup. Raw logs, masked token fields, worker identifiers and private paths are
not copied into the public evidence.

This inspects the frozen workflow and observed token permissions. It does not
audit repository settings, branch/environment protections, account access or a
secret inventory. Repository token limits are separate from hosted OS privileges:
GitHub's Windows image is administrative and Unix images support passwordless
sudo. No ordinary-user workstation verification is inferred.

The corrected contributor guidance now names the Python QA setup directly,
includes release/schema checks, and describes the actual public fixture-based
schema checker. Future changes need their own exact run; moving runner labels
are not immutable OS support promises. Bare-OS bootstrap, offline builds,
maintainer staffing/handoff, security-response operation and release readiness
remain unverified by this ticket.
