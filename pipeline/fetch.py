"""Fetch each show's RSS feed and the transcripts the show itself publishes (Podcasting 2.0 <podcast:transcript>).

    python3 pipeline/fetch.py [--shows slug,slug] [--episodes 10]

Writes only to the cache folder (.cache/ by default, AUDIOSAGE_CACHE to override), which the workflow keeps between
runs: feeds/<slug>.json (validators for conditional requests), shows/<slug>.json (the latest episodes and their
metadata) and parsed/<slug>/<episode>.json (timed segments). Transcripts are never committed or published.

Fails safe per show: a feed or transcript that is slow, missing or malformed is retried, then skipped with a
warning, and that show keeps its cached episodes (and its last published stats).
"""
import argparse
import datetime
import email.utils
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcripts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("AUDIOSAGE_CACHE") or ROOT / ".cache")
UA = "audiosage-podcaster-dashboards/1.0 (+https://github.com/theguysaccount/audiosage-podcaster-dashboards)"
NS = {"podcast": "https://podcastindex.org/namespace/1.0", "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
      "content": "http://purl.org/rss/1.0/modules/content/"}
PREFERRED = ["text/vtt", "application/x-subrip", "application/srt", "text/srt", "application/json"]
MAX_FEED = 80_000_000
MAX_ITEMS = 80
RERUN = re.compile(r"\b(replay|rerun|rewind|best of|best bits|encore|throwback)\b", re.I)
MAX_TRANSCRIPT = 8_000_000
RUN_BUDGET_S = int(os.environ.get("AUDIOSAGE_BUDGET_S", "1500"))
_started = time.time()


def request(url, headers=None, limit=None, attempts=3, timeout=40):
    last = None
    for i in range(attempts):
        if i:
            time.sleep(5 * i)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read(limit + 1 if limit else -1)
                if limit and len(body) > limit:
                    raise ValueError(f"larger than {limit} bytes")
                return r.status, dict(r.headers), body
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, dict(e.headers), b""
            last = e
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
    raise RuntimeError(f"{url}: {last}")


def text(el, path):
    found = el.find(path, NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def iso_date(raw):
    try:
        return email.utils.parsedate_to_datetime(raw).astimezone(datetime.timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None


def parse_duration(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        parts = [float(p) for p in raw.split(":")]
    except ValueError:
        return None
    secs = 0.0
    for p in parts:
        secs = secs * 60 + p
    return int(secs)


def _channel_info(ch):
    image = ch.find("itunes:image", NS)
    return {"title": text(ch, "title"), "link": text(ch, "link"), "author": text(ch, "itunes:author"),
            "image": image.get("href") if image is not None else None}


def _item_info(it):
    enc = it.find("enclosure")
    guid = text(it, "guid") or (enc.get("url") if enc is not None else "") or text(it, "title")
    trs = [{"url": t.get("url"), "type": (t.get("type") or "").lower(), "language": t.get("language"), "rel": t.get("rel")}
           for t in it.findall("podcast:transcript", NS) if t.get("url")]
    persons = [{"name": (p.text or "").strip(), "role": (p.get("role") or "host").lower(), "href": p.get("href")}
               for p in it.findall("podcast:person", NS) if (p.text or "").strip()]
    return {"id": hashlib.sha1(guid.encode("utf-8")).hexdigest()[:12], "title": text(it, "title"), "date": iso_date(text(it, "pubDate")),
            "link": text(it, "link") or None, "audio": enc.get("url") if enc is not None else None,
            "duration": parse_duration(text(it, "itunes:duration")), "transcripts": trs, "persons": persons,
            "episode_type": text(it, "itunes:episodeType") or "full"}


def parse_feed(xml_bytes):
    """Parse a whole feed (used by the tests and for small feeds)."""
    root = ET.fromstring(xml_bytes)
    ch = root.find("channel")
    if ch is None:
        raise ValueError("not an RSS feed")
    return {**_channel_info(ch), "items": [_item_info(it) for it in ch.findall("item")]}


def read_feed(response, max_items=MAX_ITEMS, chunk=262144):
    """Stream a feed and stop after the newest `max_items` items: some feeds run to tens of megabytes."""
    parser = ET.XMLPullParser(events=("start", "end"))
    root, items, total = None, [], 0
    while len(items) < max_items:
        data = response.read(chunk)
        if not data:
            break
        total += len(data)
        if total > MAX_FEED:
            raise ValueError(f"feed larger than {MAX_FEED} bytes before {max_items} items")
        parser.feed(data)
        for event, el in parser.read_events():
            if event == "start" and root is None:
                root = el
            elif event == "end" and el.tag == "item":
                items.append(_item_info(el))
                el.clear()
                if len(items) >= max_items:
                    break
    if root is None or root.find("channel") is None:
        raise ValueError("not an RSS feed")
    return {**_channel_info(root.find("channel")), "items": items}


def best_transcript(item):
    """The show's own timed transcript, preferring WebVTT, then SRT, then JSON. None if only untimed text exists."""
    ranked = sorted((t for t in item["transcripts"] if t["type"] in PREFERRED and t.get("rel") != "captions-only"),
                    key=lambda t: PREFERRED.index(t["type"]))
    return ranked[0] if ranked else None


def fetch_show(show, episodes=10):
    slug = show["slug"]
    meta_path = CACHE / "feeds" / f"{slug}.json"
    parsed_path = CACHE / "feeds" / f"{slug}.parsed.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() and parsed_path.exists() else {}
    headers = {"User-Agent": UA}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("modified"):
        headers["If-Modified-Since"] = meta["modified"]
    feed, last = None, None
    for attempt in range(3):
        if attempt:
            time.sleep(5 * attempt)
        try:
            with urllib.request.urlopen(urllib.request.Request(show["feed"], headers=headers), timeout=60) as r:
                feed = read_feed(r)
                new_meta = {"etag": r.headers.get("ETag"), "modified": r.headers.get("Last-Modified")}
            break
        except urllib.error.HTTPError as e:
            if e.code == 304 and parsed_path.exists():
                feed = json.loads(parsed_path.read_text())
                new_meta = meta
                break
            last = e
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, OSError, ValueError, ET.ParseError) as e:
            last = e
    if feed is None:
        raise RuntimeError(f"{show['feed']}: {last}")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    parsed_path.write_text(json.dumps(feed, ensure_ascii=False))
    meta_path.write_text(json.dumps(new_meta))
    chosen, problems = [], []
    include = re.compile(show["include_titles"]) if show.get("include_titles") else None
    exclude = re.compile(show["exclude_titles"]) if show.get("exclude_titles") else None
    for item in feed["items"]:
        # Network feeds mix in other shows, replays and best-ofs; count only the show's own new episodes.
        title = item["title"] or ""
        if RERUN.search(title) or (include and not include.search(title)) or (exclude and exclude.search(title)):
            continue
        if len(chosen) >= episodes or time.time() - _started > RUN_BUDGET_S:
            break
        if item["episode_type"] in ("trailer", "bonus") or not item["date"]:
            continue
        tr = best_transcript(item)
        if not tr:
            continue
        out = CACHE / "parsed" / slug / f"{item['id']}.json"
        if not out.exists():
            try:
                _, h, raw = request(tr["url"], limit=MAX_TRANSCRIPT, attempts=2)
                segments = transcripts.parse(raw.decode("utf-8", "replace"), tr["type"] or h.get("Content-Type", ""))
            except Exception as e:
                problems.append(f"{item['title'][:50]}: {e}")
                continue
            if len(segments) < 20:
                problems.append(f"{item['title'][:50]}: transcript has no usable timing")
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(segments, ensure_ascii=False))
            time.sleep(1)
        chosen.append({k: item[k] for k in ("id", "title", "date", "link", "audio", "duration", "persons")} | {"transcript": tr["url"], "transcript_type": tr["type"]})
    record = {"slug": slug, "fetched": datetime.datetime.now(datetime.timezone.utc).date().isoformat(), "title": feed["title"],
              "link": feed["link"], "author": feed["author"], "image": feed["image"], "episodes": chosen}
    (CACHE / "shows").mkdir(parents=True, exist_ok=True)
    (CACHE / "shows" / f"{slug}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1))
    # Drop parsed transcripts that fell out of the window, so the cache stays small.
    keep = {e["id"] for e in chosen}
    for f in (CACHE / "parsed" / slug).glob("*.json") if (CACHE / "parsed" / slug).exists() else []:
        if f.stem not in keep:
            f.unlink()
    return record, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shows", default="")
    ap.add_argument("--episodes", type=int, default=10)
    args = ap.parse_args()
    shows = json.loads((ROOT / "data" / "shows.json").read_text(encoding="utf-8"))["shows"]
    if args.shows:
        wanted = set(args.shows.split(","))
        shows = [s for s in shows if s["slug"] in wanted]
    ok = 0
    for show in shows:
        if show.get("paused"):
            print(f"{show['slug']}: paused ({show['paused']})")
            continue
        try:
            record, problems = fetch_show(show, args.episodes)
            ok += 1
            print(f"{show['slug']}: {len(record['episodes'])} episodes with timed transcripts")
            for p in problems[:5]:
                print(f"::warning::{show['slug']}: {p}")
        except Exception as e:
            print(f"::warning::{show['slug']}: feed skipped, keeping its last data: {e}")
        time.sleep(2)
    print(f"fetched {ok} of {len(shows)} shows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
