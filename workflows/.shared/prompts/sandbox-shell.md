<!-- required-for-tools: Bash -->
The sandbox-shell rules, for writing shell commands inside the sandbox:

- Do not use here-documents or here-strings. The shell may try to create their temporary files in a place the sandbox does not let you write, and the command then fails.
- Pass the text of a program as an argument, or pipe it to the standard input.
- When you need a file, and only when your role's rules allow you to create files, put it under the temporary directory that the environment variable TMPDIR names.
- A tool on PATH may be a version manager's shim: a stand-in executable that reads settings under HOME to pick the real tool's version. Here HOME points at the run's own place, so a shim can fail even when the same tool works for the user. When a tool fails with a message about its settings or about which version to use (for example, settings files that are not trusted or not found), the shim failed, not the tool. Do not edit, trust, or create settings files to make it start. Run the real executable by its absolute path when you can find it; otherwise say in your answer which tool did not start and the first line of its error, and go on without it.
