"""Build-only MAX recipe contracts, using small synthetic wheels."""

import base64
import hashlib
import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def recipe(monkeypatch):
    path = Path(__file__).parents[1] / "scripts" / "max_backport_build.py"
    spec = importlib.util.spec_from_file_location("max_backport_build", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def metadata(version="0.13.1", dependency="cryptography<48,>=42"):
    return (
        f"Name: kirocrew\nVersion: {version}\nRequires-Python: >=3.12\n"
        f"Requires-Dist: {dependency}\nProvides-Extra: teams\n\n"
    ).encode()


def payload(version="0.13.1"):
    return {
        f"kirocrew-{version}.dist-info/METADATA": metadata(version),
        f"kirocrew-{version}.dist-info/entry_points.txt": b"[console_scripts]\n",
        "kiro_crew/__init__.py": f'__version__ = "{version}"\n'.encode(),
        "kiro_crew/static/dist/index.html": b"original frontend",
        "kiro_crew/data/tips_curated.json": b"{}",
    }


def test_config_adds_assets_without_relaxing_dependencies(recipe):
    cfg = "[options]\ninstall_requires =\n    cryptography>=42,<48\n"
    cfg += "[options.package_data]\nkiro_crew =\n    py.typed\n"
    result = recipe.package_data_config(cfg, ["max/root.pem", "data/tips_curated.json"])
    assert "cryptography>=42,<48" in result
    assert "<51" not in result
    assert "    max/root.pem\n" in result
    assert "    data/tips_curated.json\n" in result


def test_candidate_preserves_dependency_contract_and_all_baseline_assets(recipe):
    old = payload()
    new = payload("0.13.1+max.2")
    new["kiro_crew/max/root.pem"] = b"public fixture CA"
    result = recipe.verify_candidate(old, new, {"kiro_crew/__init__.py"})
    assert result["missing_baseline"] == 0
    assert result["requires_dist"] == ["cryptography<48,>=42"]


@pytest.mark.parametrize("change", ["dependency", "missing_asset", "changed_asset"])
def test_candidate_rejects_contract_or_payload_loss(recipe, change):
    old = payload()
    new = payload("0.13.1+max.2")
    if change == "dependency":
        new["kirocrew-0.13.1+max.2.dist-info/METADATA"] = metadata(
            "0.13.1+max.2", "cryptography<51,>=42"
        )
    elif change == "missing_asset":
        new.pop("kiro_crew/data/tips_curated.json")
    else:
        new["kiro_crew/static/dist/index.html"] = b"different frontend"
    with pytest.raises(ValueError):
        recipe.verify_candidate(old, new, {"kiro_crew/__init__.py"})


@pytest.mark.parametrize("bad_name", ["../escape", "/absolute", "a/../../escape"])
def test_wheel_refuses_unsafe_member_names(recipe, tmp_path, bad_name):
    wheel = tmp_path / "bad.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(bad_name, b"untrusted")
    with pytest.raises(ValueError):
        recipe.read_wheel(wheel)


def test_wheel_verifies_record_hashes(recipe, tmp_path):
    wheel = tmp_path / "small.whl"
    data = b"package bytes"
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    record = f"kiro_crew/a.py,sha256={digest},{len(data)}\n"
    record += "kirocrew-0.13.1.dist-info/RECORD,,\n"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("kiro_crew/a.py", data)
        archive.writestr("kirocrew-0.13.1.dist-info/RECORD", record)
    assert recipe.read_wheel(wheel)["kiro_crew/a.py"] == data
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("unrecorded.py", b"not in RECORD")
    with pytest.raises(ValueError):
        recipe.read_wheel(wheel)


def test_pinned_hash_mismatch_refuses_input(recipe):
    with pytest.raises(ValueError):
        recipe.require_hash(b"different wheel", "0" * 64)
