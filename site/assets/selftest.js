// End-to-end self-test, loaded only with ?selftest=1. Checks the page against the data it was built from
// (data/stats.json), never against fixed launch-day numbers, and writes the verdict to <html data-selftest>.
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function finish(log, error) {
  const pre = document.createElement("pre");
  pre.id = "selftest";
  pre.textContent = (error ? "FAIL: " + (error.stack || error.message || error) + "\n" : "") + log.join("\n");
  document.body.append(pre);
  document.documentElement.dataset.selftest = error ? "fail" : "pass";
}

export async function run() {
  const log = [];
  try {
    const base = new URL(document.querySelector('link[rel="icon"]').href).pathname.replace(/favicon\.svg$/, "");
    const data = await (await fetch(base + "data/stats.json")).json();
    const canonical = document.querySelector('link[rel="canonical"]').href;
    if (new URL(canonical).pathname !== location.pathname) throw new Error(`canonical ${canonical} does not match ${location.pathname}`);
    for (const node of document.querySelectorAll('script[type="application/ld+json"]')) JSON.parse(node.textContent);
    if (document.body.textContent.match(/\bbias(ed)?\b.*\bscore|\bbias rating/i)) throw new Error("judgment labels must not appear");
    const path = location.pathname.slice(base.length);
    if (path === "") {
      const rows = document.querySelectorAll("table.board tbody tr");
      if (rows.length !== data.shows.length) throw new Error(`${rows.length} rows for ${data.shows.length} shows`);
      const pace = [...rows].map((r) => Number(r.cells[1].dataset.v));
      if (pace.some((v, i) => i && v > pace[i - 1])) throw new Error("leaderboard is not sorted by pace");
      document.querySelector("table.board thead th:nth-child(4)").click();
      await wait(20);
      const q = [...document.querySelectorAll("table.board tbody tr")].map((r) => Number(r.cells[3].dataset.v));
      if (q.some((v, i) => i && v > q[i - 1])) throw new Error("sorting by questions failed");
      log.push(`leaderboard ok: ${rows.length} shows, sorting works`);
    } else if (path.startsWith("show/")) {
      const slug = path.split("/")[1];
      const show = data.shows.find((s) => s.slug === slug);
      if (!show) throw new Error("show not in stats.json: " + slug);
      if (!document.querySelector(".tiles").textContent.includes(String(Math.round(show.pace_wpm)))) throw new Error("pace tile does not match the data");
      const phrases = document.querySelectorAll(".phrases > li");
      if (phrases.length !== Math.min(12, show.signature_phrases.length)) throw new Error("phrase count does not match the data");
      for (const bq of document.querySelectorAll(".phrases blockquote")) {
        const words = bq.firstChild.textContent.replace(/[“”…]/g, "").trim().split(/\s+/).length;
        if (words > 22) throw new Error(`a quote is ${words} words long`);
      }
      const moments = document.querySelectorAll('.phrases a[href*="#t="]');
      if (show.signature_phrases.some((p) => p.moments.length) && !moments.length) throw new Error("no links to moments");
      if (document.querySelectorAll("tbody tr").length < show.episodes_analyzed) throw new Error("episodes table is short");
      log.push(`dashboard ok: ${phrases.length} phrases, ${moments.length} moment links`);
    } else if (path.startsWith("compare/") && path.length > "compare/".length) {
      const rows = document.querySelectorAll("table.vs tbody tr");
      if (rows.length !== 4) throw new Error("comparison table should have 4 rows");
      log.push("comparison ok");
    }
    log.push("page ok: " + document.querySelector("h1").textContent.trim());
    finish(log);
  } catch (error) {
    finish(log, error);
  }
}
