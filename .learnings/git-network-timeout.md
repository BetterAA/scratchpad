# Git network operation timeout

- The local editor's Git service runs through the user's credential helper, so the first remote push can spend more than 20 seconds before network transfer begins.
- Keep local Git commands on the short timeout, but give `push`, `pull`, and `fetch` a separate 120-second timeout so normal credential and network latency does not look like a failed sync.
