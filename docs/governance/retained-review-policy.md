# Retained solo review policy: actual bounded verification

**#0158, 2026-10-17.** The selected #0157 option A remains in effect:
authorized direct commits/pushes after project checks, practical agent review,
and Terry's acceptance of board handoffs. The observed repository permits this
route. These are project procedures; no mandatory PR approval, CODEOWNERS or new
branch protection was adopted. Public contributors continue to submit ordinary PRs.

## Actual observation and allowed route

The current read-only observation binds
[`de24e58`](https://github.com/imageinfo/imageinfo/commit/de24e58fd88c1b64f350ac19c8854d3716ef66e6).
The rulesets API returned an empty list, the branch API returned `protected: false`
and no required status-check contexts, and the complete recursive tree contained
no CODEOWNERS file. The dedicated branch-protection and individual collaborator
permission endpoints returned 403; those reads establish no additional fact about
protection or another person's access. Authenticated repository metadata reported
push/admin capability for the current operator; no reviewer roster was inferred.

The retained parent-operated direct push of that exact commit supplies the allowed
route observation. Its [actual hosted run](https://github.com/imageinfo/imageinfo/actions/runs/39049795799)
completed successfully for `windows-2025`, `ubuntu-24.04` and `macos-15`.
These successes demonstrate executed checks, not GitHub-required checks or a
promise that every step ran on every OS. Platform-specific skips retain their
workflow meaning. The operation record, rather than repository metadata alone,
is the evidence for the direct-push route. The earlier #0157 decision commit is
not substituted for this exact-source successful check evidence.

The prior publication integration also retained independent agent review,
correction and re-review before board handoff. Terry subsequently accepted
#0160's source-candidate preparation on 2026-10-17. That is an actual owner board
acceptance, not independent human verification or approval to publish a release.
Private operational records retain the detailed review and board history; public
contributors need no access to them to use the documented procedure.

## Finite case dispositions

| Case | Actual result and limit |
| --- | --- |
| RP-01: current rules/ownership | Read-only empty rulesets, unprotected main and absent tracked CODEOWNERS observed at the exact commit above. |
| RP-02: allowed route/checks | Authorized direct push and exact-source three-OS green CI observed. This does not demonstrate enforcement. |
| RP-03: review/acceptance | Prior agent integration review and Terry board acceptance observed; the procedure remains required for current work. |
| RP-04: missing review | No adopted machine denial is claimed. No missing-review push was attempted. Project review requirements still apply. |
| RP-05: failed/missing checks | No adopted machine denial is claimed. No deliberately failing or unchecked push was attempted. Project checks still apply. |
| RP-06: bypass/force update | Not executed within the retained-policy scope. No settings changes, force push, deletion or extra test actor were used. |

The historical eighteen-case protection rehearsal remains unselected and unrun.
There is no changed rule against which to demonstrate a denial or bypass.
Absent review/check enforcement is a limit of the retained policy, not evidence
that skipping the procedure is authorized. No reviewer was contacted, permission
changed, mandatory PR installed or human reviewer appointed for this verification.

## Contributor and maintainer procedure

1. Scope the change and retain relevant correctness, provenance and safety evidence.
2. Run the [applicable project checks](../../CONTRIBUTING.md#work-locally).
   Resolve actual failures and retain exact-source results; a green unrelated
   commit or skipped work does not supply missing verification.
3. Obtain practical agent review where applicable, correct material findings and
   re-review material corrections. Describe it as agent review.
4. Use the authorized direct-push route for Terry-authorized work, or an ordinary
   PR for public contributions. Confirm the pushed source and its actual CI.
5. Hand off internal cards Ready for Review with concise scope, evidence and limits.
   Terry alone accepts Completed. Public contributions carry their context and
   evidence in the PR and do not require private board access.

The [machine-readable record](retained-review-policy.v1.json) separates actual
observations from procedural requirements and unexecuted negative cases. Run:

```console
python scripts/check_retained_review_policy.py
python scripts/check_docs.py
```

The first command checks six finite dispositions, exact-source references,
check names and absence-of-enforcement limits offline. It does not query GitHub,
validate private operational history, establish current access or exercise a push.
Reinspect live state for a later operational claim; this dated observation is not
continuous monitoring. Technical checks and the current wave's independent review,
push and handoff remain the parent's separate completion responsibilities.
