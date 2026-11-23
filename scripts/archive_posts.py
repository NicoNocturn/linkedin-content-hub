"""Archive the posts you published, and tick them off the roadmap.

Usage: python scripts/archive_posts.py <posts-read.json>

The scheduled task reads the text of each post that has no archive yet, on the post's analytics page,
and writes it to a JSON file (example: examples/posts-read-2026-11-23.json):

  {"reading": "YYYY-MM-DD", "posts": [{"id": "7397...", "text": "the post as published"}]}

The task runs it every day, with an empty list when there is nothing to archive.

For each post, the script:
  1. finds the draft it came from in posts/drafts/ (same first sentence, otherwise the closest text);
  2. writes posts/<date>-<slug>.md: the text as published, then the original draft, so you can see
     what you changed at the last minute;
  3. deletes the draft (its text now lives in the archive);
  4. marks the roadmap line that names this draft as published, in roadmap.json.
A post with no matching draft is archived too: the dashboard shows it as published off plan.
Run scripts/record_stats.py first: the date, format and first line come from today's reading.
A post that already has an archive is skipped.
"""
import csv
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DRAFTS = POSTS_DIR / "drafts"
ROADMAP = ROOT / "roadmap.json"
POSTS_CSV = ROOT / "stats" / "posts.csv"
BLANK = "⠀"  # LinkedIn keeps an empty line alive with this braille blank


def latest_reading():
    if not POSTS_CSV.exists():
        sys.exit("stats/posts.csv not found: run record_stats.py first")
    with open(POSTS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    last = max((r["reading"] for r in rows), default=None)
    return fields, rows, last


def front_matter(md):
    text = md.read_text(encoding="utf-8")
    meta = {}
    if text.startswith("---"):
        for line in text.split("---", 2)[1].splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip().strip('"')
    return meta


def archived_ids():
    out = {}
    for md in POSTS_DIR.glob("*.md"):
        m = re.search(r"activity:(\d{19})", front_matter(md).get("url", ""))
        if m:
            out[m.group(1)] = md
    return out


def normalize(s):
    s = unicodedata.normalize("NFC", s).replace(BLANK, " ").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def first_sentence(s):
    return normalize(re.split(r"[.!?:\n]", s.strip(), maxsplit=1)[0])


def draft_of(text):
    """The draft this post came from: same first sentence, otherwise the closest one above 0.6."""
    best, score = None, 0.0
    for draft in sorted(DRAFTS.glob("*.txt")):
        d = draft.read_text(encoding="utf-8")
        s = 1.0 if first_sentence(d) == first_sentence(text) else \
            difflib.SequenceMatcher(None, normalize(d)[:600], normalize(text)[:600]).ratio()
        if s > score:
            best, score = draft, s
    return (best, score) if score >= 0.6 else (None, score)


def slug_of(text):
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "-".join(normalize(ascii_text).split()[:6]) or "post"


def tick_off(draft_name, post_id, published):
    """The roadmap line that names this draft becomes published."""
    if not ROADMAP.exists():
        return "no roadmap.json"
    roadmap = json.loads(ROADMAP.read_text(encoding="utf-8"))
    for line in roadmap.get("weeks", []):
        if line.get("draft") == draft_name:
            line.update({"status": "published", "post_id": post_id, "published": published})
            ROADMAP.write_text(json.dumps(roadmap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            return f"roadmap line \"{line.get('post', '')}\" ticked off"
    return "no roadmap line names this draft"


def archive(data):
    if not data["posts"]:
        print("no post to archive today")
        return
    fields, rows, last = latest_reading()
    if last is None:
        sys.exit("stats/posts.csv has no post yet: run record_stats.py first")
    today = {r["id"]: r for r in rows if r["reading"] == last}
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    known = archived_ids()
    done = {}
    for p in data["posts"]:
        pid, text = str(p["id"]), unicodedata.normalize("NFC", p["text"]).strip()
        if pid in known:
            print(f"{pid}: already archived in posts/{known[pid].name}, skipped")
            continue
        if pid not in today:
            sys.exit(f"{pid}: not in the latest reading of stats/posts.csv, run record_stats.py first")
        if not text:
            sys.exit(f"{pid}: empty text")
        row = today[pid]
        date = row["published_at"][:10]
        draft, score = draft_of(text)
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", draft.stem) if draft else slug_of(text)
        name = f"{date}-{slug}.md"
        if (POSTS_DIR / name).exists():
            name = f"{date}-{slug}-{pid[-4:]}.md"
        verbatim = "\n".join("" if ln.strip(BLANK + " ") == "" else ln.rstrip() for ln in text.splitlines())
        title = text.splitlines()[0].strip().replace('"', "'")
        body = [
            "---",
            f'title: "{title}"',
            f"published_at: {row['published_at']}",
            f'url: "https://www.linkedin.com/feed/update/urn:li:activity:{pid}/"',
            f"format: {row['format']}",
            f'draft: "{draft.name if draft else "none"}"',
            f"read_on: {data['reading']}",
            "---",
            "",
            verbatim,
            "",
        ]
        if draft:
            body += ["---", "", "## Original draft", "",
                     f"posts/drafts/{draft.name} as it was when you published, deleted once copied here.", "",
                     draft.read_text(encoding="utf-8").strip(), ""]
        (POSTS_DIR / name).write_text("\n".join(body), encoding="utf-8", newline="\n")
        done[pid] = name
        if draft:
            how = "same first sentence" if score == 1.0 else f"similarity {score:.2f}"
            print(f"{pid}: archived in posts/{name}, from draft {draft.name} ({how})")
            draft.unlink()
            print(f"   {tick_off(draft.name, pid, date)}")
        else:
            print(f"{pid}: archived in posts/{name}, no matching draft")
    if done:
        for r in rows:
            if r["reading"] == last and r["id"] in done:
                r["archive"] = f"posts/{done[r['id']]}"
        with open(POSTS_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"stats/posts.csv: archive filled for {len(done)} post(s)")


def main():
    sys.stdout.reconfigure(errors="replace")  # a console without UTF-8 must never stop a run halfway
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    archive(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
