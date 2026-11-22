import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import transcripts as t  # noqa: E402

VTT = """WEBVTT

1
00:00:00.000 --> 00:00:04.200
<v Josh>Hey, and welcome to the podcast.</v>

2
00:00:04.200 --> 00:00:09.000
It's me and Chuck here.

3
00:00:09.000 --> 00:01:02.500
<v Chuck>That's right. &amp; we're <i>talking</i> about bees.
"""
SRT = """1
00:00:01,000 --> 00:00:03,500
Speaker 1: Hello there

2
00:00:03,500 --> 00:00:06,000
General Kenobi
"""
JSON = '{"version":"1.0.0","segments":[{"speaker":"Ana","startTime":0.5,"endTime":2.0,"body":"Hi"},{"startTime":2.0,"endTime":4.0,"body":"Hello &amp; welcome"}]}'


class Parse(unittest.TestCase):
    def test_vtt_with_voices(self):
        s = t.parse(VTT, "text/vtt")
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0]["speaker"], "Josh")
        self.assertEqual(s[1]["speaker"], "Josh", "the speaker carries forward")
        self.assertEqual(s[2]["speaker"], "Chuck")
        self.assertEqual(s[2]["text"], "That's right. & we're talking about bees.")
        self.assertAlmostEqual(s[2]["end"], 62.5)

    def test_srt_with_speaker_prefix(self):
        s = t.parse(SRT, "application/srt")
        self.assertEqual([x["speaker"] for x in s], ["Speaker 1", "Speaker 1"])
        self.assertEqual(s[0]["text"], "Hello there")
        self.assertAlmostEqual(s[1]["start"], 3.5)

    def test_json(self):
        s = t.parse(JSON, "application/json")
        self.assertEqual(s[1]["speaker"], "Ana")
        self.assertEqual(s[1]["text"], "Hello & welcome")

    def test_plain_text_has_no_timing(self):
        self.assertEqual(t.parse("Just words, no times.", "text/plain"), [])

    def test_hour_stamps_and_words(self):
        self.assertAlmostEqual(t.seconds("01:02:03.5"), 3723.5)
        self.assertEqual(t.words("Don't stop, it's 2026!"), ["Don't", "stop", "it's", "2026"])


if __name__ == "__main__":
    unittest.main()
