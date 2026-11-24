"""Owner repair uses only synthetic singleton links and process metadata."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux owner procedure")


@pytest.fixture
def repair_module():
    path = Path(__file__).parents[1] / "scripts" / "max_singleton_owner_repair.py"
    spec = importlib.util.spec_from_file_location("max_singleton_owner_repair", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synthetic(repair_module, tmp_path, monkeypatch):
    module = repair_module
    monkeypatch.setattr(module, "EXPECTED_UID", os.getuid())
    profile = tmp_path / "browser-profile"
    profile.mkdir(mode=0o700)
    proc = tmp_path / "proc"
    proc.mkdir()
    for name, stamp in module.EXPECTED_MTIMES.items():
        link = profile / name
        link.symlink_to(module.EXPECTED_LOCK if name == "SingletonLock" else "unread-target")
        os.utime(link, ns=(stamp, stamp), follow_symlinks=False)
    (profile / "profile-sentinel").write_text("untouched", encoding="utf-8")
    return module, profile, proc


@pytest.mark.parametrize(
    "host,uid,platform,environ",
    [
        ("testserver", 1002, "linux", {"KIROCREW_SANDBOX_ACTIVE": "1"}),
        ("ai-ubuntu", 1002, "linux", {}),
        ("testserver", 0, "linux", {}),
        ("testserver", 1000, "linux", {}),
        ("testserver", 1002, "win32", {}),
    ],
)
def test_context_refuses_sandbox_wrong_host_uid_and_platform(
    repair_module, host, uid, platform, environ
):
    with pytest.raises(RuntimeError):
        repair_module.guard_context(host, uid, uid, platform, environ)


def test_check_apply_and_undo_preserve_only_three_links(synthetic):
    module, profile, proc = synthetic
    before = {n: (profile / n).lstat() for n in module.NAMES}
    assert module.repair(profile, proc, "check") is None
    assert len(list(profile.parent.iterdir())) == 2
    backup = module.repair(profile, proc, "apply")
    assert backup.stat().st_mode & 0o777 == 0o700
    assert set(p.name for p in backup.iterdir()) == set(module.NAMES)
    assert all(not os.path.lexists(profile / n) for n in module.NAMES)
    for n in module.NAMES:
        assert (backup / n).lstat().st_ino == before[n].st_ino
        assert (backup / n).lstat().st_mtime_ns == before[n].st_mtime_ns
    module.repair(profile, proc, "undo", backup)
    assert list(backup.iterdir()) == []
    assert (profile / "profile-sentinel").read_text() == "untouched"
    assert all((profile / n).lstat().st_ino == before[n].st_ino for n in module.NAMES)


@pytest.mark.parametrize("change", ["new-lock", "mtime", "regular", "profile-link"])
def test_changed_metadata_refuses_without_mutation(synthetic, change):
    module, profile, proc = synthetic
    if change == "profile-link":
        alias = profile.parent / "alias"
        alias.symlink_to(profile, target_is_directory=True)
        profile = alias
    else:
        p = profile / "SingletonLock"
        if change == "mtime":
            os.utime(p, ns=(1, 1), follow_symlinks=False)
        else:
            p.unlink()
            if change == "new-lock":
                p.symlink_to("ai-ubuntu-198477")
            else:
                p.write_text("not a link")
    with pytest.raises((RuntimeError, OSError)):
        module.repair(profile, proc, "apply")
    assert not list(profile.parent.glob(module.BACKUP_PREFIX + "*"))


def test_active_chromium_refuses_before_backup(synthetic):
    module, profile, proc = synthetic
    pid = proc / "7"
    pid.mkdir()
    (pid / "comm").write_text("chromium\n")
    (pid / "cmdline").write_bytes(b"chromium\0--user-data-dir=" + os.fsencode(profile) + b"\0")
    with pytest.raises(RuntimeError, match="Active Chromium"):
        module.repair(profile, proc, "apply")
    assert not list(profile.parent.glob(module.BACKUP_PREFIX + "*"))


def test_undo_never_clobbers_new_owner_or_backup_entries(synthetic):
    module, profile, proc = synthetic
    backup = module.repair(profile, proc, "apply")
    (profile / "SingletonLock").symlink_to("testserver-new-owner")
    with pytest.raises(RuntimeError):
        module.repair(profile, proc, "undo", backup)
    assert (profile / "SingletonLock").readlink() == Path("testserver-new-owner")
    assert len(list(backup.iterdir())) == 3


def test_interrupted_move_retains_recoverable_backup(synthetic, monkeypatch):
    module, profile, proc = synthetic
    real = module.platform_compat.rename_noreplace
    calls = []

    def interrupted(*args, **kwargs):
        calls.append(args[0])
        if len(calls) == 2:
            raise OSError("synthetic interruption")
        return real(*args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(module.platform_compat, "rename_noreplace", interrupted)
        with pytest.raises(OSError):
            module.repair(profile, proc, "apply")
    backup = next(profile.parent.glob(module.BACKUP_PREFIX + "*"))
    assert os.path.lexists(profile / "SingletonLock")
    module.repair(profile, proc, "undo", backup)
    assert all(os.path.lexists(profile / n) for n in module.NAMES)


def test_atomic_move_refuses_an_existing_destination(synthetic):
    module, profile, proc = synthetic
    backup = profile.parent / (module.BACKUP_PREFIX + "synthetic")
    backup.mkdir(mode=0o700)
    (backup / "SingletonCookie").symlink_to("new-backup-entry")
    with pytest.raises(FileExistsError):
        with module.open_directory(profile) as src, module.open_directory(backup) as dst:
            module.move_link(src, dst, "SingletonCookie", module.snapshot(src, "SingletonCookie"))
    assert (backup / "SingletonCookie").readlink() == Path("new-backup-entry")
    assert os.path.lexists(profile / "SingletonCookie")


@pytest.mark.parametrize("kind", ["unreadable", "relative", "alias"])
def test_ambiguous_or_aliased_browser_metadata_refuses(synthetic, kind):
    module, profile, proc = synthetic
    pid = proc / "9"
    pid.mkdir()
    (pid / "comm").write_text("chrome\n")
    if kind == "unreadable":
        (pid / "cmdline").mkdir()
    else:
        alias = profile.parent / "alias"
        alias.symlink_to(profile, target_is_directory=True)
        value = "relative-profile" if kind == "relative" else str(alias)
        (pid / "cmdline").write_bytes(b"chrome\0--user-data-dir\0" + os.fsencode(value))
    with pytest.raises(RuntimeError):
        module.repair(profile, proc, "apply")
    assert not list(profile.parent.glob(module.BACKUP_PREFIX + "*"))


@pytest.mark.parametrize("kind", ["permissions", "extra-entry"])
def test_undo_rejects_untrusted_backup(synthetic, kind):
    module, profile, proc = synthetic
    backup = module.repair(profile, proc, "apply")
    if kind == "permissions":
        backup.chmod(0o755)
    else:
        (backup / "unexpected").write_text("untouched")
    with pytest.raises(RuntimeError):
        module.repair(profile, proc, "undo", backup)
    assert all(not os.path.lexists(profile / n) for n in module.NAMES)


def test_replacement_race_never_unlinks_new_entry(synthetic, monkeypatch):
    module, profile, proc = synthetic
    real = module.platform_compat.rename_noreplace

    def replacement(*args, **kwargs):
        real(*args, **kwargs)
        os.symlink("new-entry", args[0], dir_fd=kwargs["src_dir_fd"])

    monkeypatch.setattr(module.platform_compat, "rename_noreplace", replacement)
    with pytest.raises(RuntimeError):
        module.repair(profile, proc, "apply")
    assert (profile / "SingletonCookie").readlink() == Path("new-entry")
    assert os.path.lexists(profile / "SingletonLock")
