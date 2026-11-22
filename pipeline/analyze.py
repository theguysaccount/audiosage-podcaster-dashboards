"""Turn cached transcripts into published statistics: python3 pipeline/analyze.py

Reads .cache/shows/*.json and .cache/parsed/ (written by fetch.py). Writes data/stats/<slug>.json for every show
with at least MIN_EPISODES usable episodes, and data/corpus.json (averages across shows). A show without enough
cached episodes keeps its previous stats file untouched, so one bad week never blanks a dashboard.

Published per show: counts, rates, signature phrases with short quotes (at most QUOTE_WORDS words each) and the
moments they were said, topics relative to the other shows, and guests the show itself lists. Never transcripts.
"""
import datetime
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("AUDIOSAGE_CACHE") or ROOT / ".cache")
DATA = Path(os.environ.get("AUDIOSAGE_DATA_DIR") or ROOT / "data")
MIN_EPISODES = 3
QUOTE_WORDS = 20


def load_cached(slug):
    path = CACHE / "shows" / f"{slug}.json"
    if not path.exists():
        return None, []
    record = json.loads(path.read_text(encoding="utf-8"))
    episodes = []
    for ep in record["episodes"]:
        f = CACHE / "parsed" / slug / f"{ep['id']}.json"
        if f.exists():
            segs = json.loads(f.read_text(encoding="utf-8"))
            st = stats.episode_stats(segs)
            if st:
                episodes.append((ep, segs, st))
    return record, episodes


def median(xs):
    return round(statistics.median(xs), 1) if xs else None


def main(today=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    shows = json.loads((DATA / "shows.json").read_text(encoding="utf-8"))["shows"]
    loaded = {}
    for show in shows:
        if show.get("paused"):
            continue
        record, episodes = load_cached(show["slug"])
        if record and len(episodes) >= MIN_EPISODES:
            loaded[show["slug"]] = (show, record, episodes)
        else:
            print(f"::warning::{show['slug']}: {len(episodes)} usable episodes cached; keeping its last published stats")
    if len(loaded) < 2:
        print("::warning::fewer than two shows have fresh data; nothing written")
        return 0
    phrase = {slug: Counter() for slug in loaded}
    doc_freq = {slug: Counter() for slug in loaded}
    words_total = {}
    for slug, (_, _, episodes) in loaded.items():
        for _, segs, _ in episodes:
            c = stats.phrase_counts(segs)
            phrase[slug].update(c)
            doc_freq[slug].update(c.keys())
        words_total[slug] = sum(st["words"] for _, _, st in episodes)
    corpus = Counter()
    for c in phrase.values():
        corpus.update(c)
    corpus_words = sum(words_total.values())
    topic_rate = {}
    for slug, (_, _, episodes) in loaded.items():
        hits = Counter()
        for _, _, st in episodes:
            hits.update(st["topics"])
        topic_rate[slug] = {t: 10000 * hits[t] / max(1, words_total[slug]) for t in stats.TOPICS}
    topic_avg = {t: statistics.mean(topic_rate[s][t] for s in loaded) for t in stats.TOPICS}
    out_dir = DATA / "stats"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for slug, (show, record, episodes) in loaded.items():
        min_df = max(3, -(-4 * len(episodes) // 10))   # said in at least 3 episodes and 40% of them
        sig = stats.signature(phrase[slug], corpus, sum(phrase[slug].values()), sum(corpus.values()), df=doc_freq[slug], min_df=min_df)
        phrases = []
        for p, count, z in sig:
            moments = []
            used_eps = set()
            for ep, segs, _ in episodes:
                if ep["id"] in used_eps:
                    continue
                q = stats.quote_for(segs, p, QUOTE_WORDS)
                if q:
                    moments.append({"episode": ep["id"], "at": int(q[0]), "quote": q[1]})
                    used_eps.add(ep["id"])
                if len(moments) == 2:
                    break
            phrases.append({"phrase": p, "count": count, "episodes": doc_freq[slug][p], "z": z, "moments": moments})
        speaker_words = Counter()
        speaker_minutes = Counter()
        for _, _, st in episodes:
            for name, v in st["speakers"].items():
                speaker_words[name] += v["words"]
                speaker_minutes[name] += v["minutes"]
        speakers = [{"name": n, "words": w, "share": round(100 * w / max(1, sum(speaker_words.values())), 1),
                     "wpm": round(w / speaker_minutes[n], 1) if speaker_minutes[n] >= 5 else None}
                    for n, w in speaker_words.most_common(6) if w >= 500]
        guests = Counter()
        for ep, _, _ in episodes:
            for p in ep.get("persons", []):
                if p["role"] == "guest":
                    guests[p["name"]] += 1
        topics = sorted(({"topic": t, "per_10k": round(topic_rate[slug][t], 1),
                          "vs_average": round(topic_rate[slug][t] / topic_avg[t], 2) if topic_avg[t] else None} for t in stats.TOPICS),
                        key=lambda x: -x["per_10k"])
        eps = [{"id": ep["id"], "title": ep["title"], "date": ep["date"], "link": ep.get("link"), "audio": ep.get("audio"),
                "transcript": ep["transcript"], "minutes": st["minutes"], "words": st["words"], "wpm": st["wpm"],
                "questions_per_100_sentences": st["questions_per_100_sentences"], "variety": st["variety"]}
               for ep, _, st in episodes]
        eps.sort(key=lambda e: e["date"] or "", reverse=True)
        result = {
            "slug": slug, "name": show["name"], "updated": record["fetched"], "built": today,
            "feed": show["feed"], "website": show.get("website") or record.get("link"), "image": record.get("image"),
            "episodes_analyzed": len(eps), "first_episode": min(e["date"] for e in eps), "latest_episode": max(e["date"] for e in eps),
            "words_analyzed": words_total[slug],
            "pace_wpm": median([e["wpm"] for e in eps]),
            "minutes_median": median([e["minutes"] for e in eps]),
            "questions_per_100_sentences": median([e["questions_per_100_sentences"] for e in eps]),
            "variety": round(statistics.median([e["variety"] for e in eps]), 4),
            "signature_phrases": phrases,
            "speakers": speakers,
            "speaker_labels": bool(speakers),
            "guests": [{"name": n, "episodes": c} for n, c in guests.most_common(12)],
            "topics": topics,
            "episodes": eps,
        }
        (out_dir / f"{slug}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        summary[slug] = {k: result[k] for k in ("pace_wpm", "minutes_median", "questions_per_100_sentences", "variety", "episodes_analyzed")}
        print(f"{slug}: {len(eps)} episodes, {result['pace_wpm']} wpm, top phrase {phrases[0]['phrase'] if phrases else '-'}")
    (DATA / "corpus.json").write_text(json.dumps({"built": today, "shows_in_this_run": sorted(loaded), "topic_average_per_10k":
                                                 {t: round(v, 1) for t, v in topic_avg.items()}, "words": corpus_words}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
