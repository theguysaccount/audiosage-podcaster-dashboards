"""Parse podcast transcripts (WebVTT, SubRip, Podcasting 2.0 JSON) into timed segments.

A segment is {"start": seconds, "end": seconds, "speaker": str|None, "text": str}. Pure functions, stdlib only.
"""
import html
import json
import re

TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
TAG = re.compile(r"<[^>]+>")
VOICE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")


def seconds(stamp):
    m = TIME.search(stamp)
    if not m:
        raise ValueError(f"not a timestamp: {stamp!r}")
    h, mnt, s, frac = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(s) + int(frac.ljust(3, "0")[:3]) / 1000


def clean_text(text):
    text = html.unescape(TAG.sub("", text))
    return re.sub(r"\s+", " ", text).strip()


SPEAKER_PREFIX = re.compile(r"^([A-Z][\w.'-]*(?: [A-Z][\w.'-]*){0,3}|Speaker \d+|SPEAKER_\d+):\s+(?=\S)")


def split_speaker(text):
    """'Josh: Hey there' -> ('Josh', 'Hey there'). Only short capitalised labels count as speakers."""
    m = SPEAKER_PREFIX.match(text)
    if m and len(m.group(1)) <= 40:
        return m.group(1), text[m.end():]
    return None, text


def parse_cues(raw):
    """Shared WebVTT/SRT cue parser: blocks separated by blank lines with a 'start --> end' line."""
    segments = []
    text = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "-->" in line:
                a, b = line.split("-->", 1)
                try:
                    start, end = seconds(a), seconds(b.strip().split(" ")[0])
                except ValueError:
                    break
                body = " ".join(lines[i + 1:])
                voice = VOICE.search(body)
                speaker = clean_text(voice.group(1)) if voice else None
                body = clean_text(body)
                if speaker is None:
                    speaker, body = split_speaker(body)
                if body:
                    segments.append({"start": start, "end": max(end, start), "speaker": speaker, "text": body})
                break
    return merge_speakers(segments)


def merge_speakers(segments):
    """Cue formats often name the speaker only on their first cue; carry it forward until the next name."""
    if not any(s["speaker"] for s in segments):
        return segments
    current = None
    for s in segments:
        if s["speaker"]:
            current = s["speaker"]
        else:
            s["speaker"] = current
    return segments


def parse_json(raw):
    data = json.loads(raw)
    segs = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segs, list):
        raise ValueError("not a Podcasting 2.0 JSON transcript")
    out = []
    for s in segs:
        body = clean_text(str(s.get("body", "")))
        if not body:
            continue
        start = float(s.get("startTime", 0) or 0)
        end = float(s.get("endTime", start) or start)
        out.append({"start": start, "end": max(end, start), "speaker": (s.get("speaker") or None), "text": body})
    return merge_speakers(out)


def parse(raw, content_type=""):
    """Best effort by declared type, then by sniffing. Returns segments (possibly empty)."""
    ct = (content_type or "").lower()
    stripped = raw.lstrip("﻿ \n\r\t")
    if "json" in ct or stripped.startswith("{"):
        return parse_json(raw)
    if "-->" in raw:
        return parse_cues(raw)
    return []


def words(text):
    return re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*", text)
