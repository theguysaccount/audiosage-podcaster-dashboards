# Decisions

Defaults picked without blocking on Jack. Each can be reversed.

1. **No bias or belief labels.** The note asked for podcasters "ranked on biases, beliefs". Labels like that can be
   defamatory when wrong and can't be checked by a reader. AudioSage publishes counts that anyone can verify against
   the show's own transcript: phrases, pace, vocabulary, questions, topic words, guests. The method page says so.
2. **Only shows' own transcripts.** v1 reads the transcripts shows publish in their feeds (`podcast:transcript`) and
   never downloads or transcribes audio. That keeps the job light (free Actions minutes), avoids copying audio, and
   means every number traces to a document the show itself put out. 24 of Apple's top 200 qualified in November 2026.
3. **12 shows to start, no political commentary yet.** The first set covers science and history, true crime, business
   interviews, sports talk, outdoors, storytelling, pop culture, morning radio and markets. Political shows qualify
   (Letters from an American, Armstrong & Getty, Breaking Points, The President's Daily Brief) and are listed as
   candidates; adding them means adding several perspectives at once.
4. **Show statistics, not host statistics.** Talk pace is per episode (music and ads included), not per person,
   because most transcripts don't name speakers consistently. Where they do, a "who does the talking" table appears;
   generic labels such as "Speaker 1" are ignored.
5. **Signature phrases must recur.** A phrase counts only if it appears in at least 40% of the analyzed episodes (and
   at least 3), is distinctive against the other shows (log-odds with an informative Dirichlet prior), isn't a fragment
   ending on a function word, and doesn't come from an ad read. One episode's topic is not a habit.
6. **Network feeds are filtered.** iHeart and other networks mix other shows, replays and best-ofs into a feed; per-show
   title rules in `data/shows.json` keep only the show's own new episodes.
7. **Short quotes only.** At most 20 words per quote, one per phrase on the page, each attributed and linked to the
   moment in the episode audio (`#t=` media fragment). Each episode links to the show's own transcript.
8. **Domain.** audiosage.org already hosts a site; the dashboards stay on github.io and go to a subdomain if pointed
   (OPERATIONS.md, key 1). Nothing on audiosage.org was touched.

## Questions for Jack

- Is the site on audiosage.org the earlier Audiosage project? Should it link to these dashboards, or should the
  dashboards take a path or subdomain there?
- Fan entertainment first (as built), or an advertiser tool first (paid reports on other hosting)?
- Add the political commentary shows as a set?
