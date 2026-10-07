"""Exercise the production guard against real remote Git tags."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


GUARD = Path(__file__).resolve().parents[1] / ".github/scripts/verify_release_tag.py"
TAG = "BlueJFRI-6.0.1.1"


class ReleaseProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote = root / "remote"
        self.checkout = root / "checkout"
        self.remote.mkdir()
        self.git(self.remote, "init")
        self.git(self.remote, "config", "user.name", "Test")
        self.git(self.remote, "config", "user.email", "test@example.invalid")
        self.git(self.remote, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "tag target")
        self.tag_sha = self.git(self.remote, "rev-parse", "HEAD")
        self.git(self.remote, "tag", TAG)
        self.git(self.remote, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "different build")
        self.build_sha = self.git(self.remote, "rev-parse", "HEAD")
        # Match actions/checkout's shallow, tag-free default checkout.
        self.git(root, "clone", "--depth=1", "--no-tags", self.remote.as_uri(), str(self.checkout))

    @staticmethod
    def git(cwd, *args):
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        ).stdout.strip()

    def guard(self, sha, tag=TAG):
        return subprocess.run(
            [sys.executable, str(GUARD), tag, sha],
            cwd=self.checkout, capture_output=True, text=True,
        )

    def test_matching_lightweight_tag_succeeds_from_shallow_checkout(self):
        result = self.guard(self.tag_sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.tag_sha, result.stdout)

    def test_mismatch_fails_with_tag_and_both_commits(self):
        result = self.guard(self.build_sha)
        self.assertNotEqual(result.returncode, 0)
        for text in (TAG, self.tag_sha, self.build_sha, "Refusing to replace assets"):
            self.assertIn(text, result.stderr)

    def test_matching_annotated_tag_is_peeled_to_commit(self):
        self.git(self.remote, "-c", "tag.gpgsign=false", "tag", "-f", "-a", TAG, self.tag_sha, "-m", "release")
        result = self.guard(self.tag_sha)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_annotated_tag_mismatch_fails(self):
        self.git(self.remote, "-c", "tag.gpgsign=false", "tag", "-f", "-a", TAG, self.tag_sha, "-m", "release")
        self.assertNotEqual(self.guard(self.build_sha).returncode, 0)

    def test_stale_local_tag_does_not_override_remote_target(self):
        self.git(self.checkout, "tag", TAG, self.build_sha)
        self.assertNotEqual(self.guard(self.build_sha).returncode, 0)
        result = self.guard(self.tag_sha)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_remote_tag_fails_even_with_stale_fetch_head(self):
        self.assertEqual(self.guard(self.tag_sha).returncode, 0)
        self.git(self.remote, "tag", "-d", TAG)
        result = self.guard(self.tag_sha)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No assets were uploaded", result.stderr)

    def test_tag_targeting_non_commit_fails(self):
        tree_sha = self.git(self.remote, "rev-parse", "HEAD^{tree}")
        self.git(self.remote, "tag", "-f", TAG, tree_sha)
        self.assertNotEqual(self.guard(self.tag_sha).returncode, 0)

    def test_unreachable_remote_fails(self):
        self.git(self.checkout, "remote", "set-url", "origin", str(Path(self.temp.name) / "missing"))
        self.assertNotEqual(self.guard(self.tag_sha).returncode, 0)

    def test_invalid_build_sha_fails(self):
        self.assertNotEqual(self.guard(self.tag_sha[:7]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
