#!/bin/bash
# Install/update BlueJ FRI user-level customizations on macOS.

set -euo pipefail

REPO_OWNER="${BLUEJFRI_REPO_OWNER:-infjava}"
REPO_NAME="${BLUEJFRI_REPO_NAME:-BlueJFRI}"
REF="${1:-${BLUEJFRI_REF:-master}}"

ARCHIVE_URL="${BLUEJFRI_ARCHIVE_URL:-https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/${REF}.zip}"

BLUEJ_USER_DIR="${BLUEJFRI_USER_DIR:-$HOME/Library/Preferences/org.bluej}"
EXT_DIR="$BLUEJ_USER_DIR/extensions2"
TEMPLATE_DIR="$BLUEJ_USER_DIR/templates"

PROPERTIES="$BLUEJ_USER_DIR/bluej.properties"
STATE_FILE="$BLUEJ_USER_DIR/.bluejfri-extensions"

CHECKSTYLE_CONFIG="$EXT_DIR/default_checks.xml"

fail()
{
    echo "ERROR: $*" >&2
    exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v unzip >/dev/null 2>&1 || fail "unzip is required"
command -v find >/dev/null 2>&1 || fail "find is required"
command -v sed >/dev/null 2>&1 || fail "sed is required"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bluejfri.XXXXXX")"

trap 'rm -rf "$TMP_DIR"' EXIT INT TERM

ARCHIVE="$TMP_DIR/bluejfri.zip"
EXTRACTED="$TMP_DIR/extracted"

mkdir -p "$EXTRACTED"

echo "BlueJ FRI macOS installer"
echo "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo "Revision:   ${REF}"
echo

#
# Find BlueJ.app
#

BLUEJ_APP=""

if [ -d "/Applications/BlueJ.app" ]; then
    BLUEJ_APP="/Applications/BlueJ.app"
elif [ -d "$HOME/Applications/BlueJ.app" ]; then
    BLUEJ_APP="$HOME/Applications/BlueJ.app"
fi

if [ -n "$BLUEJ_APP" ]; then
    echo "BlueJ application:"
    echo "  $BLUEJ_APP"
else
    echo "NOTE: BlueJ.app was not found."
    echo "Templates cannot be initialized from the original BlueJ installation."
fi

#
# Download BlueJFRI repository
#

echo
echo "Downloading BlueJ FRI files ..."

curl \
    -fL \
    --retry 2 \
    --connect-timeout 15 \
    "$ARCHIVE_URL" \
    -o "$ARCHIVE"

unzip -q "$ARCHIVE" -d "$EXTRACTED" \
    || fail "Downloaded repository archive could not be extracted"

#
# Find data/
#

DATA_DIR=""

for candidate in "$EXTRACTED"/*/data; do
    if [ -d "$candidate" ]; then
        DATA_DIR="$candidate"
        break
    fi
done

[ -n "$DATA_DIR" ] \
    || fail "data/ directory was not found in the downloaded repository"

EXT_SOURCE="$DATA_DIR/extensions2"
CHECKSTYLE_SOURCE="$DATA_DIR/checkstyle"
TEMPLATE_SOURCE="$DATA_DIR/templates"
PROPERTIES_SOURCE="$DATA_DIR/bluej.properties.append"
EXTENSION_URLS_SOURCE="$DATA_DIR/extensions2.urls"

[ -f "$PROPERTIES_SOURCE" ] \
    || fail "Missing data/bluej.properties.append"

[ -f "$EXTENSION_URLS_SOURCE" ] \
    || fail "Missing data/extensions2.urls"

#
# Prepare user directories
#

mkdir -p "$BLUEJ_USER_DIR"
mkdir -p "$EXT_DIR"

#
# Templates
#

ORIGINAL_TEMPLATE_DIR=""

if [ -n "$BLUEJ_APP" ]; then

    echo
    echo "Searching for original BlueJ templates ..."

    #
    # Current BlueJ 6 macOS layout.
    #
    if [ -d "$BLUEJ_APP/Contents/Java/english/templates" ]; then

        ORIGINAL_TEMPLATE_DIR="$BLUEJ_APP/Contents/Java/english/templates"

    else

        #
        # Fallback in case the bundle layout changes.
        #
        ORIGINAL_TEMPLATE_DIR="$(
            find "$BLUEJ_APP" \
                -type d \
                -path '*/english/templates' \
                -print \
                -quit
        )"

    fi

    [ -n "$ORIGINAL_TEMPLATE_DIR" ] \
        || fail "Could not find english/templates inside $BLUEJ_APP"

    echo "Original templates:"
    echo "  $ORIGINAL_TEMPLATE_DIR"

    echo "User templates:"
    echo "  $TEMPLATE_DIR"

    #
    # Always rebuild the user template tree from the currently
    # installed BlueJ version.
    #
    rm -rf "$TEMPLATE_DIR"
    mkdir -p "$TEMPLATE_DIR"

    cp -R \
        "$ORIGINAL_TEMPLATE_DIR"/. \
        "$TEMPLATE_DIR"/

    #
    # Overlay FRI templates.
    #
    if [ -d "$TEMPLATE_SOURCE" ]; then

        echo "Overlaying BlueJ FRI templates ..."

        cp -R \
            "$TEMPLATE_SOURCE"/. \
            "$TEMPLATE_DIR"/

    fi

    echo "Templates installed."

fi

#
# Remove extensions managed by the previous BlueJ FRI install
#

if [ -f "$STATE_FILE" ]; then

    while IFS= read -r old_name || [ -n "$old_name" ]; do

        case "$old_name" in
            ""|.*|*/*)
                continue
                ;;
        esac

        rm -f "$EXT_DIR/$old_name"

    done < "$STATE_FILE"

fi

#
# Install extensions
#

NEW_STATE="$TMP_DIR/extensions.state"

: > "$NEW_STATE"

extension_count=0

install_extension_dir()
{
    source_dir="$1"

    [ -d "$source_dir" ] || return 0

    for source_file in "$source_dir"/*; do

        [ -f "$source_file" ] || continue

        name="$(basename "$source_file")"

        if grep -Fxq "$name" "$NEW_STATE"; then
            fail "Duplicate extension filename: $name"
        fi

        cp -p \
            "$source_file" \
            "$EXT_DIR/$name"

        echo "$name" >> "$NEW_STATE"

        extension_count=$((extension_count + 1))

    done
}

#
# Extensions stored directly in the repository.
#

install_extension_dir "$EXT_SOURCE"

#
# Checkstyle-related files.
#

install_extension_dir "$CHECKSTYLE_SOURCE"

#
# External extensions
#

while IFS= read -r raw_url || [ -n "$raw_url" ]; do

    url="$(
        printf '%s' "$raw_url" |
            sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
    )"

    case "$url" in

        ""|\#*)
            continue
            ;;

        http://*|https://*)
            ;;

        *)
            fail "Unsupported extension URL: $url"
            ;;

    esac

    path_without_query="${url%%\?*}"

    name="$(basename "$path_without_query")"

    case "$name" in
        ""|.|..|*/*)
            fail "Could not determine extension filename from URL: $url"
            ;;
    esac

    if grep -Fxq "$name" "$NEW_STATE"; then
        fail "Duplicate extension filename: $name"
    fi

    echo "Downloading external extension:"
    echo "  $name"

    curl \
        -fL \
        --retry 2 \
        --connect-timeout 15 \
        "$url" \
        -o "$TMP_DIR/$name"

    mv \
        "$TMP_DIR/$name" \
        "$EXT_DIR/$name"

    echo "$name" >> "$NEW_STATE"

    extension_count=$((extension_count + 1))

done < "$EXTENSION_URLS_SOURCE"

mv "$NEW_STATE" "$STATE_FILE"

#
# Verify Checkstyle configuration file
#

if [ ! -f "$CHECKSTYLE_CONFIG" ]; then
    fail "Checkstyle configuration was not installed: $CHECKSTYLE_CONFIG"
fi

#
# Rewrite bluej.properties completely
#

echo
echo "Writing BlueJ user configuration ..."

: > "$PROPERTIES"

while IFS= read -r line || [ -n "$line" ]; do

    line="${line//__BLUEJFRI_CHECKSTYLE_CONFIG__/$CHECKSTYLE_CONFIG}"

    printf '%s\n' "$line"

done < "$PROPERTIES_SOURCE" >> "$PROPERTIES"

#
# Point BlueJ to the user-level template tree.
#

if [ -n "$ORIGINAL_TEMPLATE_DIR" ]; then
    printf 'bluej.templatePath=%s\n' "$TEMPLATE_DIR" >> "$PROPERTIES"
fi

#
# Summary
#

echo
echo "BlueJ FRI configuration installed successfully."

echo
echo "Extensions installed: $extension_count"

echo
echo "Configuration:"
echo "  $PROPERTIES"

echo
echo "Extensions:"
echo "  $EXT_DIR"

echo
echo "Checkstyle config:"
echo "  $CHECKSTYLE_CONFIG"

if [ -n "$ORIGINAL_TEMPLATE_DIR" ]; then

    echo
    echo "Templates:"
    echo "  $TEMPLATE_DIR"

    echo
    echo "Template source:"
    echo "  $ORIGINAL_TEMPLATE_DIR"

fi

echo
echo "Restart BlueJ if it is currently running."
