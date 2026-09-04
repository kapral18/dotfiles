# Thread replies

## When Responding To An Existing Message/Thread

Reply mechanics (in addition to everything above):

- Reply directly; quote at most the minimum fragment needed (one short blockquote), then reply.
  Skip email-style interleaved quoting and whole-message quotes.
- Replying to a reviewer's finding on the user's work: acknowledge, state what changed (link the fix commit), name the verification done, ask for re-review.
  They found the issue — reply to the finding itself and skip explaining the reviewer's own domain or the flagged system's mechanism back at them, unless they ask.
- Match the existing register.
  For Slack or casual threads, write conversationally rather than like a report:
  prefer "I had a quick look" (or no reply) over phrases such as "I checked the history around the hypothesis".

Triage outcome — when reacting to how the other party handled a request/thread, verify the outcome against the current state first (code/head, doc, message) — act on what is actually there, not on what was claimed.
Then reply by outcome:

- **Addressed** (verified, not merely claimed): brief thanks, then close/resolve.
  - e.g. `Thanks, looks good — <one clause naming what landed>. Resolving.`
- **Not addressed / partial:** reopen/keep open and ask what's blocking it — non-accusatory, no implication of fault, offer help.
  - e.g. `Reopening — I don't think <X> made it in yet. Could we <smallest concrete ask>? Happy to help if anything's in the way.`
- Offer "drop it" as an acceptable resolution only when the user explicitly allows dropping the behavior/coverage (SOP `2.0` Compatibility Gate).
  For the user's own work, dropping is off the table by default.
- Resolution-state direction is independent of who last set it: an addressed-but-still-open item gets closed;
  a not-addressed-but-marked-resolved item gets reopened.
