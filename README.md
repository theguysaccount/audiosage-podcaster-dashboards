# AudioSage

What top podcasters actually say: per-show dashboards of signature phrases, talk pace, vocabulary, questions,
topics and guests, counted from the transcripts each show publishes in its own podcast feed. Every signature phrase
links to the moments it was said. Statistics and short attributed quotes only; no transcripts are republished, and
no one gets a bias or opinion label.

**Live:** https://theguysaccount.github.io/audiosage-podcaster-dashboards/

## Run, test, deploy

```bash
python3 pipeline/fetch.py        # read feeds and the shows' own transcripts into .cache/ (not committed)
python3 pipeline/analyze.py      # write data/stats/*.json
python3 -m pip install pillow    # optional locally: share cards
python3 pipeline/build.py        # build into dist/
scripts/e2e.sh                   # serve dist/ under the production path and drive it in headless Chrome
python3 -m unittest discover -s tests
```

GitHub Actions refreshes twice a week and deploys (`.github/workflows/refresh.yml`). `OPERATIONS.md` covers every job,
how it fails safe, adding shows, opt-outs and the switches (domain, sponsor, analytics).

## Licenses

Code: MIT. Statistics: CC BY 4.0. Quotes and transcripts belong to the shows; each quote links to its source.
