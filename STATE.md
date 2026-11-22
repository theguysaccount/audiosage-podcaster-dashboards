# State

- Before this repo: one note ("audiosage fun dashboards / visualizations of podcasters ranked on biases, beliefs,
  phrases, semantic") and a 2026 portfolio line marking an earlier "Audiosage" project inactive. No code or site found.
- Reused: Pages deploy, IndexNow, keep-alive, self-test and ops-alert patterns from sibling ventures under
  theguysaccount; the CDP screenshot script (idea-locator-prophet-fund).
- Works now: 12 show dashboards (signature phrases with quotes and moment links, talk pace, vocabulary variety,
  questions, topics, speakers where the transcript names them, guests from the feed, episodes with links to the
  show's own transcript), a sortable leaderboard, 66 head-to-head comparison pages with share cards, method page.
- Runs by itself: refresh and deploy twice a week, weekly self-test that restarts stale refreshes, keep-alive. The
  scheduled trigger is proven: the self-test's first scheduled run passed on 2026-11-22 (run 45051599880).
- Domain: live on dashboards.audiosage.org since 2026-11-22 (audiosage.org itself still serves its own site).
- Needs a human: sponsor, analytics, Search Console (OPERATIONS.md keys).
- Known limits: only shows that publish timed transcripts qualify (24 of Apple's top 200 in November 2026); machine
  transcripts have errors; ad filtering is heuristic.
