"""Real MAX mask evidence, only from an ordinary unsandboxed operator shell.

Never clear a launcher marker or weaken host policy to make this test run.
A skip is missing evidence, not successful enforcement.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kiro_crew import sandbox
from kiro_crew.sandbox_probe import _inside_kirocrew_sandbox
from kiro_crew.testing.wait import default_timeout


def test_max_state_is_hidden_and_sealed_by_the_real_namespace(tmp_path, monkeypatch):
    if sys.platform != "linux" or _inside_kirocrew_sandbox():
        pytest.skip("needs an ordinary Linux operator shell outside the agent sandbox")
    if not sandbox.userns_available():
        pytest.skip("host cannot build the namespace sandbox; do not weaken policy")

    home = tmp_path / ".kiro" / "crew"
    state = home / "max"
    state.mkdir(parents=True, mode=0o700)
    sentinel = state / "fixture-state"
    sentinel.write_text("synthetic MAX state", encoding="utf-8")
    control = tmp_path / "control"
    control.write_text("control", encoding="utf-8")
    monkeypatch.setenv("KIROCREW_HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(sandbox, "config_dir", lambda: home)
    sandbox.reset_backend()
    child = r"""
import json, os, sys
from pathlib import Path
sentinel, created, control = map(Path, sys.argv[1:])
def read(path):
    try: return path.read_text()
    except OSError: return None
def write(path):
    try: path.write_text('changed'); return True
    except OSError: return False
print(json.dumps({'read': read(sentinel), 'overwrite': write(sentinel),
    'create': write(created), 'control_read': read(control),
    'control_write': write(control), 'namespace': os.readlink('/proc/self/ns/mnt'),
    'marker': os.environ.get('KIROCREW_SANDBOX_ACTIVE')}))
"""
    try:
        argv = [sys.executable, "-c", child, str(sentinel), str(state / "new"), str(control)]
        result = subprocess.run(
            sandbox.namespace_argv(argv, "standard"),
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=default_timeout(),
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["marker"] == "1"
        assert report["namespace"] != os.readlink("/proc/self/ns/mnt")
        assert report["read"] is None
        assert report["overwrite"] is False
        assert report["create"] is False
        assert report["control_read"] == "control"
        assert report["control_write"] is True
        assert sentinel.read_text(encoding="utf-8") == "synthetic MAX state"
        assert not (state / "new").exists()
        assert control.read_text(encoding="utf-8") == "changed"
    finally:
        sandbox.reset_backend()
