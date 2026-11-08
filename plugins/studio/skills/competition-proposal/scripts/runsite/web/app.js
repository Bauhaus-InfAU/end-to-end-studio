/*
 * Runs site shell. Plain ES module, no imports: everything a page needs is on
 * window.Site. Load order (index.html): app.js, timeline.js, then the pages.
 *
 * ---------------------------------------------------------------- Site API
 * Site.index                The Index (data/index.json, see the data
 *                           contract). Set before any page mounts.
 * Site.run(key)             -> Promise<Run>   data/runs/<key>.json, cached.
 *                           Rejects if the file doesn't load.
 * Site.geo(key)             -> Promise<Geo|null>   data/geo/<key>.json, cached;
 *                           key "shared" is the project's site, climate and
 *                           analysis. Resolves null when the run has no file.
 * Site.page(name, {mount(el, run), unmount()})
 *                           Register a page. name: "model" | "panels" |
 *                           "loop" | "dash".
 *                           mount(el, run): el is a fresh, empty
 *                             <main id="view"> below the top bar (absolute,
 *                             fills the window, overflow:auto; el.dataset.page
 *                             is the page name). run is the Run, or null on
 *                             #all. mount may be async.
 *                           unmount(): called before the next mount, even when
 *                             only the run changes. Stop timers, animation
 *                             frames, deck.gl instances and window listeners
 *                             here; the shell throws el away afterwards.
 * Site.go(key, page)        Navigate: sets the hash. go(key, "model"|"panels"|
 *                           "loop") -> #<key>/<page>; go(key, "dash") ->
 *                           #all/<key>; go(null, "dash") -> #all.
 * Site.esc(str)             HTML-escape (& < > " '). null/undefined -> "".
 * Site.md(str) -> html      Markdown subset: paragraphs (single line breaks
 *                           kept as <br>), **bold**, `code`, lists (- * + 1.),
 *                           pipe tables. Nothing else; all text escaped.
 *                           Wrap the result in an element with class "md".
 * Site.timeline(el, run, opts)   defined in timeline.js; see its header.
 *
 * Routes: #<key>/model  #<key>/panels  #<key>/loop  #all  #all/<key>
 * An empty or unknown route goes to the newest run's model. An unknown key
 * shows "This run isn't on the site." in the view.
 *
 * Shared CSS in app.css: tokens (--bg --paper --ink --ink2 --muted --hair
 * --hair2 --opus --sonnet --sel --issue, plus --issue-text for words in the
 * issue red, --bar for the top bar height, --sans, --mono) and the classes
 * .mono .num .muted .label .bad .float .tip (.tip.on shows it) .md .view-msg.
 * Page styles go in <page>.css, scoped under #view[data-page="<page>"].
 * ------------------------------------------------------------------------
 */

const PAGES = ["model", "panels", "loop", "dash"];
const pages = {};
const runCache = {};
const geoCache = {};

function esc(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

/* ---------- markdown subset ---------- */
function inline(text) {
  return text.split(/(`[^`]+`)/).map((part, i) => i % 2
    ? `<code>${esc(part.slice(1, -1))}</code>`
    : esc(part).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")).join("");
}
function cells(row) {
  return row.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/)
    .map(c => inline(c.trim().replace(/\\\|/g, "|")));
}
function table(rows) {
  const sep = rows.length > 1 && /^[\s|:-]+$/.test(rows[1]);
  const head = sep ? `<thead><tr>${cells(rows[0]).map(c => `<th>${c}</th>`).join("")}</tr></thead>` : "";
  const body = (sep ? rows.slice(2) : rows)
    .map(r => `<tr>${cells(r).map(c => `<td>${c}</td>`).join("")}</tr>`).join("");
  return `<div class="md-table"><table>${head}<tbody>${body}</tbody></table></div>`;
}
const IS_TABLE = /^\s*\|/;
const IS_ITEM = /^\s*([-*+]|\d+[.)])\s+/;
function md(src) {
  if (!src) return "";
  const lines = String(src).replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (IS_TABLE.test(line)) {
      const rows = [];
      while (i < lines.length && IS_TABLE.test(lines[i])) rows.push(lines[i++]);
      out.push(table(rows));
    } else if (IS_ITEM.test(line)) {
      const tag = /^\s*\d/.test(line) ? "ol" : "ul";
      const items = [];
      while (i < lines.length && lines[i].trim() && !IS_TABLE.test(lines[i])) {
        if (IS_ITEM.test(lines[i])) items.push(lines[i].replace(IS_ITEM, ""));
        else if (/^\s/.test(lines[i])) items[items.length - 1] += " " + lines[i].trim();
        else break;
        i++;
      }
      out.push(`<${tag}>${items.map(x => `<li>${inline(x)}</li>`).join("")}</${tag}>`);
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !IS_TABLE.test(lines[i]) && !IS_ITEM.test(lines[i])) {
        para.push(inline(lines[i++].trim()));
      }
      out.push(`<p>${para.join("<br>")}</p>`);
    }
  }
  return out.join("");
}

/* ---------- data ---------- */
async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}
function run(key) {
  if (!runCache[key]) {
    runCache[key] = getJSON(`data/runs/${encodeURIComponent(key)}.json`);
    runCache[key].catch(() => delete runCache[key]);
  }
  return runCache[key];
}
function geo(key) {
  if (!geoCache[key]) {
    geoCache[key] = fetch(`data/geo/${encodeURIComponent(key)}.json`)
      .then(res => res.ok ? res.json() : null);
  }
  return geoCache[key];
}

/* ---------- routing ---------- */
const picker = document.getElementById("run-picker");
let lastKey = null;      // the run the picker shows; kept while on #all
let mounted = null;      // the page object currently mounted
let routeId = 0;         // drops a mount whose route was left while it loaded

const card = key => Site.index.runs.find(r => r.key === key);
const newest = () => Site.index.runs[Site.index.runs.length - 1];

function hashFor(key, page) {
  if (page === "dash") return key ? `#all/${encodeURIComponent(key)}` : "#all";
  return `#${encodeURIComponent(key)}/${page}`;
}
function go(key, page) {
  location.hash = hashFor(key, page);
}
function parse(hash) {
  const h = decodeURIComponent(hash.replace(/^#/, ""));
  if (h === "all") return { key: null, page: "dash" };
  let m = h.match(/^all\/(.+)$/);
  if (m) return { key: m[1], page: "dash" };
  m = h.match(/^(.+)\/(model|panels|loop)$/);
  if (m) return { key: m[1], page: m[2] };
  if (h && card(h)) return { key: h, page: "model" };
  return null;
}

function freshView(page) {
  const old = document.getElementById("view");
  const el = old.cloneNode(false);
  el.removeAttribute("style");
  el.dataset.page = page;
  old.replaceWith(el);
  document.querySelectorAll(".tip.on").forEach(t => t.classList.remove("on"));
  return el;
}
function message(el, text) {
  el.innerHTML = `<p class="view-msg">${esc(text)}</p>`;
}
function updateBar(route) {
  if (route.key && card(route.key)) lastKey = route.key;
  if (!lastKey) lastKey = newest().key;
  picker.value = lastKey;
  document.querySelectorAll(".tabs a").forEach(a => {
    const page = a.dataset.page;
    a.href = page === "dash" ? "#all" : hashFor(lastKey, page);
    if (page === route.page) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const names = { model: "Model", panels: "Panels", loop: "Loop", dash: "All runs" };
  const c = route.key && card(route.key);
  document.title = [c && c.label, names[route.page], "Studio runs"].filter(Boolean).join(" · ");
}

async function route() {
  const r = parse(location.hash);
  if (!r) { location.replace(hashFor(newest().key, "model")); return; }
  const id = ++routeId;
  if (mounted) {
    try { mounted.unmount(); } catch (e) { console.error(e); }
    mounted = null;
  }
  const el = freshView(r.page);
  updateBar(r);
  if (r.key && !card(r.key)) { message(el, "This run isn't on the site."); return; }
  let data = null;
  if (r.key) {
    try { data = await run(r.key); } catch (e) {
      console.error(e);
      if (id === routeId) message(el, "This run's data didn't load.");
      return;
    }
  }
  const page = pages[r.page];
  if (id !== routeId || !page) return;
  mounted = page;
  try { await page.mount(el, data); } catch (e) { console.error(e); }
}

function fillBar() {
  const { project, runs } = Site.index;
  document.querySelector(".picker .project").textContent = project && project.name || "";
  picker.innerHTML = runs.slice().reverse().map(r => {
    const name = r.title && r.title !== r.label ? `${r.label} · ${r.title}` : r.label;
    return `<option value="${esc(r.key)}">${esc(name)}</option>`;
  }).join("");
  picker.addEventListener("change", () => {
    const r = parse(location.hash);
    go(picker.value, r ? r.page : "model");
  });
}

const Site = {
  index: null,
  run,
  geo,
  page(name, impl) {
    if (!PAGES.includes(name)) throw new Error(`Site.page: unknown page "${name}"`);
    pages[name] = impl;
  },
  go,
  esc,
  md,
};
window.Site = Site;

/* Start once the index is in and every deferred module (the pages) has run. */
const domReady = new Promise(res => document.readyState === "loading"
  ? document.addEventListener("DOMContentLoaded", res, { once: true }) : res());
Promise.all([getJSON("data/index.json"), domReady]).then(([index]) => {
  Site.index = index;
  if (!index.runs || !index.runs.length) { message(document.getElementById("view"), "No runs on the site yet."); return; }
  fillBar();
  window.addEventListener("hashchange", route);
  route();
}).catch(e => {
  console.error(e);
  message(document.getElementById("view"), "The site's data didn't load.");
});
