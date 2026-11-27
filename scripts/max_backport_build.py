"""Build and audit a MAX wheel from a pinned public 0.13.1 wheel. Never install it."""

import argparse
import base64
import csv
import email
import hashlib
import io
import json
import os
import stat
import subprocess
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
BUILD_MANIFEST = REPO / "compat/max-0.13.1-build.json"
PATCH = REPO / "compat/max-0.13.1.patch"
BASE_VERSION = "0.13.1"
BUILD_FILE_LIMIT = 1_000_000
DOWNLOAD_TIMEOUT = 60
BUILD_TIMEOUT = 900


def require_hash(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Pinned SHA256 mismatch")


def read_wheel(path):
    with zipfile.ZipFile(path) as archive:
        files = {}
        for info in archive.infolist():
            name = info.filename
            parts = PurePosixPath(name)
            if (
                parts.is_absolute()
                or ".." in parts.parts
                or "\\" in name
                or ":" in name
                or stat.S_ISLNK(info.external_attr >> 16)
                or name in files
            ):
                raise ValueError("Unsafe or duplicate wheel member")
            if not info.is_dir():
                files[name] = archive.read(info)
    records = [name for name in files if name.endswith(".dist-info/RECORD")]
    if len(records) != 1:
        raise ValueError("Expected one wheel RECORD")
    listed = set()
    for name, digest, size in csv.reader(io.StringIO(files[records[0]].decode("utf-8"))):
        if name not in files or name in listed:
            raise ValueError("Invalid RECORD member")
        listed.add(name)
        if name == records[0]:
            if digest or size:
                raise ValueError("RECORD must not hash itself")
            continue
        data = files[name]
        actual = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        if digest != "sha256=" + actual or str(len(data)) != size:
            raise ValueError("Wheel RECORD mismatch")
    if listed != set(files):
        raise ValueError("Unrecorded wheel member")
    return files


def metadata_in(files):
    names = [name for name in files if name.endswith(".dist-info/METADATA")]
    if len(names) != 1:
        raise ValueError("Expected one distribution metadata file")
    return names[0], email.message_from_bytes(files[names[0]])


def verify_candidate(baseline, candidate, allowed_changes):
    old_path, old = metadata_in(baseline)
    new_path, new = metadata_in(candidate)
    for field in ("Requires-Dist", "Provides-Extra", "Requires-Python", "Name", "License-File"):
        if old.get_all(field) != new.get_all(field):
            raise ValueError("Distribution contract changed: " + field)
    if (
        baseline[old_path.replace("METADATA", "entry_points.txt")]
        != candidate[new_path.replace("METADATA", "entry_points.txt")]
    ):
        raise ValueError("Entrypoints changed")
    for name, data in baseline.items():
        if not name.startswith("kiro_crew/"):
            continue
        if name not in candidate:
            raise ValueError("Missing baseline file: " + name)
        if name not in allowed_changes and candidate[name] != data:
            raise ValueError("Unrelated package file changed: " + name)
    for license_file in old.get_all("License-File", []):
        old_license = old_path.replace("METADATA", "licenses/" + license_file)
        new_license = new_path.replace("METADATA", "licenses/" + license_file)
        if baseline[old_license] != candidate[new_license]:
            raise ValueError("License changed")
    return {"missing_baseline": 0, "requires_dist": new.get_all("Requires-Dist", [])}


def package_data_config(config, assets):
    anchor = "[options.package_data]\nkiro_crew =\n"
    if config.count(anchor) != 1:
        raise ValueError("Unexpected 0.13.1 package_data layout")
    return config.replace(anchor, anchor + "".join("    " + asset + "\n" for asset in assets))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_wheel", type=Path)
    parser.add_argument("output", type=Path, help="new directory outside the repository")
    args = parser.parse_args()
    manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
    require_hash(args.base_wheel.read_bytes(), manifest["base_wheel_sha256"])
    require_hash(PATCH.read_bytes(), manifest["patch_sha256"])
    baseline = read_wheel(args.base_wheel)
    old_meta_path, old_meta = metadata_in(baseline)
    if old_meta["Version"] != BASE_VERSION:
        raise ValueError("Expected base version 0.13.1")
    require_hash(
        "\n".join(old_meta.get_all("Requires-Dist", [])).encode(),
        manifest["requires_dist_sha256"],
    )
    output = args.output.resolve()
    if output.is_relative_to(REPO):
        raise ValueError("Build output must be outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    with zipfile.ZipFile(args.base_wheel) as archive:
        for name, data in baseline.items():
            if not name.startswith("kiro_crew/"):
                continue
            target = source / "src" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod((archive.getinfo(name).external_attr >> 16) & 0o777 or 0o644)
    base_files = json.loads((REPO / "compat/max-0.13.1-base.json").read_text(encoding="utf-8"))
    for name, expected in base_files["files"].items():
        path = source / name
        if expected is None:
            if path.exists():
                raise ValueError("Unexpected existing MAX file")
        else:
            require_hash(path.read_bytes(), expected)
    for name, expected in manifest["build_files"].items():
        url = (
            "https://raw.githubusercontent.com/kirodotdev/KiroCrew/"
            + manifest["base_git_sha"]
            + "/"
            + name
        )
        with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
            data = response.read(BUILD_FILE_LIMIT + 1)
        require_hash(data, expected)
        (source / name).write_bytes(data)
    for name in old_meta.get_all("License-File", []):
        if PurePosixPath(name).name != name:
            raise ValueError("Unsafe license name")
        (source / name).write_bytes(baseline[old_meta_path.replace("METADATA", "licenses/" + name)])
    (source / "CHANGELOG.md").write_bytes(baseline["kiro_crew/CHANGELOG.md"])
    config = source / "setup.cfg"
    config.write_text(
        package_data_config(config.read_text(encoding="utf-8"), manifest["package_data"]),
        encoding="utf-8",
        newline="\n",
    )
    version = manifest["version"]
    for name, before, after in (
        ("pyproject.toml", f'version = "{BASE_VERSION}"', f'version = "{version}"'),
        (
            "src/kiro_crew/__init__.py",
            f'__version__ = "{BASE_VERSION}"',
            f'__version__ = "{version}"',
        ),
    ):
        path = source / name
        text = path.read_text(encoding="utf-8")
        if text.count(before) != 1:
            raise ValueError("Unexpected base version declaration")
        path.write_text(text.replace(before, after), encoding="utf-8", newline="\n")
    constraints = output / "build-constraints.txt"
    constraints.write_text("\n".join(manifest["build_constraints"]) + "\n", encoding="utf-8")
    env = dict(os.environ)
    env.update(
        UV_CACHE_DIR=str(output / "uv-cache"),
        KIROCREW_BUILD_EDITION="oss",
        SOURCE_DATE_EPOCH=str(manifest["source_date_epoch"]),
    )
    with (output / "build.log").open("w", encoding="utf-8") as log:
        for command in (
            ["git", "apply", "--check", str(PATCH)],
            ["git", "apply", str(PATCH)],
            [
                "uv",
                "--no-config",
                "build",
                "--wheel",
                "--build-constraints",
                str(constraints),
                "--out-dir",
                str(output / "dist"),
                str(source),
            ],
        ):
            subprocess.run(
                command,
                cwd=source,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=BUILD_TIMEOUT,
                encoding="utf-8",
            )
    wheels = list((output / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Expected one candidate wheel")
    wheel = wheels[0]
    candidate = read_wheel(wheel)
    changed = {name.removeprefix("src/") for name in base_files["files"]}
    result = verify_candidate(baseline, candidate, changed | {"kiro_crew/__init__.py"})
    require_hash(candidate[manifest["ca_path"]], manifest["ca_sha256"])
    _, new_meta = metadata_in(candidate)
    if new_meta["Version"] != version:
        raise ValueError("Wrong candidate version")
    old_payload = {name for name in baseline if name.startswith("kiro_crew/")}
    new_payload = {name for name in candidate if name.startswith("kiro_crew/")}
    expected_new = {
        name.removeprefix("src/") for name, digest in base_files["files"].items() if digest is None
    }
    if new_payload - old_payload != expected_new:
        raise ValueError("Unexpected added package files")
    result.update(
        wheel=wheel.name,
        sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        base_git_sha=manifest["base_git_sha"],
        patch_sha256=manifest["patch_sha256"],
        ca_sha256=manifest["ca_sha256"],
        version=version,
    )
    (output / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
