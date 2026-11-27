"""Owner-only trial launcher; no product imports, credential copies or policy edits."""

import os
import socket
import stat
import subprocess
import sys
from pathlib import Path


def private_directory(path: Path, uid: int) -> None:
    for component in (path, *path.parents):
        if stat.S_ISLNK(component.lstat().st_mode):
            raise ValueError("symlink in trial/runtime path")
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("trial/runtime directory must be same-owner mode 0700")


def validate_runtime(path: Path, uid: int) -> None:
    private_directory(path, uid)
    bus = (path / "bus").lstat()
    if not stat.S_ISSOCK(bus.st_mode) or bus.st_uid != uid:
        raise ValueError("user bus must be a same-owner socket, not a symlink")


def trial_env(home: Path, runtime: Path, taskenv: Path) -> dict[str, str]:
    return {
        "PATH": f"{taskenv}/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "KIRO_HOME": str(home / ".kiro"),
        # Default .kiro/crew under the fresh HOME avoids a reserved spec env pin.
        "KIROCREW_BIND": "127.0.0.1",
        "KIROCREW_WORKSPACE": str(home / "workspace"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus",
        "LANG": "C.UTF-8",
        "TERM": "xterm",
        "MAX_BOT_TOKEN": "secret://bot_max_kda",
        "MAX_WEBHOOK_SECRET": "secret://max-webhook",
    }


def main() -> None:
    if os.environ.get("KIROCREW_SANDBOX_ACTIVE"):
        raise ValueError("use an ordinary owner terminal; never clear the sandbox marker")
    if (
        socket.gethostname().split(".")[0] != "testserver"
        or os.getuid() != 1002
        or os.geteuid() != 1002
    ):
        raise ValueError("this prepared trial requires adminuser UID 1002 on testserver")
    runtime = Path("/run/user/1002")
    validate_runtime(runtime, 1002)
    controllers = (
        Path("/sys/fs/cgroup/user.slice/user-1002.slice/cgroup.controllers").read_text().split()
    )
    if not {"pids", "memory"}.issubset(controllers):
        raise ValueError(
            "user slice lacks delegated memory/pids controllers; stop before engine launch"
        )
    home = Path("/home/adminuser/.max-trial-11249e86")
    taskenv = Path(__file__).resolve().parents[2] / "max-source-test-env"
    env = trial_env(home, runtime, taskenv)
    # Read-only manager check: a socket file alone does not prove a live user bus.
    subprocess.run(
        ["/usr/bin/systemctl", "--user", "is-active", "default.target"],
        env=env,
        check=True,
        timeout=10,
        stdout=subprocess.DEVNULL,
    )
    try:
        home.mkdir(mode=0o700)
    except FileExistsError:
        pass
    private_directory(home, 1002)
    cli = str(taskenv / "bin/kirocrew")
    config = home / ".kiro/crew/config.json"
    if not config.exists():
        subprocess.run(
            [cli, "config", "set", "dashboard.url", "http://localhost:55476"],
            env=env,
            cwd=home,
            check=True,
        )
    args = sys.argv[1:] or [
        "gateway",
        "--no-open",
        "--no-tunnel",
        "--no-crons",
        "--port",
        "55476",
        "--approval",
        "interactive",
    ]
    os.chdir(home)
    os.execve(cli, [cli, *args], env)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Trial preflight refused: {exc}", file=sys.stderr)
        sys.exit(1)
