#!/usr/bin/env python3
"""Owner-run, testserver-only recovery of three pinned stale singleton symlinks.

Keep browser launches stopped throughout check/apply/undo. No profile content or
symlink target other than SingletonLock is read. No browser is launched.
shortcut: process discovery sees this host's PID namespace; use an ordinary host
terminal, never a container, remote PID view or an agent sandbox.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import socket
import stat
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

from kiro_crew import platform_compat

PROFILE = Path("/home/adminuser/.kiro/crew/browser-profile")
EXPECTED_UID = 1002
EXPECTED_LOCK = "ai-ubuntu-1680"
EXPECTED_MTIMES = {
    "SingletonLock": 1795444513707827341,
    "SingletonSocket": 1795444513708827341,
    "SingletonCookie": 1795444513708827341,
}
NAMES = tuple(EXPECTED_MTIMES)
BACKUP_PREFIX = "max-singleton-testserver-"


def guard_context(
    host: str, uid: int, euid: int, platform: str, environ: Mapping[str, str]
) -> None:
    if environ.get("KIROCREW_SANDBOX_ACTIVE"):
        raise RuntimeError("Use an ordinary owner terminal; never clear the sandbox marker")
    if platform != "linux" or host != "testserver":
        raise RuntimeError("This procedure is only for the testserver Linux host")
    if uid != EXPECTED_UID or euid != EXPECTED_UID:
        raise RuntimeError("Run as UID1002, without sudo or impersonation")


@contextlib.contextmanager
def open_directory(path: Path) -> Iterator[int]:
    """Refuse symlinks at every directory component, not only the final name."""
    path = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def no_active_browser(profile: Path, proc: Path) -> None:
    wanted = os.path.realpath(profile)
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip().lower()
            if not comm.startswith(("chrome", "chromium")):
                continue
            args = (entry / "cmdline").read_bytes().split(b"\0")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RuntimeError("Cannot establish browser process state; refusing changes") from exc
        profiles = []
        for i, arg in enumerate(args):
            if arg.startswith(b"--user-data-dir="):
                profiles.append(os.fsdecode(arg.split(b"=", 1)[1]))
            elif arg == b"--user-data-dir" and i + 1 < len(args):
                profiles.append(os.fsdecode(args[i + 1]))
        if not profiles:
            raise RuntimeError("Chromium profile metadata is ambiguous; refusing changes")
        for value in profiles:
            if not os.path.isabs(value):
                raise RuntimeError("Relative Chromium profile path; refusing changes")
            if os.path.realpath(value) == wanted:
                raise RuntimeError("Active Chromium uses this profile; refusing changes")


def snapshot(fd: int, name: str) -> tuple[int, int, int] | None:
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISLNK(info.st_mode) or info.st_uid != EXPECTED_UID:
        raise RuntimeError(f"{name}: unexpected type or owner")
    if info.st_mtime_ns != EXPECTED_MTIMES[name]:
        raise RuntimeError(f"{name}: metadata changed; obtain a fresh owner review")
    if name == "SingletonLock" and os.readlink(name, dir_fd=fd) != EXPECTED_LOCK:
        raise RuntimeError("Unexpected lock target; no repair applies to another owner")
    return info.st_dev, info.st_ino, info.st_mtime_ns


def move_link(src: int, dst: int, name: str, expected: tuple[int, int, int] | None) -> None:
    if expected is None or snapshot(src, name) != expected:
        raise RuntimeError(f"{name}: source changed before move")
    platform_compat.rename_noreplace(name, name, src_dir_fd=src, dst_dir_fd=dst)
    if snapshot(dst, name) != expected:
        raise RuntimeError(f"{name}: moved entry changed; backup retained, stop for review")
    try:
        os.stat(name, dir_fd=src, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise RuntimeError(f"{name}: new source entry appeared; leave it untouched and stop")


def check_directory(fd: int, *, private: bool = False) -> None:
    info = os.fstat(fd)
    mode = stat.S_IMODE(info.st_mode)
    if info.st_uid != EXPECTED_UID or mode & 0o022 or (private and mode != 0o700):
        raise RuntimeError("Unexpected directory owner or permissions")


def repair(
    profile: Path, proc: Path, mode: str = "check", backup: Path | None = None
) -> Path | None:
    if mode not in {"check", "apply", "undo"}:
        raise ValueError("Unknown repair mode")
    no_active_browser(profile, proc)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with contextlib.ExitStack() as stack:
        parent = stack.enter_context(open_directory(profile.parent))
        check_directory(parent)
        source = os.open(profile.name, flags, dir_fd=parent)
        stack.callback(os.close, source)
        check_directory(source)
        current = {name: snapshot(source, name) for name in NAMES}
        if mode == "undo":
            if backup is None:
                raise RuntimeError("Undo needs the exact backup printed by apply")
            backup = Path(os.path.abspath(backup))
            if backup.parent != profile.parent or not backup.name.startswith(BACKUP_PREFIX):
                raise RuntimeError("Backup must be a private sibling created by this procedure")
            destination = os.open(backup.name, flags, dir_fd=parent)
            stack.callback(os.close, destination)
            check_directory(destination, private=True)
            if set(os.listdir(destination)) - set(NAMES):
                raise RuntimeError("Unexpected backup entries; refusing undo")
            saved = {name: snapshot(destination, name) for name in NAMES}
            for name in NAMES:
                if (saved[name] is None) == (current[name] is None):
                    raise RuntimeError(
                        f"{name}: missing or conflicting entry; undo refuses overwrite"
                    )
            # Restore the stale lock first so launches stay blocked during undo.
            for name in NAMES:
                no_active_browser(profile, proc)
                if saved[name] is not None:
                    move_link(destination, source, name, saved[name])
            print("Undo complete; empty private backup retained")
            return backup
        if any(value is None for value in current.values()):
            raise RuntimeError("All three reviewed singleton symlinks must be present")
        if mode == "check":
            print("CHECK OK: host-reviewed singleton metadata; no files changed")
            return None
        no_active_browser(profile, proc)
        backup = profile.parent / (BACKUP_PREFIX + secrets.token_hex(12))
        os.mkdir(backup.name, mode=0o700, dir_fd=parent)
        destination = os.open(backup.name, flags, dir_fd=parent)
        stack.callback(os.close, destination)
        check_directory(destination, private=True)
        print(json.dumps({"backup": str(backup), "undo": ["--undo", str(backup)]}), flush=True)
        # Keep the stale lock until the socket/cookie links are safely backed up.
        for name in reversed(NAMES):
            no_active_browser(profile, proc)
            move_link(source, destination, name, current[name])
        no_active_browser(profile, proc)
        print("APPLY complete: three symlinks moved; no profile contents read")
        return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="metadata only; default")
    modes.add_argument("--apply", action="store_true", help="move the three reviewed links")
    modes.add_argument("--undo", type=Path, metavar="BACKUP")
    args = parser.parse_args(argv)
    try:
        if sys.platform != "linux":
            raise RuntimeError("This procedure requires an ordinary Linux owner terminal")
        guard_context(socket.gethostname(), os.getuid(), os.geteuid(), sys.platform, os.environ)
        mode = "undo" if args.undo else "apply" if args.apply else "check"
        repair(PROFILE, Path("/proc"), mode, args.undo)
    except (OSError, RuntimeError, ValueError, NotImplementedError) as exc:
        print(f"REFUSED/STOPPED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
