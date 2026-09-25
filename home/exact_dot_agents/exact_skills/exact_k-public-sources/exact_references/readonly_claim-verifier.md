# Final Claim Audit

Use only for an explicit final Verify packet containing the draft claim set and source evidence.
If the packet is not a claim set plus its named primary sources, return `blocked: wrong lane` and do nothing else; this lane MUST NOT run a code or diff review.
Check material claims against the actual supporting sources; reuse complete unchanged evidence.
Match the source identity/date/ref to the claim.
Confirm the quoted passage occurs in the captured primary source and entails the claim, not just a related fact.
For web/doc claims, a missing primary-source URL or exact quote is an evidence gap;
every numeric literal in the claim must occur verbatim in that quote.
Fetch web sources with the harness web-fetch or web-search tool (fallback `ddgr --noua`); never `curl` or `wget`.
Do not credit a collector's rationale as source evidence or infer missing values. Keep quotations within copyright/source limits.
Reject or qualify the unsupported claim, not unrelated supported claims from that source.
Return supported, unsupported, or unknown per claim with concise anchors and corrections where justified. Do not spawn agents.
Do not collect a new landscape, deepen the synthesis, or verify your own audit again.
Return one consolidated terminal result; the root owns delivery.
