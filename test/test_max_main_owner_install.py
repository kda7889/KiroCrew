"""Owner deployment helper: fake service calls and temporary trees only."""

import importlib.util
import io
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="testserver helper is Linux-only")


@pytest.fixture
def helper():
    path = Path(__file__).parents[1] / "scripts/max_main_owner_install.py"
    spec = importlib.util.spec_from_file_location("max_main_owner_install", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sandbox_is_refused_before_owner_checks(helper, monkeypatch):
    monkeypatch.setenv("KIROCREW_SANDBOX_ACTIVE", "synthetic")
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    with pytest.raises(ValueError, match="owner terminal"):
        helper.check_operator()


def test_non_root_or_wrong_host_is_refused(helper, monkeypatch):
    monkeypatch.delenv("KIROCREW_SANDBOX_ACTIVE", raising=False)
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1002)
    with pytest.raises(ValueError):
        helper.check_operator()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(helper.socket, "gethostname", lambda: "another-host")
    with pytest.raises(ValueError):
        helper.check_operator()


def test_owner_terminal_is_required(helper, monkeypatch):
    monkeypatch.delenv("KIROCREW_SANDBOX_ACTIVE", raising=False)
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setattr(helper.socket, "gethostname", lambda: "testserver")
    monkeypatch.setattr(
        helper.pwd, "getpwnam", lambda name: SimpleNamespace(pw_uid=1002, pw_dir=str(helper.HOME))
    )
    monkeypatch.setattr(helper.os, "isatty", lambda fd: False)
    with pytest.raises(ValueError, match="interactive"):
        helper.check_operator()
    monkeypatch.setattr(helper.os, "isatty", lambda fd: True)
    helper.check_operator()


def test_tree_guard_rejects_external_mutable_state_link(helper, tmp_path):
    home = tmp_path / "crew"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "history").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="external"):
        helper.inspect_tree(home, state=True)


def test_archive_covers_hidden_files_and_keeps_symlinks(helper, tmp_path, monkeypatch):
    home = tmp_path / "crew"
    home.mkdir()
    (home / ".hidden").write_bytes(b"synthetic state")
    (home / "linked").symlink_to(".hidden")
    archive = tmp_path / "state.tar"
    monkeypatch.chdir(home)
    with socket.socket(socket.AF_UNIX) as endpoint:
        endpoint.bind("socket")
        helper.archive_tree(home, archive)
    (home / ".hidden").write_bytes(b"new state")
    saved = tmp_path / "failed-state"
    helper.restore_tree(home, archive, saved)
    assert (home / ".hidden").read_bytes() == b"synthetic state"
    assert (home / "linked").is_symlink()
    assert (saved / ".hidden").read_bytes() == b"new state"


def test_restore_never_overwrites_retained_failed_state(helper, tmp_path):
    home = tmp_path / "crew"
    home.mkdir()
    saved = tmp_path / "failed"
    saved.mkdir()
    with pytest.raises(FileExistsError):
        helper.restore_tree(home, tmp_path / "unused.tar", saved)
    assert home.is_dir()


def test_changed_archive_is_refused(helper, tmp_path):
    archive = tmp_path / "state.tar"
    archive.write_bytes(b"synthetic")
    digest = helper.digest(archive)
    archive.write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest"):
        helper.verify_digest(archive, digest)


def test_only_scalar_systemd_properties_are_requested(helper, monkeypatch):
    seen = []

    def capture(args, **kwargs):
        seen.append(args)
        return b"ActiveState=inactive\nMainPID=0\n"

    monkeypatch.setattr(helper.subprocess, "check_output", capture)
    assert helper.service_info()["MainPID"] == "0"
    assert "status" not in seen[0]
    assert "Environment" not in " ".join(seen[0])


def test_rollback_stops_before_restoring_and_starts_last(helper, monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(helper, "validate_backup", lambda p: events.append("verify"))
    monkeypatch.setattr(helper, "stop_service", lambda: events.append("stop"))
    monkeypatch.setattr(helper, "restore_tree", lambda *a: events.append(str(a[0])))
    monkeypatch.setattr(helper, "remove_dropin", lambda: events.append("dropin"))
    monkeypatch.setattr(helper, "run", lambda args: events.append(args[-2]))
    monkeypatch.setattr(helper, "wait_health", lambda version: events.append(version))
    helper.rollback(tmp_path)
    assert events[:2] == ["verify", "stop"]
    assert events[-2:] == ["start", "0.13.1"]


def test_failed_stop_never_restores_state(helper, monkeypatch, tmp_path):
    monkeypatch.setattr(helper, "validate_backup", lambda p: None)

    def refuse():
        raise ValueError("not idle")

    monkeypatch.setattr(helper, "stop_service", refuse)
    monkeypatch.setattr(helper, "restore_tree", lambda *a: pytest.fail("restore while live"))
    with pytest.raises(ValueError, match="idle"):
        helper.rollback(tmp_path)


def test_repeated_undo_refuses_before_stopping(helper, monkeypatch, tmp_path):
    (tmp_path / "failed-state").mkdir()
    monkeypatch.setattr(helper, "validate_backup", lambda p: None)
    monkeypatch.setattr(helper, "stop_service", lambda: pytest.fail("repeat undo stopped service"))
    with pytest.raises(ValueError, match="already attempted"):
        helper.rollback(tmp_path)


def test_foreign_service_is_rejected(helper):
    with pytest.raises(ValueError, match="reviewed"):
        helper.check_service({"FragmentPath": "/elsewhere/kirocrew.service", "User": "root"})


def test_stop_refuses_a_service_that_is_still_active(helper, monkeypatch):
    events = []
    monkeypatch.setattr(helper, "check_service", lambda info: None)
    monkeypatch.setattr(helper, "service_info", lambda: {"ActiveState": "active", "MainPID": "1"})
    monkeypatch.setattr(helper, "run", lambda args: events.append(args[-2]))
    with pytest.raises(ValueError, match="idle"):
        helper.stop_service()
    assert events == ["stop"]


def test_health_requires_ready_and_serving_service(helper, monkeypatch):
    responses = iter(
        [
            {"ok": True, "version": "0.14.0"},
            {"ready": False},
            {"ok": True, "version": "0.14.0"},
            {"ready": True},
        ]
    )

    class Opener:
        def open(self, url, timeout):
            assert url.startswith("http://127.0.0.1:5477/api/")
            return io.BytesIO(json.dumps(next(responses)).encode())

    clock = iter([0, 1, 2])
    sleeps = []
    monkeypatch.setattr(helper.urllib.request, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(
        helper, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=sleeps.append)
    )
    monkeypatch.setattr(helper, "service_info", lambda: {"ActiveState": "active"})
    helper.wait_health("0.14.0")
    assert sleeps == [1]


def test_health_timeout_is_bounded(helper, monkeypatch):
    clock = iter([0, 121])
    monkeypatch.setattr(helper, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(helper.urllib.request, "build_opener", lambda *a: object())
    with pytest.raises(ValueError, match="health/version"):
        helper.wait_health("0.14.0")


def test_install_keeps_dependencies_and_configures_only_max(helper, monkeypatch):
    seen = []
    monkeypatch.setattr(helper, "verify_digest", lambda *a: None)
    monkeypatch.setattr(helper, "run", lambda args: seen.append(args))
    helper.install_package()
    install = next(args for args in seen if "install" in args)
    assert "--offline" in install and "--no-deps" in install
    assert str(helper.WHEEL) in install
    configs = [args[-2:] for args in seen if "config" in args]
    assert configs == [
        ["max.delivery_mode", "polling"],
        ["max.allowed_user_ids", "[]"],
        ["max.enabled", "true"],
    ]


def test_dropin_never_clobbers_an_existing_file(helper, monkeypatch, tmp_path):
    target = tmp_path / "max.conf"
    target.write_bytes(b"existing")
    monkeypatch.setattr(helper, "DROPIN", target)
    with pytest.raises(FileExistsError):
        helper.write_dropin()
    assert target.read_bytes() == b"existing"


def test_undo_refuses_a_changed_dropin(helper, monkeypatch, tmp_path):
    target = tmp_path / "max.conf"
    target.write_bytes(b"outside change")
    monkeypatch.setattr(helper, "DROPIN", target)
    with pytest.raises(ValueError, match="drop-in"):
        helper.remove_dropin()
    assert target.read_bytes() == b"outside change"


@pytest.fixture
def prepared_apply(helper, monkeypatch, tmp_path):
    state = tmp_path / "crew"
    runtime = tmp_path / "runtime"
    base = tmp_path / "backups"
    for path in (state, runtime, base):
        path.mkdir()
    current = tmp_path / "current"
    current.symlink_to(runtime, target_is_directory=True)
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"synthetic wheel")
    for key, value in (
        ("STATE", state),
        ("OWNER_UID", state.stat().st_uid),
        ("RUNTIME", runtime),
        ("CURRENT", current),
        ("BASE", base),
        ("WHEEL", wheel),
        ("WHEEL_SHA", helper.digest(wheel)),
        ("DROPIN", tmp_path / "max.conf"),
    ):
        monkeypatch.setattr(helper, key, value)
    info = {"ActiveState": "active", "SubState": "running", "MainPID": "123"}
    monkeypatch.setattr(helper, "service_info", lambda: info)
    monkeypatch.setattr(helper, "check_service", lambda i: None)
    monkeypatch.setattr(helper, "wait_health", lambda v: None)
    monkeypatch.setattr(helper, "validate_backup", lambda p: None)
    monkeypatch.setattr(helper, "require_idle", lambda: None)
    events = []
    monkeypatch.setattr(helper, "stop_service", lambda: events.append("stop"))
    monkeypatch.setattr(helper, "run", lambda args: events.append(args[-2]))

    def archive(root, output):
        events.append(root.name)
        output.write_bytes(b"synthetic archive")

    monkeypatch.setattr(helper, "archive_tree", archive)
    monkeypatch.setattr(helper, "rollback", lambda p: events.append("rollback"))
    return helper, events


def test_failed_backup_restarts_old_service_without_mutation(prepared_apply, monkeypatch):
    helper, events = prepared_apply

    def fail(*args):
        raise ValueError("backup failure")

    monkeypatch.setattr(helper, "archive_tree", fail)
    monkeypatch.setattr(helper, "install_package", lambda: pytest.fail("install without backup"))
    with pytest.raises(ValueError, match="backup failure"):
        helper.apply()
    assert events == ["stop", "start"]


def test_failed_install_rolls_back_after_both_archives(prepared_apply, monkeypatch):
    helper, events = prepared_apply

    def fail():
        events.append("install")
        raise ValueError("install failure")

    monkeypatch.setattr(helper, "install_package", fail)
    with pytest.raises(ValueError, match="install failure"):
        helper.apply()
    assert events == ["stop", "crew", "runtime", "install", "rollback"]


def test_success_backs_up_before_install_and_starts_once(prepared_apply, monkeypatch):
    helper, events = prepared_apply
    monkeypatch.setattr(helper, "install_package", lambda: events.append("install"))
    monkeypatch.setattr(helper, "write_dropin", lambda: events.append("dropin"))
    helper.apply()
    assert events == ["stop", "crew", "runtime", "install", "dropin", helper.SYSTEMCTL, "start"]


def test_timeout_kills_only_the_helpers_own_process_group(helper, monkeypatch):
    waits = []
    killed = []

    class Child:
        pid = 12345

        def wait(self, timeout):
            waits.append(timeout)
            if len(waits) == 1:
                raise helper.subprocess.TimeoutExpired(["synthetic"], timeout)
            return 0

    def start(args, **kwargs):
        assert kwargs["start_new_session"] is True
        assert kwargs["stdin"] == helper.subprocess.DEVNULL
        return Child()

    monkeypatch.setattr(helper.subprocess, "Popen", start)
    monkeypatch.setattr(helper.os, "killpg", lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(helper.subprocess.TimeoutExpired):
        helper.run(["synthetic"])
    assert waits == [1800, 15]
    assert killed == [(12345, helper.signal.SIGKILL)]


def test_unreaped_child_blocks_recovery(prepared_apply, monkeypatch):
    helper, events = prepared_apply

    def fail():
        events.append("install")
        raise helper.ChildStillRunning("synthetic child still running")

    monkeypatch.setattr(helper, "install_package", fail)
    with pytest.raises(helper.ChildStillRunning):
        helper.apply()
    assert events == ["stop", "crew", "runtime", "install"]


def test_unreaped_child_raises_a_distinct_recovery_refusal(helper, monkeypatch):
    class Child:
        pid = 12345

        def wait(self, timeout):
            raise helper.subprocess.TimeoutExpired(["synthetic"], timeout)

    monkeypatch.setattr(helper.subprocess, "Popen", lambda *a, **k: Child())
    monkeypatch.setattr(helper.os, "killpg", lambda *a: None)
    with pytest.raises(helper.ChildStillRunning, match="not reaped"):
        helper.run(["synthetic"])
