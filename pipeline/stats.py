"""Statistics from timed transcript segments. Pure functions, stdlib only.

Nothing here labels people. Every number is a count or a rate that a reader can check against the transcript the
show itself publishes, and every phrase comes with the moments it was said.
"""
import math
import re
from collections import Counter, defaultdict

from transcripts import words

STOP = set("""a about above after again against all am an and any are aren't as at be because been before being below between both but by
can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its
itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she
she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's these they they'd
they'll they're they've this those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when
when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself
yourselves yeah uh um oh okay ok like just so really got get gonna gotta wanna right well know mean think thing things going go one also
said say says lot kind sort yes mm hmm mhm actually something anything everything nothing""".split())

# Phrases that come from ads and boilerplate rather than from the hosts' own way of talking.
AD_WORDS = {"sponsor", "sponsored", "promo", "code", "offer", "discount", "subscribe", "subscription", "download", "app", "trial",
            "shipping", "betterhelp", "dot", "com", "www", "http", "https", "podcast", "podcasts", "iheartradio", "spotify", "apple",
            "patreon", "wondery", "siriusxm", "audible", "advertise", "advertising", "ad", "ads", "brought", "terms", "apply",
            "visit", "slash", "percent", "off", "free", "episode", "episodes", "listen", "listening"}

TOPICS = {
    "Technology and AI": "ai artificial intelligence algorithm app apps chatgpt computer computers software tech technology internet robot robots openai startup startups data online digital",
    "Business and money": "business money market markets company companies economy economic investors investing invest stock stocks dollars revenue profit ceo billion million price prices bank jobs",
    "Health and medicine": "health doctor doctors medical medicine hospital disease cancer brain body sleep diet exercise mental therapy patients drug drugs virus vaccine nutrition",
    "Science": "science scientist scientists research study studies experiment universe physics biology chemistry evolution species planet theory",
    "Politics and government": "president election vote voters congress senate government policy politics political democrats republicans campaign law laws supreme court administration",
    "Crime and justice": "crime murder police killer victim victims detective prison jail trial evidence investigation suspect killed murdered case",
    "Sports": "game games team teams season player players coach football basketball baseball soccer nfl nba league championship playoff playoffs",
    "Movies, TV and entertainment": "movie movies film films show shows tv television actor actress hollywood netflix series character characters celebrity",
    "Music": "music song songs album albums band singer rapper concert tour guitar",
    "History": "history historical century war ancient empire king queen medieval revolution",
    "Family and relationships": "family mom dad mother father kids children parents wife husband marriage married dating relationship relationships friend friends",
    "Food and drink": "food eat eating cook cooking restaurant restaurants recipe drink drinks coffee wine beer",
    "Religion and spirituality": "god church faith religion religious jesus bible spiritual prayer pray",
    "Climate and environment": "climate environment environmental carbon energy weather emissions fossil renewable warming",
}
TOPIC_WORDS = {t: set(v.split()) for t, v in TOPICS.items()}
WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
GENERIC_SPEAKER = re.compile(r"^(speaker|spk|voice|host|guest|unknown)[ _-]?\d*$", re.I)


def tokens(text):
    return WORD_RE.findall(text.lower().replace("’", "'"))


def ngrams(toks, n):
    return zip(*(toks[i:] for i in range(n)))


FUNCTION = set("the a an and or but of to in on at for with by from as into than that this these those is are was were be".split())


def good_phrase(gram):
    if all(w in STOP for w in gram):
        return False
    # "the army", "brooks and", "stuff you": a phrase that starts or ends on a function word is a fragment, not a saying.
    if gram[0] in FUNCTION or gram[-1] in FUNCTION or gram[-1] in {"you", "i", "we", "he", "she", "they", "it"}:
        return False
    if gram[0] in STOP and len(gram) == 2 and gram[1] in STOP:
        return False
    if any(w in AD_WORDS for w in gram):
        return False
    if any(w.isdigit() for w in gram):
        return False
    if len(set(gram)) < len(gram):
        return False
    return len("".join(gram)) >= 6


def mattr(toks, window=500, step=25):
    """Moving-average type-token ratio: vocabulary variety that doesn't depend on episode length.
    The exact moving window, sampled every `step` words for speed."""
    if not toks:
        return 0.0
    if len(toks) < window:
        return len(set(toks)) / len(toks)
    total, steps = 0.0, 0
    for start in range(0, len(toks) - window + 1, step):
        total += len(set(toks[start:start + window])) / window
        steps += 1
    return total / steps


def episode_stats(segments):
    """Counts for one episode. Returns a dict, or None when the transcript has no usable timing."""
    if not segments:
        return None
    start = min(s["start"] for s in segments)
    end = max(s["end"] for s in segments)
    minutes = (end - start) / 60
    toks = []
    for s in segments:
        toks += tokens(s["text"])
    if minutes < 3 or len(toks) < 300:
        return None
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", " ".join(s["text"] for s in segments)) if x.strip()]
    questions = sum(1 for x in sentences if x.rstrip().endswith("?"))
    speakers = defaultdict(lambda: [0, 0.0])
    for s in segments:
        # Generic labels ("Speaker 1") can name different people in different episodes, so they don't count.
        if s["speaker"] and not GENERIC_SPEAKER.match(s["speaker"]):
            speakers[s["speaker"]][0] += len(tokens(s["text"]))
            speakers[s["speaker"]][1] += max(0.0, s["end"] - s["start"])
    topic_hits = {t: sum(1 for w in toks if w in ws) for t, ws in TOPIC_WORDS.items()}
    return {
        "minutes": round(minutes, 1),
        "words": len(toks),
        "wpm": round(len(toks) / minutes, 1),
        "questions_per_100_sentences": round(100 * questions / max(1, len(sentences)), 1),
        "variety": round(mattr(toks), 4),
        "speakers": {k: {"words": v[0], "minutes": round(v[1] / 60, 1)} for k, v in speakers.items() if v[0] >= 50},
        "topics": topic_hits,
    }


AD_SEGMENT = re.compile(r"(promo code|offer code|use code|\.com\b|\bdot com\b|\bslash [a-z]+|percent off|% off|free trial|terms apply|"
                        r"sponsored by|brought to you by|this episode is (brought|sponsored)|\b(go|head) to [a-z0-9]+\.(com|org|co)|"
                        r"download the [a-z]+ app|first order|free shipping|money[- ]back)", re.I)


def is_ad(text):
    """A segment that reads like an ad or sponsor read. Such segments are left out of phrases and quotes."""
    return bool(AD_SEGMENT.search(text))


def phrase_counts(segments, sizes=(2, 3)):
    counts = Counter()
    for s in segments:
        if is_ad(s["text"]):
            continue
        toks = tokens(s["text"])
        for n in sizes:
            for g in ngrams(toks, n):
                if good_phrase(g):
                    counts[" ".join(g)] += 1
    return counts


def signature(show_counts, corpus_counts, show_total, corpus_total, top=12, min_count=6, prior=0.01, df=None, min_df=0):
    """Phrases a show uses far more than the other shows: log-odds ratio with an informative Dirichlet prior
    (Monroe, Colaresi and Quinn, 2008), ranked by z-score. `df` (episodes containing each phrase) with `min_df`
    keeps only phrases that recur across episodes, so one episode's topic isn't mistaken for a habit.
    Returns [(phrase, count, z)]."""
    rest_total = max(1, corpus_total - show_total)
    alpha0 = prior * corpus_total
    out = []
    for phrase, y_i in show_counts.items():
        if y_i < min_count or (df is not None and df.get(phrase, 0) < min_df):
            continue
        y_all = corpus_counts.get(phrase, y_i)
        y_j = max(0, y_all - y_i)
        a_w = max(1e-3, alpha0 * y_all / max(1, corpus_total))
        d_i = math.log((y_i + a_w) / (show_total + alpha0 - y_i - a_w))
        d_j = math.log((y_j + a_w) / (rest_total + alpha0 - y_j - a_w))
        z = (d_i - d_j) / math.sqrt(1 / (y_i + a_w) + 1 / (y_j + a_w))
        out.append((phrase, y_i, z))
    out.sort(key=lambda x: (-x[2], x[0]))
    picked = []
    for phrase, count, z in out:
        # Skip a phrase that is just part of one already picked ("the bees" inside "talking about the bees").
        if any(phrase in p or p in phrase for p, _, _ in picked):
            continue
        picked.append((phrase, count, round(z, 2)))
        if len(picked) == top:
            break
    return picked


def quote_for(segments, phrase, max_words=20):
    """The sentence around the first use of `phrase` in these segments, trimmed to max_words. (start, text) or None."""
    target = phrase.split()
    for s in segments:
        if is_ad(s["text"]):
            continue
        toks = tokens(s["text"])
        for i in range(len(toks) - len(target) + 1):
            if toks[i:i + len(target)] == target:
                text = s["text"]
                ws = text.split()
                low = [re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'")) for w in ws]
                for k in range(len(low) - len(target) + 1):
                    if low[k:k + len(target)] == target:
                        a = max(0, k - (max_words - len(target)) // 2)
                        b = min(len(ws), a + max_words)
                        a = max(0, b - max_words)
                        snippet = " ".join(ws[a:b])
                        return s["start"], ("…" if a > 0 else "") + snippet + ("…" if b < len(ws) else "")
                return s["start"], " ".join(ws[:max_words])
    return None
