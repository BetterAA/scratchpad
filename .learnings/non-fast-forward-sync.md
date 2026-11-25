# Git content sync with divergent branches

- A push can be rejected because another editor or code update advanced the remote branch. Network retries alone cannot resolve this; use two independent clones of a temporary bare repository to reproduce it.
- Fetch and merge remote commits before retrying a rejected push, with a bounded retry count for concurrent remote updates. Preserve both histories and do not force-push.
- The editor's same-title overwrite rule requires restoring the entire submitted content after merging, even when Git can combine edits without a conflict. Limit automatic conflict resolution to titles in the current request; abort other conflicts and retain local commits and staged changes.
- Preserve the actual Git error output. Taking only the last stderr line can display an unhelpful fast-forward hint while discarding the cause.
