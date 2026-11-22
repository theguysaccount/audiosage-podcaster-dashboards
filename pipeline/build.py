"""Build the static site into dist/ from data/shows.json and data/stats/*.json.

    python3 pipeline/build.py
    SITE_URL=https://audiosage.org python3 pipeline/build.py
"""
import datetime
import hashlib
import html
import itertools
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = Path(os.environ.get("AUDIOSAGE_DATA_DIR") or ROOT / "data")
DIST = Path(os.environ.get("BUILD_DIR") or ROOT / "dist")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/") or "https://theguysaccount.github.io/audiosage-podcaster-dashboards"
BASE = urlparse(SITE_URL).path.rstrip("/") + "/"
REPO_URL = "https://github.com/theguysaccount/audiosage-podcaster-dashboards"
NAME = "AudioSage"
GOATCOUNTER_URL = os.environ.get("GOATCOUNTER_URL", "").strip()
SPONSOR_URL = os.environ.get("SPONSOR_URL", "").strip()
SPONSOR_LABEL = os.environ.get("SPONSOR_LABEL", "").strip()
GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "").strip()
TODAY = datetime.datetime.now(datetime.timezone.utc).date()
STALE_DAYS = 21

e = html.escape


def url(path=""):
    return BASE + path


def absolute(path=""):
    return SITE_URL + "/" + path


def asset(name, _cache={}):
    if name not in _cache:
        digest = hashlib.sha256((SITE / "assets" / name).read_bytes()).hexdigest()[:10]
        _cache[name] = f"{BASE}assets/{name}?v={digest}"
    return _cache[name]


def jsonld(data):
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def clock(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def moment_link(ep, at):
    """Link to the moment: the episode audio with a media fragment (#t=seconds) the browser jumps to."""
    if ep and ep.get("audio"):
        return f'{ep["audio"]}#t={int(at)}'
    return ep.get("link") if ep else None


NAV = [("", "Leaderboard"), ("compare/", "Compare"), ("method/", "Method"), ("about/", "About")]
LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#2d1b69"/>'
        '<path d="M8 20v-8M12 23V9M16 26V6M20 22v-12M24 18v-4" stroke="#ffb347" stroke-width="2.6" stroke-linecap="round"/></svg>')


def shell(*, path, title, description, body, og="assets/og/home.png", head="", scripts="", index=True):
    canonical = absolute(path)
    robots = "" if index else '<meta name="robots" content="noindex,follow">\n'
    verification = f'<meta name="google-site-verification" content="{e(GOOGLE_SITE_VERIFICATION)}">\n' if GOOGLE_SITE_VERIFICATION and path == "" else ""
    analytics = f'<script data-goatcounter="{e(GOATCOUNTER_URL)}" async src="https://gc.zgo.at/count.js"></script>\n' if GOATCOUNTER_URL else ""
    current = ' aria-current="page"'
    links = "".join(f'<a href="{url(p)}"{current if p == path else ""}>{e(label)}</a>' for p, label in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
{robots}{verification}<link rel="canonical" href="{e(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:image" content="{e(absolute(og))}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#2d1b69">
<link rel="icon" href="{url('favicon.svg')}" type="image/svg+xml">
<link rel="stylesheet" href="{asset('site.css')}">
{head}{analytics}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site"><div class="wrap"><a class="brand" href="{url()}">{LOGO}{NAME}</a><nav class="top" aria-label="Site">{links}</nav></div></header>
<main id="main"><div class="wrap">
{body}
</div></main>
<footer class="site"><div class="wrap"><nav aria-label="Footer"><a href="{url('method/')}">How the numbers are made</a><a href="{REPO_URL}/issues/new?template=correction.yml">Report a mistake</a>
<a href="{url('about/')}#shows">For shows: corrections and opting out</a><a href="{url('data/stats.json')}">Data (JSON)</a><a href="{REPO_URL}">Source on GitHub</a></nav>
<p>Counts from the transcripts each show publishes in its own podcast feed. Short quotes only, each linked to its moment. No ratings of people's views. Not affiliated with any show.</p></div></footer>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
{scripts}
<script type="module" src="{asset('page.js')}"></script>
</body>
</html>
"""


def write(path, text):
    out = DIST / path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def sponsor_box():
    if not SPONSOR_URL:
        return ""
    return (f'<aside class="box sponsor" data-sponsor><small>Sponsor</small>'
            f'<a href="{e(SPONSOR_URL)}" rel="sponsored noopener" target="_blank">{e(SPONSOR_LABEL or "Support AudioSage")}</a></aside>')


def load():
    shows = json.loads((DATA / "shows.json").read_text(encoding="utf-8"))["shows"]
    out = []
    for s in shows:
        if s.get("paused"):
            continue
        f = DATA / "stats" / f"{s['slug']}.json"
        if not f.exists():
            continue
        st = json.loads(f.read_text(encoding="utf-8"))
        st["genre"] = s.get("genre")
        st["eps"] = {ep["id"]: ep for ep in st["episodes"]}
        out.append(st)
    out.sort(key=lambda x: x["name"].lower())
    return out


def ranks(shows, key, reverse=True):
    order = sorted(shows, key=lambda s: (s[key] is None, -(s[key] or 0) if reverse else (s[key] or 0)))
    return {s["slug"]: i + 1 for i, s in enumerate(order)}


def variety_score(v):
    """Vocabulary variety as distinct words per 100 in a 500-word window."""
    return round(v * 100, 1)


def stat_tiles(s, shows):
    r_pace, r_var, r_q, r_len = ranks(shows, "pace_wpm"), ranks(shows, "variety"), ranks(shows, "questions_per_100_sentences"), ranks(shows, "minutes_median")
    n = len(shows)
    tiles = [
        ("Talk pace", f'{s["pace_wpm"]:.0f}', "words per minute", f"#{r_pace[s['slug']]} of {n} for speed"),
        ("Vocabulary variety", f'{variety_score(s["variety"]):.1f}', "different words per 100", f"#{r_var[s['slug']]} of {n}"),
        ("Questions", f'{s["questions_per_100_sentences"]:.1f}', "per 100 sentences", f"#{r_q[s['slug']]} of {n}"),
        ("Typical episode", f'{s["minutes_median"]:.0f}', "minutes (median)", f"#{r_len[s['slug']]} of {n} for length"),
    ]
    return '<ul class="tiles">' + "".join(
        f'<li><span class="k">{e(k)}</span><strong>{e(v)}</strong><span class="u">{e(u)}</span><span class="r">{e(r)}</span></li>' for k, v, u, r in tiles) + "</ul>"


def phrase_list(s, limit=12):
    items = ""
    for p in s["signature_phrases"][:limit]:
        moments = p["moments"]
        quote_html = ""
        if moments:
            m = moments[0]
            ep = s["eps"].get(m["episode"])
            link = moment_link(ep, m["at"])
            title = ep["title"] if ep else ""
            quote_html = (f'<blockquote>“{e(m["quote"])}”<footer>{e(title)}, '
                          f'{f"<a href={chr(34)}{e(link)}{chr(34)} rel={chr(34)}noopener{chr(34)} target={chr(34)}_blank{chr(34)}>▶ {clock(m[chr(97) + chr(116)])}</a>" if link else clock(m["at"])}</footer></blockquote>')
            more = []
            for m2 in moments[1:]:
                ep2 = s["eps"].get(m2["episode"])
                l2 = moment_link(ep2, m2["at"])
                if l2:
                    more.append(f'<a href="{e(l2)}" rel="noopener" target="_blank" title="{e(ep2["title"])}">▶ {clock(m2["at"])}</a>')
            if more:
                quote_html += f'<p class="note">Also said here: {" ".join(more)}</p>'
        items += (f'<li><div class="ph"><strong>“{e(p["phrase"])}”</strong> <span class="note">said {p["count"]} times, '
                  f'in {p["episodes"]} of {s["episodes_analyzed"]} episodes</span></div>{quote_html}</li>')
    return f'<ol class="phrases">{items}</ol>'


def topic_bars(s):
    top = [t for t in s["topics"] if t["per_10k"] > 0][:8]
    if not top:
        return "<p>No topic words counted.</p>"
    peak = max(t["per_10k"] for t in top)
    rows = ""
    for t in top:
        width = max(2, round(100 * t["per_10k"] / peak))
        vs = t["vs_average"]
        rel = "" if vs is None else (f'{vs:.1f}× the average show here' if vs >= 1.05 else (f'{vs:.1f}× the average' if vs <= 0.95 else "about average"))
        rows += (f'<li><span class="lbl">{e(t["topic"])}</span><span class="bar" style="--w:{width}%"></span>'
                 f'<span class="val">{t["per_10k"]:.0f} per 10,000 words · {e(rel)}</span></li>')
    return f'<ul class="bars">{rows}</ul>'


def page_show(s, shows):
    eps_rows = ""
    for ep in s["episodes"]:
        links = []
        if ep.get("link"):
            links.append(f'<a href="{e(ep["link"])}" rel="noopener" target="_blank">episode</a>')
        links.append(f'<a href="{e(ep["transcript"])}" rel="noopener" target="_blank">transcript</a>')
        if ep.get("audio"):
            links.append(f'<a href="{e(ep["audio"])}" rel="noopener" target="_blank">audio</a>')
        eps_rows += (f'<tr><td>{e(ep["date"] or "")}</td><td>{e(ep["title"])}</td><td class="num">{ep["minutes"]:.0f}</td>'
                     f'<td class="num">{ep["wpm"]:.0f}</td><td>{" · ".join(links)}</td></tr>')
    speakers = ""
    if s["speakers"]:
        rows = "".join(f'<tr><td>{e(sp["name"])}</td><td class="num">{sp["share"]:.0f}%</td><td class="num">{"" if sp["wpm"] is None else f"{sp[chr(119)+chr(112)+chr(109)]:.0f}"}</td></tr>'
                       for sp in s["speakers"])
        speakers = (f'<h2>Who does the talking</h2><p class="note">From the speaker names in the show\'s own transcripts.</p>'
                    f'<div class="scroll"><table><thead><tr><th>Speaker (as labelled)</th><th class="num">Share of words</th><th class="num">Words per minute</th></tr></thead><tbody>{rows}</tbody></table></div>')
    guests = ('<p class="note">This show\'s feed doesn\'t list guests in a machine-readable way, so none are counted.</p>' if not s["guests"] else
              '<ul class="guests">' + "".join(f'<li>{e(g["name"])} <span class="note">{g["episodes"]} episode{"s" if g["episodes"] != 1 else ""}</span></li>' for g in s["guests"]) + "</ul>")
    others = [o for o in shows if o["slug"] != s["slug"]]
    compare = "".join(f'<li><a href="{url("compare/" + pair_slug(s, o) + "/")}">{e(s["name"])} vs {e(o["name"])}</a></li>' for o in others)
    age = (TODAY - datetime.date.fromisoformat(s["updated"])).days
    stale = (f'<div class="notice"><strong>These numbers are {age} days old.</strong> The weekly update could not read this show\'s feed recently; '
             f'the figures are from {nice_date(s["updated"])}.</div>' if age > STALE_DAYS else "")
    here = absolute(f"show/{s['slug']}/")
    top_phrase = s["signature_phrases"][0]["phrase"] if s["signature_phrases"] else ""
    body = f"""<p class="crumbs"><a href="{url()}">Leaderboard</a> › {e(s["name"])}</p>
<h1>{e(s["name"])}: signature phrases, talk pace and topics</h1>
<p class="lead">Counted from the transcripts {e(s["name"])} publishes in its own podcast feed: {s["episodes_analyzed"]} recent episodes
({nice_date(s["first_episode"])} to {nice_date(s["latest_episode"])}), {s["words_analyzed"]:,} words. Updated {nice_date(s["updated"])}.</p>
{stale}
{stat_tiles(s, shows)}
<p class="cta"><button type="button" class="quiet" data-copy="{e(here)}">Copy link</button> <button type="button" class="quiet" data-share>Share</button>
<label class="skip" for="vs">Compare with</label><select class="jump" id="vs"><option value="">Compare with…</option>{"".join(f'<option value="{url("compare/" + pair_slug(s, o) + "/")}">{e(o["name"])}</option>' for o in others)}</select></p>
<h2>Signature phrases</h2>
<p class="note">Phrases this show says much more often than the other {len(shows) - 1} shows here, ranked by how distinctive they are. Each has a short quote and a link to the moment in the episode audio.</p>
{phrase_list(s)}
<h2>Topics</h2>
<p class="note">How often words from each topic come up, per 10,000 words, compared with the average show on AudioSage.</p>
{topic_bars(s)}
{speakers}
<h2>Guests</h2>
{guests}
<h2>Episodes analyzed</h2>
<div class="scroll"><table><thead><tr><th>Date</th><th>Episode</th><th class="num">Minutes</th><th class="num">Words/min</th><th>The show's own pages</th></tr></thead><tbody>{eps_rows}</tbody></table></div>
<h2>Compare</h2>
<ul class="pairs">{compare}</ul>
{sponsor_box()}
<p class="note">These are counts, not judgments. <a href="{url('method/')}">How each number is made</a>. Something wrong, or are you with the show?
<a href="{REPO_URL}/issues/new?template=correction.yml&amp;title={quote('Correction: ' + s['name'])}">Tell us</a>.</p>"""
    desc = f"{s['name']} by the numbers: talks at {s['pace_wpm']:.0f} words a minute; signature phrase “{top_phrase}”. Topics, guests and moments from {s['episodes_analyzed']} recent episodes."
    data = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{s['name']} podcast stats", "url": here, "description": desc,
            "about": {"@type": "PodcastSeries", "name": s["name"], "url": s.get("website") or s["feed"], "webFeed": s["feed"]},
            "dateModified": s["updated"]}
    write(f"show/{s['slug']}/index.html", shell(path=f"show/{s['slug']}/", title=f"{s['name']} podcast stats: signature phrases, talk pace, topics",
                                                description=desc, body=body, og=f"assets/og/{s['slug']}.png" if OG else "assets/og/home.png",
                                                head=jsonld(data) + "\n"))


def pair_slug(a, b):
    x, y = sorted([a["slug"], b["slug"]])
    return f"{x}-vs-{y}"


def page_compare(a, b, shows):
    a, b = sorted([a, b], key=lambda s: s["slug"])
    def row(label, key, fmt, unit, higher):
        va, vb = a[key], b[key]
        win = ""
        if va is not None and vb is not None and va != vb:
            win = a["name"] if (va > vb) == higher else b["name"]
        return (f'<tr><th scope="row">{e(label)}</th><td class="num" data-label="{e(a["name"])}">{fmt(va)}</td>'
                f'<td class="num" data-label="{e(b["name"])}">{fmt(vb)}</td>'
                f'<td data-label="Who">{e(win) + " " + e(unit) if win else "tie"}</td></tr>')
    rows = (row("Talk pace (words/min)", "pace_wpm", lambda v: f"{v:.0f}", "talks faster", True)
            + row("Vocabulary variety (per 100 words)", "variety", lambda v: f"{variety_score(v):.1f}", "uses more different words", True)
            + row("Questions per 100 sentences", "questions_per_100_sentences", lambda v: f"{v:.1f}", "asks more questions", True)
            + row("Typical episode (minutes)", "minutes_median", lambda v: f"{v:.0f}", "runs longer", True))
    def phrases(s):
        return "".join(f'<li>“{e(p["phrase"])}” <span class="note">×{p["count"]}</span></li>' for p in s["signature_phrases"][:6])
    body = f"""<p class="crumbs"><a href="{url()}">Leaderboard</a> › <a href="{url('compare/')}">Compare</a> › {e(a["name"])} vs {e(b["name"])}</p>
<h1>{e(a["name"])} vs {e(b["name"])}</h1>
<p class="lead">Side by side, counted from each show's own published transcripts ({a["episodes_analyzed"]} and {b["episodes_analyzed"]} recent episodes).</p>
<div class="scroll"><table class="vs"><thead><tr><th></th><th class="num"><a href="{url('show/' + a['slug'] + '/')}">{e(a["name"])}</a></th><th class="num"><a href="{url('show/' + b['slug'] + '/')}">{e(b["name"])}</a></th><th>Who</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="two"><div><h2>{e(a["name"])} says</h2><ol class="mini">{phrases(a)}</ol></div><div><h2>{e(b["name"])} says</h2><ol class="mini">{phrases(b)}</ol></div></div>
<p class="cta"><button type="button" data-copy="{e(absolute('compare/' + pair_slug(a, b) + '/'))}">Copy this comparison</button> <button type="button" class="quiet" data-share>Share</button></p>
<p class="note">Counts, not judgments: see <a href="{url('method/')}">how each number is made</a>. Full dashboards: <a href="{url('show/' + a['slug'] + '/')}">{e(a["name"])}</a> · <a href="{url('show/' + b['slug'] + '/')}">{e(b["name"])}</a>.</p>"""
    slug = pair_slug(a, b)
    faster = a if a["pace_wpm"] >= b["pace_wpm"] else b
    desc = f"{a['name']} vs {b['name']}: who talks faster ({faster['name']}, {faster['pace_wpm']:.0f} words a minute), who asks more questions, and each show's signature phrases."
    write(f"compare/{slug}/index.html", shell(path=f"compare/{slug}/", title=f"{a['name']} vs {b['name']}: podcast stats compared", description=desc,
                                              body=body, og=f"assets/og/vs-{slug}.png" if OG else "assets/og/home.png"))


def page_compare_index(shows):
    items = "".join(f'<li><a href="{url("compare/" + pair_slug(a, b) + "/")}">{e(a["name"])} vs {e(b["name"])}</a></li>'
                    for a, b in itertools.combinations(shows, 2))
    opts = "".join(f'<option value="{s["slug"]}">{e(s["name"])}</option>' for s in shows)
    body = f"""<h1>Compare two podcasts</h1>
<p>Pick two shows to see who talks faster, who asks more questions, and what each one says that the other doesn't.</p>
<form class="pick" data-compare><label for="ca">First show</label><select id="ca">{opts}</select><label for="cb">Second show</label><select id="cb">{opts}</select><button type="submit">Compare</button></form>
<h2>Every pair</h2><ul class="pairs">{items}</ul>"""
    write("compare/index.html", shell(path="compare/", title="Compare podcasts: talk pace, questions, signature phrases",
                                      description="Side-by-side stats for popular podcasts, counted from their own transcripts: talk pace, vocabulary, questions and signature phrases.",
                                      body=body))


def page_home(shows):
    by_pace = sorted(shows, key=lambda s: -s["pace_wpm"])
    rows = ""
    for s in by_pace:
        sig = s["signature_phrases"][0]["phrase"] if s["signature_phrases"] else ""
        rows += (f'<tr><td><a href="{url("show/" + s["slug"] + "/")}">{e(s["name"])}</a></td><td class="num" data-v="{s["pace_wpm"]}">{s["pace_wpm"]:.0f}</td>'
                 f'<td class="num" data-v="{s["variety"]}">{variety_score(s["variety"]):.1f}</td><td class="num" data-v="{s["questions_per_100_sentences"]}">{s["questions_per_100_sentences"]:.1f}</td>'
                 f'<td class="num" data-v="{s["minutes_median"]}">{s["minutes_median"]:.0f}</td><td>“{e(sig)}”</td></tr>')
    words = sum(s["words_analyzed"] for s in shows)
    eps = sum(s["episodes_analyzed"] for s in shows)
    newest = max(s["updated"] for s in shows)
    body = f"""<section class="hero"><h1>What top podcasters actually say</h1>
<p class="lead">Signature phrases, talk pace, topics and guests for {len(shows)} popular shows, counted from the transcripts the shows publish themselves. Every phrase links to the moments it was said.</p></section>
<div class="scroll"><table class="board" data-sortable><caption>{eps} episodes, {words:,} words. Updated {nice_date(newest)}. Click a column to sort.</caption>
<thead><tr><th>Show</th><th class="num" aria-sort="descending">Talk pace<br><small>words/min</small></th><th class="num">Vocabulary<br><small>per 100 words</small></th><th class="num">Questions<br><small>per 100 sentences</small></th><th class="num">Episode<br><small>minutes</small></th><th>Signature phrase</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>Compare two shows</h2>
<form class="pick" data-compare><label for="ca">First show</label><select id="ca">{"".join(f'<option value="{s["slug"]}">{e(s["name"])}</option>' for s in shows)}</select>
<label for="cb">Second show</label><select id="cb">{"".join(f'<option value="{s["slug"]}"{" selected" if i == 1 else ""}>{e(s["name"])}</option>' for i, s in enumerate(shows))}</select><button type="submit">Compare</button></form>
<h2>How to read this</h2>
<ul><li><strong>Talk pace</strong>: words per minute across each episode, from the timestamps in the show's transcript.</li>
<li><strong>Vocabulary variety</strong>: how many different words appear in a typical 100, averaged over 500-word stretches so long and short episodes compare fairly.</li>
<li><strong>Signature phrases</strong>: two- and three-word phrases a show says far more often than the others here. Ads and sponsor reads are filtered out as far as possible.</li>
<li>No scores for opinions, bias or beliefs: AudioSage counts words, it doesn't rate people. <a href="{url('method/')}">More on the method</a>.</li></ul>
{sponsor_box()}"""
    data = {"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": absolute(),
            "description": "Podcast stats from shows' own transcripts: signature phrases, talk pace, topics and guests."}
    write("index.html", shell(path="", title="AudioSage: podcast stats from real transcripts (signature phrases, talk pace)",
                              description=f"What top podcasters actually say: signature phrases, talk pace, topics and guests for {len(shows)} popular shows, counted from their own transcripts, each linked to the moment.",
                              body=body, head=jsonld(data) + "\n"))


def page_method(shows):
    body = f"""<h1>How the numbers are made</h1>
<h2>Where the words come from</h2>
<p>AudioSage reads only transcripts that shows publish themselves, through the <code>podcast:transcript</code> tag in their own podcast feed. It doesn't record, transcribe or download audio. Each week it reads every show's feed, takes the {max(s["episodes_analyzed"] for s in shows)} most recent full episodes that have a timed transcript, and recounts everything. Transcripts are not stored or republished here; each episode links to the show's own copy.</p>
<h2>The numbers</h2>
<ul>
<li><strong>Talk pace</strong>: words in the transcript divided by the minutes between its first and last timestamp. The show figure is the median of its episodes. Music, ads and pauses count as time, so read it as "pace of the episode", not of one person.</li>
<li><strong>Vocabulary variety</strong>: the moving-average type-token ratio over 500-word windows (Covington and McFall, 2010), shown as different words per 100.</li>
<li><strong>Questions</strong>: sentences ending in a question mark, per 100 sentences, as punctuated by the show's transcript.</li>
<li><strong>Signature phrases</strong>: every two- and three-word phrase is counted per show and compared with all the other shows using the log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi and Quinn, 2008). The phrases with the highest z-scores are shown, after dropping phrases made only of common words, numbers, and words typical of ads ("promo code", sponsor names). A phrase must appear at least 6 times.</li>
<li><strong>Topics</strong>: how often words from a fixed list for each topic appear, per 10,000 words, compared with the average show here. The word lists are in the <a href="{REPO_URL}/blob/main/pipeline/stats.py">source code</a>.</li>
<li><strong>Who does the talking</strong>: only when the show's transcript names its speakers. Generic labels like "Speaker 1" are ignored because they can mean different people in different episodes.</li>
<li><strong>Guests</strong>: only people the show lists as guests in its own feed (<code>podcast:person role="guest"</code>).</li></ul>
<h2>What AudioSage doesn't do</h2>
<ul><li>No labels for bias, beliefs, politics or character. These are counts of words, not judgments of people.</li>
<li>No full transcripts. Quotes are at most 20 words, attributed, and link to the moment in the episode.</li>
<li>Machine transcripts have errors, and ads can slip through the filters. Treat every number as approximate and check the moment behind it.</li></ul>
<h2>Data</h2>
<p>All statistics are in <a href="{url('data/stats.json')}">stats.json</a> (CC BY 4.0) and the code is <a href="{REPO_URL}">open source</a>.</p>"""
    write("method/index.html", shell(path="method/", title="Method: how AudioSage counts podcast phrases, pace and topics",
                                     description="How AudioSage turns podcasts' own published transcripts into signature phrases, talk pace, vocabulary, topics and guest counts, and what it deliberately doesn't do.",
                                     body=body))


def page_about(shows):
    paused = [s for s in json.loads((DATA / "shows.json").read_text(encoding="utf-8"))["shows"] if s.get("paused")]
    body = f"""<h1>About AudioSage</h1>
<p>AudioSage is a set of playful, checkable dashboards about what popular podcasts actually say: the phrases each show leans on, how fast it talks, what it talks about, and who it has on. Every number is counted from the show's own published transcripts, and every phrase links to the moments it was said.</p>
<h2 id="shows">For shows</h2>
<ul><li><strong>Corrections.</strong> If something is wrong, <a href="{REPO_URL}/issues/new?template=correction.yml">open a correction</a>. It gets fixed.</li>
<li><strong>Opting out.</strong> If your show doesn't want a dashboard, <a href="{REPO_URL}/issues/new?template=correction.yml&amp;title=Opt%20out">say so</a> and it comes down at the next weekly build, no questions asked.</li>
<li><strong>Getting in.</strong> Shows are included when they publish timed transcripts in their feed (<code>podcast:transcript</code>). Publishing them makes your show eligible.</li></ul>
<h2>Shows covered</h2>
<ul>{"".join(f'<li><a href="{url("show/" + s["slug"] + "/")}">{e(s["name"])}</a></li>' for s in shows)}</ul>
{"<p class='note'>Paused at a show's request or for review: " + ", ".join(e(s["name"]) for s in paused) + ".</p>" if paused else ""}
<h2>Privacy</h2>
<p>No accounts and no cookies. {"Visits are counted with GoatCounter, which stores no personal data." if GOATCOUNTER_URL else "The site doesn't count visits."}</p>"""
    write("about/index.html", shell(path="about/", title="About AudioSage: corrections, opting out, which shows are covered",
                                    description="What AudioSage is, which podcasts it covers and why, and how shows can correct a number or opt out.", body=body))


def page_404():
    write("404.html", shell(path="404.html", title="Page not found", description="Page not found.", index=False,
                            body=f'<h1>That page isn\'t here</h1><p><a href="{url()}">See the leaderboard</a>.</p>'))


OG = False


def write_static(shows):
    shutil.copytree(SITE / "assets", DIST / "assets", dirs_exist_ok=True)
    shutil.copy(SITE / "favicon.svg", DIST / "favicon.svg")
    key = (SITE / "indexnow-key.txt").read_text().strip()
    write(f"{key}.txt", key)
    pages = ["", "compare/"] + [f"show/{s['slug']}/" for s in shows] + \
            [f"compare/{pair_slug(a, b)}/" for a, b in itertools.combinations(shows, 2)] + ["method/", "about/"]
    lastmod = {f"show/{s['slug']}/": s["updated"] for s in shows}
    newest = max(s["updated"] for s in shows)
    items = "".join(f"<url><loc>{e(absolute(p))}</loc><lastmod>{lastmod.get(p, newest)}</lastmod></url>\n" for p in pages)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {absolute('sitemap.xml')}\n")
    write("urls.txt", "\n".join(absolute(p) for p in pages) + "\n")
    public = [{k: v for k, v in s.items() if k != "eps"} for s in shows]
    write("data/stats.json", json.dumps({"built": TODAY.isoformat(), "license": "CC BY 4.0", "shows": public}, ensure_ascii=False))
    write("data/meta.json", json.dumps({"built": TODAY.isoformat(), "shows": len(shows), "newest_update": newest,
                                        "oldest_update": min(s["updated"] for s in shows), "sample_show": shows[0]["slug"],
                                        "sample_compare": pair_slug(shows[0], shows[1])}, indent=1))


def build():
    global OG
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shows = load()
    if len(shows) < 2:
        raise SystemExit("need stats for at least two shows (run pipeline/fetch.py and pipeline/analyze.py)")
    write_static(shows)
    try:
        if os.environ.get("SKIP_OG"):
            raise ImportError("SKIP_OG is set")
        import og
        OG = og.render_all(shows, [(a, b) for a, b in itertools.combinations(shows, 2)], DIST / "assets" / "og", SITE_URL, pair_slug)
    except ImportError as err:
        if os.environ.get("REQUIRE_OG"):
            raise SystemExit(f"share cards are required but Pillow is missing: {err}")
        print(f"note: share cards skipped ({err})")
    page_home(shows)
    page_compare_index(shows)
    for s in shows:
        page_show(s, shows)
    for a, b in itertools.combinations(shows, 2):
        page_compare(a, b, shows)
    page_method(shows)
    page_about(shows)
    page_404()
    print(f"built {sum(1 for _ in DIST.rglob('*.html'))} pages for {len(shows)} shows; site {SITE_URL}")


if __name__ == "__main__":
    build()
