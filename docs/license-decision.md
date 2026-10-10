# License decision: MIT

Accepted by Terry on **2026-10-10**, following his note on board card #0010 and a
comparison of current primary license texts. The project uses the unmodified
[MIT license](../LICENSE).

**Decision locked.** Terry explicitly accepted the recommendation and closed the
license-selection question. Reopen it only at his request; future third-party
provenance work applies this decision rather than restarting the comparison.

The copyright notice is:

```text
Copyright (c) 2026 Terry Ott and imageinfo contributors
```

The requested policy is broad freedom to use, modify, distribute, and commercialize
imageinfo, with the copyright and license notice retained in redistributed
code/products. Terry explicitly chose that form of attribution over a mandatory
visible acknowledgment in an application, README, or credits screen.

## Why MIT fits

MIT grants broad rights, including commercial distribution and sublicensing, subject
to retaining its copyright and permission notice in copies or substantial portions.
It does not require publishing modifications or adding visible UI credit.
[Official MIT text](https://opensource.org/license/mit)

There is no useful single ranking of “most permissive.” The relevant comparison is
which grants and obligations fit this project's policy:

| License | Relevant distinction |
| --- | --- |
| [MIT](https://opensource.org/license/mit) | Broad grants with retained copyright/permission notice; matches the requested attribution policy. |
| [ISC](https://opensource.org/license/isc) | Similarly broad permission with retained copyright/permission notice; a shorter alternative, not a necessary change. |
| [BSD-2-Clause](https://opensource.org/license/bsd-2-clause) | Permissive source/binary redistribution; explicitly describes notices in accompanying binary-distribution materials. |
| [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) | Explicit contributor patent grant and termination condition, plus change notices and applicable NOTICE obligations; useful protections with more conditions. |
| [0BSD](https://opensource.org/license/0bsd) | Omits an attribution-retention condition, so it does not meet the requested policy. |

MIT's text contains no express patent grant. This comparison does not conclude that
all patent questions are settled by choosing MIT. Visible credit remains welcome,
but it is not an added license condition. Do not append a custom attribution clause
and still call the result the standard MIT license.

## Third-party artifact rules

The project-license choice is resolved. Card #0010 now provides the
[artifact provenance policy](provenance/README.md), [workflow](provenance/review-workflow.md)
and review-record schema. Actual asset permissions and admissions still require
their own evidence:
third-party code, tag definitions, documentation, sample media, optional databases,
and generated outputs keep their applicable terms. Record provenance and review
the intended reuse path before import. MIT licensing of imageinfo does not grant
permission to relicense ExifTool material or publish someone else's photographs.

Maintain contributor authorship/copyright information as the project grows. This
decision sets the outbound project license; it does not assign contributors'
copyright to another person or silently change third-party notices.
