/*
 * Panels page: the run's boards side by side (wheel zooms, drag moves,
 * double-click on the background fits, on a drawing shows it full screen),
 * every drawing a button at its place on the panel. A
 * drawing opens the card on the right: its image, then a provenance graph
 * (drawing -> skill -> what that skill read -> ...) and a story of the
 * picked node. The detailed timeline sits under the boards; a drawing marks
 * its skill's row, a row outlines that skill's drawings. API: see app.js.
 */

const NO_LAYOUT = "This run has no layout file, so its drawings can't be traced.";
const NO_ITEMS = "This run's layout places no drawings, so they can't be traced.";
const MODEL = { opus: "Opus", sonnet: "Sonnet" };
const KIND = { first: "First run", second: "Second run", rerun: "Rerun" };
const BOARD_H = 1000;          // stage units per panel height
const BOARD_GAP = 44;
const LABEL_H = 28;
// provenance graph, px
const NW = 108, NH = 46, COL_GAP = 20, ROW_GAP = 6, HEAD_H = 18, PAD = 2, ARC = 14;

let state = null;              // everything mount made, for unmount

/* ---------- small helpers ---------- */
const pad2 = n => String(n).padStart(2, "0");
function clock(run, t) {
  if (!run.start) return `${Math.round(t)} min`;
  const [h, m] = run.start.split(":").map(Number);
  const x = (((h * 60 + m + Math.round(t)) % 1440) + 1440) % 1440;
  return `${pad2(Math.floor(x / 60))}:${pad2(x % 60)}`;
}
const usd = v => (v === null || v === undefined ? null : "$" + Number(v).toFixed(2));
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

/* ---------- provenance graph ---------- */
// Columns: 0 the drawing (when there is one), then the skill, then each level
// of reads. A node sits in the first column it reaches. Every read between two
// nodes on screen is drawn: into the next column as an S-curve, within a
// column or back to an earlier one as a quiet arc. reads_end and after_end
// reads are dashed. The picked node's lines stand out, the rest fade.
function loopIndex(run) {
  const idx = {};
  ((run.loop && run.loop.nodes) || []).forEach(n => { idx[n.id] = n; });
  return idx;
}
// every read of a node: [{to, end}]
function readsOf(n) {
  if (!n) return [];
  const reads = n.reads || [], ends = n.after_end || [], rEnd = n.reads_end || [];
  return [...new Set([...reads, ...rEnd])].map(to => ({ to, end: !(reads.includes(to) && !ends.includes(to)) }));
}
function graphLevels(loopNodes, rootSkill, depth) {
  const seen = new Set([rootSkill]);
  const levels = [[rootSkill]];
  let more = 0;
  for (let L = 0; L <= depth; L++) {
    const next = [];
    levels[L].forEach(src => readsOf(loopNodes[src]).forEach(({ to }) => {
      if (!seen.has(to)) { seen.add(to); next.push(to); }
    }));
    if (!next.length) break;
    if (L === depth) { more = next.length; break; }
    levels.push(next);
  }
  return { levels, more };
}

function nodeInfo(run, id, loopNodes) {
  const s = (run.skills || {})[id];
  const ln = loopNodes[id];
  if (s) {
    const n = (s.runs || []).length;
    const sub = [MODEL[s.model || (ln && ln.model)], usd(s.usd)].filter(Boolean).join(" · ") || "model unknown";
    return { name: id, sub, sub2: n ? plural(n, "run") : "no runs logged", red: !!s.red, kind: "skill" };
  }
  if (ln && ln.kind === "input") return { name: id, sub: "input", red: false, kind: "input" };
  if (ln && ln.kind === "lead") return { name: id, sub: "the lead's script", red: false, kind: "lead" };
  if (ln) return { name: id, sub: [MODEL[ln.model], "not in this run"].filter(Boolean).join(" · "), red: false, kind: "skill" };
  if (/^every/.test(id)) return { name: id, sub: "a group of skills", red: false, kind: "group" };
  return { name: id, sub: "not in this run", red: false, kind: "other" };
}

function drawGraph(box, run, ctx, loopNodes) {
  const { esc } = window.Site;
  const g = graphLevels(loopNodes, ctx.skill, ctx.depth);
  const cols = [];
  if (ctx.item) cols.push([{ id: "§item", info: { name: ctx.item.caption || ctx.item.id, sub: ctx.item.scale || "drawing", red: false, kind: "item" } }]);
  g.levels.forEach(lv => cols.push(lv.map(id => ({ id, info: nodeInfo(run, id, loopNodes) }))));
  const heads = (ctx.item ? ["Drawing"] : []).concat(["Made by", "Reads"]);
  while (heads.length < cols.length) heads.push("Which read");
  const colOf = {};
  cols.forEach((col, c) => col.forEach(n => { colOf[n.id] = c; }));

  // every read between nodes on screen
  const edges = [];
  if (ctx.item) edges.push({ from: "§item", to: ctx.skill, end: false });
  Object.keys(colOf).forEach(src => readsOf(loopNodes[src]).forEach(({ to, end }) => {
    if (colOf[to] !== undefined && to !== src) edges.push({ from: src, to, end });
  }));
  const forward = e => colOf[e.to] === colOf[e.from] + 1;

  // order each column by its readers' rows, so the forward lines stay tidy
  const row = {};
  cols.forEach((col, c) => {
    if (c > 0) {
      const bary = id => {
        const ps = edges.filter(e => e.to === id && forward(e) && row[e.from] !== undefined).map(e => row[e.from]);
        return ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 0;
      };
      col.sort((a, b) => bary(a.id) - bary(b.id));
    }
    col.forEach((n, i) => { row[n.id] = i; });
  });
  // columns start at the top, so the drawing and its skill show first;
  // the "+ n more" button sits under the deepest column
  const slots = c => cols[c].length + (g.more && c === cols.length - 1 ? 1 : 0);
  const tallest = Math.max(...cols.map((_, c) => slots(c)), 1);
  const H = HEAD_H + PAD * 2 + tallest * NH + (tallest - 1) * ROW_GAP;
  const W = cols.length * NW + (cols.length - 1) * COL_GAP + PAD * 2 + ARC;
  const pos = {};
  cols.forEach((col, c) => col.forEach((n, i) => {
    pos[n.id] = { x: PAD + c * (NW + COL_GAP), y: HEAD_H + PAD + i * (NH + ROW_GAP) };
  }));

  const sel = ctx.sel;
  const edgeSvg = edges.map(e => {
    const a = pos[e.from], b = pos[e.to];
    const y1 = a.y + NH / 2, y2 = b.y + NH / 2;
    let d, kind;
    if (forward(e)) {
      // a shared trunk in the gap with rounded turns, so a fan reads as one line with branches
      const x1 = a.x + NW, x2 = b.x, mx = (x1 + x2) / 2, dy = y2 - y1;
      const r = Math.min(6, Math.abs(dy) / 2), sg = Math.sign(dy);
      d = dy ? `M${x1} ${y1}H${mx - r}Q${mx} ${y1} ${mx} ${y1 + sg * r}V${y2 - sg * r}Q${mx} ${y2} ${mx + r} ${y2}H${x2}`
        : `M${x1} ${y1}H${x2}`;
      kind = "";
    } else if (colOf[e.to] === colOf[e.from]) {
      // same column: an arc out to the right, wider for nodes further apart
      const x = a.x + NW, off = Math.min(ARC - 2, 6 + Math.abs(row[e.to] - row[e.from]) * 2);
      d = `M${x} ${y1 - 6}C${x + off} ${y1 - 6} ${x + off} ${y2 + 6} ${x} ${y2 + 6}`;
      kind = " arc";
    } else {
      // back to an earlier column: from the reader's left side to the read's right side
      const x1 = a.x, x2 = b.x + NW, k = Math.max(16, (x1 - x2) / 3);
      d = `M${x1} ${y1 + 8}C${x1 - k} ${y1 + 8} ${x2 + k} ${y2 + 8} ${x2} ${y2 + 8}`;
      kind = " arc";
    }
    const on = sel && (e.from === sel || e.to === sel);
    return { on, svg: `<path class="pg-edge${kind}${e.end ? " end" : ""}${sel ? (on ? " hl" : " dim") : ""}" d="${d}"/>` };
  }).sort((p, q) => p.on - q.on).map(p => p.svg).join("");
  const headSvg = heads.map((h, c) =>
    `<text class="pg-head" x="${PAD + c * (NW + COL_GAP)}" y="11">${esc(h)}</text>`).join("");
  const nodeSvg = cols.flat().map(n => {
    const p = pos[n.id], i = n.info;
    const cls = ["pg-node", i.kind, i.red ? "red" : "", sel === n.id ? "sel" : ""].filter(Boolean).join(" ");
    const label = [i.name, i.sub, i.sub2, i.red ? "has problems" : ""].filter(Boolean).join(", ");
    return `<g class="${cls}" data-id="${esc(n.id)}" transform="translate(${p.x} ${p.y})" tabindex="0" role="button" aria-label="${esc(label)}">` +
      `<title>${esc(i.name)}</title><rect width="${NW}" height="${NH}" rx="5"/>` +
      `<text class="pg-name" x="9" y="15" data-max="${NW - (i.red ? 24 : 13)}">${esc(i.name)}</text>` +
      `<text class="pg-sub" x="9" y="28" data-max="${NW - 16}">${esc(i.sub)}</text>` +
      (i.sub2 ? `<text class="pg-sub" x="9" y="39" data-max="${NW - 16}">${esc(i.sub2)}</text>` : "") +
      (i.red ? `<circle cx="${NW - 10}" cy="11" r="3"/>` : "") + `</g>`;
  }).join("");
  let moreSvg = "";
  if (g.more) {
    const c = cols.length - 1, x = PAD + c * (NW + COL_GAP), y0 = HEAD_H + PAD + cols[c].length * (NH + ROW_GAP);
    moreSvg = `<g class="pg-node pg-more" data-more="1" transform="translate(${x} ${y0})" tabindex="0" role="button" aria-label="Show ${g.more} more, the next level">` +
      `<rect width="${NW}" height="${NH}" rx="5"/><text class="pg-name" x="9" y="15">+ ${g.more} more</text>` +
      `<text class="pg-sub" x="9" y="28">the next level</text></g>`;
  }
  box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-label="What this drawing was made from">${edgeSvg}${headSvg}${nodeSvg}${moreSvg}</svg>`;
  // shorten names that don't fit their box
  box.querySelectorAll("text[data-max]").forEach(t => {
    const max = +t.dataset.max;
    let s = t.textContent;
    if (t.getComputedTextLength() <= max) return;
    while (s.length > 1 && t.getComputedTextLength() > max) { s = s.slice(0, -1); t.textContent = s.trimEnd() + "…"; }
  });
  if (!(run.loop && run.loop.nodes)) {
    box.insertAdjacentHTML("beforeend", `<p class="pg-none muted">This run has no record of what each skill reads.</p>`);
  }
}

/* ---------- story ---------- */
// first run -> art direction's fixes and the issues -> the redraw -> least sure -> the jury
function step(title, html, bad) {
  return `<div class="pp-step${bad ? " bad" : ""}"><div class="t">${title}</div>${html}</div>`;
}
function storyHtml(run, id, item, loopNodes) {
  const { esc } = window.Site;
  const links = (run.jury && run.jury.links) || {};
  const skills = run.skills || {};
  const s = skills[id];
  const info = nodeInfo(run, id, loopNodes);
  const out = [];
  const meta = esc([info.sub, info.sub2].filter(Boolean).join(" · "));

  // what it read, red ones marked
  const names = list => list.map(t => skills[t] && skills[t].red
    ? `<span class="pp-red">${esc(t)}<i aria-hidden="true"></i><span class="pp-sr"> (has problems)</span></span>` : esc(t)).join(", ");
  const rs = readsOf(loopNodes[id]);
  const now = rs.filter(r => !r.end).map(r => r.to), atEnd = rs.filter(r => r.end).map(r => r.to);
  if (rs.length) {
    out.push(step("Reads", (now.length ? names(now) : `<span class="muted">nothing at the start</span>`) +
      (atEnd.length ? `<div class="pp-fix"><span class="muted">At the end:</span> ${names(atEnd)}</div>` : ""), false));
  }
  // a jury point is red only when it sits on a problem: a fix or issue of the skill, or a flagged drawing
  const juryItem = item ? (links[item.id] || []).map(x => step("Jury, on this drawing", esc(x), !!item.flagged)) : [];
  if (!s) {
    const what = { input: "An input of the run, not a skill.", lead: "One of the lead's scripts, not a skill.",
      group: "A group: it stands for every skill it names." }[info.kind] || "This skill has no record in this run.";
    out.push(`<p class="muted">${esc(what)}</p>`);
    (links[id] || []).forEach(x => out.push(step("Jury", esc(x), false)));
    return `<h3>${esc(id)}</h3><div class="meta mono">${meta}</div><div class="pp-story">${out.join("")}</div>`;
  }
  const runStep = b => step(
    `${esc(KIND[b.kind] || b.kind)} · <span class="num">${esc(clock(run, b.t0))}–${esc(clock(run, b.t1))}</span>`,
    b.line ? esc(b.line) : `<span class="muted">no log line</span>`, false);
  const runs = (s.runs || []).slice().sort((a, b) => a.t0 - b.t0);
  const firstAt = Math.max(0, runs.findIndex(b => b.kind === "first"));
  if (runs.length) out.push(runStep(runs[firstAt]));
  if (item && item.flagged) out.push(step("Frame check", esc(item.flagged), true));
  const fixes = s.fixes || [], issues = s.issues || [];
  if (fixes.length) {
    out.push(step(`Art direction's fixes · ${fixes.length}`, `<ul>${fixes.map(f => `<li>${esc(f)}</li>`).join("")}</ul>`, true));
  }
  issues.forEach(x => out.push(step(
    `Issue${x.severity ? " · " + esc(x.severity) : ""}`,
    esc(x.issue) + (x.fix ? `<div class="pp-fix muted">Fix: ${esc(x.fix)}</div>` : ""), true)));
  runs.forEach((b, i) => { if (i !== firstAt) out.push(runStep(b)); });
  if (s.unsure) out.push(step("Least sure", esc(s.unsure), true));
  out.push(...juryItem);
  const tied = fixes.length > 0 || issues.length > 0;
  (links[id] || []).forEach(x => out.push(step("Jury", esc(x), tied)));
  if (!out.length) out.push(`<p class="muted">Nothing logged.</p>`);
  return `<h3>${esc(id)}${s.red ? `<span class="pp-dot" title="has problems"></span>` : ""}</h3>` +
    `<div class="meta mono">${meta}</div><div class="pp-story">${out.join("")}</div>`;
}

/* ---------- the page ---------- */
function mount(el, run) {
  const { esc } = window.Site;
  if (!run) return;
  const panels = run.panels || [];
  const traced = !!(run.has && run.has.layout);   // no layout file: no areas, even if Items came through
  const items = traced ? panels.flatMap(p => (p.items || []).map(it => ({ ...it, panel: p.n }))) : [];
  const line = !traced ? NO_LAYOUT : items.length ? null : NO_ITEMS;

  el.innerHTML = `
    <div class="pp">
      <section class="pp-boards" aria-label="Panels">
        <div class="pp-stage"></div>
        ${panels.length ? `<div class="pp-hint mono">Scroll to zoom · drag to move · double-click a drawing for full screen, the background to fit</div>` : ""}
        ${line ? `<div class="pp-line float">${esc(line)}</div>` : ""}
      </section>
      <aside class="pp-card side"><div class="label pp-lbl"></div><h2 aria-live="polite" hidden></h2><div class="pp-body"></div></aside>
      <div class="pp-tl"></div>
    </div>`;
  const boards = el.querySelector(".pp-boards");
  const stage = el.querySelector(".pp-stage");
  const cardEl = el.querySelector(".pp-card");
  const st = state = { el, ro: null, tip: null, tl: null };

  /* boards */
  let x = 0;
  const hots = [];
  panels.forEach(p => {
    const w = p.w_px && p.h_px ? (BOARD_H * p.w_px) / p.h_px : BOARD_H * 0.707;
    const b = document.createElement("div");
    b.className = "pp-board";
    Object.assign(b.style, { left: x + "px", top: LABEL_H + "px", width: w + "px", height: BOARD_H + "px" });
    b.innerHTML = `<span class="pp-n mono">PANEL ${esc(p.n)}</span>` +
      (p.img ? `<img src="${esc(p.img)}" alt="Panel ${esc(p.n)}" draggable="false" decoding="async">` : "");
    items.filter(i => i.panel === p.n).forEach(item => {
      const it = item;
      const h = document.createElement("button");
      h.type = "button";
      h.className = "pp-hot";
      Object.assign(h.style, { left: it.x * 100 + "%", top: it.y * 100 + "%", width: it.w * 100 + "%", height: it.h * 100 + "%" });
      h.setAttribute("aria-label", `${it.caption || it.id}, by ${it.skill}`);
      h._item = item;
      b.appendChild(h);
      hots.push(h);
    });
    stage.appendChild(b);
    x += w + BOARD_GAP;
  });
  const stageW = Math.max(1, x - BOARD_GAP), stageH = BOARD_H + LABEL_H;
  stage.style.width = stageW + "px";
  stage.style.height = stageH + "px";
  if (!panels.length) boards.insertAdjacentHTML("beforeend", `<p class="view-msg">This run has no panels.</p>`);

  /* zoom and pan */
  let view = { s: 1, x: 0, y: 0 }, fit = { s: 1, x: 0, y: 0 }, touched = false;
  const apply = () => {
    stage.style.transform = `translate(${view.x}px,${view.y}px) scale(${view.s})`;
    stage.style.setProperty("--inv", 1 / view.s);   // keeps outlines one screen pixel wide at any zoom
  };
  const refit = () => {
    const vw = boards.clientWidth, vh = boards.clientHeight;
    if (!vw || !vh) return;
    const s = Math.min((vw - 48) / stageW, (vh - 40) / stageH);
    fit = { s, x: (vw - stageW * s) / 2, y: (vh - stageH * s) / 2 };
    if (!touched) { view = { ...fit }; apply(); }
  };
  const zoomAt = (px, py, k) => {
    const s = Math.min(fit.s * 14, Math.max(fit.s * 0.6, view.s * k));
    k = s / view.s;
    view = { s, x: px - (px - view.x) * k, y: py - (py - view.y) * k };
    touched = true;
    apply();
  };
  st.ro = new ResizeObserver(refit);
  st.ro.observe(boards);
  refit();

  boards.addEventListener("wheel", e => {
    if (!panels.length) return;
    e.preventDefault();
    const r = boards.getBoundingClientRect();
    const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1);
    zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-dy * 0.0015));
  }, { passive: false });
  boards.addEventListener("dblclick", e => {
    e.preventDefault();
    const hot = e.target.closest && e.target.closest(".pp-hot");
    if (hot && hot._item.img) { openFull(hot._item); return; }
    touched = false;
    view = { ...fit };
    apply();
  });
  // one pointer drags, two pinch; capture only once it moves, so a click still reaches a drawing
  const ptrs = new Map();
  let moved = false, last = null;
  const pinch = () => {
    const [a, b] = [...ptrs.values()];
    return { d: Math.hypot(a.x - b.x, a.y - b.y), x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  };
  boards.addEventListener("pointerdown", e => {
    if (e.button !== 0 || !panels.length) return;
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY });
    if (ptrs.size === 1) moved = false;
    last = ptrs.size === 2 ? pinch() : null;
  });
  boards.addEventListener("pointermove", e => {
    const p = ptrs.get(e.pointerId);
    if (p) {
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      if (!moved && Math.hypot(p.x - p.x0, p.y - p.y0) > 4) {
        moved = true;
        boards.classList.add("dragging");
        hideTip();
      }
      if (moved && !boards.hasPointerCapture(e.pointerId)) boards.setPointerCapture(e.pointerId);
      if (!moved) return;
      if (ptrs.size === 2) {
        const now = pinch(), r = boards.getBoundingClientRect();
        if (last && last.d) {
          view.x += now.x - last.x; view.y += now.y - last.y;
          zoomAt(now.x - r.left, now.y - r.top, now.d / last.d);
        }
        last = now;
      } else if (ptrs.size === 1) {
        view.x += dx; view.y += dy;
        touched = true;
        apply();
      }
      return;
    }
    const hot = e.target.closest && e.target.closest(".pp-hot");
    if (hot) showTip(e, `<b>${esc(hot._item.caption || hot._item.id)}</b><br>${esc(hot._item.skill)}${hot._item.scale ? " · " + esc(hot._item.scale) : ""}`);
    else hideTip();
  });
  const up = e => {
    ptrs.delete(e.pointerId);
    last = ptrs.size === 2 ? pinch() : null;
    if (!ptrs.size) boards.classList.remove("dragging");
  };
  boards.addEventListener("pointerup", up);
  boards.addEventListener("pointercancel", up);
  boards.addEventListener("pointerleave", hideTip);
  boards.addEventListener("click", e => {
    const hot = e.target.closest(".pp-hot");
    if (!hot || (moved && e.detail !== 0)) return;   // detail 0: a key press, never a drag
    pickItem(hot._item);
  });

  /* tooltip, this page's own */
  function showTip(e, html) {
    if (!st.tip) {
      st.tip = document.createElement("div");
      st.tip.className = "tip";
      document.body.appendChild(st.tip);
    }
    const t = st.tip;
    t.innerHTML = html;
    t.classList.add("on");
    const w = t.offsetWidth, h = t.offsetHeight;
    t.style.left = Math.max(4, e.clientX + 12 + w > innerWidth ? e.clientX - 12 - w : e.clientX + 12) + "px";
    t.style.top = Math.max(4, e.clientY + 12 + h > innerHeight ? e.clientY - 12 - h : e.clientY + 12) + "px";
  }
  function hideTip() { if (st.tip) st.tip.classList.remove("on"); }

  /* one drawing, full screen; where the browser refuses real full screen it still fills the window */
  function openFull(item) {
    if (st.full) return;
    hideTip();
    const back = document.activeElement;
    const box = document.createElement("div");
    const title = item.caption || item.id;
    box.className = "pp-full";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", title);
    box.innerHTML = `<div class="pp-full-bar"><b>${esc(title)}</b><span class="mono muted">${esc(item.skill)}</span><button class="btn" type="button">Close</button></div>` +
      `<img src="${esc(item.img)}" alt="${esc(title)}">`;
    const onKey = e => { if (e.key === "Escape") close(); };
    const onScreen = () => { if (!document.fullscreenElement) close(); };
    function close() {
      if (st.full !== close) return;
      st.full = null;
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("fullscreenchange", onScreen);
      if (document.fullscreenElement === box) document.exitFullscreen().catch(() => {});
      box.remove();
      if (back && back.isConnected) back.focus({ preventScroll: true });
    }
    box.addEventListener("click", e => { if (!e.target.closest(".pp-full-bar") || e.target.closest(".btn")) close(); });
    document.addEventListener("keydown", onKey);
    document.addEventListener("fullscreenchange", onScreen);
    st.full = close;
    document.body.appendChild(box);
    box.querySelector(".btn").focus({ preventScroll: true });
    if (box.requestFullscreen) box.requestFullscreen().catch(() => {});
  }

  /* card: a label, the title (the only live part, so a pick is announced once) and the body */
  const loopNodes = loopIndex(run);
  const lblEl = cardEl.querySelector(".pp-lbl"), titleEl = cardEl.querySelector("h2"), bodyEl = cardEl.querySelector(".pp-body");
  let ctx = null;   // {item|null, skill, depth, sel}
  function renderCard() {
    if (!ctx) {
      lblEl.textContent = items.length ? "Drawing" : "Skill";
      titleEl.hidden = true;
      bodyEl.innerHTML = `<p class="muted pp-empty">${items.length
        ? "Click a drawing on the panels to see which skill made it and what that skill read."
        : "Pick a row in the timeline to see that skill's story and what it read."}</p>`;
      return;
    }
    const it = ctx.item;
    lblEl.textContent = it ? `Drawing · panel ${it.panel}` : "Skill";
    const title = it ? it.caption || it.id : ctx.skill;
    if (titleEl.textContent !== title) titleEl.textContent = title;
    titleEl.hidden = false;
    const head = it
      ? `<div class="meta mono">${[it.scale, it.file].filter(Boolean).map(esc).join(" · ")}</div>` +
        (it.img ? `<img class="pp-img" src="${esc(it.img)}" alt="${esc(it.caption || it.id)}">` : "") +
        (it.shows ? `<p class="pp-shows">${esc(it.shows)}</p>` : "")
      : "";
    const selId = ctx.sel === "§item" ? ctx.skill : ctx.sel;
    bodyEl.innerHTML = head +
      `<div class="label pp-gl">Made from</div><div class="pp-graph"></div>` +
      `<div class="pp-key key"><span><i class="k-read"></i>reads</span><span><i class="k-end"></i>reads at the end</span><span><i class="k-red"></i>has problems</span></div>` +
      `<div class="label pp-gl">Story</div>` + storyHtml(run, selId, selId === ctx.skill ? it : null, loopNodes);
    const box = cardEl.querySelector(".pp-graph");
    drawGraph(box, run, ctx, loopNodes);
    if (ctx.scrollEnd) { box.scrollLeft = box.scrollWidth; ctx.scrollEnd = false; }
  }
  cardEl.addEventListener("click", e => {
    const node = e.target.closest && e.target.closest(".pg-node");
    if (!node || !ctx) return;
    if (node.dataset.more) { ctx.depth += 1; ctx.scrollEnd = true; }
    else ctx.sel = node.dataset.id;
    const old = cardEl.querySelector(".pp-graph");
    const top = cardEl.scrollTop, left = old.scrollLeft, gtop = old.scrollTop;
    renderCard();
    cardEl.scrollTop = top;
    cardEl.querySelector(".pp-graph").scrollTop = gtop;
    if (!node.dataset.more) cardEl.querySelector(".pp-graph").scrollLeft = left;
    const again = cardEl.querySelector(node.dataset.more ? ".pg-more" : `.pg-node[data-id="${CSS.escape(node.dataset.id)}"]`);
    if (again) again.focus({ preventScroll: true });
  });
  cardEl.addEventListener("dblclick", e => {
    if (e.target.classList.contains("pp-img") && ctx && ctx.item) openFull(ctx.item);
  });
  cardEl.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("pg-node")) {
      e.preventDefault();
      e.target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    }
  });

  function pickItem(item) {
    hots.forEach(h => { h.classList.toggle("on", h._item === item); h.classList.remove("out"); });
    if (st.tl) st.tl.highlight(item.skill);
    ctx = { item, skill: item.skill, depth: 1, sel: item.skill };
    renderCard();
    cardEl.scrollTop = 0;
  }
  function pickSkill(skill) {
    hots.forEach(h => { h.classList.remove("on"); h.classList.toggle("out", h._item.skill === skill); });
    if (st.tl) st.tl.highlight(skill);
    ctx = { item: null, skill, depth: 1, sel: skill };
    renderCard();
    cardEl.scrollTop = 0;
  }

  renderCard();
  st.tl = window.Site.timeline(el.querySelector(".pp-tl"), run, { detailed: true, onPick: pickSkill });
}

function unmount() {
  if (!state) return;
  if (state.full) state.full();
  if (state.ro) state.ro.disconnect();
  if (state.tip) state.tip.remove();
  state = null;
}

window.Site.page("panels", { mount, unmount });
