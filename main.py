#!/usr/bin/env python3
"""
Simple in-memory POSIX-like filesystem that supports multiple users,
read/write file operations and directory listing.

This is a teaching/demo implementation (not for production). It models
users, files and directories with a UNIX-style permission mask (owner/others).

API highlights:
- FileSystem.create_user(username)
- FileSystem.mkdir(path, username)
- FileSystem.write_file(path, username, data)
- FileSystem.read_file(path, username) -> data
- FileSystem.list_dir(path, username) -> [names]
- FileSystem.move(src_path, dest_path, username)

Run this module as a script for a small demo and self-checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Union
import os
import sys


class FsError(Exception):
    pass


class FsPermissionError(FsError, PermissionError):
    pass


def _split_path(path: str) -> List[str]:
    p = os.path.normpath(path)
    if p == ".":
        return []
    if p.startswith(os.sep):
        p = p[1:]
    return [part for part in p.split(os.sep) if part]


@dataclass
class Node:
    name: str
    owner: str
    mode: int  # unix-style permission bits, e.g. 0o755 or 0o644


@dataclass
class File(Node):
    content: bytes = b""


@dataclass
class Directory(Node):
    entries: Dict[str, Node] = field(default_factory=dict)


class FileSystem:
    """In-memory filesystem supporting multiple users and basic permissions."""

    def __init__(self):
        self.users: Dict[str, Dict] = {}
        # root directory - make world-writable so users can create top-level dirs
        self.root = Directory(name="/", owner="root", mode=0o777)

    def create_user(self, username: str):
        if username in self.users:
            return
        self.users[username] = {"name": username}

    def _get_node(self, path: str) -> Node:
        parts = _split_path(path)
        cur: Node = self.root
        for part in parts:
            if not isinstance(cur, Directory):
                raise FileNotFoundError(path)
            if part not in cur.entries:
                raise FileNotFoundError(path)
            cur = cur.entries[part]
        return cur

    def _get_parent_dir(self, path: str) -> Directory:
        parts = _split_path(path)
        if not parts:
            return self.root
        parent_parts = parts[:-1]
        cur: Node = self.root
        for part in parent_parts:
            if not isinstance(cur, Directory):
                raise FileNotFoundError(path)
            if part not in cur.entries:
                raise FileNotFoundError(path)
            cur = cur.entries[part]
        if not isinstance(cur, Directory):
            raise FileNotFoundError(path)
        return cur

    def _check_perm(self, node: Node, username: str, perm: str) -> bool:
        # perm in {'r','w','x'}
        perms_map = {"r": 4, "w": 2, "x": 1}
        bit = perms_map[perm]
        if username == node.owner:
            shift = 6
        else:
            # we don't model groups; check "others"
            shift = 0
        return bool((node.mode >> shift) & bit)

    def mkdir(self, path: str, username: str, mode: int = 0o755):
        if username not in self.users:
            raise FsError(f"unknown user: {username}")
        if path == "/" or path == "":
            return
        parts = _split_path(path)
        cur = self.root
        for i, part in enumerate(parts):
            if part not in cur.entries:
                # to create here, current user must have write permission on cur
                if not self._check_perm(cur, username, "w") and username != cur.owner:
                    raise FsPermissionError("permission denied")
                # create directory
                newdir = Directory(name=part, owner=username, mode=mode)
                cur.entries[part] = newdir
                cur = newdir
            else:
                node = cur.entries[part]
                if isinstance(node, Directory):
                    cur = node
                else:
                    raise FsError("path component is a file")

    def write_file(self, path: str, username: str, data: Union[str, bytes], mode: int = 0o644):
        if username not in self.users:
            raise FsError(f"unknown user: {username}")
        parts = _split_path(path)
        if not parts:
            raise FsError("cannot write to root")
        parent = self._get_parent_dir(path)
        # need write permission on parent to create/overwrite
        if not self._check_perm(parent, username, "w") and username != parent.owner:
            raise FsPermissionError("permission denied")

        name = parts[-1]
        existing = parent.entries.get(name)
        data_bytes = data.encode() if isinstance(data, str) else data
        if existing is None:
            # create new file
            f = File(name=name, owner=username, mode=mode, content=data_bytes)
            parent.entries[name] = f
            return
        if isinstance(existing, Directory):
            raise FsError("path is a directory")
        # check write permission on file
        if not self._check_perm(existing, username, "w") and username != existing.owner:
            raise FsPermissionError("permission denied")
        if isinstance(existing, File):
            existing.content = data_bytes

    def read_file(self, path: str, username: str) -> bytes:
        node = self._get_node(path)
        if isinstance(node, Directory):
            raise FsError("path is a directory")
        if not self._check_perm(node, username, "r") and username != node.owner:
            raise FsPermissionError("permission denied")
        return node.content # type: ignore
        

    def list_dir(self, path: str, username: str) -> List[str]:
        node = self._get_node(path) if path not in ("", "/") else self.root
        if not isinstance(node, Directory):
            raise FsError("not a directory")
        if not self._check_perm(node, username, "r") and username != node.owner:
            raise FsPermissionError("permission denied")
        return sorted(node.entries.keys())

    def move(self, src_path: str, dest_path: str, username: str):
        """Move a file or directory from src_path to dest_path."""
        if username not in self.users:
            raise FsError(f"unknown user: {username}")
        
        # Get source node and its parent
        src_parts = _split_path(src_path)
        if not src_parts:
            raise FsError("cannot move root")
        
        src_parent = self._get_parent_dir(src_path)
        src_name = src_parts[-1]
        
        if src_name not in src_parent.entries:
            raise FileNotFoundError(src_path)
        
        # Check write permission on source parent (to remove from it)
        if not self._check_perm(src_parent, username, "w") and username != src_parent.owner:
            raise FsPermissionError(f"permission denied on source parent")
        
        src_node = src_parent.entries[src_name]
        
        # Get destination parent
        dest_parts = _split_path(dest_path)
        if not dest_parts:
            raise FsError("cannot move to root")
        
        dest_parent = self._get_parent_dir(dest_path)
        dest_name = dest_parts[-1]
        
        # Check write permission on destination parent
        if not self._check_perm(dest_parent, username, "w") and username != dest_parent.owner:
            raise FsPermissionError(f"permission denied on destination parent")
        
        # Check if destination exists
        if dest_name in dest_parent.entries:
            raise FsError(f"destination already exists: {dest_path}")
        
        # Perform the move
        del src_parent.entries[src_name]
        src_node.name = dest_name
        dest_parent.entries[dest_name] = src_node


def _demo_and_tests():
    fs = FileSystem()
    fs.create_user("alice")
    fs.create_user("bob")

    # alice creates a directory and writes a file
    fs.mkdir("/docs", "alice", mode=0o777)  # world-writable so bob can move files out
    fs.write_file("/docs/readme.txt", "alice", "Hello from Alice")

    # listing as alice
    assert fs.list_dir("/docs", "alice") == ["readme.txt"]

    # bob cannot overwrite alice's file
    try:
        fs.write_file("/docs/readme.txt", "bob", "Bob was here")
    except FsPermissionError:
        pass
    else:
        raise AssertionError("bob should not be able to overwrite alice's file")

    # make file world-readable and then bob can read
    node = fs._get_node("/docs/readme.txt")
    node.mode = 0o644  # owner rw, others r
    content = fs.read_file("/docs/readme.txt", "bob")
    assert content.decode() == "Hello from Alice"

    # bob can create his own file
    fs.write_file("/docs/todo.txt", "bob", "- buy milk")
    listing = fs.list_dir("/docs", "bob")
    assert set(listing) == {"readme.txt", "todo.txt"}

    # test move operation - bob can move his own file to a directory he can write to
    fs.mkdir("/bob_files", "bob")
    fs.move("/docs/todo.txt", "/bob_files/todo.txt", "bob")
    assert "todo.txt" not in fs.list_dir("/docs", "alice")
    assert "todo.txt" in fs.list_dir("/bob_files", "bob")

    print("Demo checks passed. Example directory listing (/docs):")
    for name in fs.list_dir("/docs", "alice"):
        node = fs._get_node(f"/docs/{name}")
        typ = "dir" if isinstance(node, Directory) else "file"
        print(f" - {name} ({typ}) owner={node.owner} mode={oct(node.mode)}")


def _interactive_cli():
    """Simple CLI for interacting with the filesystem."""
    fs = FileSystem()
    current_user = None
    
    print("=== In-Memory POSIX-like Filesystem CLI ===")
    print("Commands: adduser <name>, user <name>, mkdir <path>, write <path> <text>,")
    print("          cat <path>, ls <path>, mv <src> <dest>, whoami, exit")
    print()
    
    while True:
        try:
            if current_user:
                line = input(f"{current_user}> ").strip()
            else:
                line = input("(no user)> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        
        if not line:
            continue
        
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        try:
            if cmd in ("exit", "quit"):
                print("Goodbye!")
                break
            
            elif cmd == "adduser":
                if not args:
                    print("Usage: adduser <username>")
                    continue
                fs.create_user(args)
                print(f"User '{args}' created.")
            
            elif cmd == "user":
                if not args:
                    print("Usage: user <username>")
                    continue
                if args not in fs.users:
                    print(f"User '{args}' does not exist. Use 'adduser {args}' first.")
                    continue
                current_user = args
                print(f"Switched to user '{current_user}'")
            
            elif cmd == "whoami":
                if current_user:
                    print(current_user)
                else:
                    print("No user selected. Use 'user <name>' to switch.")
            
            elif cmd == "mkdir":
                if not current_user:
                    print("Please select a user first with 'user <name>'")
                    continue
                if not args:
                    print("Usage: mkdir <path>")
                    continue
                fs.mkdir(args, current_user)
                print(f"Directory '{args}' created.")
            
            elif cmd == "write":
                if not current_user:
                    print("Please select a user first with 'user <name>'")
                    continue
                arg_parts = args.split(maxsplit=1)
                if len(arg_parts) < 2:
                    print("Usage: write <path> <text>")
                    continue
                path, text = arg_parts
                fs.write_file(path, current_user, text)
                print(f"File '{path}' written.")
            
            elif cmd in ("ls", "list"):
                if not current_user:
                    print("Please select a user first with 'user <name>'")
                    continue
                path = args if args else "/"
                entries = fs.list_dir(path, current_user)
                if not entries:
                    print("(empty)")
                else:
                    for name in entries:
                        full_path = f"{path}/{name}".replace("//", "/")
                        try:
                            node = fs._get_node(full_path)
                            typ = "dir " if isinstance(node, Directory) else "file"
                            print(f"  {typ} {name}")
                        except:
                            print(f"  ?    {name}")
            
            elif cmd in ("read", "cat"):
                if not current_user:
                    print("Please select a user first with 'user <name>'")
                    continue
                if not args:
                    print("Usage: read <path>")
                    continue
                content = fs.read_file(args, current_user)
                print(content.decode())
            
            elif cmd in ("mv", "move"):
                if not current_user:
                    print("Please select a user first with 'user <name>'")
                    continue
                arg_parts = args.split()
                if len(arg_parts) != 2:
                    print("Usage: mv <src_path> <dest_path>")
                    continue
                src, dest = arg_parts
                fs.move(src, dest, current_user)
                print(f"Moved '{src}' to '{dest}'")
            
            else:
                print(f"Unknown command: {cmd}")
        
        except FsPermissionError as e:
            print(f"Permission denied: {e}")
        except FileNotFoundError as e:
            print(f"Not found: {e}")
        except FsError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


if __name__ == "__main__":
    import sys
    import traceback
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        try:
            _demo_and_tests()
        except Exception as e:
            print("Demo failed:", e, file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)
    else:
        _interactive_cli()
