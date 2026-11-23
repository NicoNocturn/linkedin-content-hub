"""Runs the whole chain on a temporary copy: record a reading, archive a post, build the dashboard.

python -m unittest discover tests
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        shutil.copytree(ROOT / "scripts", self.tmp / "scripts")
        (self.tmp / "posts" / "drafts").mkdir(parents=True)
        (self.tmp / "inbox").mkdir()
        self.reading = json.loads((ROOT / "examples" / "reading-2026-11-23.json").read_text(encoding="utf-8"))
        self.read = json.loads((ROOT / "examples" / "posts-read-2026-11-23.json").read_text(encoding="utf-8"))
        self.post = self.read["posts"][0]
        # The draft as validated: the post lost its last line before going out.
        draft = self.post["text"] + "\n\nOne more line I cut before posting."
        (self.tmp / "posts" / "drafts" / "2026-11-16-test-draft.txt").write_text(draft, encoding="utf-8")
        roadmap = {"weeks": [{"monday": "2026-11-16", "post": "Test post", "status": "ready",
                              "draft": "2026-11-16-test-draft.txt"}]}
        (self.tmp / "roadmap.json").write_text(json.dumps(roadmap), encoding="utf-8")
        self.write_json("reading.json", self.reading)
        self.write_json("posts-read.json", self.read)

    def write_json(self, name, data):
        (self.tmp / "inbox" / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def run_script(self, *args, check=True):
        return subprocess.run([sys.executable, "-I", *args], cwd=self.tmp, check=check, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")

    def rows(self, name):
        with open(self.tmp / "stats" / name, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_whole_chain(self):
        self.run_script("scripts/record_stats.py", "inbox/reading.json")
        posts = self.rows("posts.csv")
        self.assertEqual(len(posts), len(self.reading["posts"]))
        self.assertEqual(len(self.rows("days.csv")), 90)
        self.assertEqual(len(self.rows("totals.csv")), 1)
        row = next(r for r in posts if r["id"] == self.post["id"])
        self.assertEqual(row["archive"], "")

        out = self.run_script("scripts/archive_posts.py", "inbox/posts-read.json").stdout
        self.assertIn("same first sentence", out)
        archive = self.tmp / "posts" / f"{row['published_at'][:10]}-test-draft.md"
        self.assertTrue(archive.exists(), out)
        text = archive.read_text(encoding="utf-8")
        self.assertIn(self.post["text"].splitlines()[0], text)
        self.assertIn("One more line I cut before posting.", text)  # the original draft is kept
        self.assertFalse((self.tmp / "posts" / "drafts" / "2026-11-16-test-draft.txt").exists())
        line = json.loads((self.tmp / "roadmap.json").read_text(encoding="utf-8"))["weeks"][0]
        self.assertEqual((line["status"], line["post_id"]), ("published", self.post["id"]))
        row = next(r for r in self.rows("posts.csv") if r["id"] == self.post["id"])
        self.assertEqual(row["archive"], f"posts/{archive.name}")

        again = self.run_script("scripts/archive_posts.py", "inbox/posts-read.json").stdout
        self.assertIn("already archived", again)

        self.run_script("scripts/build_dashboard.py")
        html = (self.tmp / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('"reading": "2026-11-23"', html)
        self.assertIn("Test post", html)
        self.assertNotIn("/*__DATA__*/null", html)

    def test_same_day_replaces(self):
        self.run_script("scripts/record_stats.py", "inbox/reading.json")
        self.run_script("scripts/record_stats.py", "inbox/reading.json")
        self.assertEqual(len(self.rows("posts.csv")), len(self.reading["posts"]))
        self.assertEqual(len(self.rows("days.csv")), 90)

    def test_missing_value_stays_empty(self):
        self.reading["posts"][0]["members_reached"] = None
        self.write_json("reading.json", self.reading)
        self.run_script("scripts/record_stats.py", "inbox/reading.json")
        row = next(r for r in self.rows("posts.csv") if r["id"] == self.reading["posts"][0]["id"])
        self.assertEqual(row["members_reached"], "")

    def test_new_post_needs_its_format(self):
        del self.reading["posts"][0]["format"]
        self.write_json("reading.json", self.reading)
        result = self.run_script("scripts/record_stats.py", "inbox/reading.json", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("give its format", result.stderr)

    def test_empty_day_archives_nothing(self):
        self.run_script("scripts/record_stats.py", "inbox/reading.json")
        self.write_json("posts-read.json", {"reading": "2026-11-23", "posts": []})
        out = self.run_script("scripts/archive_posts.py", "inbox/posts-read.json").stdout
        self.assertIn("no post to archive today", out)
        self.assertTrue((self.tmp / "posts" / "drafts" / "2026-11-16-test-draft.txt").exists())


if __name__ == "__main__":
    unittest.main()
