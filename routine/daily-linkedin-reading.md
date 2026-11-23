# The daily reading: a scheduled task for Claude Code

This is the prompt of the task that runs every morning on my computer. It opens my LinkedIn analytics in Chrome, read-only, records the numbers, archives what I published, and rebuilds the dashboard.

**What it needs.** Everything in the README's "What you need": the Claude desktop app on a direct Anthropic plan, the Claude in Chrome extension connected and signed in to the same organization as Claude Code, LinkedIn signed in in that browser, and Python 3.10 or later. At the scheduled time, the app must be running, the browser open and the computer awake: a scheduled task does not run while the computer sleeps (the app has a setting to keep it awake).

**How to install it.**

1. In the desktop app, Code tab, click Scheduled in the sidebar and create a task. Paste everything below the line as its instructions, and pick your copy of this repo as its local folder.
2. Replace every `<REPO>` with the absolute path of that copy, with forward slashes (for example `D:/code/linkedin-content-hub`). On macOS or Linux, also replace `python` with `python3` in steps 6, 7 and 8.
3. Schedule it daily or on weekdays, at an hour your computer is on. Mine runs at 9:30.
4. Set the task's permission mode to Accept edits: it writes two files in `inbox/` every day.
5. Click Run now and stay in front of it. Approve each prompt with "always allow", and allow linkedin.com when Claude in Chrome asks. Every command below is fixed text and runs every day; Anthropic's docs say later runs then skip most prompts, so watch the first scheduled run too.

**If your LinkedIn is not in French.** The snippets in steps 4 and 5 look for the words of a French interface: « Découverte » and « Impressions », « relations », « Membres touchés », « Vues du profil », « Abonnés gagnés », « Réactions », « Commentaires », « Enregistrements », and « a publié ce contenu » around the post text. That is the only version I have tested. On your first run by hand, if the task stops because the labels don't match, ask Claude to read the text of one post's analytics page and rewrite these patterns with your interface's words, then save the edited prompt in your task.

**What it never does.** It never publishes, comments, reacts, sends or clicks anything on LinkedIn. You write and publish every post yourself.

---

You do today's LinkedIn reading for my content hub. Read-only on LinkedIn: you never publish, comment, react, send or click anything on a post or a profile. One command per call, with absolute paths, written exactly as below.

## 1. The repo up to date

Run `git -C "<REPO>" pull --ff-only`. If it fails, carry on with the local copy and say so in your report.

## 2. Chrome

Call `mcp__claude-in-chrome__tabs_context_mcp` with `createIfEmpty: true`, then `mcp__claude-in-chrome__tabs_create_mcp`: that tab is yours. If the Chrome tools don't answer, or a LinkedIn page shows a sign-in screen, stop there: write one line, "LinkedIn reading not done: <the reason>", and write nothing else.

To read a page: `navigate` to the address, `computer` with action `wait` for 3 seconds (otherwise you read the previous page), then `javascript_tool`. A script returns about 1,000 characters at most: keep long text in `window` and read it in slices. Group these steps in `mcp__claude-in-chrome__browser_batch`.

## 3. The list of posts

Page: `https://www.linkedin.com/analytics/creator/top-posts/?metricType=IMPRESSIONS&timeRange=past_90_days`. The post ids:

```
const ids=[...new Set([...document.querySelectorAll('a[href*="urn:li:activity:"]')].map(a=>a.href.match(/activity:(\d+)/)[1]))]; window.__ids=ids; ids.length
```

Keep only the posts I published: the list also holds posts I reposted, which show another author; drop them. A post's date is `new Date(Number(BigInt(id) >> 22n))`, in UTC. The known posts are the `id` column of `<REPO>/stats/posts.csv` (read it with Read; it may not exist yet). A new post is one of mine whose id is not there.

## 4. Each post

For each post you kept, open `https://www.linkedin.com/analytics/post-summary/urn:li:activity:<id>/`, wait 3 seconds, then run:

```
(()=>{const t=(document.querySelector('main')||document.body).innerText.normalize('NFC').replace(/\s+/g,' ').replace(/(\d)[\s\u202f\u00a0](\d{3})/g,'$1$2');const g=r=>{const m=t.match(r);return m?m[1]:''};return [location.pathname.match(/\d{19}/)[0],g(/couverte (\d+) Impressions/),g(/relations\) (\d+) ?%/),g(/(\d+) Membres touch/),g(/(\d+) Vues du profil/),g(/(\d+) Abonn\S+ gagn/),g(/actions (\d+)/),g(/Commentaires (\d+)/),g(/Enregistrements (\d+)/)].join(',')})()
```

It returns, in this order: id, impressions, share in my network (%), members reached, profile views, followers gained, reactions, comments, saves. An empty value means LinkedIn doesn't show it today (often the case for members reached): write `null`, never copy it from an earlier reading. If the impressions are empty, read the page again once after 5 seconds. If they are still empty for every post, the labels no longer match the page: stop there, write nothing, and say so in one line.

A new post also needs its `format`: `document` if the list of posts shows a page count under it, `image` or `video` if the post carries one, otherwise `text`. If you are unsure, open `https://www.linkedin.com/feed/update/urn:li:activity:<id>/` and look. Say in your report which format you chose and why.

**The text of posts without an archive.** A post has no archive when it is new, or when the `archive` column of its row in the latest reading of `posts.csv` is empty. For each of them, on the same analytics page, keep its full text:

```
const t=(document.querySelector('main')||document.body).innerText.normalize('NFC'); const m=t.match(/a publié ce contenu[^\n]*\n+([\s\S]*?)\n+Découverte\n/); window.__txt=m?m[1]:''; window.__txt.length
```

then read it in slices of 800 characters, `JSON.stringify(window.__txt.slice(0,800))`, `JSON.stringify(window.__txt.slice(800,1600))`, and so on up to the length returned. Put the slices back together without changing anything: no space, no line break, no `⠀` character (U+2800, the blank line of LinkedIn). If the length is 0 (a page that didn't load), read again once after 5 seconds, then leave that post aside and say so. The first line of the text is the post's `first_line`.

## 5. Totals and curves

Page: `https://www.linkedin.com/analytics/creator/content/?metricType=IMPRESSIONS&timeRange=past_90_days`. The text of `main` gives the total impressions, their change against the previous 90 days, and under the engagement block the reactions, comments, reposts and saves; members reached and the share in my network only when the page shows them. The day-by-day curve:

```
const L=[...document.querySelectorAll('[aria-label]')].map(e=>e.getAttribute('aria-label')).filter(s=>/\d{4},/.test(s)&&/Impressions\.?$/.test(s.trim())); window.__pts=L; [L.length, L[0], L[L.length-1]]
```

then `window.__pts.map(s=>s.match(/,\s*([\d\s\u202f\u00a0]+)\./)[1].replace(/\D/g,'')).join(' ')`. You need 90 points, cumulative; the first `aria-label` gives the first day.

Page: `https://www.linkedin.com/analytics/creator/audience/?timeRange=past_90_days`. The text gives the total number of followers. The curve of new followers, cumulative, reads like the previous one, with the `/\d{4},/` filter alone; its last point is the number of followers gained over 90 days.

Close your tab (`tabs_close_mcp`).

## 6. Record the reading

With Write, create `<REPO>/inbox/reading.json` (replace it if it exists), in the format described at the top of `<REPO>/scripts/record_stats.py` (read that header; an example is in `<REPO>/examples/reading-2026-11-23.json`): `reading` (today's date), `posts` (one object per post, with `format` and `first_line` for a new post), `totals`, and `days` (`start` and the two lists of 90 numbers). A missing value is `null`. Then:

    python -I "<REPO>/scripts/record_stats.py" "<REPO>/inbox/reading.json"

If it stops on an error, fix the JSON and run it again: a reading of the same day replaces the previous one. When it passes, check in its output that posts.csv has as many rows as posts you kept, and days.csv 90.

## 7. Archive what I published

With Write, create `<REPO>/inbox/posts-read.json` (replace it if it exists): `{"reading": "<YYYY-MM-DD>", "posts": [{"id": "<id>", "text": "<the text put back together>"}]}`, with an empty `posts` list if you read no text today. Then:

    python -I "<REPO>/scripts/archive_posts.py" "<REPO>/inbox/posts-read.json"

Its output says, for each post, the archive written, the draft it came from (or "no matching draft") and the roadmap line ticked off. Never fix `posts/`, `roadmap.json` or `stats/` by hand: if the script stops, say why in your report.

## 8. Rebuild the dashboard

    python -I "<REPO>/scripts/build_dashboard.py"

## 9. Commit

    git -C "<REPO>" add stats posts roadmap.json
    git -C "<REPO>" commit -m "Daily LinkedIn reading"
    git -C "<REPO>" push

If there is no remote, skip the push.

## 10. Report

Three lines at most: the number of posts read, and each post archived (its first line, its draft or "no matching draft", and "no roadmap line names this draft" when the script says so); impressions and followers gained over 90 days; what could not be done.
