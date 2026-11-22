# Operations

AudioSage is a static site on GitHub Pages. Each week GitHub Actions reads every show's podcast feed and the
transcripts the show publishes itself (`podcast:transcript`), recounts the statistics, and redeploys. Transcripts
are cached between runs in the Actions cache and are never committed or published; only statistics and short
attributed quotes are (`data/stats/*.json`).

**Live:** https://dashboards.audiosage.org/ (since 2026-11-22; the old github.io address redirects there)
**Repo:** https://github.com/theguysaccount/audiosage-podcaster-dashboards

## Automated jobs

| Job | Workflow | When | What it does | How it fails safe |
|---|---|---|---|---|
| Refresh and deploy | `refresh.yml` | Tuesdays 05:37 UTC, Fridays 17:11 UTC, every push to `main`, by hand | On schedule or by hand: reads each show's feed (streaming, newest 80 items), keeps the show's own new episodes (per-show title rules drop replays and other shows in network feeds), downloads new timed transcripts (WebVTT/SRT/JSON), recounts everything (`pipeline/fetch.py`, `pipeline/analyze.py`). Then: tests, build with share cards, four end-to-end checks in headless Chrome, commits the new statistics, deploys, the same checks live, IndexNow. | A feed or transcript that fails is retried, then skipped with a warning; the show keeps its cached episodes and its last published numbers. A show with fewer than 3 usable episodes keeps its previous stats file. Any failed test or check stops the run before the commit and deploy. A run-time budget (25 minutes of fetching) keeps one slow host from eating the job. Safe to re-run. |
| Weekly self-test | `selftest.yml` | Sundays 14:53 UTC, by hand | Tests; the live end-to-end checks; every sitemap page answers 200 with its canonical; the data file matches the sitemap; freshness of every show. | A show not updated for 9 days starts `refresh.yml`. If no show has been updated for 21 days, or a page breaks, the run fails and opens (or comments on) one `ops-alert` issue; GitHub emails the owner. |
| Keep-alive | `selftest.yml` → `scripts/keepalive.sh` | weekly | Re-enables scheduled workflows (except any turned off by hand); empty `[skip ci]` commit after 45 quiet days. | The weekly statistics commits normally keep the repo active anyway. |

The cost is small: no audio is downloaded or transcribed, only feeds and text transcripts. A refresh takes a few
minutes; public repositories get Actions minutes free.

## What to watch

- `ops-alert` issues, and the warnings in each refresh's log (a show whose feed or transcripts stopped working).
- `correction` issues: wrong numbers or quotes, and opt-out requests. **Opt-outs come first**: set `"paused": "<reason>"`
  on the show in `data/shows.json` and push. Its dashboard and comparisons come down at that deploy.
- A show that stops publishing transcripts drops below 3 usable episodes and keeps its last numbers; the page shows
  when they're from. After a few weeks, pause it or swap in another show.

## Adding or swapping shows

`data/shows.json` lists the shows. A show qualifies when its feed carries timed transcripts (`podcast:transcript`
with `text/vtt`, `application/srt` or `application/json`). `candidates_not_yet_included` lists qualifying shows from
the November 2026 survey of Apple's top 200. For a network feed that mixes in other shows, add `include_titles` or
`exclude_titles` (regular expressions on episode titles). Then run `python3 pipeline/fetch.py --shows <slug>` and
`python3 pipeline/analyze.py`, check the dashboard, and push.

## Keys Jack can turn later

### 1. Custom domain (done: dashboards.audiosage.org)

audiosage.org already serves a site ("AudioSage - AI-Powered Podcast Analytics & Insights", SiteGround, A record
216.150.1.1, checked 2026-11-22). Nothing may replace it, so the dashboards are on a subdomain,
`dashboards.audiosage.org`. The domain rollout session put the site there on 2026-11-22 with the steps below (DNS at
SiteGround, Pages custom domain with HTTPS enforced, `SITE_URL`, redeploy). The base URL is one setting: the
repository variable `SITE_URL`. Canonical URLs, the sitemap, robots.txt, share cards, structured data, IndexNow and
the self-tests all follow it.

1. DNS (done by the domain rollout): add `CNAME dashboards → theguysaccount.github.io` in the
   audiosage.org zone (SiteGround today). Leave every existing record alone.
2. `gh api -X PUT repos/theguysaccount/audiosage-podcaster-dashboards/pages -f cname=dashboards.audiosage.org`, then once
   the certificate is issued `gh api -X PUT repos/theguysaccount/audiosage-podcaster-dashboards/pages -F https_enforced=true`.
3. `gh variable set SITE_URL -b https://dashboards.audiosage.org -R theguysaccount/audiosage-podcaster-dashboards`
4. `gh workflow run refresh.yml -R theguysaccount/audiosage-podcaster-dashboards -f refresh=false`

To move it again, repeat steps 1 to 4 with the new host. To go back to github.io: `gh variable delete SITE_URL -R
theguysaccount/audiosage-podcaster-dashboards`, `gh api -X PUT repos/theguysaccount/audiosage-podcaster-dashboards/pages -F
cname=null`, then step 4. Leave the DNS record until the redeploy is live.

A link from the existing audiosage.org site to the dashboards would connect the two; that site is outside this repo.

### 2. Money

Pages is non-commercial. One slot is built in: a sponsor box on the leaderboard, hidden until set. Set `SPONSOR_URL`
(and optionally `SPONSOR_LABEL`) and redeploy. Advertiser reports or an API tier would need other hosting and Stripe.

### 3. Analytics

Off by default. Create a GoatCounter site (cookieless), set `GOATCOUNTER_URL` = `https://<code>.goatcounter.com/count`,
redeploy. Events: `compare_pick` (**activation**: a visitor compares two shows), `copy_link`, `compare_copy`, `share`
(**the loop**), `sort`.

### 4. Search Console

Set `GOOGLE_SITE_VERIFICATION` and redeploy, then submit `/sitemap.xml`. IndexNow covers Bing and Yandex on every deploy.

### 5. More shows by transcription (optional, later)

Most top shows don't publish transcripts. Transcribing their audio (for example faster-whisper on the runner) would
widen coverage but costs far more Actions time and brings audio downloading into the job. Not done in v1 on purpose:
the brief prefers shows' own transcripts.

## Running it by hand

```bash
python3 -m unittest discover -s tests -v
python3 pipeline/fetch.py            # reads feeds and transcripts into .cache/
python3 pipeline/analyze.py          # writes data/stats/*.json and data/corpus.json
python3 pipeline/build.py && scripts/e2e.sh
scripts/e2e.sh https://dashboards.audiosage.org/
python3 scripts/check_live.py https://dashboards.audiosage.org
gh workflow run refresh.yml -R theguysaccount/audiosage-podcaster-dashboards -f refresh=true
```
