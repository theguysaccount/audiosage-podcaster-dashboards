// Small behaviours: copy and share, the compare pickers, sortable leaderboard, and the self-test hook.
const toast = document.getElementById("toast");
const base = new URL(document.querySelector('link[rel="icon"]').href).pathname.replace(/favicon\.svg$/, "");

function say(message) {
  toast.textContent = message;
  toast.classList.add("on");
  clearTimeout(say.t);
  say.t = setTimeout(() => toast.classList.remove("on"), 1800);
}

function track(name) {
  try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: "event/" + name, title: name, event: true }); } catch (e) { /* never break the page */ }
}

for (const button of document.querySelectorAll("[data-copy]")) {
  button.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(button.dataset.copy); say("Link copied"); } catch (e) { window.prompt("Copy this link:", button.dataset.copy); }
    track(location.pathname.includes("/compare/") ? "compare_copy" : "copy_link");
  });
}
for (const button of document.querySelectorAll("[data-share]")) {
  if (!navigator.share) { button.hidden = true; continue; }
  button.addEventListener("click", () => { navigator.share({ title: document.title, url: location.href.split("?")[0] }).catch(() => {}); track("share"); });
}
for (const select of document.querySelectorAll("select.jump")) {
  select.addEventListener("change", () => { if (select.value) { track("compare_pick"); location.href = select.value; } });
}
for (const form of document.querySelectorAll("form[data-compare]")) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const a = form.querySelector("#ca").value, b = form.querySelector("#cb").value;
    if (a === b) return say("Pick two different shows");
    const [x, y] = [a, b].sort();
    track("compare_pick");
    location.href = `${base}compare/${x}-vs-${y}/`;
  });
}
for (const table of document.querySelectorAll("table[data-sortable]")) {
  const heads = [...table.tHead.rows[0].cells];
  heads.forEach((th, col) => th.addEventListener("click", () => {
    const desc = th.getAttribute("aria-sort") !== "descending";
    heads.forEach((h) => h.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", desc ? "descending" : "ascending");
    const rows = [...table.tBodies[0].rows];
    const val = (r) => { const c = r.cells[col]; return c.dataset.v !== undefined ? Number(c.dataset.v) : c.textContent.trim().toLowerCase(); };
    rows.sort((r1, r2) => { const a = val(r1), b = val(r2); return (a > b ? 1 : a < b ? -1 : 0) * (desc ? -1 : 1); });
    rows.forEach((r) => table.tBodies[0].append(r));
    track("sort");
  }));
}
if (new URLSearchParams(location.search).has("selftest")) import("./selftest.js").then((m) => m.run());
