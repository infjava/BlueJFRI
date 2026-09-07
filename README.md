# BlueJ FRI Edition

FRI customizations for BlueJ on Windows and macOS. Official BlueJ binaries are not stored in this repository.

## Configuration in `data/`

- `bluej-version.txt` — BlueJ version used by the Windows build.
- `bluej.defs.append` — lines appended to packaged Windows `lib/bluej.defs`.
- `bluej.properties.append` — per-user properties installed on macOS.
- `extensions2/` — optional extension files stored in this repository.
- `extensions2.urls` — external extensions downloaded at build/install time, one direct HTTP/HTTPS URL per line.
- `templates/` — custom templates overlaid on the original English templates.
- `setup.iss` — Inno Setup template.

## Windows

Run:

```powershell
py build.py
```

The build downloads the official `BlueJ-windows-<version>.zip`, copies the complete distribution, removes non-English language packs, overlays FRI templates/extensions, downloads extensions listed in `data/extensions2.urls`, appends `bluej.defs.append`, and generates `dst/setup.iss`.

Compile locally with Inno Setup 6:

```powershell
ISCC.exe dst\setup.iss
```

The installer is written to `dst/output/BlueJFRI-<version>.exe`.

### Manual GitHub release

The `Build and release Windows installer` GitHub Actions workflow is **manual only** (`workflow_dispatch`). It is never triggered by push, tag, schedule, or merge.

In GitHub open **Actions → Build and release Windows installer → Run workflow**. It builds the installer on `windows-latest`, creates `SHA256SUMS.txt`, uploads a workflow artifact, and creates a `BlueJFRI-<version>` release. An existing release is not overwritten unless the manual `replace_existing_release` option is enabled.

## macOS

The macOS installer does not modify `BlueJ.app`. Install the official BlueJ separately, then run:

```bash
curl -fLO https://raw.githubusercontent.com/infjava/BlueJFRI/master/install-macos.sh
chmod +x install-macos.sh
./install-macos.sh
```

For testing another branch:

```bash
./install-macos.sh feature/bluej6-build-and-macos
```

It installs extensions into:

```text
~/Library/Preferences/org.bluej/extensions2/
```

and maintains one managed FRI block in:

```text
~/Library/Preferences/org.bluej/bluej.properties
```

The state file `.bluejfri-extensions` records extensions owned by the installer, so updates can remove obsolete FRI extensions without deleting unrelated user extensions.

## External extensions

To keep a plugin binary out of Git, put its direct URL in `data/extensions2.urls`:

```text
https://example.org/path/plugin.jar
```

The same URL list is used by the Windows build and macOS installer. The filename is derived from the URL path. Do not configure the same filename both locally in `data/extensions2/` and via URL.
