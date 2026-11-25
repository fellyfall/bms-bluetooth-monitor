#!/usr/bin/env python3
"""Package committed project files from HEAD for a GitHub release."""

import argparse
import io
import json
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


VERSION_PATTERN = re.compile(r"v\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.-]+)?\Z")
EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "venv",
}


def should_include(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name

    if any(part in EXCLUDED_DIRECTORIES for part in parts):
        return False
    if name == "config.toml" or name == ".env" or name.startswith(".env."):
        return False
    if name.startswith("battery_log") and name.endswith(".csv"):
        return False
    if name.endswith((".log", ".pyc", ".pyo", ".zip")):
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Release version, for example v0.3")
    args = parser.parse_args()
    if not VERSION_PATTERN.fullmatch(args.version):
        parser.error("version must look like v0.3 or v1.2.3")

    archive_data = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    revision = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    prefix = f"bms-bluetooth-monitor-{args.version}/"
    output_dir = Path("dist")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"bms-bluetooth-monitor-{args.version}.zip"

    with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:") as source:
        with zipfile.ZipFile(
            output_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as package:
            for member in source:
                if not member.isfile() or not should_include(member.name):
                    continue
                fileobj = source.extractfile(member)
                if fileobj is None:
                    continue
                info = zipfile.ZipInfo(prefix + member.name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (member.mode & 0xFFFF) << 16
                package.writestr(info, fileobj.read())
            package.writestr(
                prefix + "version.json",
                json.dumps(
                    {"version": args.version, "revision": revision},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
            )

    print(f"Created {output_path}")


if __name__ == "__main__":
    main()
