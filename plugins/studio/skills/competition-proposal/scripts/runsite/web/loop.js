// Loop page: the skills a run used, left to right in waves, with the lead's
// steps and the redraw loop, and a comparison with another run. API: see app.js.

const NODE_W = 138, LEAD_W = 92, GAP = 40, PAD_X = 24;
const RAIL_Y = 26, TOP = 52, BOTTOM = 34, ROW_GAP = 10;
const NAME_H = 22, LINE_H = 13, PAD_B = 8, PILL_H = 24, PILL_GAP = 16;

const ALL_WORD = /^(everything|all|every summary|every skill|all skills)\b/i;
const TOPIC_WORD = /^every\s+(\S+?)(?:\s*\(end\))?$/i;

/* ---------- small helpers ---------- */
const esc = s => window.Site.esc(s);
const pad = n => String(n).padStart(2, "0");
function clock(run, t) {
  if (!run || !run.start) return `${Math.round(t)}`;
  const [h, m] = run.start.split(":").map(Number);
  const x = ((h * 60 + m + Math.round(t)) % 1440 + 1440) % 1440;
  return `${pad(Math.floor(x / 60))}:${pad(x % 60)}`;
}
function span(run, r) {
  const s = `${clock(run, r.t0)}–${clock(run, r.t1)}`;
  return run && run.start ? s : `${s} min`;
}
const cut = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
const money = x => (typeof x === "number" ? `$${x.toFixed(2)}` : "");
function words(list) {
  const a = list.map(say);
  return a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}`;
}
function say(item) {
  const t = String(item).match(TOPIC_WORD);
  return t ? `every ${t[1]} skill` : String(item);
}
const isSkill = v => v.node.kind === "skill";

/* ---------- the graph: which run of which skill waits for which ---------- */
function graph(loop) {
  const nodes = (loop && loop.nodes) || [];
  const byId = new Map(nodes.map(n => [n.id, n]));
  const g = new Map();
  const add = (key, node, second) => {
    const v = { key, id: node.id, node, second, deps: new Set(), all: false, topics: [], unknown: [] };
    g.set(key, v);
    return v;
  };
  nodes.filter(n => n.kind === "input").forEach(n => add(n.id, n, false));
  nodes.filter(n => n.kind === "skill").forEach(n => {
    add(n.id, n, false);
    if ((n.reads_end || []).length) add(n.id + "@2", n, true);
  });
  // A read names a skill's first run, or its second run when marked "(end)".
  const want = (v, items, ends) => {
    for (const raw of items || []) {
      const item = String(raw).trim();
      if (ALL_WORD.test(item)) { v.all = true; continue; }
      const t = item.match(TOPIC_WORD);
      if (t) { v.topics.push({ topic: t[1], end: ends.has(item) }); continue; }
      const n = byId.get(item);
      if (!n) { v.unknown.push(item); continue; }
      if (n.id === v.id || n.kind === "lead") continue;
      v.deps.add(ends.has(item) && g.has(item + "@2") ? item + "@2" : item);
    }
  };
  for (const n of nodes) {
    if (n.kind !== "skill") continue;
    want(g.get(n.id), n.reads, new Set(n.after_end || []));
    const second = g.get(n.id + "@2");
    if (second) { second.deps.add(n.id); want(second, n.reads_end, new Set()); }
  }
  const anc = (key, seen = new Set()) => {
    for (const d of g.get(key).deps) if (!seen.has(d)) { seen.add(d); anc(d, seen); }
    return seen;
  };
  // "every <topic>": the skills of that topic that don't wait for this one.
  for (const v of g.values()) {
    for (const { topic, end } of v.topics) {
      for (const c of g.values()) {
        if (!isSkill(c) || c.second || c.id === v.id || c.node.topic !== topic) continue;
        const key = end && g.has(c.id + "@2") ? c.id + "@2" : c.id;
        if (!anc(key).has(v.key)) v.deps.add(key);
      }
    }
  }
  // "everything": every skill that doesn't wait for this one; the first such reader goes first.
  const alls = [...g.values()].filter(v => v.all);
  const pending = new Set(alls.map(v => v.key));
  for (const v of alls) {
    const cand = [];
    for (const c of g.values()) {
      if (c.key === v.key || !isSkill(c)) continue;
      const a = anc(c.key);
      a.add(c.key);
      if (a.has(v.key) || [...a].some(k => pending.has(k))) continue;
      cand.push(c.key);
    }
    cand.filter(k => !cand.includes(k + "@2")).forEach(k => v.deps.add(k));
    pending.delete(v.key);
  }
  // Columns: 1 + the largest column of what it reads; inputs in column 0.
  const col = new Map();
  const colOf = (key, stack = new Set()) => {
    if (col.has(key)) return col.get(key);
    const v = g.get(key);
    if (v.node.kind === "input") { col.set(key, 0); return 0; }
    if (stack.has(key)) return Infinity;
    stack.add(key);
    let c = 1;
    for (const d of v.deps) c = Math.max(c, colOf(d, stack) + 1);
    stack.delete(key);
    col.set(key, c);
    return c;
  };
  g.forEach((v, k) => colOf(k));
  // The end: second runs that read everything, and what waits for them.
  const end = new Set();
  for (const v of g.values()) {
    if (v.all || [...anc(v.key)].some(k => g.get(k).all)) end.add(v.key);
  }
  return { g, col, end, anc, lead: nodes.filter(n => n.kind === "lead").map(n => n.id) };
}

/* ---------- placing: which box goes in which column ---------- */
// competition-proposal's step 2: side_by_side runs before art-direction starts;
// frames, cost and the redraw run before panel-layout's second run, which waits for them.
const SIDE_BY_SIDE_BEFORE = "art-direction";
const REDRAW_BEFORE = "panel-layout@2";

function place(G) {
  const { g, col, end, anc } = G;
  const stuckAll = [...g.keys()].filter(k => col.get(k) === Infinity);
  const inLoop = new Set(stuckAll.filter(k => anc(k).has(k)));
  // Drawn boxes: inputs, first runs, and every run in the end. A second run
  // before the end is drawn on its skill's box, with dashed lines.
  const drawn = [...g.values()].filter(v => !stuckAll.includes(v.key) && (!v.second || end.has(v.key)));
  const wave = drawn.filter(v => !end.has(v.key));
  const used = [...new Set(wave.map(v => col.get(v.key)))].sort((a, b) => a - b);
  const at = new Map(), pills = new Map();
  wave.forEach(v => at.set(v.key, used.indexOf(col.get(v.key))));
  const has = id => G.lead.includes(id);
  // side_by_side: a slim column of its own, just before art-direction.
  if (has("side_by_side") && at.get(SIDE_BY_SIDE_BEFORE) > 0) {
    const a = at.get(SIDE_BY_SIDE_BEFORE);
    for (const [k, c] of at) if (c >= a) at.set(k, c + 1);
    pills.set("side_by_side", a);
  }
  const lastWave = Math.max(0, ...wave.map(v => at.get(v.key)));
  // depth of a node counted only through nodes of the same part
  const depth = (part, memo = new Map()) => {
    const d = key => {
      if (memo.has(key)) return memo.get(key);
      memo.set(key, 0);
      let c = 0;
      for (const k of g.get(key).deps) if (part.has(k)) c = Math.max(c, d(k) + 1);
      memo.set(key, c);
      return c;
    };
    return d;
  };
  // The end: what panel-layout's second run waits for runs beside the lead's
  // checks; panel-layout's second run and what waits for it come after the redraw.
  const endNodes = drawn.filter(v => end.has(v.key));
  const target = end.has(REDRAW_BEFORE) ? REDRAW_BEFORE : (endNodes.filter(v => v.all).pop() || {}).key || null;
  const post = new Set(endNodes.filter(v => target && (v.key === target || anc(v.key).has(target))).map(v => v.key));
  const pre = new Set(endNodes.filter(v => !post.has(v.key)).map(v => v.key));
  const leadSteps = ["side_by_side", "frames", "cost"].filter(id => has(id) && !pills.has(id));
  const leadCol = leadSteps.length || pre.size ? lastWave + 1 : null;
  const dPre = depth(pre);
  pre.forEach(k => at.set(k, leadCol + dPre(k)));
  leadSteps.forEach(id => pills.set(id, leadCol));
  const beforePost = Math.max(lastWave, leadCol === null ? 0 : leadCol, ...[...pre].map(k => at.get(k)));
  const dPost = depth(post);
  post.forEach(k => at.set(k, beforePost + 1 + dPost(k)));
  let last = Math.max(0, ...at.values(), ...pills.values());
  const stuckCol = stuckAll.length ? last + 1 : null;
  stuckAll.forEach(k => at.set(k, stuckCol));
  if (stuckAll.length) last = stuckCol;
  const nodeCols = new Set(drawn.map(v => at.get(v.key)));
  const pillOnly = new Set([...pills.values()].filter(c => !nodeCols.has(c)));
  const waves = [...nodeCols].filter(c => c > 0).length;
  return {
    at, pills, pillOnly, drawn: drawn.concat(stuckAll.map(k => g.get(k))), stuck: new Set(stuckAll), inLoop,
    lastWave, leadCol, target, last, stuckCol, waves,
  };
}

/* ---------- the page ---------- */
let state = null;

function runsOf(run, id) {
  const s = run && run.skills && run.skills[id];
  return (s && s.runs) || [];
}

function boxFor(v, run, P, G) {
  const n = v.node;
  const runs = runsOf(run, v.id);
  const lines = [];
  let used = true, name = v.id;
  if (n.kind === "input") {
    lines.push("input");
  } else if (v.second) {
    const r = runs.find(x => x.kind === "second");
    used = !!r;
    lines.push(r ? `2nd ${span(run, r)}` : "2nd run, not run");
    if (v.all) lines.push("reads everything");
  } else {
    used = runs.length > 0;
    if (!used) lines.push("not run");
    else {
      const first = runs.find(x => x.kind === "first") || runs[0];
      const s = run.skills[v.id];
      lines.push([span(run, first), money(s.usd != null ? s.usd : (run.usd_by_skill || {})[v.id])].filter(Boolean).join(" · "));
      const second = runs.find(x => x.kind === "second");
      if (second && !G.end.has(v.id + "@2")) lines.push(`2nd ${span(run, second)}`);
      const re = runs.find(x => x.kind === "rerun");
      if (re) lines.push(`↺ ${span(run, re)}`);
    }
    if (v.all) lines.push("reads everything");
  }
  if (P.stuck.has(v.key)) {
    lines.length = 0;
    lines.push(P.inLoop.has(v.key) ? "waits for itself" : "skipped");
    used = false;
  }
  const sk = run && run.skills && run.skills[v.id];
  const model = (sk && sk.model) || n.model || (n.kind === "skill" ? "sonnet" : null);
  return {
    key: v.key, id: v.id, v, name, lines, used, model, kind: n.kind, col: P.at.get(v.key),
    w: NODE_W, h: NAME_H + lines.length * LINE_H + PAD_B, stuck: P.inLoop.has(v.key),
  };
}

function compareInfo(G, P, loop, other) {
  if (!other || !other.loop) return null;
  const mine = new Map(loop.nodes.map(n => [n.id, n]));
  const theirs = new Map(other.loop.nodes.map(n => [n.id, n]));
  const added = loop.nodes.filter(n => n.kind === "skill" && !theirs.has(n.id)).map(n => n.id);
  const removed = other.loop.nodes.filter(n => n.kind === "skill" && !mine.has(n.id));
  const OG = graph(other.loop), OP = place(OG);
  const ghosts = removed.map(n => {
    const c = OP.at.get(n.id);
    return { node: n, col: Math.max(1, Math.min(P.lastWave, c === undefined || c > OP.lastWave ? P.lastWave : c)) };
  });
  const changes = [];
  const diff = (a, b) => (a || []).filter(x => !(b || []).includes(x));
  if (P.waves !== OP.waves) changes.push(`${P.waves} waves instead of ${OP.waves}.`);
  const leadOf = l => l.nodes.filter(n => n.kind === "lead").map(n => n.id);
  const la = diff(leadOf(loop), leadOf(other.loop)), lg = diff(leadOf(other.loop), leadOf(loop));
  if (la.length) changes.push(`The lead's ${words(la)} step${la.length > 1 ? "s are" : " is"} new.`);
  if (lg.length) changes.push(`The lead no longer runs ${words(lg)}.`);
  for (const n of loop.nodes) {
    const o = theirs.get(n.id);
    if (n.kind !== "skill" || !o) continue;
    const add = diff(n.reads, o.reads), gone = diff(o.reads, n.reads);
    if (add.length) changes.push(`${n.id} now reads ${words(add)}.`);
    if (gone.length) changes.push(`${n.id} no longer reads ${words(gone)}.`);
    const re = n.reads_end || [], ro = o.reads_end || [];
    if (re.length && !ro.length) changes.push(`${n.id} now runs a second time at the end, reading ${words(re)}.`);
    else if (!re.length && ro.length) changes.push(`${n.id} no longer runs a second time.`);
    else {
      const ea = diff(re, ro), eg = diff(ro, re);
      if (ea.length) changes.push(`${n.id}'s second run now reads ${words(ea)}.`);
      if (eg.length) changes.push(`${n.id}'s second run no longer reads ${words(eg)}.`);
    }
    const wa = diff(n.after_end, o.after_end), wg = diff(o.after_end, n.after_end);
    if (wa.length) changes.push(`${n.id} now waits for the second run of ${words(wa)}.`);
    if (wg.length) changes.push(`${n.id} no longer waits for the second run of ${words(wg)}.`);
    const ma = n.model || "sonnet", mo = o.model || "sonnet";
    if (ma !== mo) changes.push(`${n.id} now runs on ${ma === "opus" ? "Opus" : "Sonnet"}.`);
  }
  return { added: new Set(added), removed, ghosts, changes };
}

function layout(run, G, P, cmp) {
  const boxes = P.drawn.map(v => boxFor(v, run, P, G));
  if (cmp) {
    cmp.ghosts.forEach(({ node, col }) => boxes.push({
      key: "gone:" + node.id, id: node.id, name: node.id, lines: ["not in this run"], used: false,
      gone: true, model: null, kind: "skill", col, w: NODE_W, h: NAME_H + LINE_H + PAD_B,
    }));
    boxes.forEach(b => { if (!b.gone && cmp.added.has(b.id)) b.added = true; });
  }
  // Column x positions.
  const ncol = P.last + 1;
  const xs = [];
  let x = PAD_X;
  const colW = c => (P.pillOnly.has(c) ? LEAD_W : NODE_W);
  for (let c = 0; c < ncol; c++) { xs.push(x); x += colW(c) + GAP; }
  const width = x - GAP + PAD_X;
  // Lead pills, in the order the lead runs them.
  const pills = ["side_by_side", "frames", "cost"].filter(id => P.pills.has(id))
    .map(id => ({ key: "lead:" + id, id, name: id, kind: "lead", col: P.pills.get(id), w: LEAD_W, h: PILL_H, pill: true }));
  const cols = Array.from({ length: ncol }, () => []);
  boxes.forEach(b => cols[b.col].push(b));
  pills.forEach(b => cols[b.col].push(b));
  const colH = cols.map(list => list.reduce((s, b, i) => s + b.h + (i ? (b.pill ? PILL_GAP : ROW_GAP) : 0), 0));
  const maxH = Math.max(...colH, 0);
  const byKey = new Map(boxes.map(b => [b.key, b]));
  const src = key => byKey.get(key) || byKey.get(key.replace(/@2$/, ""));
  const order = new Map(boxes.map((b, i) => [b.key, i]));
  cols.forEach((list, c) => {
    const bx = list.filter(b => !b.pill), pl = list.filter(b => b.pill);
    if (c > 0) {
      const bary = b => {
        const ys = b.v ? [...b.v.deps].map(src).filter(s => s && s.y !== undefined).map(s => s.y + s.h / 2) : [];
        return ys.length ? ys.reduce((a, y) => a + y, 0) / ys.length : Infinity;
      };
      bx.forEach(b => { b._b = bary(b); });
      bx.sort((a, b) => (a._b - b._b) || (order.get(a.key) - order.get(b.key)));
    }
    list.splice(0, list.length, ...bx, ...pl);
    let y = TOP + (maxH - colH[c]) / 2;
    list.forEach((b, i) => {
      if (i) y += b.pill ? PILL_GAP : ROW_GAP;
      b.x = xs[c];
      b.y = y;
      y += b.h;
    });
  });
  const sbs = pills.find(p => p.id === "side_by_side"), anchor = byKey.get(SIDE_BY_SIDE_BEFORE);
  if (sbs && anchor && P.pillOnly.has(sbs.col) && sbs.col < anchor.col) sbs.y = Math.max(TOP, anchor.y - PILL_H - 10);
  return { boxes, pills, byKey, src, xs, colW, width, height: TOP + maxH + BOTTOM, cols };
}

/* ---------- drawing ---------- */
const arrow = (x, y, dir) => `<path class="ah" d="M${x},${y}L${x - 5 * dir},${y - 3}L${x - 5 * dir},${y + 3}Z"/>`;
const f = n => Math.round(n * 10) / 10;

function forward(s, t, ty) {
  const sx = s.x + s.w, sy = s.y + s.h / 2, tx = t.x - 1;
  ty = ty === undefined ? t.y + t.h / 2 : ty;
  const dx = Math.max(16, (tx - sx) / 2);
  return `<path d="M${f(sx)},${f(sy)}C${f(sx + dx)},${f(sy)} ${f(tx - 4 - dx)},${f(ty)} ${f(tx - 4)},${f(ty)}"/>${arrow(tx, f(ty), 1)}`;
}
function backward(s, t) {
  if (s.col === t.col) {
    const sx = s.x + s.w, sy = s.y + s.h - 7, tx = t.x + t.w + 1, ty = t.y + t.h - 7;
    return `<path d="M${f(sx)},${f(sy)}C${f(sx + 26)},${f(sy)} ${f(tx + 30)},${f(ty)} ${f(tx + 4)},${f(ty)}"/>${arrow(tx, f(ty), -1)}`;
  }
  const sx = s.x, sy = s.y + s.h - 7, tx = t.x + t.w + 1, ty = t.y + t.h - 7;
  const dx = Math.max(16, (sx - tx) / 2);
  return `<path d="M${f(sx)},${f(sy)}C${f(sx - dx)},${f(sy)} ${f(tx + 4 + dx)},${f(ty)} ${f(tx + 4)},${f(ty)}"/>${arrow(tx, f(ty), -1)}`;
}

function draw(run, G, P, L) {
  const { boxes, pills, byKey, src } = L;
  const edges = [];
  const edge = (a, b, html, cls = "") => edges.push(`<g class="lp-edge ${cls}" data-a="${esc(a)}" data-b="${esc(b)}">${html}</g>`);
  const real = boxes.filter(b => b.v);
  for (const b of real) {
    const v = b.v;
    if (b.kind === "input") continue;
    const deps = [...v.deps];
    if (!deps.length && !v.second && !v.all) {
      boxes.filter(i => i.kind === "input").forEach(i => edge(i.key, b.key, forward(i, b)));
    }
    for (const d of deps) {
      if (v.all && !G.end.has(d)) continue;          // "everything" is written in the box
      if (v.second && d === v.id) continue;           // its own first run
      const s = src(d);
      if (!s || s === b) continue;
      edge(s.key, b.key, s.col < b.col ? forward(s, b) : backward(s, b), s.col < b.col ? "" : "end");
    }
    // A second run before the end: dashed lines from what it reads then.
    const second = G.g.get(v.id + "@2");
    if (!v.second && second && !G.end.has(second.key)) {
      for (const d of second.deps) {
        if (d === v.id) continue;
        const s = src(d);
        if (!s || s === b) continue;
        edge(s.key, b.key, s.col < b.col ? forward(s, b, b.y + b.h - 7) : backward(s, b), "end");
      }
    }
  }
  // Lead steps, as competition-proposal runs them: side_by_side before
  // art-direction; then frames, cost and the redraw before panel-layout's second run.
  const pill = id => pills.find(p => p.id === id);
  const events = run.events || [];
  const hit = re => events.find(e => re.test(e.text || ""));
  const leadUsed = { side_by_side: hit(/side_by_side/), frames: hit(/frames\.py/), cost: hit(/cost\.py/) };
  const lastWave = real.filter(b => b.col === P.lastWave && b.kind !== "input");
  const sbs = pill("side_by_side"), anchor = byKey.get(SIDE_BY_SIDE_BEFORE);
  if (sbs && anchor && sbs.col < anchor.col) edge(sbs.key, anchor.key, forward(sbs, anchor, anchor.y + 8));
  const chain = pills.filter(p => p.col === P.leadCol);
  if (chain.length) lastWave.forEach(b => edge(b.key, chain[0].key, forward(b, chain[0])));
  for (let i = 1; i < chain.length; i++) {
    const a = chain[i - 1], b = chain[i], cx = f(a.x + a.w / 2);
    edge(a.key, b.key, `<path d="M${cx},${f(a.y + a.h)}V${f(b.y - 4)}"/><path class="ah" d="M${cx},${f(b.y)}L${cx - 3},${f(b.y - 5)}L${cx + 3},${f(b.y - 5)}Z"/>`);
  }
  // What runs beside the checks (narrative's second run) is fed from the last wave.
  real.filter(b => G.end.has(b.key) && b.key !== P.target && !(P.target && G.anc(b.key).has(P.target)))
    .filter(b => ![...b.v.deps].some(d => G.end.has(d)))
    .forEach(b => lastWave.forEach(s => edge(s.key, b.key, forward(s, b))));
  // Redraw: from cost back into every skill with a rerun bar, then on into panel-layout's second run.
  let loopSvg = "";
  const cost = pill("cost") || chain[chain.length - 1];
  const target = P.target && byKey.get(P.target);
  state.loop = null;
  if (cost) {
    const reruns = G.lead.includes("redraw")
      ? real.filter(b => b.kind === "skill" && !b.v.second && runsOf(run, b.id).some(r => r.kind === "rerun")) : [];
    const sx = cost.x + cost.w, sy = cost.y + cost.h / 2;
    const xr = cost.x + L.colW(cost.col) + GAP / 2;
    const into = target ? `<path d="M${f(sx)},${f(sy)}H${f(xr)}"/>${forward({ x: xr, y: sy - 1, w: 0, h: 2 }, target)}` : "";
    if (reruns.length) {
      const all = reruns.flatMap(b => runsOf(run, b.id).filter(r => r.kind === "rerun"));
      const gx = b => b.x + b.w + GAP / 2;
      const minGx = Math.min(...reruns.map(gx));
      let p = `<path d="M${f(sx)},${f(sy)}H${f(xr)}V${RAIL_Y}H${f(minGx)}"/>`;
      reruns.forEach(b => {
        const ty = b.y + 9;
        p += `<g class="lp-drop" data-b="${esc(b.key)}"><path d="M${f(gx(b))},${RAIL_Y}V${f(ty)}H${f(b.x + b.w + 5)}"/>${arrow(b.x + b.w + 1, f(ty), -1)}</g>`;
      });
      const t0 = Math.min(...all.map(r => r.t0)), t1 = Math.max(...all.map(r => r.t1));
      const label = `redraw · ${reruns.length} skill${reruns.length > 1 ? "s" : ""} · ${span(run, { t0, t1 })}`;
      loopSvg = `<g class="lp-loop" data-key="lead:redraw" tabindex="0" role="img" aria-label="${esc(label)}">${p}${into}
        <text x="${f(xr - 6)}" y="${RAIL_Y - 7}" text-anchor="end">${esc(label)}</text></g>`;
      state.loop = { cost: cost.key, target: target ? target.key : null, reruns: reruns.map(b => b.key) };
    } else if (G.lead.includes("redraw")) {
      const lx = Math.max(PAD_X, xr - 2 * (NODE_W + GAP));
      loopSvg = `<g class="lp-loop off" data-key="lead:redraw"><path d="M${f(xr)},${f(sy)}V${RAIL_Y}H${f(lx + 5)}"/>${arrow(lx, RAIL_Y, -1)}
        <text x="${f(xr - 6)}" y="${RAIL_Y - 7}" text-anchor="end">redraw · not in this run</text></g>` +
        (into ? `<g class="lp-edge" data-a="${esc(cost.key)}" data-b="${esc(target.key)}">${into}</g>` : "");
      state.loop = { cost: cost.key, target: target ? target.key : null, reruns: [] };
    } else if (into) {
      edge(cost.key, target.key, into);
    }
  }
  // Boxes.
  const node = b => {
    const cls = ["lp-node", b.used ? "" : "off", b.added ? "added" : "", b.gone ? "gone" : "", b.stuck ? "stuck" : ""].join(" ");
    const dot = b.kind === "skill" && b.model ? `<circle cx="13" cy="13.5" r="3" class="${b.model === "opus" ? "m-opus" : "m-sonnet"}"/>` : "";
    const nx = dot ? 22 : 10;
    const lines = b.lines.map((l, i) => `<text class="mt" x="10" y="${NAME_H + 6 + i * LINE_H}">${esc(l)}</text>`).join("");
    const label = [b.name, ...b.lines].join(", ");
    return `<g class="${cls}" data-key="${esc(b.key)}" transform="translate(${f(b.x)},${f(b.y)})" tabindex="0" role="img" aria-label="${esc(label)}">
      <rect width="${b.w}" height="${f(b.h)}" rx="6"/>${dot}<text class="nm" x="${nx}" y="17.5" data-w="${b.w - nx - 6}">${esc(b.name)}</text>${lines}</g>`;
  };
  const pillSvg = b => {
    const ev = leadUsed[b.id];
    return `<g class="lp-node lp-pill ${ev ? "" : "off"}" data-key="${esc(b.key)}" transform="translate(${f(b.x)},${f(b.y)})" tabindex="0" role="img" aria-label="${esc(b.name + (ev ? ", " + clock(run, ev.t) : ", not in this run"))}">
      <rect width="${b.w}" height="${b.h}" rx="${b.h / 2}"/><text class="mt" x="${b.w / 2}" y="15.5" text-anchor="middle">${esc(b.name)}</text></g>`;
  };
  // Column numbers below.
  let n = 0;
  const pillCols = new Set(P.pills.values());
  const foot = L.xs.map((x, c) => {
    const w = L.colW(c);
    const t = c === 0 ? "in" : P.pillOnly.has(c) ? "lead" : c === P.stuckCol ? "stuck"
      : pillCols.has(c) ? `${++n} · lead` : String(++n);
    return `<text class="lp-foot" x="${f(x + w / 2)}" y="${L.height - 12}" text-anchor="middle">${t}</text>`;
  }).join("");
  return `<svg class="lp-svg" width="${f(L.width)}" height="${f(L.height)}" viewBox="0 0 ${f(L.width)} ${f(L.height)}" aria-label="The loop of this run">
    <g class="lp-edges">${edges.join("")}</g>${loopSvg}
    <g>${boxes.map(node).join("")}${pills.map(pillSvg).join("")}</g>${foot}</svg>`;
}

/* ---------- tooltip, pinned panel and highlight ---------- */
const nameOf = k => (k.endsWith("@2") ? `${k.slice(0, -2)} (2nd run)` : k.replace(/^lead:/, ""));

// What a box reads and who reads it, from the graph (lines into "everything" readers aren't drawn).
function readsOf(G, key) {
  const v = G.g.get(key);
  if (!v) return null;
  const deps = [...v.deps].filter(d => !(v.second && d === v.id)).map(nameOf);
  if (v.all) return `everything that doesn't wait for it (${deps.length})`;
  return deps.length ? deps.join(", ") : v.node.kind === "input" ? "" : "nothing but the brief and the site";
}
function readBy(G, key, svg) {
  const keys = new Set([key]);
  const second = G.g.get(key + "@2");
  if (second && !G.end.has(second.key)) keys.add(second.key);
  const own = key.replace(/@2$/, "");
  const out = new Set();
  for (const w of G.g.values()) {
    if (w.id === own) continue;
    if ([...w.deps].some(d => keys.has(d))) out.add(nameOf(w.key));
  }
  if (svg) {
    svg.querySelectorAll(".lp-edge").forEach(e => {
      if (e.dataset.a === key && e.dataset.b.startsWith("lead:")) out.add(nameOf(e.dataset.b));
    });
  }
  return [...out].join(", ");
}

function tipHtml(run, G, key, svg) {
  if (key === "lead:redraw") {
    return "<b>redraw</b><br>The lead's one extra round: every skill that art direction or the frame check names draws again, then panel-layout's second run starts.";
  }
  if (key.startsWith("lead:")) {
    const id = key.slice(5);
    const re = { side_by_side: /side_by_side/, frames: /frames\.py/, cost: /cost\.py/ }[id];
    const ev = (run.events || []).find(e => re && re.test(e.text || ""));
    const what = {
      side_by_side: "puts the reference drawings beside ours, before art direction starts",
      frames: "checks each drawing against its frame on the panels",
      cost: "adds up the cost so far; past the ceiling, no redraw",
    }[id] || "";
    return `<b>${esc(id)}</b> · lead<br>${esc(what)}${ev
      ? `<br><span class="tip-dim">${esc(clock(run, ev.t))} · ${esc(cut(ev.text, 160))}</span>`
      : '<br><span class="tip-dim">not in this run</span>'}`;
  }
  if (key.startsWith("gone:")) return `<b>${esc(key.slice(5))}</b><br>In the other run, not in this one.`;
  const v = G.g.get(key);
  if (!v) return "";
  const n = v.node;
  const by = readBy(G, key, svg);
  if (n.kind === "input") return `<b>${esc(n.id)}</b><br>The project's input, shared by every run.${by ? `<br>Read by: ${esc(by)}` : ""}`;
  const parts = [`<b>${esc(n.id)}</b>${v.second ? " · second run" : ""}${n.topic ? ` <span class="tip-dim">· ${esc(n.topic)}</span>` : ""}`];
  const sk = run.skills && run.skills[n.id];
  const model = (sk && sk.model) || n.model || "sonnet";
  parts.push(`${model === "opus" ? "Opus" : "Sonnet"}${sk && sk.usd != null ? " · " + money(sk.usd) : ""}`);
  parts.push(`Reads: ${esc(readsOf(G, key))}`);
  const second = G.g.get(n.id + "@2");
  if (!v.second && second && !G.end.has(second.key)) parts.push(`Reads at the end: ${esc(readsOf(G, second.key))}`);
  parts.push(`Read by: ${esc(by || "nobody")}`);
  if (v.unknown.length) parts.push(`<span class="tip-dim">Not a skill at this commit: ${esc(v.unknown.join(", "))}</span>`);
  const runs = runsOf(run, n.id).filter(r => !v.second || r.kind === "second");
  runs.forEach(r => parts.push(`<span class="tip-dim">${esc(r.kind)} ${esc(span(run, r))}${r.line ? " · " + esc(cut(r.line, 90)) : ""}</span>`));
  if (!runs.length) parts.push('<span class="tip-dim">not run in this run</span>');
  if (state && state.P.inLoop.has(key)) parts.push('<span class="tip-dim">It waits for a skill that waits for it, so it never runs.</span>');
  else if (state && state.P.stuck.has(key)) parts.push('<span class="tip-dim">Skipped: it waits for skills that wait for each other.</span>');
  return parts.join("<br>");
}

// Lines into the box in --ink, lines out of it in --ink2, the rest faded.
function highlight(svg, key) {
  svg.classList.toggle("hl", !!key);
  const rel = new Set(key ? [key] : []);
  svg.querySelectorAll(".lp-edge").forEach(e => {
    const into = !!key && e.dataset.b === key, from = !!key && e.dataset.a === key;
    e.classList.toggle("in", into);
    e.classList.toggle("out", from && !into);
    if (into || from) { rel.add(e.dataset.a); rel.add(e.dataset.b); }
  });
  const lp = state.loop;
  const loopOn = !!key && !!lp && (key === "lead:redraw" || key === lp.cost);
  if (loopOn) [lp.cost, lp.target, ...lp.reruns].forEach(k => k && rel.add(k));
  svg.querySelectorAll(".lp-drop").forEach(d => d.classList.toggle("mine", !loopOn && d.dataset.b === key));
  svg.querySelectorAll(".lp-node").forEach(n => {
    n.classList.toggle("rel", rel.has(n.dataset.key));
    n.classList.toggle("pin", n.dataset.key === state.pin);
  });
  const loopG = svg.querySelector(".lp-loop");
  if (loopG) loopG.classList.toggle("on", loopOn);
}

/* A SKILL.md as html: headings and code fences here, the rest by Site.md. */
function skillHtml(text) {
  const out = [];
  let chunk = [], code = null;
  const flush = () => { if (chunk.length) out.push(window.Site.md(chunk.join("\n"))); chunk = []; };
  for (const line of text.split("\n")) {
    if (/^\s*```/.test(line)) {
      if (code) { out.push(`<pre>${esc(code.join("\n"))}</pre>`); code = null; } else { flush(); code = []; }
      continue;
    }
    if (code) { code.push(line); continue; }
    const h = line.match(/^#{1,6}\s+(.*)/);
    if (h) { flush(); out.push(`<h3>${esc(h[1])}</h3>`); continue; }
    chunk.push(line);
  }
  if (code) out.push(`<pre>${esc(code.join("\n"))}</pre>`);
  flush();
  return out.join("");
}

/* The node behind a box, from the other run's loop when the skill exists only there. */
function nodeOf(key) {
  if (key.startsWith("lead:")) return null;
  const gone = key.startsWith("gone:");
  const loop = gone ? state.other && state.other.loop : state.run.loop;
  const id = key.replace(/^gone:/, "").replace(/@2$/, "");
  return loop ? loop.nodes.find(n => n.id === id) || null : null;
}

function pinPanel() {
  const card = state.el.querySelector(".lp-card");
  const svg = state.el.querySelector(".lp-svg");
  if (!card) return;
  const lbl = card.querySelector(".lp-lbl"), title = card.querySelector("h2"), body = card.querySelector(".lp-body"), clear = card.querySelector(".lp-unpin");
  const key = state.pin;
  card.scrollTop = 0;
  clear.hidden = !key || !svg;
  if (!key || !svg) {
    lbl.textContent = "Skill";
    title.hidden = true;
    body.innerHTML = '<p class="muted lp-hint">Click a box, or press Enter on it, to read that skill and keep its lines lit while you scroll. Escape clears it.</p>';
    return;
  }
  let reads = "", by = "";
  if (key.startsWith("lead:") || key.startsWith("gone:")) {
    const ins = new Set(), outs = new Set();
    svg.querySelectorAll(".lp-edge").forEach(e => {
      if (e.dataset.b === key) ins.add(nameOf(e.dataset.a));
      if (e.dataset.a === key) outs.add(nameOf(e.dataset.b));
    });
    const lp = state.loop;
    if (lp && key === lp.cost) {
      if (lp.reruns.length) outs.add("redraw");
      if (lp.target) outs.add(nameOf(lp.target));
    }
    if (lp && key === "lead:redraw") {
      ins.add(nameOf(lp.cost));
      lp.reruns.forEach(k => outs.add(nameOf(k)));
    }
    reads = [...ins].join(", ");
    by = [...outs].join(", ");
    if (lp && key === "lead:redraw" && lp.target) by += `${by ? ", then " : ""}${nameOf(lp.target)}`;
  } else {
    reads = readsOf(state.G, key) || "";
    const second = state.G.g.get(key + "@2");
    if (second && !state.G.end.has(second.key)) reads += `; at the end: ${readsOf(state.G, second.key)}`;
    by = readBy(state.G, key, svg);
  }
  const node = nodeOf(key);
  const isSkill = !!node && node.kind === "skill";
  const name = nameOf(key.replace(/^gone:/, ""));
  lbl.textContent = isSkill ? `Skill${node.topic ? ` · ${node.topic}` : ""}` : key.startsWith("lead:") ? "Lead's step" : "Input";
  if (title.textContent !== name) title.textContent = name;
  title.hidden = false;
  const commit = key.startsWith("gone:") ? state.other.loop.commit : state.run.loop.commit;
  const meta = isSkill ? [node.model === "opus" ? "Opus" : "Sonnet", commit ? `SKILL.md at ${commit}` : ""].filter(Boolean).join(" · ") : "";
  const text = !isSkill ? `<p class="muted">${key.startsWith("lead:") ? "A step the lead runs itself, so it has no skill text of its own." : "An input to the run, not a skill."}</p>`
    : node.text ? `<div class="md lp-text">${skillHtml(node.text)}</div>`
    : '<p class="muted">This build has no text for this skill.</p>';
  body.innerHTML = `${meta ? `<div class="meta mono">${esc(meta)}</div>` : ""}
    <dl class="lp-rel"><dt>Reads</dt><dd>${esc(reads || "nothing")}</dd><dt>Read by</dt><dd>${esc(by || "nobody")}</dd></dl>
    ${isSkill ? '<div class="label lp-tl">Skill text</div>' : ""}${text}`;
}

function setPin(key) {
  state.pin = key || null;
  const svg = state.el.querySelector(".lp-svg");
  if (svg && state.pin && ![...svg.querySelectorAll("[data-key]")].some(n => n.dataset.key === state.pin)) state.pin = null;
  if (svg) highlight(svg, state.pin);
  pinPanel();
}

function showTip(e, html, target) {
  const tip = state.tip;
  tip.innerHTML = html;
  tip.classList.add("on");
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x, y;
  if (!target && e && e.clientX !== undefined) { x = e.clientX + 12; y = e.clientY + 12; }
  else { const r = (target || e.target).getBoundingClientRect(); x = r.right + 8; y = r.top; }
  if (x + w > innerWidth - 4) x = Math.max(4, x - w - 24);
  if (y + h > innerHeight - 4) y = Math.max(4, innerHeight - h - 4);
  tip.style.left = x + "px";
  tip.style.top = y + "px";
}

/* ---------- texts ---------- */
const HOW = `
  <p>Each box is a skill, and each line comes from its <code>Reads:</code> line: the skill on the right needs the one on the left.
  The lead, <code>competition-proposal</code>, runs each skill as its own agent, in waves: a column is a round, and a skill starts as soon as everything it reads is done.
  A skill whose input is missing is skipped, and the run's report says which input it waited for.
  A skill with a <code>Reads (end):</code> line runs again once those exist, and a dashed line points back to what it reads then.
  Before art direction the lead puts the reference drawings beside ours; after it, the lead checks the drawings against their frames and the cost and sends the skills with fixes back to redraw once, and then <code>panel-layout</code> lays out the panels again for the jury.</p>`;

function keyHtml(comparing) {
  const sw = (svg, text) => `<span><svg width="22" height="12" aria-hidden="true">${svg}</svg>${text}</span>`;
  const items = [
    sw('<circle cx="11" cy="6" r="3" class="m-opus"/>', "Opus"),
    sw('<circle cx="11" cy="6" r="3" class="m-sonnet"/>', "Sonnet"),
    sw('<path d="M1 6H21" class="k-line"/>', "reads"),
    sw('<path d="M1 6H21" class="k-line k-dash"/>', "reads again at the end"),
    sw('<path d="M21 9V3H3" class="k-loop"/><path d="M1 3L6 0.5V5.5Z" class="k-loop-ah"/>', "redraw"),
    sw('<rect x="1.5" y="1.5" width="19" height="9" rx="3" class="k-off"/>', "not run in this run"),
  ];
  if (comparing) {
    items.push(sw('<rect x="1.5" y="1.5" width="19" height="9" rx="3" class="k-added"/>', "new in this run"));
    items.push(sw('<rect x="1.5" y="1.5" width="19" height="9" rx="3" class="k-gone"/>', "gone in this run"));
  }
  return items.join("");
}

function fitNames(svg) {
  svg.querySelectorAll("text.nm").forEach(t => {
    const max = +t.dataset.w;
    if (!max || t.getComputedTextLength() <= max) return;
    const full = t.textContent;
    let s = full;
    while (s.length > 1 && t.getComputedTextLength() > max) { s = s.slice(0, -1); t.textContent = s + "…"; }
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = full;
    t.appendChild(title);
  });
}

/* ---------- render ---------- */
function render() {
  const { el, run, G, P } = state;
  const cmp = state.other ? compareInfo(G, P, run.loop, state.other) : null;
  const L = layout(run, G, P, cmp);
  const scroller = el.querySelector(".lp-scroll");
  const left = scroller.scrollLeft;
  scroller.innerHTML = draw(run, G, P, L);
  scroller.scrollLeft = left;
  el.querySelector(".lp-key").innerHTML = keyHtml(!!cmp);
  const svg = scroller.querySelector("svg");
  fitNames(svg);
  setPin(state.pin);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (state && svg.isConnected) fitNames(svg); });
  // The differences, in plain words.
  const box = el.querySelector(".lp-diff");
  if (!cmp) {
    const ids = keys => [...new Set(keys.map(k => G.g.get(k).id))];
    const loopIds = ids([...P.inLoop]);
    const skipped = ids([...P.stuck].filter(k => !P.inLoop.has(k))).filter(id => !loopIds.includes(id));
    const stuckNote = loopIds.length ? `<p class="bad">${esc(words(loopIds))} wait for each other, so none of them runs.` +
      (skipped.length ? ` ${esc(words(skipped))} ${skipped.length > 1 ? "are" : "is"} skipped, because ${skipped.length > 1 ? "they wait" : "it waits"} for them.` : "") + "</p>" : "";
    box.innerHTML = stuckNote;
    return;
  }
  const o = state.other;
  const added = [...cmp.added];
  const gone = cmp.removed.map(n => n.id);
  const head = `Compared with ${esc(o.label)}${o.loop.commit ? `, skills at <span class="mono">${esc(o.loop.commit)}</span>` : ""}.`;
  const lines = [];
  lines.push(added.length ? `<span class="lp-new">${esc(words(added))}</span> ${added.length > 1 ? "are" : "is"} new in this run.` : "No skill is new in this run.");
  if (gone.length) lines.push(`${esc(words(gone))} ${gone.length > 1 ? "are" : "is"} gone.`);
  box.innerHTML = `<div class="label">What changed</div><p>${head} ${lines.join(" ")}</p>` +
    (cmp.changes.length ? `<ul>${cmp.changes.map(c => `<li>${esc(c)}</li>`).join("")}</ul>` : `<p class="muted">Every skill that is in both reads the same as before.</p>`);
}

function bind(el) {
  const scroller = el.querySelector(".lp-scroll");
  const svgOf = () => scroller.querySelector("svg");
  const keyOf = e => { const g = e.target.closest && e.target.closest("[data-key]"); return g ? g.dataset.key : null; };
  const hideTip = () => state.tip.classList.remove("on");
  const over = e => {
    const key = keyOf(e), svg = svgOf();
    if (!svg) return;
    if (!state.pin) highlight(svg, key);
    if (!key) { hideTip(); return; }
    showTip(e, tipHtml(state.run, state.G, key, svg));
  };
  const out = () => {
    const svg = svgOf();
    if (svg) highlight(svg, state.pin);
    hideTip();
  };
  scroller.addEventListener("pointermove", over);
  scroller.addEventListener("pointerleave", out);
  scroller.addEventListener("focusin", e => {
    const key = keyOf(e), svg = svgOf();
    if (!key || !svg) return;
    state.focusAt = performance.now();
    if (!state.pin) highlight(svg, key);
    showTip(null, tipHtml(state.run, state.G, key, svg), e.target.closest("[data-key]"));
  });
  scroller.addEventListener("focusout", out);
  // A scroll that keyboard focus caused keeps the tooltip, moved to the focused box.
  scroller.addEventListener("scroll", () => {
    const f = document.activeElement;
    if (performance.now() - state.focusAt < 600 && f && scroller.contains(f) && f.dataset && f.dataset.key) {
      showTip(null, state.tip.innerHTML, f);
    } else hideTip();
  }, { passive: true });
  // Click a box to pin its lines; click it again, or empty space, to clear.
  scroller.addEventListener("click", e => {
    const key = keyOf(e);
    setPin(key && key !== state.pin ? key : null);
  });
  el.addEventListener("click", e => { if (e.target.closest(".lp-unpin")) setPin(null); });
  el.addEventListener("keydown", e => {
    if (e.key === "Escape" && state.pin) { setPin(null); return; }
    if ((e.key === "Enter" || e.key === " ") && scroller.contains(e.target)) {
      const key = keyOf(e);
      if (!key) return;
      e.preventDefault();
      setPin(key !== state.pin ? key : null);
    }
  });
  const sel = el.querySelector(".lp-cmp select");
  if (sel) {
    sel.addEventListener("change", () => {
      const key = sel.value;
      const seq = ++state.seq;
      const note = el.querySelector(".lp-cmp-note");
      note.textContent = "";
      if (!key) { state.other = null; render(); return; }
      window.Site.run(key).then(o => {
        if (!state || seq !== state.seq || !el.isConnected) return;
        if (!o.loop) { note.textContent = "That run has no loop."; return; }
        state.other = o;
        render();
      }).catch(err => {
        console.error(err);
        if (state && seq === state.seq && el.isConnected) note.textContent = "That run's data didn't load.";
      });
    });
  }
}

window.Site.page("loop", {
  mount(el, run) {
    const Site = window.Site;
    if (!run) { el.innerHTML = '<p class="view-msg">Pick a run to see its loop.</p>'; return; }
    const date = run.date ? run.date.split("-").reverse().join(".") : "";
    const top = [run.label, date, run.loop && run.loop.commit ? `skills at ${run.loop.commit}` : ""].filter(Boolean).join(" · ");
    const head = sum => `<header class="lp-head">
        <div class="mono muted lp-over">${esc(top.toUpperCase())}</div>
        <h1>${esc(run.title || run.label)}</h1>
        ${sum ? `<p class="lp-sum muted num">${esc(sum)}</p>` : ""}
        <div class="label">How a run works</div>
        <div class="lp-how">${HOW}</div>
      </header>`;
    if (!run.loop || !(run.loop.nodes || []).length) {
      el.innerHTML = `<div class="lp">${head("")}<p class="lp-none">This run's commit isn't known, so its loop can't be drawn.</p></div>`;
      return;
    }
    const G = graph(run.loop);
    const P = place(G);
    const skills = run.loop.nodes.filter(n => n.kind === "skill");
    const ran = skills.filter(n => runsOf(run, n.id).length).length;
    const waves = P.waves;
    const others = Site.index.runs.filter(r => r.key !== run.key && r.has && r.has.loop).slice().reverse();
    const picker = others.length ? `<label class="lp-cmp"><span>Compare with</span>
        <select class="select"><option value="">no other run</option>${others.map(r => `<option value="${esc(r.key)}">${esc(r.title && r.title !== r.label ? `${r.label} · ${r.title}` : r.label)}</option>`).join("")}</select>
        <span class="lp-cmp-note bad" aria-live="polite"></span></label>` : "";
    el.innerHTML = `<div class="lp-wrap"><div class="lp">${head(`${skills.length} skills in ${waves} waves; ${ran} of them ran in this run.`)}
      <div class="lp-bar"><div class="lp-key key"></div>${picker}</div>
      <div class="lp-scroll" tabindex="-1"></div>
      <section class="lp-diff" aria-live="polite"></section></div>
      <aside class="lp-card side"><div class="lp-chead"><div class="label lp-lbl"></div><button type="button" class="lp-unpin btn" hidden>Clear</button></div><h2 aria-live="polite" hidden></h2><div class="lp-body"></div></aside></div>`;
    const tip = document.createElement("div");
    tip.className = "tip lp-tip";
    document.body.appendChild(tip);
    state = { el, run, G, P, tip, other: null, seq: 0, reruns: null, pin: null, focusAt: 0 };
    bind(el);
    render();
  },
  unmount() {
    if (state) {
      state.seq++;
      state.tip.remove();
    }
    state = null;
  },
});
