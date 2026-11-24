"""Owner trial preparation: synthetic paths only, no product/receiver execution."""

import importlib.util
import socket
from pathlib import Path

import pytest


@pytest.fixture
def runtime_helper():
    path = Path(__file__).parents[1] / "scripts" / "max_trial_runtime.py"
    spec = importlib.util.spec_from_file_location("max_trial_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_env_keeps_validated_user_bus_and_short_default_home(runtime_helper):
    env = runtime_helper.trial_env(
        Path("/home/test/.max-trial"), Path("/run/user/123"), Path("/task/env")
    )
    assert env["HOME"] == "/home/test/.max-trial"
    assert env["XDG_RUNTIME_DIR"] == "/run/user/123"
    assert env["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/run/user/123/bus"
    assert "KIROCREW_HOME" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert len((env["HOME"] + "/.kiro/crew/kirocrew-mcp-gateway.sock").encode()) < 108


def test_runtime_requires_private_same_owner_directory(runtime_helper, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    uid = runtime.stat().st_uid
    runtime_helper.private_directory(runtime, uid)
    with pytest.raises(ValueError):
        runtime_helper.private_directory(runtime, uid + 1)
    runtime.chmod(0o755)
    with pytest.raises(ValueError):
        runtime_helper.private_directory(runtime, uid)


def test_runtime_rejects_symlink(runtime_helper, tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        runtime_helper.private_directory(alias, target.stat().st_uid)


def test_owned_bus(runtime_helper, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    uid = runtime.stat().st_uid
    with pytest.raises((ValueError, FileNotFoundError)):
        runtime_helper.validate_runtime(runtime, uid)
    with socket.socket(socket.AF_UNIX) as bus:
        bus.bind(str(runtime / "bus"))
        runtime_helper.validate_runtime(runtime, uid)
    (runtime / "bus").unlink()
    (runtime / "bus").write_text("not a socket")
    with pytest.raises(ValueError):
        runtime_helper.validate_runtime(runtime, uid)


def test_sandbox_guard_precedes_all_runtime_actions(runtime_helper, monkeypatch):
    monkeypatch.setenv("KIROCREW_SANDBOX_ACTIVE", "synthetic")
    with pytest.raises(ValueError, match="ordinary owner terminal"):
        runtime_helper.main()
