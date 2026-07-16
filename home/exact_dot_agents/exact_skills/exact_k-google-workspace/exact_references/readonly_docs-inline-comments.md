# Google Docs inline comments (UI fallback)

Anchored (highlighted) Google Docs comments cannot be created via API: the Docs API has no comment methods, and Drive API `comments.create` accepts an `anchor` but Google Workspace editors treat API-created comments as unanchored (documented constraint) — they land in the comments panel with no highlight.
True highlight + comment requires driving the Docs editor UI with `k-playwriter` (`~/.agents/skills/k-playwriter/SKILL.md`).

Comments post as the logged-in Chrome user.
This is human-visible publication: the SOP publication gate (draft → show payload → approval) applies before posting anything.

## Procedure (per comment)

1. Resolve the target passage first: extract doc text via `gws docs documents get --params '{"documentId":"<id>","includeTabsContent":true}'` and pick a verbatim quote long enough to be unique in the doc (Find jumps to the first match).
   Tab IDs come from the same response (`tabProperties.tabId`).
2. Open `https://docs.google.com/document/d/<id>/edit?tab=<tabId>`; wait for load;
   a snapshot must show the doc title and the expected logged-in account.
3. Select the passage via the keyboard Find flow — DOM selectors cannot select passage text because Docs renders text on canvas:
   click the editor (`.kix-appview-editor`) → `Cmd+F` → fill the "Find in document" textbox (locator from snapshot;
   its id is dynamic) with the quote → `Enter` → `Escape`. `Escape` closes the find bar and leaves the match selected.
4. `Cmd+Alt+M` opens the anchored comment box. Completion check: snapshot shows `textbox "Comment draft"`.
   If not, the selection was lost — redo step 3.
5. Type the comment as plain text (comment boxes render no markdown/backticks), then click `role=button[name="Post Comment"]`.
6. Verify: `gws drive comments list` for the file shows the new comment with a real `kix.*` `anchor` and the expected `quotedFileContent.value`; a screenshot confirms the visible highlight.
   A comment without both is not anchored — delete and redo.
