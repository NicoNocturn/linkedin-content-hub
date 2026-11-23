"""Build dashboard.html from roadmap.json and the latest reading in stats/.

Usage: python scripts/build_dashboard.py [--out <file.html>]

The page is a single file with the data inside: open it in any browser, no server needed.
Dates and times are shown in the time zone of the browser that opens it.
"""
import csv
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "stats"
TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"


def latest(name):
    path = STATS / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    last = max(r["reading"] for r in rows)
    return [r for r in rows if r["reading"] == last]


def main():
    sys.stdout.reconfigure(errors="replace")  # a console without UTF-8 must never stop a run halfway
    args = sys.argv[1:]
    out = ROOT / "dashboard.html"
    if args[:1] == ["--out"] and len(args) == 2:
        out = Path(args[1])
    elif args:
        sys.exit(__doc__)
    roadmap_path = ROOT / "roadmap.json"
    roadmap = json.loads(roadmap_path.read_text(encoding="utf-8")) if roadmap_path.exists() else {"weeks": []}
    totals = latest("totals.csv")
    data = {
        "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "roadmap": roadmap,
        "posts": latest("posts.csv"),
        "totals": totals[0] if totals else {},
        "days": latest("days.csv"),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out.write_text(html, encoding="utf-8", newline="\n")
    reading = data["totals"].get("reading", "no reading yet")
    print(f"{out.name}: reading of {reading}, {len(data['posts'])} posts, {len(roadmap.get('weeks', []))} roadmap lines")


if __name__ == "__main__":
    main()
