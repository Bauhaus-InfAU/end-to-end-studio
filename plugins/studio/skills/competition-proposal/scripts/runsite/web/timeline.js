/*
 * Shared timeline. Adds Site.timeline to window.Site (app.js loads first).
 *
 * Site.timeline(el, run, {detailed, onTime(t), onPick(skill), grip})
 *     -> { set(t), highlight(skill | null) }
 *
 * el        an empty element; the timeline fills its width (class "tl" is
 *           added) and takes the height of its rows. The page positions el.
 * run       a Run. Rows: every skill with runs, in order of first start.
 *           Opus bars --opus, Sonnet --sonnet, reruns as outlines; check
 *           events as dashed --issue lines. t is minutes from the run start,
 *           shown as clock time when run.start is known.
 * detailed  false (default): a play button and a draggable cursor; bars that
 *             end after the cursor fade to 18 %. The cursor starts at the
 *             end without calling onTime.
 *           true: per row the skill name, its usd and a one-line state (the
 *             first of issues[0].issue, fixes[0], unsure, else "done"), red
 *             when the skill is red; check event labels above the rows.
 *             No cursor.
 * onTime(t) called when the cursor moves: drag, play, arrow keys, or set(t).
 * onPick(s) called with the skill name when a bar (or, detailed, a row name)
 *           is clicked.
 * grip      which edge resizes it: "top" (default, for a timeline pinned to the
 *           bottom of the page) or "bottom" (for one inside a scrolling page).
 * set(t)    moves the cursor to t (clamped to the run) and calls onTime(t).
 *           Does nothing when detailed.
 * highlight(skill|null)  marks that skill's row in --sel; null clears.
 *
 * Every timeline can be resized by dragging that edge (double-click for the usual
 * size) and hidden with its button; the two are one setting, kept between pages.
 * Hovering a bar shows skill, times, model and its log line in a tooltip.
 * Play stops by itself when the timeline leaves the page or is rebuilt. A run with no bars renders
 * "No timeline: this run's log has no times." and returns no-op methods.
 */

const PLAY_SECONDS = 8;          // a whole run plays in this many seconds
const FUTURE_EPS = 0.01;

/* ---------- tooltip, one for all timelines ---------- */
let tipEl = null;
function showTip(e, html) {
  if (!tipEl) {
    tipEl = document.createElement("div");
    tipEl.className = "tip";
    document.body.appendChild(tipEl);
  }
  tipEl.innerHTML = html;
  tipEl.classList.add("on");
  const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  const x = e.clientX + 12 + w > innerWidth ? e.clientX - 12 - w : e.clientX + 12;
  const y = e.clientY + 12 + h > innerHeight ? e.clientY - 12 - h : e.clientY + 12;
  tipEl.style.left = Math.max(4, x) + "px";
  tipEl.style.top = Math.max(4, y) + "px";
}
function hideTip() {
  if (tipEl) tipEl.classList.remove("on");
}

/* ---------- time ---------- */
const pad = n => String(n).padStart(2, "0");
const toMin = hhmm => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
function clock(run, t) {
  if (!run.start) return `${Math.round(t)} min`;
  const x = ((toMin(run.start) + Math.round(t)) % 1440 + 1440) % 1440;
  return `${pad(Math.floor(x / 60))}:${pad(x % 60)}`;
}
function ticks(run, T, most) {
  const step = [5, 10, 15, 20, 30, 60, 120].find(s => T / s <= most) || 240;
  const s0 = run.start ? toMin(run.start) : 0;
  const out = [];
  for (let t = Math.ceil(s0 / step) * step - s0; t <= T + 1e-9; t += step) out.push(t);
  return out;
}

function stateLine(s) {
  return (s.issues && s.issues[0] && s.issues[0].issue) || (s.fixes && s.fixes[0]) || s.unsure || "done";
}
const MODEL = { opus: "Opus", sonnet: "Sonnet" };
const ICON_PLAY = '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1l7 4-7 4z" fill="currentColor"/></svg>';
const ICON_PAUSE = '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 1h2v8H2zM6 1h2v8H6z" fill="currentColor"/></svg>';

/* ---------- size and hiding: one setting for every timeline, kept between pages and visits ---------- */
const PREFS_KEY = "runs-site.timeline";
const MIN_ROW = 4, MIN_ROW_DETAILED = 11.5;   // px; a detailed row must still fit its text
const STAGE_MIN = 340;                        // px the page keeps for what sits beside the timeline
const KEY_STEP = 0.1;
const prefs = { scale: 1, hidden: false };
try {
  const saved = JSON.parse(localStorage.getItem(PREFS_KEY)) || {};
  if (saved.scale > 0) prefs.scale = +saved.scale;
  prefs.hidden = saved.hidden === true;
} catch { /* no storage here: the setting lasts until the page is closed */ }
function savePrefs() {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch { /* as above */ }
}

function sizing(el, lanes, nRows, detailed, edge) {
  const base = parseFloat(getComputedStyle(el).getPropertyValue("--rh")) || 7;
  const least = (detailed ? MIN_ROW_DETAILED : MIN_ROW) / base;
  const grip = el.querySelector(".tl-grip");
  const toggle = el.querySelector(".tl-toggle");
  const most = () => {
    const view = document.getElementById("view");
    const room = edge === "bottom" ? view.clientHeight : view.clientHeight - STAGE_MIN;   // a scrolling page keeps nothing beside it
    return Math.max(1, (room - (el.offsetHeight - lanes.offsetHeight)) / (nRows * base));
  };
  const fit = s => Math.min(most(), Math.max(least, s));
  const apply = () => {
    if (prefs.hidden) return;
    const s = fit(prefs.scale);
    el.style.setProperty("--s", s);
    grip.setAttribute("aria-valuenow", Math.round(s * 100));
  };
  const resize = s => { prefs.scale = fit(s); apply(); };
  const showState = () => {
    el.classList.toggle("tl-hidden", prefs.hidden);
    toggle.textContent = prefs.hidden ? "Show timeline" : "Hide timeline";
    toggle.setAttribute("aria-expanded", String(!prefs.hidden));
    apply();
  };
  toggle.addEventListener("click", () => { prefs.hidden = !prefs.hidden; showState(); savePrefs(); });

  const sign = edge === "bottom" ? 1 : -1;     // dragging away from the rows makes them taller
  let from = null;
  grip.addEventListener("pointerdown", e => {
    e.preventDefault();
    hideTip();
    grip.setPointerCapture(e.pointerId);
    from = { y: e.clientY, h: lanes.offsetHeight };
  });
  grip.addEventListener("pointermove", e => {
    if (from) resize((from.h + sign * (e.clientY - from.y)) / (nRows * base));
  });
  const end = () => { if (from) savePrefs(); from = null; };
  grip.addEventListener("pointerup", end);
  grip.addEventListener("pointercancel", end);
  grip.addEventListener("dblclick", () => { resize(1); savePrefs(); });
  grip.addEventListener("keydown", e => {
    const step = { ArrowUp: -sign * KEY_STEP, ArrowDown: sign * KEY_STEP }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    resize(fit(prefs.scale) + step);
    savePrefs();
  });
  showState();
  return apply;
}

function timeline(el, run, opts = {}) {
  const { esc } = window.Site;
  const detailed = !!opts.detailed;
  const noop = { set() {}, highlight() {} };
  el.classList.add("tl");
  el.classList.toggle("detailed", detailed);

  const rows = Object.entries(run.skills || {})
    .filter(([, s]) => s.runs && s.runs.length)
    .map(([name, s]) => ({ name, s, first: Math.min(...s.runs.map(b => b.t0)) }))
    .sort((a, b) => a.first - b.first);
  if (!rows.length) {
    el.innerHTML = `<p class="tl-empty">No timeline: this run's log has no times.</p>`;
    return noop;
  }

  const checks = {};
  (run.events || []).filter(e => e.kind === "check").forEach(e => (checks[e.t] = checks[e.t] || []).push(e.text));
  const T = Math.max(run.minutes || 0, ...rows.flatMap(r => r.s.runs.map(b => b.t1)), ...Object.keys(checks).map(Number)) || 1;
  const pct = t => `${(t / T) * 100}%`;

  const edge = opts.grip === "bottom" ? "bottom" : "top";
  el.innerHTML = `
    <div class="tl-grip${edge === "bottom" ? " bottom" : ""}" role="separator" aria-orientation="horizontal" aria-label="Timeline height" tabindex="0" title="Drag to resize. Double-click for the usual size."></div>
    <div class="tl-head">
      ${detailed ? "" : `<button class="tl-play btn btn-icon" type="button" aria-label="Play">${ICON_PLAY}</button>`}
      <span class="tl-now mono num">${detailed ? esc(run.start ? `${clock(run, 0)}–${clock(run, T)}` : `${Math.round(T)} min`) : ""}</span>
      <span class="tl-key key"><span><i class="k-opus"></i>Opus</span><span><i class="k-sonnet"></i>Sonnet</span><span><i class="k-rerun"></i>rerun</span><span><i class="k-check"></i>check</span></span>
      <button class="tl-toggle btn" type="button"></button>
    </div>
    <div class="tl-axis mono num"></div>
    ${detailed ? `<div class="tl-evlabels"></div>` : ""}
    <div class="tl-lanes"><div class="tl-over"></div></div>`;

  const lanes = el.querySelector(".tl-lanes");
  const over = el.querySelector(".tl-over");
  const axis = el.querySelector(".tl-axis");
  // Ticks about every 60 px of track, redrawn when the width changes.
  let shownMost = 0;
  new ResizeObserver(() => {
    if (!axis.clientWidth) return;       // hidden
    applySize();
    const most = Math.max(2, Math.min(6, Math.floor(axis.clientWidth / 60)));
    if (most === shownMost) return;
    shownMost = most;
    axis.innerHTML = ticks(run, T, most).map(t => `<span style="left:${pct(t)}">${esc(clock(run, t))}</span>`).join("");
  }).observe(axis);
  const pick = name => opts.onPick && opts.onPick(name);

  rows.forEach(({ name, s }) => {
    const lane = document.createElement("div");
    lane.className = "tl-lane";
    lane.dataset.skill = name;
    lane.innerHTML = `<div class="tl-nm">${detailed ? esc(name) : ""}</div><div class="tl-tr"></div>` + (detailed
      ? `<div class="tl-cost mono num">${s.usd === null || s.usd === undefined ? "–" : "$" + s.usd.toFixed(2)}</div>` +
        `<div class="tl-note${s.red ? " bad" : ""}">${esc(stateLine(s))}</div>`
      : "");
    if (detailed) lane.querySelector(".tl-nm").addEventListener("click", () => pick(name));
    const track = lane.querySelector(".tl-tr");
    s.runs.forEach(b => {
      const bar = document.createElement("div");
      bar.className = "tl-bar" + (s.model === "opus" ? " opus" : "") + (b.kind === "rerun" ? " rerun" : "");
      bar.style.left = pct(b.t0);
      bar.style.width = pct(Math.max(0, b.t1 - b.t0));
      bar.dataset.end = b.t1;
      const tipHtml = `<b>${esc(name)}</b>${b.kind !== "first" ? ` · ${esc(b.kind)}` : ""}<br>` +
        `${esc(clock(run, b.t0))}–${esc(clock(run, b.t1))} · ${MODEL[s.model] || "model unknown"}` +
        (b.line ? `<br><span class="tip-dim">${esc(b.line)}</span>` : "");
      bar.addEventListener("pointermove", e => { if (!dragging) showTip(e, tipHtml); });
      bar.addEventListener("pointerleave", hideTip);
      bar.addEventListener("click", () => pick(name));
      track.appendChild(bar);
    });
    lanes.insertBefore(lane, over);
  });

  const labels = el.querySelector(".tl-evlabels");
  Object.entries(checks).forEach(([t, texts]) => {
    over.insertAdjacentHTML("beforeend", `<div class="tl-ev" style="left:${pct(+t)}"></div>`);
    if (!labels) return;
    const lbl = document.createElement("div");
    lbl.className = "tl-evlbl" + (+t / T > 0.6 ? " end" : "");
    lbl.style.left = pct(+t);
    lbl.textContent = texts[0] + (texts.length > 1 ? ` (+${texts.length - 1})` : "");
    const tipHtml = `<b>${esc(clock(run, +t))}</b>` + texts.map(x => `<br>${esc(x)}`).join("");
    lbl.addEventListener("pointermove", e => showTip(e, tipHtml));
    lbl.addEventListener("pointerleave", hideTip);
    labels.appendChild(lbl);
  });

  const applySize = sizing(el, lanes, rows.length, detailed, edge);

  const api = {
    set() {},
    highlight(skill) {
      lanes.querySelectorAll(".tl-lane").forEach(l => l.classList.toggle("hl", l.dataset.skill === skill));
    },
  };
  let dragging = false;
  if (detailed) return api;

  /* ---------- cursor, drag, play ---------- */
  const cursor = document.createElement("div");
  cursor.className = "tl-cursor";
  over.appendChild(cursor);
  const now = el.querySelector(".tl-now");
  const bars = [...lanes.querySelectorAll(".tl-bar")];
  let cur = T;
  const show = t => {
    cur = Math.max(0, Math.min(T, t));
    cursor.style.left = pct(cur);
    bars.forEach(b => b.classList.toggle("future", +b.dataset.end > cur + FUTURE_EPS));
    now.textContent = clock(run, cur);
    lanes.setAttribute("aria-valuenow", Math.round(cur));
    lanes.setAttribute("aria-valuetext", clock(run, cur));
  };
  api.set = t => {
    show(t);
    if (opts.onTime) opts.onTime(cur);
  };

  lanes.tabIndex = 0;
  lanes.setAttribute("role", "slider");
  lanes.setAttribute("aria-label", "Time in the run");
  lanes.setAttribute("aria-valuemin", 0);
  lanes.setAttribute("aria-valuemax", Math.round(T));
  show(T);

  const atPointer = e => {
    const r = over.getBoundingClientRect();
    api.set(((e.clientX - r.left) / r.width) * T);
  };
  // Capture the pointer only once it moves, so a plain click still reaches a bar.
  [axis, lanes].forEach(area => {
    area.style.cursor = "ew-resize";
    area.style.touchAction = "none";
    let startX = 0;
    area.addEventListener("pointerdown", e => {
      dragging = true;
      startX = e.clientX;
      hideTip();
      stop();
      atPointer(e);
      window.addEventListener("pointerup", () => { dragging = false; }, { once: true });
    });
    area.addEventListener("pointermove", e => {
      if (!dragging) return;
      if (!area.hasPointerCapture(e.pointerId) && Math.abs(e.clientX - startX) > 3) area.setPointerCapture(e.pointerId);
      atPointer(e);
    });
    area.addEventListener("pointercancel", () => { dragging = false; });
  });
  lanes.addEventListener("keydown", e => {
    const step = { ArrowLeft: -1, ArrowRight: 1, Home: -T, End: T }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    stop();
    api.set(cur + step);
  });

  const btn = el.querySelector(".tl-play");
  let frame = null;
  function stop() {
    if (frame) cancelAnimationFrame(frame);
    frame = null;
    btn.innerHTML = ICON_PLAY;
    btn.setAttribute("aria-label", "Play");
  }
  btn.addEventListener("click", () => {
    if (frame) return stop();
    if (cur >= T) api.set(0);
    btn.innerHTML = ICON_PAUSE;
    btn.setAttribute("aria-label", "Pause");
    let last = performance.now();
    const tick = time => {
      if (!cursor.isConnected) { frame = null; return; }
      api.set(cur + ((time - last) / 1000) * (T / PLAY_SECONDS));
      last = time;
      if (cur >= T) stop();
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
  });

  return api;
}

window.Site.timeline = timeline;
