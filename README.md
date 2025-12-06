# OS-Assignment2

Requirement

- Python 3.8 or newer

## Running

Interactive CLI:

```bash
python3 main.py
```

Then enter commands such as `adduser alice`, `user alice`, `mkdir /docs`, `write /docs/readme.txt hello`, `ls /docs`, `cat /docs/readme.txt`, `mv /docs/readme.txt /docs/old.txt`.

## What `main.py` provides

- `FileSystem` class with Unix-like permission checks and in-memory directories/files
- Operations: `adduser`, `user`, `whoami`, `mkdir`, `write`, `cat`, `ls`, `mv`

## CLI command descriptions

- `adduser <name>`: create a user so it can own and access files.
- `user <name>`: switch the current session to that user (must exist first).
- `whoami`: print the active user or a hint to select one.
- `mkdir <path>`: create a directory at the given absolute or relative path; requires write perms on the parent.
- `write <path> <text>`: create or overwrite a file with the provided text; requires write perms on the parent and the file (if it exists).
- `ls [path]` or `list [path]`: list directory entries (defaults to `/`).
- `cat <path>` or `read <path>`: output the file contents if readable by the current user.
- `mv <src> <dest>` or `move <src> <dest>`: move/rename a file or directory; requires write perms on both source and destination parents and fails if the destination exists.
- `exit` or `quit`: leave the CLI.
