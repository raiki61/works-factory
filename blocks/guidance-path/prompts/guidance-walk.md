<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are a first-time contributor to this repository, started in a new conversation. You know nothing about it beyond what you read now. Someone asked you for one change (below). By reading the repository from its entry files, find where the change should go and which existing files you would copy as a model. Do not make the change; report where you would make it.
Your tools are Read, Glob, and Grep. You cannot write files.

- Start from the entry files listed below. Follow only what the files you read point to (links, paths, and names they mention), and searches for names you have already seen there. Do not pick a place from the habits of other projects.
- Record every file you opened, in order, with one line on what pointed you to it.
- Say where you would put the change: each file or folder you would create or edit, with one line on what you would change there.
- Say what you would copy as a model: each existing file whose shape you would follow, and why it is the model.
- Write down where you got stuck (a question the documents did not answer) and what you filled in by guessing.

## The request

{request}

## Entry files

{entry}

## How to answer

- `steps`: the files you opened, in order, as `{file, why}`. `file` is the path from the repository root.
- `placed`: where you would make the change, as `{path, change}`. `path` is from the repository root; it may not exist yet.
- `copied`: the files you would follow as a model, as `{path, why}`. Empty if none.
- `stuck`: the questions the documents did not answer. Empty if none.
- `guessed`: what you filled in by guessing. Empty if none.
- Write `why`, `change`, `stuck`, and `guessed` in {lang}. Keep paths, names, and commands as they are.

Return only JSON that matches the output schema.
