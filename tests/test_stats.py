import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import stats  # noqa: E402


def seg(start, end, text, speaker=None):
    return {"start": start, "end": end, "speaker": speaker, "text": text}


class Stats(unittest.TestCase):
    def test_episode_stats_need_real_timing(self):
        self.assertIsNone(stats.episode_stats([seg(0, 60, "too short")]))
        words = " ".join(["alpha beta gamma delta"] * 100)
        segs = [seg(i * 60, i * 60 + 60, words + " Is that right?", "Ana" if i % 2 else "Speaker 1") for i in range(5)]
        st = stats.episode_stats(segs)
        self.assertEqual(st["minutes"], 5.0)
        self.assertAlmostEqual(st["wpm"], st["words"] / 5, places=0)
        self.assertIn("Ana", st["speakers"])
        self.assertNotIn("Speaker 1", st["speakers"], "generic labels are ignored")
        self.assertGreater(st["questions_per_100_sentences"], 0)

    def test_variety_is_length_independent(self):
        text = ("the quick brown fox jumps over the lazy dog " * 300).split()
        self.assertAlmostEqual(stats.mattr(text[:1000]), stats.mattr(text), places=2)
        self.assertEqual(stats.mattr([]), 0.0)

    def test_fragments_and_ads_are_not_phrases(self):
        self.assertFalse(stats.good_phrase(("the", "army")))
        self.assertFalse(stats.good_phrase(("brooks", "and")))
        self.assertFalse(stats.good_phrase(("promo", "code")))
        self.assertFalse(stats.good_phrase(("you", "know")))
        self.assertTrue(stats.good_phrase(("et", "cetera")))
        self.assertTrue(stats.good_phrase(("oh", "my", "god")))

    def test_signature_prefers_distinctive_recurring_phrases(self):
        show = Counter({"et cetera": 40, "data center": 30, "good morning": 8})
        corpus = Counter({"et cetera": 41, "data center": 33, "good morning": 300})
        df = {"et cetera": 9, "data center": 2, "good morning": 5}
        sig = stats.signature(show, corpus, 1000, 20000, df=df, min_df=3)
        names = [p for p, _, _ in sig]
        self.assertEqual(names[0], "et cetera")
        self.assertNotIn("data center", names, "a phrase from too few episodes is a topic, not a habit")
        self.assertTrue(names.index("et cetera") < (names.index("good morning") if "good morning" in names else 99))

    def test_quotes_are_short_and_contain_the_phrase(self):
        long = " ".join(f"w{i}" for i in range(60)) + " et cetera " + " ".join(f"x{i}" for i in range(60))
        at, q = stats.quote_for([seg(10, 20, "nothing here"), seg(30, 90, long)], "et cetera", 20)
        self.assertEqual(at, 30)
        self.assertIn("et cetera", q)
        self.assertLessEqual(len(q.replace("…", "").split()), 20)
        self.assertIsNone(stats.quote_for([seg(0, 1, "nothing")], "et cetera"))


if __name__ == "__main__":
    unittest.main()


class Ads(unittest.TestCase):
    def test_ad_reads_are_left_out(self):
        self.assertTrue(stats.is_ad("get $30 off your first order at cometeer.com slash stephen"))
        self.assertTrue(stats.is_ad("This episode is brought to you by Example"))
        self.assertFalse(stats.is_ad("I guess we should take a break"))
        c = stats.phrase_counts([seg(0, 5, "your first order at example.com slash pod"), seg(5, 9, "et cetera et cetera")])
        self.assertNotIn("first order", c)
        self.assertIn("et cetera", c)
