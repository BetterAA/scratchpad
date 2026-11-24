# Git network operation timeout

- A real remote push dry run spent about 20 seconds waiting for the initial network handshake, followed by about half a second querying the user's credential helper. Read trace timestamps at component boundaries before attributing the delay.
- Keep local Git commands on the short timeout, but give `push`, `pull`, and `fetch` a separate 120-second timeout so normal credential and network latency does not look like a failed sync.
- A failed push may already have committed content locally. Even if content is unchanged on retry, attempt the remote push so a local commit cannot be mistaken for a completed upload.
