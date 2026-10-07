"""Refuse release asset replacement unless the remote tag matches the build SHA."""

import argparse
import re
import subprocess
import sys


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def verify_release_tag(tag, build_sha):
    git("check-ref-format", f"refs/tags/{tag}")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", build_sha):
        raise ValueError(f"Invalid build commit SHA: '{build_sha}'")
    # Checkout is shallow and may have no tags or stale local tags. Fetch the
    # exact remote ref into FETCH_HEAD without relying on the local tag cache.
    git("fetch", "--no-tags", "--depth=1", "origin", f"refs/tags/{tag}")
    tag_sha = git("rev-parse", "--verify", "FETCH_HEAD^{commit}")
    if tag_sha.lower() != build_sha.lower():
        raise ValueError(
            f"Refusing to replace assets for release '{tag}': "
            f"tag commit {tag_sha} does not match build commit {build_sha}. "
            "Run from the matching tag or use a new FRI version."
        )
    print(f"Verified release tag '{tag}': tag and build commit are {tag_sha}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("build_sha")
    args = parser.parse_args()
    try:
        verify_release_tag(args.tag, args.build_sha)
    except (subprocess.CalledProcessError, OSError, ValueError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        # Escape workflow annotation delimiters and line breaks.
        detail = detail.strip().replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::Release tag verification failed: {detail}. No assets were uploaded.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
