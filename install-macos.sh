#!/bin/bash
# Install/update BlueJ FRI user-level customizations on macOS.
set -euo pipefail

REPO_OWNER="${BLUEJFRI_REPO_OWNER:-infjava}"
REPO_NAME="${BLUEJFRI_REPO_NAME:-BlueJFRI}"
REF="${1:-${BLUEJFRI_REF:-master}}"
ARCHIVE_URL="${BLUEJFRI_ARCHIVE_URL:-https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/${REF}.zip}"
BLUEJ_USER_DIR="${BLUEJFRI_USER_DIR:-$HOME/Library/Preferences/org.bluej}"
EXT_DIR="$BLUEJ_USER_DIR/extensions2"
PROPERTIES="$BLUEJ_USER_DIR/bluej.properties"
STATE_FILE="$BLUEJ_USER_DIR/.bluejfri-extensions"
BEGIN_MARKER="# BEGIN BLUEJ FRI MANAGED SETTINGS"
END_MARKER="# END BLUEJ FRI MANAGED SETTINGS"
CHECKSTYLE_CONFIG="$EXT_DIR/default_checks.xml"

fail() { echo "ERROR: $*" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v unzip >/dev/null 2>&1 || fail "unzip is required"
command -v awk >/dev/null 2>&1 || fail "awk is required"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bluejfri.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT INT TERM
ARCHIVE="$TMP_DIR/bluejfri.zip"
EXTRACTED="$TMP_DIR/extracted"
mkdir -p "$EXTRACTED"

echo "BlueJ FRI macOS installer"
echo "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo "Revision:   ${REF}"
echo
echo "Downloading BlueJ FRI files ..."
curl -fL --retry 2 --connect-timeout 15 "$ARCHIVE_URL" -o "$ARCHIVE"
unzip -q "$ARCHIVE" -d "$EXTRACTED" || fail "Downloaded repository archive could not be extracted"

DATA_DIR=""
for candidate in "$EXTRACTED"/*/data; do
    if [ -d "$candidate" ]; then DATA_DIR="$candidate"; break; fi
done
[ -n "$DATA_DIR" ] || fail "data/ directory was not found in the downloaded repository"
EXT_SOURCE="$DATA_DIR/extensions2"
CHECKSTYLEDATA_SOURCE="$DATA_DIR/checkstyle"
PROPERTIES_SOURCE="$DATA_DIR/bluej.properties.append"
EXTENSION_URLS_SOURCE="$DATA_DIR/extensions2.urls"
[ -f "$PROPERTIES_SOURCE" ] || fail "Missing data/bluej.properties.append in the repository"
[ -f "$EXTENSION_URLS_SOURCE" ] || fail "Missing data/extensions2.urls in the repository"

mkdir -p "$EXT_DIR"
touch "$PROPERTIES"
cp -p "$PROPERTIES" "$PROPERTIES.bluejfri-backup"

begin_count="$(grep -Fxc "$BEGIN_MARKER" "$PROPERTIES" || true)"
end_count="$(grep -Fxc "$END_MARKER" "$PROPERTIES" || true)"
if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then fail "bluej.properties contains an invalid BlueJ FRI managed block"; fi

CLEAN_PROPERTIES="$TMP_DIR/bluej.properties.clean"
awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '$0 == begin { managed = 1; next } $0 == end && managed { managed = 0; next } !managed { print }' "$PROPERTIES" > "$CLEAN_PROPERTIES"
cp "$CLEAN_PROPERTIES" "$PROPERTIES"
if [ -s "$PROPERTIES" ]; then printf '\n' >> "$PROPERTIES"; fi
{
    echo "$BEGIN_MARKER"
    awk -v checkstyle_config="$CHECKSTYLE_CONFIG" '{ gsub(/__BLUEJFRI_CHECKSTYLE_CONFIG__/, checkstyle_config); print }' "$PROPERTIES_SOURCE"
    if [ -s "$PROPERTIES_SOURCE" ] && [ "$(tail -c 1 "$PROPERTIES_SOURCE" | wc -l | tr -d ' ')" -eq 0 ]; then printf '\n'; fi
    echo "$END_MARKER"
} >> "$PROPERTIES"

if [ -f "$STATE_FILE" ]; then
    while IFS= read -r old_name || [ -n "$old_name" ]; do
        case "$old_name" in ""|.*|*/*) continue ;; esac
        rm -f "$EXT_DIR/$old_name"
    done < "$STATE_FILE"
fi

NEW_STATE="$TMP_DIR/extensions.state"
: > "$NEW_STATE"
extension_count=0

install_extension_dir() {
    source_dir="$1"
    [ -d "$source_dir" ] || return 0

    for source_file in "$source_dir"/*; do
        [ -f "$source_file" ] || continue
        name="$(basename "$source_file")"
        if grep -Fxq "$name" "$NEW_STATE"; then
            fail "Duplicate extension filename: $name"
        fi
        cp -p "$source_file" "$EXT_DIR/$name"
        echo "$name" >> "$NEW_STATE"
        extension_count=$((extension_count + 1))
    done
}

# Regular extensions stored in data/extensions2.
install_extension_dir "$EXT_SOURCE"

# Checkstyle-related files stored separately in data/checkstyle are also
# installed into BlueJ's user-level extensions2 directory on macOS.
install_extension_dir "$CHECKSTYLEDATA_SOURCE"

while IFS= read -r raw_url || [ -n "$raw_url" ]; do
    url="$(printf '%s' "$raw_url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    case "$url" in ""|\#*) continue ;; http://*|https://*) ;; *) fail "Unsupported extension URL: $url" ;; esac
    path_without_query="${url%%\?*}"
    name="$(basename "$path_without_query")"
    case "$name" in ""|.|..|*/*) fail "Could not determine extension filename from URL: $url" ;; esac
    if grep -Fxq "$name" "$NEW_STATE"; then fail "Duplicate extension filename: $name"; fi
    echo "Downloading external extension: $name"
    curl -fL --retry 2 --connect-timeout 15 "$url" -o "$TMP_DIR/$name"
    mv "$TMP_DIR/$name" "$EXT_DIR/$name"
    echo "$name" >> "$NEW_STATE"
    extension_count=$((extension_count + 1))
done < "$EXTENSION_URLS_SOURCE"
mv "$NEW_STATE" "$STATE_FILE"

if [ ! -d "/Applications/BlueJ.app" ] && [ ! -d "$HOME/Applications/BlueJ.app" ]; then
    echo; echo "NOTE: BlueJ.app was not found in /Applications or ~/Applications."
    echo "Install the official BlueJ for macOS separately from https://www.bluej.org/."
fi

echo
echo "BlueJ FRI configuration installed successfully."
echo "Extensions installed: $extension_count"
echo "Configuration:        $PROPERTIES"
echo "Extensions directory: $EXT_DIR"
echo "Checkstyle config:     $CHECKSTYLE_CONFIG"
echo; echo "Restart BlueJ if it is currently running."
