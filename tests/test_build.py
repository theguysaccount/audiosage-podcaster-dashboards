"""Build the site from the committed statistics into a temporary folder and check what it publishes."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://example.test/sage"


def build(data_dir, out_dir, **env):
    e = dict(os.environ, BUILD_DIR=str(out_dir), AUDIOSAGE_DATA_DIR=str(data_dir), SITE_URL=SITE_URL, SKIP_OG="1")
    for k in ("GOATCOUNTER_URL", "SPONSOR_URL"):
        e.pop(k, None)
    e.update(env)
    r = subprocess.run([sys.executable, str(ROOT / "pipeline" / "build.py")], env=e, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(r.stdout + r.stderr)


@unittest.skipUnless(len(list((ROOT / "data" / "stats").glob("*.json"))) >= 2, "no statistics yet")
class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "data", cls.tmp / "data")
        cls.dist = cls.tmp / "dist"
        build(cls.tmp / "data", cls.dist)
        cls.shows = [json.loads(p.read_text()) for p in sorted((cls.tmp / "data" / "stats").glob("*.json"))]
        listed = {s["slug"] for s in json.loads((cls.tmp / "data" / "shows.json").read_text())["shows"] if not s.get("paused")}
        cls.shows = [s for s in cls.shows if s["slug"] in listed]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def read(self, rel):
        return (self.dist / rel).read_text(encoding="utf-8")

    def test_every_show_has_a_dashboard_with_short_attributed_quotes(self):
        for s in self.shows:
            page = self.read(f"show/{s['slug']}/index.html")
            self.assertIn(f'<link rel="canonical" href="{SITE_URL}/show/{s["slug"]}/">', page)
            for q in re.findall(r"<blockquote>“(.*?)”<footer>", page, re.S):
                self.assertLessEqual(len(q.replace("…", " ").split()), 20, q)
            # A dashboard publishes statistics and short quotes, never transcripts.
            quoted = sum(len(q.split()) for q in re.findall(r"<blockquote>“(.*?)”", page, re.S))
            self.assertLess(quoted, 400)
            for ep in s["episodes"]:
                self.assertIn(ep["transcript"].replace("&", "&amp;"), page, "each episode links to the show's own transcript")

    def test_no_judgment_labels(self):
        for f in self.dist.rglob("*.html"):
            # Our own words only: quotes are what people on the shows said, attributed to them.
            page = re.sub(r"<blockquote>.*?</blockquote>", " ", f.read_text(encoding="utf-8"), flags=re.S)
            text = re.sub(r"<[^>]+>", " ", page).lower()
            for bad in ("bias score", "biased", "bias rating", "left-wing", "right-wing", "liberal bias", "conservative bias"):
                self.assertNotIn(bad, text, f"{f}: {bad}")

    def test_sitemap_lists_shows_and_pairs(self):
        urls = re.findall(r"<loc>([^<]+)</loc>", self.read("sitemap.xml"))
        self.assertEqual(len(urls), len(set(urls)))
        n = len(self.shows)
        self.assertEqual(sum(1 for u in urls if "/show/" in u), n)
        self.assertEqual(sum(1 for u in urls if re.search(r"/compare/.+-vs-.+/$", u)), n * (n - 1) // 2)
        for u in urls:
            self.assertIn(f'<link rel="canonical" href="{u}">', self.read(u[len(SITE_URL) + 1:] + "index.html"))

    def test_paused_show_comes_down(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(self.tmp / "data", Path(tmp) / "data")
            f = Path(tmp) / "data" / "shows.json"
            d = json.loads(f.read_text())
            slug = self.shows[0]["slug"]
            next(s for s in d["shows"] if s["slug"] == slug)["paused"] = "opted out (test)"
            f.write_text(json.dumps(d))
            build(Path(tmp) / "data", Path(tmp) / "dist")
            self.assertFalse((Path(tmp) / "dist" / "show" / slug).exists())
            self.assertNotIn(f"/show/{slug}/", (Path(tmp) / "dist" / "sitemap.xml").read_text())

    def test_sponsor_only_when_set(self):
        self.assertNotIn("data-sponsor", self.read("index.html"))


if __name__ == "__main__":
    unittest.main()
