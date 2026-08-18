# GitHub Attachments — Browser-Assisted Upload (Images, Videos, Files)

Reference for the `k-github` skill.
Load when any flow needs to upload a local image/video/file to GitHub and get a `user-attachments` URL:
issue/PR bodies, comments, replies, review comments, or a direct "upload this image" request.

The REST/GraphQL APIs cannot upload attachments.
GitHub's web comment boxes can, and they upload **immediately on file selection without posting anything** —
that is the mechanism this flow drives.

Load and follow `~/.agents/skills/k-playwriter/SKILL.md` before any browser action.

## Upload flow

1. **Resolve the destination before uploading.**
   Identify the exact target repository/object, verify the logged-in browser identity, and record whether the repository is public, private, or internal.
   Use an editor in that repository, preferably the exact target object's editor.
   If a direct upload request has no destination, ask which repository/object should own the attachment;
   use only a comment box in the resolved destination.
   For an existing PR/issue, the Conversation tab's main comment box is a known surface:
   `textarea#new_comment_field` with a paired hidden `input[type="file"]#fc-new_comment_field`.
   For another editor, inspect the DOM and verify its paired file input rather than assuming an id convention.
   The `accept` list is broad — images (`.png`, `.jpg`, `.gif`, `.svg`, `.webp`), video (`.mov`, `.mp4`, `.webm`), docs/archives (`.pdf`, `.zip`, `.gz`, `.log`, `.txt`, …).
2. **Preserve the editor state.** Read and save the textarea's exact existing value before selecting a file.
3. **Upload and harvest one file at a time.**
   `setInputFiles()` on the verified file input uploads via GitHub's `upload/policies/assets` flow and inserts markup into the textarea without submitting the form.
   Poll until the `Uploading` placeholder is gone, then diff the textarea against the saved value to isolate the new markup.
   Small images are inserted as `<img ... alt="NAME" src="https://github.com/user-attachments/assets/UUID" />`;
   other files (and larger media) use `![NAME](URL)` or a bare link — match all forms.
4. **Restore the editor state.**
   Restore the exact saved textarea value after each upload and verify it matches, preserving pre-existing draft text and keeping harvested markup out of anywhere it could be submitted accidentally.
5. **Keep the URL in the resolved visibility context.**
   [GitHub documents](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files) that public-repository uploads are accessible without authentication, while private/internal uploads require repository access.
   Use the URL only in the resolved destination; it is repository/visibility-scoped, not account-scoped.

## Pre-upload QA

Before uploading any image or video:

- Verify every file exists and is non-empty.
- Verify dimensions are sane for the intended caption and placement.
- Verify md5s are pairwise distinct across the batch; upload each distinct state exactly once, with duplicates excluded.
- View every file in this session and confirm it matches its intended caption/placement.
  Upload only images and videos you have viewed in this session.

## Presentation in comment/issue/PR bodies

- One image per line — keep each `<img>` tag on its own line, separate from other images and paragraphs;
  GitHub renders side-by-side images squeezed and unreadable.
- Precede every image with its own bold title line (e.g. `**Before — sortable Description column:**`), a blank line, then the `<img>` tag, then a blank line.
- Before/after pairs are two titled blocks, not a `before | after` row.
- Videos: paste the bare `user-attachments` URL on its own line (GitHub renders a player); same titled-block rule.
  Players never render inside markdown table cells or link/`<img>` syntax — a video URL in a table cell degrades to a text link (verified live).
  For a behavior's before/after video pair, stack under one bold caption: `Before:` line, blank line, before URL;
  then `After:` line, blank line, after URL.
- Verify after publishing/recreating: attachment counts via `--jq`, and rendered `naturalWidth > 0` via the browser when it matters.

## Gates

- Selecting the file creates the asset immediately and can make it publicly accessible when the destination repository is public.
  Treat the upload as a GitHub side effect and perform it only for the user-requested/approved target and visibility.
- Embedding the URLs in any human-visible body stays behind the normal Human-Visible Publication Gate and skill-specific approval rules.
