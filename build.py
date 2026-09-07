#!/usr/bin/env python3
"""Build BlueJ FRI Edition from an official BlueJ Windows standalone ZIP.

FRI-specific content lives in data/:
    data/bluej-version.txt   BlueJ version to download (for example 6.0.1)
    data/bluej.defs.append  Optional lines appended to lib/bluej.defs
    data/extensions2/       Optional overlay for lib/extensions2
    data/extensions2.urls   Optional external extension download URLs
    data/templates/         Optional overlay for lib/english/templates
    data/setup.iss          Inno Setup template

The BlueJ standalone ZIP is downloaded from the official GitHub release,
extracted into a temporary directory, copied to dst/bluej, customized, and
then dst/setup.iss is generated.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DST = ROOT / "dst"
DST_BLUEJ = DST / "bluej"
CACHE = ROOT / ".cache" / "bluej"

VERSION_FILE = DATA / "bluej-version.txt"
DEFS_APPEND_FILE = DATA / "bluej.defs.append"
SETUP_TEMPLATE = DATA / "setup.iss"
EXTENSION_URLS_FILE = DATA / "extensions2.urls"

GITHUB_RELEASE_BASE = (
    "https://github.com/k-pet-group/BlueJ-Greenfoot/releases/download"
)


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_version(cli_version: str | None) -> str:
    if cli_version:
        version = cli_version.strip()
    else:
        if not VERSION_FILE.is_file():
            fail(f"Missing version file: {VERSION_FILE}")
        version = VERSION_FILE.read_text(encoding="utf-8").strip()

    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        fail(f"Invalid BlueJ version '{version}'. Expected e.g. 6.0.1")
    return version


def release_url(version: str) -> str:
    filename = f"BlueJ-windows-{version}.zip"
    tag = f"BLUEJ-RELEASE-{version}"
    return f"{GITHUB_RELEASE_BASE}/{tag}/{filename}"


def download_file(url: str, destination: Path, force: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.is_file() and not force:
        print(f"Using cached archive: {destination}")
        return

    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)

    print(f"Downloading:\n  {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BlueJFRI-build/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
    except (urllib.error.URLError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        fail(f"Could not download file: {exc}")

    temporary.replace(destination)


def safe_extract_zip(archive: Path, destination: Path) -> None:
    """Extract ZIP while rejecting paths that escape the destination."""
    destination = destination.resolve()

    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                target = (destination / member.filename).resolve()
                try:
                    target.relative_to(destination)
                except ValueError:
                    fail(f"Unsafe path in ZIP: {member.filename}")
            zf.extractall(destination)
    except zipfile.BadZipFile as exc:
        fail(f"Downloaded file is not a valid ZIP: {archive}: {exc}")


def find_bluej_root(extracted: Path) -> Path:
    """Find the directory containing BlueJ.exe in the standalone archive."""
    direct = extracted / "BlueJ.exe"
    if direct.is_file():
        return extracted

    candidates = [p.parent for p in extracted.rglob("BlueJ.exe")]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        fail("BlueJ.exe was not found in the downloaded standalone ZIP")

    display = ", ".join(str(p.relative_to(extracted)) for p in candidates[:5])
    fail(f"Several BlueJ.exe files were found in the ZIP: {display}")


def validate_bluej_tree(bluej_root: Path, version: str) -> None:
    required = [
        bluej_root / "BlueJ.exe",
        bluej_root / "lib" / "bluej.defs",
        bluej_root / "lib" / "english" / "labels",
        bluej_root / "LICENSE.txt",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        fail("Unexpected BlueJ archive layout; missing: " + ", ".join(missing))

    readme = bluej_root / "README.TXT"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8", errors="ignore")
        if version not in text:
            fail(
                f"README.TXT does not contain requested version {version}. "
                "Refusing to build from a mismatched archive."
            )


def remove_non_english_languages(lib_dir: Path) -> list[str]:
    removed: list[str] = []
    for item in sorted(lib_dir.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_dir() or item.name.lower() == "english":
            continue
        if (item / "labels").is_file():
            shutil.rmtree(item)
            removed.append(item.name)
    return removed


def overlay_directory(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if not source.is_dir():
        fail(f"Expected directory: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def external_extension_entries() -> list[tuple[str, str]]:
    """Return (filename, URL) pairs from data/extensions2.urls."""
    if not EXTENSION_URLS_FILE.exists():
        return []
    if not EXTENSION_URLS_FILE.is_file():
        fail(f"Expected file: {EXTENSION_URLS_FILE}")

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(EXTENSION_URLS_FILE.read_text(encoding="utf-8").splitlines(), 1):
        url = raw.strip()
        if not url or url.startswith("#"):
            continue

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            fail(f"Unsupported URL scheme on line {number} of {EXTENSION_URLS_FILE}: {url}")

        filename = Path(urllib.parse.unquote(parsed.path)).name
        if not filename or filename in {".", ".."}:
            fail(f"Could not determine extension filename from URL on line {number}: {url}")
        if filename in seen:
            fail(f"Duplicate external extension filename '{filename}' in {EXTENSION_URLS_FILE}")
        seen.add(filename)
        entries.append((filename, url))

    return entries


def install_external_extensions(destination: Path) -> int:
    entries = external_extension_entries()
    if not entries:
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    local_dir = DATA / "extensions2"
    local_names = {p.name for p in local_dir.iterdir() if p.is_file()} if local_dir.is_dir() else set()

    for filename, url in entries:
        if filename in local_names:
            fail(
                f"Extension '{filename}' is configured both in data/extensions2/ "
                f"and {EXTENSION_URLS_FILE.name}"
            )
        print(f"Downloading external extension: {filename}")
        download_file(url, destination / filename, force=True)

    return len(entries)


def append_bluej_defs(defs_path: Path) -> int:
    if not DEFS_APPEND_FILE.exists():
        return 0
    if not DEFS_APPEND_FILE.is_file():
        fail(f"Expected file: {DEFS_APPEND_FILE}")

    raw_lines = DEFS_APPEND_FILE.read_text(encoding="utf-8").splitlines()
    additions = [line for line in raw_lines if line.strip()]
    if not additions:
        return 0

    original = defs_path.read_text(encoding="utf-8")
    existing = set(original.splitlines())
    additions = [line for line in additions if line not in existing]
    if not additions:
        return 0

    with defs_path.open("a", encoding="utf-8", newline="\n") as handle:
        if original and not original.endswith(("\n", "\r")):
            handle.write("\n")
        handle.write("\n# BlueJ FRI Edition custom settings\n")
        for line in additions:
            handle.write(line.rstrip("\r\n") + "\n")

    return len(additions)


def generate_setup(version: str) -> Path:
    if not SETUP_TEMPLATE.is_file():
        fail(f"Missing Inno Setup template: {SETUP_TEMPLATE}")

    content = SETUP_TEMPLATE.read_text(encoding="utf-8")
    if "###VER###" not in content:
        fail("data/setup.iss does not contain the ###VER### placeholder")

    output = DST / "setup.iss"
    output.write_text(
        content.replace("###VER###", version),
        encoding="utf-8",
        newline="\n",
    )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Override data/bluej-version.txt for this build")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Download the BlueJ ZIP again even when it is cached",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    version = read_version(args.version)
    archive_name = f"BlueJ-windows-{version}.zip"
    archive = CACHE / archive_name
    url = release_url(version)

    print("=== BlueJ FRI build ===")
    print(f"BlueJ version: {version}")

    download_file(url, archive, force=args.force_download)

    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="bluejfri-") as temp:
        extracted = Path(temp) / "extracted"
        extracted.mkdir()
        safe_extract_zip(archive, extracted)
        bluej_root = find_bluej_root(extracted)
        validate_bluej_tree(bluej_root, version)

        print("=== copying complete BlueJ distribution")
        shutil.copytree(bluej_root, DST_BLUEJ)

    lib_dir = DST_BLUEJ / "lib"

    removed = remove_non_english_languages(lib_dir)
    print(f"=== removed {len(removed)} non-English language packs")
    if removed:
        print("    " + ", ".join(removed))

    print("=== overlaying FRI templates")
    overlay_directory(DATA / "templates", lib_dir / "english" / "templates")

    print("=== overlaying repository extensions")
    overlay_directory(DATA / "extensions2", lib_dir / "extensions2")

    print("=== copying checkstyle checks")
    overlay_directory(DATA / "checkstyle", lib_dir / "checkstyle")

    external_count = install_external_extensions(lib_dir / "extensions2")
    print(f"=== downloaded {external_count} external extension(s)")

    

    appended = append_bluej_defs(lib_dir / "bluej.defs")
    print(f"=== appended {appended} bluej.defs line(s)")

    setup_path = generate_setup(version)

    print()
    print("Build tree prepared successfully.")
    print(f"BlueJ tree: {DST_BLUEJ}")
    print(f"Inno Setup: {setup_path}")
    print(f"Expected installer: {DST / 'output' / f'BlueJFRI-{version}.exe'}")


if __name__ == "__main__":
    main()
