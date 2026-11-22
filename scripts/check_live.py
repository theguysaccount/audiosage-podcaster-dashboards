"""Weekly health check of the live site: python3 scripts/check_live.py https://theguysaccount.github.io/audiosage-podcaster-dashboards

Every sitemap page answers 200 with its own canonical URL; stats.json parses and matches the sitemap; the IndexNow
key is served; each show's numbers are fresh. A show not updated for more than 9 days writes stale=true to
$GITHUB_OUTPUT (the workflow then starts a refresh); if every show is older than 21 days, that's an error.
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "audiosage-healthcheck/1.0 (+https://github.com/theguysaccount/audiosage-podcaster-dashboards)"


def get(url):
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return e.code, b""
            last = e
        except OSError as e:
            last = e
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def main(base):
    base = base.rstrip("/")
    errors, warnings = [], []
    status, body = get(f"{base}/sitemap.xml")
    urls = re.findall(r"<loc>([^<]+)</loc>", body.decode())
    if status != 200 or len(urls) < 5:
        errors.append(f"sitemap: status {status}, {len(urls)} URLs")
    for u in urls:
        status, page = get(u)
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', page.decode("utf-8", "replace"))
        if status != 200 or not canon or canon.group(1) != u:
            errors.append(f"{u}: status {status}, canonical {canon.group(1) if canon else None}")
    shows = json.loads(get(f"{base}/data/stats.json")[1])["shows"]
    for s in shows:
        if f"{base}/show/{s['slug']}/" not in urls:
            errors.append(f"{s['slug']} is missing from the sitemap")
    today = datetime.datetime.now(datetime.timezone.utc).date()
    ages = {s["slug"]: (today - datetime.date.fromisoformat(s["updated"])).days for s in shows}
    for slug, age in ages.items():
        if age > 9:
            warnings.append(f"{slug} was last updated {age} days ago")
    if ages and min(ages.values()) > 21:
        errors.append("no show has been updated for three weeks: the weekly refresh is failing")
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"stale={'true' if any(a > 9 for a in ages.values()) else 'false'}\n")
    key = (ROOT / "site" / "indexnow-key.txt").read_text().strip()
    if get(f"{base}/{key}.txt")[1].decode().strip() != key:
        errors.append("IndexNow key file not served")
    print(f"checked {len(urls)} pages and {len(shows)} shows (newest update {min(ages.values()) if ages else '-'} days ago)")
    for w in warnings:
        print(f"::warning::{w}")
    for e in errors:
        print(f"::error::{e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
