"""Record one reading of your LinkedIn analytics into stats/.

Usage: python scripts/record_stats.py <reading.json>

The scheduled task (routine/daily-linkedin-reading.md) reads your LinkedIn analytics in Chrome,
read-only, and writes what it read to a JSON file (example: examples/reading-2026-11-23.json):

  {"reading": "YYYY-MM-DD",
   "posts": [{"id": "7397...", "impressions": 1234, "reactions": 12, "comments": 3, "saves": 1,
              "profile_views": 9, "followers": 0, "members_reached": 800, "in_network_pct": 41,
              "format": "text", "first_line": "..."}],
   "totals": {"impressions": 41000, "change_pct": 336, "members_reached": 20000, "in_network_pct": 30,
              "reactions": 300, "comments": 40, "saves": 12, "reposts": 2,
              "followers_total": 2900, "followers_gained": 130},
   "days": {"start": "YYYY-MM-DD", "impressions_cumulative": [90 numbers],
            "followers_cumulative": [90 numbers]}}

`format` (text, image, video, document) and `first_line` are only needed the first time a post is seen:
a known post keeps the values of its last row. A value LinkedIn did not show that day is null and stays an
empty cell; it is never copied from an earlier reading. Running the same day twice replaces that day.

The publication time comes from the post id (its first 41 bits are a timestamp in milliseconds) and is
stored in UTC; the dashboard shows it in your own time zone.
"""
import csv
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "stats"
POSTS_DIR = ROOT / "posts"

FIELDS = {
    "posts.csv": ["reading", "id", "published_at", "first_line", "format", "impressions", "reactions",
                  "comments", "saves", "profile_views", "followers", "members_reached", "in_network_pct",
                  "archive"],
    "totals.csv": ["reading", "impressions", "change_pct", "members_reached", "in_network_pct", "reactions",
                   "comments", "saves", "reposts", "followers_total", "followers_gained"],
    "days.csv": ["reading", "day", "impressions_cumulative", "impressions", "followers_cumulative"],
}
METRICS = ["impressions", "reactions", "comments", "saves", "profile_views", "followers", "members_reached",
           "in_network_pct"]


def read(name):
    path = STATS / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows):
    STATS.mkdir(parents=True, exist_ok=True)
    with open(STATS / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS[name], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def replace_reading(name, reading, new_rows):
    """Rows of other readings stay; rows of this reading are replaced by new_rows."""
    for row in new_rows:
        row["reading"] = reading
        unknown = set(row) - set(FIELDS[name])
        if unknown:
            sys.exit(f"{name}: unknown columns {sorted(unknown)}")
    kept = [r for r in read(name) if r["reading"] != reading]
    write(name, kept + new_rows)
    return len(new_rows)


def cell(value):
    return "" if value is None else str(value)


def published_at(post_id):
    ms = int(post_id) >> 22
    return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def front_matter(md):
    text = md.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        for line in text.split("---", 2)[1].splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"')
    return meta


def archive_of(post_id):
    """The archived post (posts/*.md) whose url cites this id, with its front matter."""
    for md in sorted(POSTS_DIR.glob("*.md")):
        meta = front_matter(md)
        if re.search(rf"activity:{post_id}\b", meta.get("url", "")):
            return md, meta
    return None, {}


def record_posts(reading, posts):
    last = {}
    for row in read("posts.csv"):
        if row["reading"] != reading:
            last[row["id"]] = row
    fixed = ["published_at", "first_line", "format", "archive"]
    rows = []
    for p in posts:
        pid = str(p["id"])
        if not re.fullmatch(r"\d{19}", pid):
            sys.exit(f"post id {pid!r}: expected the 19 digits of urn:li:activity:<id>")
        base = {k: last[pid][k] for k in fixed} if pid in last else {}
        if not base or not base["archive"]:
            md, meta = archive_of(pid)
            if not base:
                base = {
                    "published_at": published_at(pid),
                    "first_line": p.get("first_line") or meta.get("title", ""),
                    "format": p.get("format") or meta.get("format", ""),
                }
                if not base["format"]:
                    sys.exit(f"post {pid}: seen for the first time, give its format in the JSON")
            base["archive"] = f"posts/{md.name}" if md else ""
        rows.append({"id": pid, **base, **{k: cell(p.get(k)) for k in METRICS}})
    rows.sort(key=lambda r: r["published_at"])
    return replace_reading("posts.csv", reading, rows)


def record_days(reading, days):
    start = datetime.date.fromisoformat(days["start"])
    imp, fol = days["impressions_cumulative"], days["followers_cumulative"]
    if len(imp) != len(fol):
        sys.exit(f"days: {len(imp)} impression points for {len(fol)} follower points")
    rows = []
    for i, (c, f) in enumerate(zip(imp, fol)):
        rows.append({"day": (start + datetime.timedelta(days=i)).isoformat(),
                     "impressions_cumulative": str(c),
                     "impressions": str(c - imp[i - 1] if i else c),
                     "followers_cumulative": str(f)})
    return replace_reading("days.csv", reading, rows)


def main():
    sys.stdout.reconfigure(errors="replace")  # a console without UTF-8 must never stop a run halfway
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for key in ("reading", "posts", "totals", "days"):
        if key not in data:
            sys.exit(f"reading JSON: the key {key!r} is missing (see the format at the top of this script)")
    for key in ("start", "impressions_cumulative", "followers_cumulative"):
        if key not in data["days"]:
            sys.exit(f"reading JSON: the key 'days.{key}' is missing")
    reading = data["reading"]
    datetime.date.fromisoformat(reading)
    print(f"posts.csv: {record_posts(reading, data['posts'])} rows for {reading}")
    totals = {k: cell(v) for k, v in data["totals"].items()}
    print(f"totals.csv: {replace_reading('totals.csv', reading, [totals])} row")
    print(f"days.csv: {record_days(reading, data['days'])} rows")


if __name__ == "__main__":
    main()
