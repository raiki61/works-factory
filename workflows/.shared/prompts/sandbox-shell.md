<!-- required-for-tools: Bash -->
The sandbox-shell rules, for writing shell commands inside the sandbox:

- Do not use here-documents or here-strings. The shell may try to create their temporary files in a place the sandbox does not let you write, and the command then fails.
- Pass the text of a program as an argument, or pipe it to the standard input.
- When you need a file, and only when your role's rules allow you to create files, put it under the temporary directory that the environment variable TMPDIR names.
