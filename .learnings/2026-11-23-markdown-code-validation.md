# Markdown code validation

- When a Markdown document explains forbidden syntax in prose, scan extracted code blocks rather than the whole document; otherwise the explanation itself creates false positives.
- When embedding Markdown fenced code in a JavaScript tool call, avoid raw backticks inside template literals. Build the command from lines or represent the fence with `String.fromCharCode(96)`.
