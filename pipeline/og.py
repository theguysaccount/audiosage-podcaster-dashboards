"""Open Graph share cards (1200x630 PNG): one per show and one per comparison. Text only. Needs Pillow."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
INK, PAPER, BRAND, ACCENT, SOFT = (29, 22, 49), (250, 248, 255), (45, 27, 105), (255, 179, 71), (95, 88, 122)
W, H = 1200, 630


def font(cands, size):
    for c in cands:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default(size=size)


def fit(d, text, cands, size, width, min_size=30):
    while size > min_size and d.textlength(text, font=font(cands, size)) > width:
        size -= 2
    f = font(cands, size)
    while d.textlength(text, font=f) > width and len(text) > 4:
        text = text[:-2].rstrip() + "…"
    return text, f


def frame(footer):
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 96], fill=BRAND)
    for i, h in enumerate([20, 40, 60, 34, 18]):
        x = 48 + i * 16
        d.rounded_rectangle([x, 48 - h // 2, x + 8, 48 + h // 2], radius=4, fill=ACCENT)
    d.text((150, 26), "AudioSage", font=font(BOLD, 40), fill=(255, 255, 255))
    d.text((64, H - 62), footer, font=font(REG, 26), fill=SOFT)
    return img, d


def show_card(path, s, host):
    img, d = frame(f"Counted from the show's own transcripts · {host}")
    title, f = fit(d, s["name"], BOLD, 72, W - 128)
    d.text((64, 130), title, font=f, fill=INK)
    stats = [(f"{s['pace_wpm']:.0f}", "words per minute"), (f"{s['questions_per_100_sentences']:.0f}", "questions per 100 sentences"),
             (f"{s['minutes_median']:.0f}", "minute typical episode")]
    x = 64
    for big, small in stats:
        d.text((x, 240), big, font=font(BOLD, 84), fill=BRAND)
        d.text((x, 340), small, font=font(REG, 24), fill=SOFT)
        x += 370
    if s["signature_phrases"]:
        phrase, f2 = fit(d, f"Signature phrase: “{s['signature_phrases'][0]['phrase']}”", BOLD, 40, W - 128)
        d.text((64, 420), phrase, font=f2, fill=INK)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


def vs_card(path, a, b, host):
    img, d = frame(f"Who talks faster? Who asks more questions? · {host}")
    t1, f1 = fit(d, a["name"], BOLD, 60, W - 128)
    d.text((64, 124), t1, font=f1, fill=INK)
    d.text((64, 200), "vs", font=font(BOLD, 40), fill=ACCENT)
    t2, f2 = fit(d, b["name"], BOLD, 60, W - 128)
    d.text((64, 248), t2, font=f2, fill=INK)
    line = f"{a['pace_wpm']:.0f} vs {b['pace_wpm']:.0f} words per minute"
    d.text((64, 360), line, font=font(BOLD, 44), fill=BRAND)
    q = f"{a['questions_per_100_sentences']:.0f} vs {b['questions_per_100_sentences']:.0f} questions per 100 sentences"
    d.text((64, 430), q, font=font(REG, 34), fill=SOFT)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


def home_card(path, n, host):
    img, d = frame(host)
    d.text((64, 140), "What top podcasters", font=font(BOLD, 76), fill=INK)
    d.text((64, 230), "actually say", font=font(BOLD, 76), fill=INK)
    d.text((64, 350), f"Signature phrases, talk pace and topics for {n} shows,", font=font(REG, 34), fill=SOFT)
    d.text((64, 396), "from their own transcripts. Every phrase linked to the moment.", font=font(REG, 34), fill=SOFT)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


def render_all(shows, pairs, out_dir, site_url, pair_slug):
    out_dir = Path(out_dir)
    host = re.sub(r"^https?://", "", site_url).rstrip("/")
    home_card(out_dir / "home.png", len(shows), host)
    for s in shows:
        show_card(out_dir / f"{s['slug']}.png", s, host)
    for a, b in pairs:
        x, y = sorted([a, b], key=lambda s: s["slug"])
        vs_card(out_dir / f"vs-{pair_slug(x, y)}.png", x, y, host)
    return True
