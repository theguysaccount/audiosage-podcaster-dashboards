#!/usr/bin/env bash
# Drive the real pages in headless Chrome (site/assets/selftest.js): the leaderboard (including sorting), one show
# dashboard and one comparison, each checked against the data the site was built from.
#   scripts/e2e.sh                  # serve dist/ locally under the production path and test it
#   scripts/e2e.sh https://host/x/  # test a live site
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")}"
base="${1:-}"
dist="${DIST:-dist}"
work="$(mktemp -d)"
trap 'kill ${srv:-} 2>/dev/null || true; rm -rf "$work"' EXIT
if [ -z "$base" ]; then
  site_path="$(python3 -c 'import os,urllib.parse;u=os.environ.get("SITE_URL","https://theguysaccount.github.io/audiosage-podcaster-dashboards");print(urllib.parse.urlparse(u).path.strip("/"))')"
  port="${PORT:-9365}"
  while (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; do port=$((port + 1)); done
  root="$work/root"; mkdir -p "$root"
  if [ -n "$site_path" ]; then mkdir -p "$root/$(dirname "$site_path")"; ln -s "$(cd "$dist" && pwd)" "$root/$site_path"; else root="$(cd "$dist" && pwd)"; fi
  python3 -m http.server "$port" --bind 127.0.0.1 --directory "$root" >/dev/null 2>&1 &
  srv=$!
  base="http://127.0.0.1:$port/${site_path:+$site_path/}"
  for _ in $(seq 1 50); do curl -s -o /dev/null "$base" && break; sleep 0.1; done
fi
meta="$(curl -fsS "${base}data/meta.json")"
show="$(printf '%s' "$meta" | python3 -c 'import json,sys;print(json.load(sys.stdin)["sample_show"])')"
pair="$(printf '%s' "$meta" | python3 -c 'import json,sys;print(json.load(sys.stdin)["sample_compare"])')"
fail=0
for target in "?selftest=1" "show/$show/?selftest=1" "compare/$pair/?selftest=1" "method/?selftest=1"; do
  out="$("$CHROME" --headless=new --disable-gpu --no-sandbox --no-first-run --no-default-browser-check \
    --user-data-dir="$work/profile-$RANDOM" --virtual-time-budget=30000 --dump-dom "${base}${target}" 2>/dev/null || true)"
  status="$(printf '%s' "$out" | grep -o 'data-selftest="[^"]*"' | head -1 || true)"
  echo "/${target}: ${status:-no result}"
  printf '%s\n' "$out" | sed -n '/<pre id="selftest">/,/<\/pre>/p' | sed 's/<[^>]*>//g' | sed 's/^/    /' | head -10
  case "$status" in *'"pass"'*) ;; *) fail=1 ;; esac
done
exit "$fail"
