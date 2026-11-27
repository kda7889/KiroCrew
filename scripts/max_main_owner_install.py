"""Pinned main deployment, executed only by the host owner, never by an agent."""

import argparse
import fcntl
import hashlib
import json
import os
import pwd
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

HOME = Path("/home/adminuser")
OWNER_UID = 1002
STATE = HOME / ".kiro/crew"
RUNTIME = HOME / ".kiro/crew-venv-0.13.1"
CURRENT = HOME / ".kiro/crew-venv-current"
WHEEL = (
    STATE
    / "workspace-member-codex-dev/_only_local/max-main-compatible"
    / "kirocrew-0.14.0-py3-none-any.whl"
)
WHEEL_SHA = "1a55ffb83739890fbb514fc349b3049cef4044c9cd13ba7b0bc6cc4ed9054d62"
BASE = Path("/var/backups/kirocrew-max")
UNIT = "kirocrew.service"
SYSTEMCTL = "/usr/bin/systemctl"
DROPIN = Path("/etc/systemd/system/kirocrew.service.d/90-max-channel.conf")
DROPIN_BYTES = b'[Service]\nEnvironment="MAX_BOT_TOKEN=secret://bot_max_kda"\n'
LOG = None
STATUS_DIR = STATE / "workspace-member-codex-dev/_only_local/max-main-status"
STATUS = None
STATUS_FORMAT = "max-main-status-v1"
STATUS_LIMIT = 65536
STATUS_EVENTS = 64


def open_status_directory():
    """Pin every user-controlled path component; never follow a root-write link."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(HOME, flags)
    created = False
    try:
        parts = STATUS_DIR.relative_to(HOME).parts
        for index, part in enumerate(parts):
            info = os.fstat(fd)
            if info.st_uid not in (0, OWNER_UID) or info.st_mode & 0o002:
                raise ValueError("unsafe status parent directory")
            if index == len(parts) - 1:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=fd)
                    created = True
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or (not created and stat.S_IMODE(info.st_mode) != 0o755):
            raise ValueError("unsafe status directory ownership or permissions")
        os.fchmod(fd, 0o755)
        return fd
    except BaseException:
        os.close(fd)
        raise


class StatusLog:
    """A bounded diagnostic snapshot, never raw exception or subprocess output."""

    def __init__(self):
        self.events = []
        self.stage = "preflight"
        self.deferred = 0
        self.private_log = None

    def write(self):
        if self.deferred:
            return
        payload = json.dumps(
            {"format": STATUS_FORMAT, "private_log": self.private_log, "events": self.events},
            separators=(",", ":"),
        ).encode()
        if len(payload) > STATUS_LIMIT:
            raise ValueError("status diagnostic exceeds its size limit")
        directory = open_status_directory()
        fd = None
        try:
            flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
            try:
                fd = os.open("status.json", flags | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=directory)
            except FileExistsError:
                fd = os.open("status.json", flags, dir_fd=directory)
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_nlink != 1
                or info.st_size > STATUS_LIMIT
            ):
                raise ValueError("unsafe status file ownership, links or type")
            prefix = os.read(fd, 64)
            expected = ('{"format":"' + STATUS_FORMAT + '"').encode()
            if info.st_size and not prefix.startswith(expected):
                raise ValueError("refuse to overwrite an unrelated status file")
            os.fchmod(fd, 0o644)
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(fd)
        finally:
            if fd is not None:
                os.close(fd)
            os.close(directory)

    def flush(self):
        try:
            self.write()
        except (OSError, ValueError):
            # Diagnostics must never prevent an already-required service recovery.
            print("Readable status unavailable; owner must consult the private recovery log.")


def status_event(event, *, stage=None, error=None, returncode=None, private_log=None, numbers=None):
    if STATUS is None:
        return
    if stage is not None:
        STATUS.stage = stage
    record = {"event": event, "stage": STATUS.stage, "time": int(time.time())}
    if error is not None:
        record["error_type"] = type(error).__name__
        if isinstance(error, OSError) and isinstance(error.errno, int):
            record["errno"] = error.errno
        if isinstance(error, subprocess.CalledProcessError):
            record["returncode"] = error.returncode
        trace = error.__traceback__
        while trace is not None:
            if trace.tb_frame.f_code.co_filename == __file__:
                record["function"] = trace.tb_frame.f_code.co_name
                record["line"] = trace.tb_lineno
            trace = trace.tb_next
        # Only these fixed messages may cross into the readable log.
        safe = {
            "artifact digest mismatch",
            "MAX deployment drop-in already exists",
            "service differs from the reviewed system unit",
            "runtime/data paths differ from the reviewed main install",
            "runtime/data ownership differs from adminuser UID1002",
            "expected the current system service to be active",
            "external mutable state is outside backup coverage",
            "nested mount is outside backup coverage",
            "unsupported special file in state",
            "backup and restored trees must share a filesystem for retained renames",
            "backup root must be root-owned mode 0700, not a symlink",
            "backup root must be a real directory",
        }
        record["reason"] = (
            str(error) if type(error) is ValueError and str(error) in safe else "text withheld"
        )
    if returncode is not None:
        record["returncode"] = int(returncode)
    if private_log is not None:
        STATUS.private_log = str(private_log)
    if numbers is not None:
        record["bytes"] = {key: int(value) for key, value in numbers.items()}
    STATUS.events.append(record)
    STATUS.events = STATUS.events[-STATUS_EVENTS:]
    STATUS.flush()


@contextmanager
def defer_status():
    logger = STATUS
    if logger is not None:
        logger.deferred += 1
    try:
        yield
    finally:
        if logger is not None:
            logger.deferred -= 1
            logger.flush()


class ChildStillRunning(RuntimeError):
    """Recovery must wait for the helper's own installer to leave the tree."""


def check_operator():
    if os.environ.get("KIROCREW_SANDBOX_ACTIVE"):
        raise ValueError("use an ordinary owner terminal; never clear the sandbox marker")
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "testserver":
        raise ValueError("requires the host owner through sudo on testserver")
    owner = pwd.getpwnam("adminuser")
    if owner.pw_uid != OWNER_UID or owner.pw_dir != str(HOME):
        raise ValueError("adminuser identity differs from the reviewed UID/home")
    if not (os.isatty(0) and os.isatty(1)):
        raise ValueError("requires an interactive owner terminal")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_digest(path, expected):
    if path.is_symlink() or not path.is_file() or digest(path) != expected:
        raise ValueError("artifact digest mismatch")


def run(args):
    status_event("subprocess_start")
    child = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=LOG,
        stderr=LOG,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"},
        start_new_session=True,
    )
    try:
        result = child.wait(timeout=1800)
        status_event("subprocess_exit", returncode=result)
        if result:
            raise subprocess.CalledProcessError(result, args)
    except BaseException:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired as exc:
            raise ChildStillRunning(
                "helper child not reaped; keep the system service stopped"
            ) from exc
        raise


def service_info():
    raw = subprocess.check_output(
        [
            SYSTEMCTL,
            "show",
            UNIT,
            "--no-pager",
            "--property=" "ActiveState,SubState,MainPID,FragmentPath,User,ExecStart,ControlGroup",
        ],
        timeout=15,
    )
    if len(raw) > 8192:
        raise ValueError("unexpected service metadata size")
    return dict(line.split("=", 1) for line in raw.decode().splitlines() if "=" in line)


def check_service(info):
    expected = f"argv[]={CURRENT}/bin/kirocrew gateway --no-open ;"
    if (
        info.get("FragmentPath") != "/etc/systemd/system/kirocrew.service"
        or info.get("User") != "adminuser"
        or expected not in info.get("ExecStart", "")
        or info.get("ControlGroup", "") not in ("", "/system.slice/kirocrew.service")
    ):
        raise ValueError("service differs from the reviewed system unit")


def stop_service():
    check_service(service_info())
    run([SYSTEMCTL, "stop", UNIT])
    require_idle()


def require_idle():
    info = service_info()
    check_service(info)
    if info.get("ActiveState") != "inactive" or info.get("MainPID") != "0":
        raise ValueError("system service is not idle")
    events = Path("/sys/fs/cgroup/system.slice/kirocrew.service/cgroup.events")
    if events.exists() and "populated 0" not in events.read_text():
        raise ValueError("service cgroup still contains processes")
    try:
        with socket.create_connection(("127.0.0.1", 5477), timeout=1):
            raise ValueError("port 5477 is still occupied; no installation attempted")
    except ConnectionRefusedError:
        pass


def inspect_tree(root, *, state=False):
    """Count opaque backup bytes; do not follow links or cross mount boundaries."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("backup root must be a real directory")
    device = root.stat().st_dev
    mutable = {
        "config.json",
        "config.local.json",
        "memory_stores",
        "history",
        "sessions",
        "conversations",
        "workspace",
        "apps",
        "agents",
    }
    size = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                relative = path.relative_to(root)
                if state and relative.parts[0] in mutable:
                    if not path.resolve().is_relative_to(root.resolve()):
                        raise ValueError("external mutable state is outside backup coverage")
            elif info.st_dev != device:
                raise ValueError("nested mount is outside backup coverage")
            elif stat.S_ISREG(info.st_mode):
                size += info.st_size
            elif not (stat.S_ISDIR(info.st_mode) or stat.S_ISSOCK(info.st_mode)):
                raise ValueError("unsupported special file in state")
    return size


def space_report():
    """Owner metadata only: preserve the full backup and retained-restore budget."""
    state_size = inspect_tree(STATE, state=True)
    runtime_size = inspect_tree(RUNTIME)
    size = state_size + runtime_size
    fs = os.statvfs(BASE.parent)
    available = fs.f_bavail * fs.f_frsize
    required = 2 * size + 512 * 1024 * 1024
    return {
        "state_bytes": state_size,
        "runtime_bytes": runtime_size,
        "source_bytes": size,
        "available_bytes": available,
        "reserved_bytes": max(0, fs.f_bfree - fs.f_bavail) * fs.f_frsize,
        "required_bytes": required,
        "shortfall_bytes": max(0, required - available),
        "restore_floor_bytes": size + 512 * 1024 * 1024,
    }


def require_space():
    report = space_report()
    status_event("space", numbers=report)
    if report["shortfall_bytes"]:
        raise ValueError(
            "insufficient space for verified backup and retained rollback state: "
            + ", ".join(f"{key}={value}" for key, value in report.items())
        )


@defer_status()
def archive_tree(root, archive):
    run(
        [
            "/usr/bin/tar",
            "--create",
            "--file",
            str(archive),
            "--one-file-system",
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--numeric-owner",
            "--directory",
            str(root.parent),
            root.name,
        ]
    )
    run(
        [
            "/usr/bin/tar",
            "--compare",
            "--file",
            str(archive),
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--directory",
            str(root.parent),
        ]
    )


@defer_status()
def restore_tree(root, archive, saved):
    if saved.exists() or saved.is_symlink():
        raise FileExistsError("retained failed state already exists")
    if root.exists() or root.is_symlink():
        root.rename(saved)
    run(
        [
            "/usr/bin/tar",
            "--extract",
            "--file",
            str(archive),
            "--acls",
            "--xattrs",
            "--xattrs-include=*",
            "--numeric-owner",
            "--same-owner",
            "--directory",
            str(root.parent),
        ]
    )


def write_dropin():
    DROPIN.parent.mkdir(mode=0o755, exist_ok=True)
    with DROPIN.open("xb") as stream:
        stream.write(DROPIN_BYTES)


def remove_dropin():
    if DROPIN.is_symlink() or (DROPIN.exists() and DROPIN.read_bytes() != DROPIN_BYTES):
        raise ValueError("drop-in was changed outside this deployment; refuse overwrite")
    if DROPIN.exists():
        DROPIN.unlink()


def install_package():
    verify_digest(WHEEL, WHEEL_SHA)
    owner = ["/usr/sbin/runuser", "-u", "adminuser", "--"]
    run(
        owner
        + [
            str(HOME / ".local/bin/uv"),
            "pip",
            "install",
            "--offline",
            "--no-deps",
            "--reinstall-package",
            "kirocrew",
            "--python",
            str(RUNTIME / "bin/python"),
            str(WHEEL),
        ]
    )
    run(
        owner
        + [str(HOME / ".local/bin/uv"), "pip", "check", "--python", str(RUNTIME / "bin/python")]
    )
    for key, value in (
        ("max.delivery_mode", "polling"),
        ("max.allowed_user_ids", "[]"),
        ("max.enabled", "true"),
    ):
        run(owner + [str(RUNTIME / "bin/kirocrew"), "config", "set", key, value])


def wait_health(version):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with opener.open("http://127.0.0.1:5477/api/health", timeout=2) as response:
                payload = json.loads(response.read(8192))
                if payload.get("ok") and payload.get("version") == version:
                    with opener.open("http://127.0.0.1:5477/api/ready", timeout=2) as ready:
                        if json.loads(ready.read(8192)).get("ready") is True:
                            if service_info().get("ActiveState") == "active":
                                return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise ValueError("main health/version did not become ready")


def validate_backup(backup):
    if CURRENT.resolve() != RUNTIME or STATE.is_symlink() or RUNTIME.is_symlink():
        raise ValueError("deployment target changed; refuse recovery over another install")
    if backup.is_symlink() or backup.parent != BASE or backup.stat().st_uid != 0:
        raise ValueError("backup must be a root-owned child of the private backup directory")
    if stat.S_IMODE(backup.stat().st_mode) != 0o700:
        raise ValueError("backup directory must be mode 0700")
    manifest = json.loads((backup / "manifest.json").read_text())
    if manifest.get("wheel_sha256") != WHEEL_SHA:
        raise ValueError("backup belongs to another deployment")
    for name in ("state.tar", "runtime.tar"):
        verify_digest(backup / name, manifest[name])
    required = sum((backup / name).stat().st_size for name in ("state.tar", "runtime.tar"))
    if shutil.disk_usage(BASE).free < required + 512 * 1024 * 1024:
        raise ValueError("insufficient space to restore without deleting retained state")
    if DROPIN.is_symlink() or (DROPIN.exists() and DROPIN.read_bytes() != DROPIN_BYTES):
        raise ValueError("drop-in changed; refusing rollback over another owner's edit")


def rollback(backup):
    status_event("stage", stage="rollback_validate")
    validate_backup(backup)
    if any((backup / name).exists() for name in ("failed-state", "failed-runtime")):
        raise ValueError("recovery was already attempted; retained state must not be overwritten")
    stop_service()
    status_event("stage", stage="rollback_state")
    restore_tree(STATE, backup / "state.tar", backup / "failed-state")
    status_event("stage", stage="rollback_runtime")
    restore_tree(RUNTIME, backup / "runtime.tar", backup / "failed-runtime")
    remove_dropin()
    run([SYSTEMCTL, "daemon-reload"])
    run([SYSTEMCTL, "start", UNIT])
    wait_health("0.13.1")
    status_event("recovery_complete", stage="rollback_ready")


def apply():
    status_event("stage", stage="artifact_check")
    verify_digest(WHEEL, WHEEL_SHA)
    if CURRENT.resolve() != RUNTIME or RUNTIME.is_symlink() or STATE.is_symlink():
        raise ValueError("runtime/data paths differ from the reviewed main install")
    if STATE.stat().st_uid != OWNER_UID or RUNTIME.stat().st_uid != OWNER_UID:
        raise ValueError("runtime/data ownership differs from adminuser UID1002")
    if DROPIN.exists() or DROPIN.is_symlink():
        raise FileExistsError("MAX deployment drop-in already exists")
    status_event("stage", stage="service_check")
    info = service_info()
    check_service(info)
    if (
        info.get("ActiveState") != "active"
        or info.get("SubState") != "running"
        or not info.get("MainPID", "").isdigit()
        or int(info["MainPID"]) == 0
    ):
        raise ValueError("expected the current system service to be active")
    status_event("stage", stage="baseline_ready")
    wait_health("0.13.1")
    if BASE.stat().st_dev != STATE.stat().st_dev or BASE.stat().st_dev != RUNTIME.stat().st_dev:
        raise ValueError("backup and restored trees must share a filesystem for retained renames")
    status_event("stage", stage="space_check")
    require_space()
    backup = Path(tempfile.mkdtemp(prefix="main-", dir=BASE))
    global LOG
    with (backup / "operations.log").open("xb") as LOG:
        status_event("private_log", private_log=backup / "operations.log")
        stopped = False
        mutated = False
        try:
            status_event("stage", stage="stop_service")
            stop_service()
            stopped = True
            require_space()
            status_event("stage", stage="archive_state")
            archive_tree(STATE, backup / "state.tar")
            status_event("stage", stage="archive_runtime")
            archive_tree(RUNTIME, backup / "runtime.tar")
            manifest = {name: digest(backup / name) for name in ("state.tar", "runtime.tar")}
            manifest["wheel_sha256"] = WHEEL_SHA
            with (backup / "manifest.json").open("x") as stream:
                json.dump(manifest, stream)
            status_event("stage", stage="backup_validate")
            validate_backup(backup)
            require_idle()
            mutated = True
            status_event("stage", stage="install_package")
            install_package()
            status_event("stage", stage="write_dropin")
            write_dropin()
            status_event("stage", stage="start_service")
            run([SYSTEMCTL, "daemon-reload"])
            run([SYSTEMCTL, "start", UNIT])
            status_event("stage", stage="candidate_ready")
            wait_health("0.14.0")
        except BaseException as exc:
            status_event("apply_error", error=exc)
            print(f"Private recovery files: {backup}")
            if isinstance(exc, ChildStillRunning):
                raise
            if mutated:
                rollback(backup)
                print("Restored the pre-deployment package and data; failed state was retained.")
            elif stopped:
                run([SYSTEMCTL, "start", UNIT])
            raise
    LOG = None
    print("Main 0.14.0 health passed. Pair owner and actual MAX /help remain unverified.")
    print(f"Undo: sudo /usr/bin/python3 -I {Path(__file__).resolve()} --undo {backup}")


def main():
    check_operator()
    if not sys.flags.isolated:
        raise ValueError("run the owner command with python3 -I")
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--undo", type=Path)
    mode.add_argument("--space-report", action="store_true")
    args = parser.parse_args()
    if args.space_report:
        print(json.dumps(space_report(), indent=2))
        return
    global STATUS
    STATUS = StatusLog()
    try:
        STATUS.write()
        status_event("start")
        owner_operation(args)
        status_event("success")
    except BaseException as exc:
        status_event("error", error=exc)
        raise
    finally:
        STATUS = None


def owner_operation(args):
    status_event("stage", stage="private_backup_root")
    os.umask(0o077)
    BASE.mkdir(mode=0o700, exist_ok=True)
    if BASE.is_symlink() or BASE.stat().st_uid != 0 or stat.S_IMODE(BASE.stat().st_mode) != 0o700:
        raise ValueError("backup root must be root-owned mode 0700, not a symlink")
    with (BASE / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.undo:
            rollback(args.undo)
        else:
            apply()


if __name__ == "__main__":
    main()
