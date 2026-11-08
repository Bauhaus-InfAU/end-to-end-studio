/*
 * All runs page: the dashboard (#all) and one run's summary (#all/<key>).
 * Registered as "dash". Uses only the Site API of app.js and timeline.js.
 * Every string from the data goes through Site.esc / Site.md.
 */
const { esc, md } = window.Site;

const money = v => "$" + v.toFixed(2);
const short = r => r.kind === "variant" ? r.label.split("-").pop() : r.label.replace(/^run-/, "");
const href = (key, page) => page ? `#${encodeURIComponent(key)}/${page}` : `#all/${encodeURIComponent(key)}`;
const dmy = d => { const [y, m, dd] = String(d).split("-"); return `${dd}.${m}.${y}`; };
const isPrize = v => !!v && !/^no award/i.test(v);
const vclass = v => !v ? "v-none" : isPrize(v) ? "v-prize" : "v-no";
const median = a => { const s = a.slice().sort((x, y) => x - y), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0; };

let cleanup = [];

/* ---------- tooltip ---------- */
function makeTip(el) {
  const tip = document.createElement("div");
  tip.className = "tip";
  document.body.appendChild(tip);
  const tips = [];
  const reg = html => { tips.push(html); return tips.length - 1; };
  const hide = () => tip.classList.remove("on");
  const move = e => {
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (!t || !el.contains(t)) return hide();
    tip.innerHTML = tips[+t.dataset.tip];
    tip.classList.add("on");
    const w = tip.offsetWidth, h = tip.offsetHeight;
    const x = e.clientX + 12 + w > innerWidth ? e.clientX - 12 - w : e.clientX + 12;
    const y = e.clientY + 12 + h > innerHeight ? e.clientY - 12 - h : e.clientY + 12;
    tip.style.left = Math.max(4, x) + "px";
    tip.style.top = Math.max(4, y) + "px";
  };
  el.addEventListener("pointermove", move);
  el.addEventListener("pointerleave", hide);
  el.addEventListener("scroll", hide);
  cleanup.push(() => {
    el.removeEventListener("pointermove", move);
    el.removeEventListener("pointerleave", hide);
    el.removeEventListener("scroll", hide);
    tip.remove();
  });
  return reg;
}

/* ---------- the dashboard ---------- */
function headline(runs, ledgerRuns) {
  const only = runs.filter(r => r.kind === "run");
  const vars = runs.filter(r => r.kind === "variant");
  const total = runs.reduce((s, r) => s + (r.usd || 0), 0);
  const med = median(only.filter(r => r.usd != null).map(r => r.usd));
  const prized = only.filter(r => isPrize(r.verdict));
  const names = [...new Set(prized.map(r => r.verdict))];
  const last = only.filter(r => r.items).pop();
  const k = [
    [only.length, "runs" + (vars.length ? `, and ${vars.length} variant (${vars.map(v => v.label).join(", ")})` : "")],
    ["$" + total.toFixed(0), "spent in all" + (vars.length ? ", the variant included" : "")],
    [money(med), "median run"],
    [prized.length + " ×", names.length ? names.join(", ") : "placed by the jury"],
    [last ? `${last.items[0]} / ${last.items[1]}` : "–", last ? `required items on the panels, ${last.label}` : "required items"],
  ];
  return `<div class="dash-kpis num">${k.map(([b, s]) => `<div class="kpi"><b>${esc(b)}</b><span>${esc(s)}</span></div>`).join("")}</div>`;
}

function costChart(runs, reg, runData) {
  const W = 640, H = 280, pl = 34, pb = 84, pt = 10;
  const bw = (W - pl) / runs.length;
  const top = Math.max(10, Math.ceil(Math.max(...runs.map(r => r.usd || 0)) / 10) * 10);
  const maxMin = Math.max(60, Math.ceil(Math.max(...runs.map(r => r.minutes || 0)) / 20) * 20);
  const y = v => pt + (H - pt - pb) * (1 - v / top);
  const ym = v => pt + (H - pt - pb) * (1 - v / maxMin);
  let s = "";
  for (let v = 0; v <= top; v += 10) {
    s += `<line class="grid" x1="${pl}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/><text class="ax" x="${pl - 8}" y="${y(v) + 4}" text-anchor="end">$${v}</text>`;
  }
  const pts = [];
  runs.forEach((r, i) => {
    const x = pl + i * bw + bw * 0.22, w = bw * 0.56, cx = x + w / 2;
    const usd = r.usd || 0;
    const m = (runData[r.key] || {}).usd_by_model || {};
    const op = m.opus || 0, so = m.sonnet || 0, known = op + so;
    const opH = known ? usd * op / known : 0;
    const tip = reg(`<b>${esc(r.label)}${r.title && r.title !== r.label ? " · " + esc(r.title) : ""}</b>` +
      `<br>${r.usd == null ? "no cost" : money(r.usd)} · ${r.minutes == null ? "no time" : r.minutes + " min"} · ${r.n_skills} skills` +
      (r.usd == null ? "" : known ? `<br>Opus ${money(op)}, Sonnet ${money(so)}` : `<br><span class="tip-dim">whole-session cost only</span>`) +
      `<br>${esc(r.verdict || "no jury yet")}${r.kind === "variant" ? "<br><span class=\"tip-dim\">variant</span>" : ""}`);
    s += `<a href="${href(r.key)}" aria-label="${esc(r.label)}: open its summary"><g data-tip="${tip}">` +
      (usd ? `<rect class="${known ? "b-son" : "b-whole"}" x="${x}" y="${y(usd)}" width="${w}" height="${y(0) - y(usd)}" rx="2"/>` : "") +
      (known && opH ? `<rect class="b-op" x="${x}" y="${y(opH)}" width="${w}" height="${y(0) - y(opH)}" rx="2"/>` : "") +
      `<rect class="hit" x="${pl + i * bw}" y="0" width="${bw}" height="${H}"/>` +
      `<text class="lbl" x="${cx}" y="${H - pb + 16}" text-anchor="middle">${esc(short(r))}</text>` +
      `<circle class="${vclass(r.verdict)}" cx="${cx}" cy="${H - pb + 32}" r="4.5"/></g></a>`;
    pts.push(r.minutes == null ? null : [cx, ym(r.minutes), r]);
  });
  // the minutes line, broken where a run has no time
  let seg = [];
  const segs = [];
  pts.forEach(p => { if (p) seg.push(p); else { segs.push(seg); seg = []; } });
  segs.push(seg);
  segs.forEach(g => { if (g.length > 1) s += `<polyline class="min" points="${g.map(p => p[0] + "," + p[1]).join(" ")}"/>`; });
  pts.filter(Boolean).forEach(p => {
    s += `<circle class="min-dot" cx="${p[0]}" cy="${p[1]}" r="2.5" data-tip="${reg(`<b>${esc(p[2].label)}</b><br>${p[2].minutes} min`)}"/>`;
  });
  s += `<text class="ax" x="${pl}" y="${H - 4}">run</text>
    <g class="ax" transform="translate(${pl + 40},${H - 8})"><rect class="b-op" width="10" height="7" y="-7"/><text x="14">Opus</text><rect class="b-son" x="52" width="10" height="7" y="-7"/><text x="66">Sonnet</text><rect class="b-whole" x="118" width="10" height="7" y="-7"/><text x="132">whole session only</text><line class="min" x1="262" x2="276" y1="-3.5" y2="-3.5"/><text x="280">minutes</text></g>
    <g class="ax" transform="translate(${pl + 40},${H - 24})"><circle class="v-prize" cx="4" cy="-3.5" r="4"/><text x="14">prize or mention</text><circle class="v-no" cx="120" cy="-3.5" r="4"/><text x="130">no award</text><circle class="v-none" cx="200" cy="-3.5" r="4"/><text x="210">no jury yet</text></g>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cost and time per run">${s}</svg>`;
}

function itemsChart(runs, reg) {
  const R = runs.filter(r => r.items);
  const W = 460, rh = 22, x0 = 60, ww = W - x0 - 60;
  let s = "";
  R.forEach((r, i) => {
    const [a, b] = r.items, yy = i * rh + 6;
    const tip = reg(`<b>${esc(r.label)}</b><br>${a} of ${b} required items placed`);
    s += `<a href="${href(r.key)}" aria-label="${esc(r.label)}: open its summary"><g data-tip="${tip}">
      <rect class="hit" x="0" y="${yy - 2}" width="${W}" height="${rh}"/>
      <text class="lbl" x="0" y="${yy + 11}">${esc(r.label)}</text>
      <rect class="track" x="${x0}" y="${yy + 3}" width="${ww}" height="9" rx="4.5"/>
      <rect class="${a === b ? "b-op" : "b-son"}" x="${x0}" y="${yy + 3}" width="${b ? ww * a / b : 0}" height="9" rx="4.5"/>
      <text class="lbl num" x="${W - 50}" y="${yy + 11}">${a} / ${b}</text></g></a>`;
  });
  return `<svg viewBox="0 0 ${W} ${R.length * rh + 10}" role="img" aria-label="Required items on the panels">${s}</svg>`;
}

function heatChart(runs, runData, reg) {
  const cols = runs.filter(r => runData[r.key] && Object.keys(runData[r.key].usd_by_skill || {}).length);
  const sum = {};
  cols.forEach(r => Object.entries(runData[r.key].usd_by_skill).forEach(([k, v]) => {
    if (k !== "total" && k !== "lead") sum[k] = (sum[k] || 0) + (v || 0);
  }));
  const SK = Object.entries(sum).sort((a, b) => b[1] - a[1]).slice(0, 16).map(x => x[0]);
  if (!cols.length) return `<p class="muted">No cost per skill is known yet.</p>`;
  const cw = 34, ch = 18, lx = 120;
  let s = "";
  cols.forEach((r, j) => {
    s += `<a href="${href(r.key)}" aria-label="${esc(r.label)}: open its summary"><text class="ax" x="${lx + j * cw + cw / 2}" y="12" text-anchor="middle">${esc(short(r))}</text></a>`;
  });
  SK.forEach((k, i) => {
    s += `<text class="lbl" x="${lx - 10}" y="${22 + i * ch + 12}" text-anchor="end">${esc(k)}</text>`;
    cols.forEach((r, j) => {
      const v = runData[r.key].usd_by_skill[k] || 0, a = Math.min(1, v / 5);
      const tip = reg(`<b>${esc(k)}</b> · ${esc(r.label)}<br>${v ? money(v) : "not run"}`);
      s += `<a href="${href(r.key)}" aria-label="${esc(k)}, ${esc(r.label)}: open its summary"><rect class="cell" data-tip="${tip}" style="${v ? `fill-opacity:${(0.1 + a * 0.9).toFixed(2)}` : ""}" ` +
        `x="${lx + j * cw + 1}" y="${22 + i * ch + 1}" width="${cw - 2}" height="${ch - 2}" rx="3"${v ? "" : ' data-empty="1"'}/></a>`;
    });
  });
  const w = lx + cols.length * cw + 4, h = 22 + SK.length * ch + 4;
  return `<svg style="width:${w}px" viewBox="0 0 ${w} ${h}" role="img" aria-label="Dollars per skill and run">${s}</svg>`;
}

function ledgerChart(runs, ledger, reg) {
  const cols = runs.filter(r => r.kind === "run");
  const lw = 210, cw = 30, rh = 22;
  let s = "";
  cols.forEach((r, j) => {
    s += `<a href="${href(r.key)}" aria-label="${esc(r.label)}: open its summary"><text class="ax" x="${lw + j * cw + cw / 2}" y="12" text-anchor="middle">${esc(short(r))}</text></a>`;
  });
  ledger.forEach((row, i) => {
    const yy = 28 + i * rh;
    const fj = row.fix ? cols.findIndex(c => c.label === row.fix.after) : -1;
    const fixTxt = row.fix ? `<br>fix after ${esc(row.fix.after)}: ${esc(row.fix.what)} (${row.fix.held ? "held" : "did not hold"})` : "<br>no fix yet";
    s += `<g data-tip="${reg(`<b>${esc(row.error)}</b><br><span class="tip-dim">${esc(row.kind)}</span>${fixTxt}`)}"><rect class="hit" x="0" y="${yy - rh / 2}" width="${lw + cols.length * cw}" height="${rh}"/>` +
      `<text class="lbl" x="0" y="${yy + 4}">${esc(row.error.length > 34 ? row.error.slice(0, 33) + "…" : row.error)}</text>` +
      `<line class="grid" x1="${lw}" x2="${lw + cols.length * cw}" y1="${yy}" y2="${yy}"/></g>`;
    if (fj >= 0) s += `<line class="fix${row.fix.held ? "" : " fix-no"}" x1="${lw + (fj + 1) * cw}" x2="${lw + (fj + 1) * cw}" y1="${yy - 8}" y2="${yy + 8}"/>`;
    cols.forEach((c, j) => {
      const m = row.runs[c.label];
      if (!m) return;
      const after = fj >= 0 && j > fj;
      const tip = reg(`<b>${esc(row.error)}</b><br>${esc(c.label)}: ${m === "q" ? "present, not reported" : "seen"}${after ? ", after the fix" : ""}`);
      s += `<a href="${href(c.key)}" aria-label="${esc(row.error)}, ${esc(c.label)}"><circle class="dot${after ? " back" : ""}${m === "q" ? " maybe" : ""}" data-tip="${tip}" cx="${lw + j * cw + cw / 2}" cy="${yy}" r="${m === "q" ? 3.5 : 4.5}"/></a>`;
    });
  });
  const w = lw + cols.length * cw + 4, h = 28 + ledger.length * rh;
  return `<svg style="width:${w}px" viewBox="0 0 ${w} ${h}" role="img" aria-label="Problems that come back">${s}</svg>`;
}

async function dashboard(el) {
  const { project, runs, ledger } = Site.index;
  const only = runs.filter(r => r.kind === "run");
  const reg = makeTip(el);
  const range = runs.length ? `${dmy(runs[0].date)} to ${dmy(runs[runs.length - 1].date)}` : "";
  el.innerHTML = `<div class="dash-wrap">
    <h1>All runs</h1>
    <div class="dash-sub">${esc(project && project.name || "")} · ${only.length} runs from ${esc(range)}</div>
    ${headline(runs)}
    <div class="dash-grid g1">
      <section class="chart"><h2>Cost and time per run</h2><p>Bars are dollars, split Opus and Sonnet where the cost log has it; the line is minutes. Dot below: the jury's verdict.</p><div class="dash-scroll" id="d-cost"></div></section>
      <section class="chart"><h2>Required items on the panels</h2><p>Of what the brief asks for, how many made it onto the panels.</p><div class="dash-scroll" id="d-items"></div></section>
    </div>
    <div class="dash-grid g2">
      <section class="chart"><h2>Where the money goes</h2><p>Dollars per skill and run. Darker is more.</p><div class="dash-scroll" id="d-heat"><p class="muted">Loading the runs…</p></div></section>
      <section class="chart"><h2>Problems that come back</h2><p>Line: when a fix landed (dashed: it did not hold). Hollow: it came back after the fix. Small: present, not reported.</p><div class="dash-scroll" id="d-led"></div></section>
    </div></div>`;
  const $ = id => el.querySelector(id);
  $("#d-items").innerHTML = itemsChart(runs, reg);
  $("#d-led").innerHTML = ledgerChart(runs, ledger || [], reg);
  $("#d-cost").innerHTML = costChart(runs, reg, {});
  // the cost per skill and the Opus/Sonnet split need each run's file
  const data = {};
  await Promise.all(runs.map(r => Site.run(r.key).then(d => { data[r.key] = d; }, () => {})));
  if (!el.isConnected) return;
  $("#d-cost").innerHTML = costChart(runs, reg, data);
  $("#d-heat").innerHTML = heatChart(runs, data, reg);
}

/* ---------- one run's summary ---------- */
function summary(el, run) {
  const reg = makeTip(el);
  const c = Site.index.runs.find(r => r.key === run.key) || run;
  const name = run.title && run.title !== run.label ? run.title : "";
  const when = [dmy(run.date), run.start && run.end ? `${run.start}–${run.end}` : null, run.commit ? `commit ${run.commit}` : null].filter(Boolean);
  const hl = run.headline || {};
  const num = (v, f) => v == null ? "–" : f(v);
  const facts = [
    ["Cost", run.usd == null ? "–" : money(run.usd)],
    ["Time", run.minutes == null ? "–" : run.minutes + " min"],
    ["Skills", run.n_skills],
    ["Required items", run.items ? `${run.items[0]} / ${run.items[1]}` : "–"],
    ["Homes", num(hl.homes, v => v.toLocaleString("en"))],
    ["Floor area", num(hl.gfa_m2, v => v.toLocaleString("en") + " m²")],
    ["New buildings", num(hl.new_buildings, v => v.toLocaleString("en"))],
    ["Green", num(hl.green_ha, v => v.toFixed(1) + " ha")],
  ];
  // cost per skill, biggest first, coloured by the skill's model
  const bySkill = Object.entries(run.usd_by_skill || {}).filter(([k, v]) => k !== "total" && k !== "lead" && v != null).sort((a, b) => b[1] - a[1]);
  const mx = bySkill.length ? bySkill[0][1] : 1;
  const m = run.usd_by_model || {};
  const split = (m.opus || m.sonnet) ? `Opus ${money(m.opus || 0)} · Sonnet ${money(m.sonnet || 0)}` : "whole-session cost only";
  const rows = bySkill.map(([k, v]) => {
    const model = run.skills && run.skills[k] ? run.skills[k].model : null;
    const tip = reg(`<b>${esc(k)}</b><br>${money(v)} · ${model === "opus" ? "Opus" : model === "sonnet" ? "Sonnet" : "model unknown"}${run.usd ? ` · ${Math.round(v / run.usd * 100)} % of the run` : ""}`);
    return `<div class="cs-row" data-tip="${tip}"><span class="cs-nm">${esc(k)}</span><span class="cs-tr"><i class="${model === "opus" ? "opus" : model === "sonnet" ? "sonnet" : "unk"}" style="width:${(v / mx * 100).toFixed(1)}%"></i></span><span class="cs-v mono num">${money(v)}</span></div>`;
  }).join("");
  const links = [["Model", "model", true], ["Panels", "panels", run.has && run.has.panels], ["Loop", "loop", run.has && run.has.loop]]
    .map(([t, p, on]) => on ? `<a href="${href(run.key, p)}">${t}</a>` : `<span class="off">${t}</span>`).join("");
  const jv = run.jury && run.jury.verdict || run.verdict;
  el.innerHTML = `<div class="dash-wrap sum">
    <a class="back" href="#all">← All runs</a>
    <h1>${esc(run.label)}${name ? ` <span class="muted">· ${esc(name)}</span>` : ""}</h1>
    <div class="dash-sub">${esc(when.join(" · "))}${c.kind === "variant" ? " · variant" : ""}</div>
    <div class="dash-links">${links}</div>
    <div class="dash-facts num">${facts.map(([k, v]) => `<div class="kpi"><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join("")}</div>
    ${run.new_in_run ? `<section class="blk"><div class="label">New in this run</div><div class="md">${md(run.new_in_run)}</div></section>` : ""}
    <section class="blk"><div class="label">Cost per skill</div>
      <div class="cs-key muted"><span><i class="opus"></i>Opus</span><span><i class="sonnet"></i>Sonnet</span>${run.usd_lead != null ? `<span>lead ${money(run.usd_lead)}</span>` : ""}<span>${esc(split)}</span></div>
      ${rows ? `<div class="cs">${rows}</div>` : `<p class="muted">No cost per skill for this run.</p>`}</section>
    <section class="blk tlblk"><div class="label">Timeline</div><div class="dash-tl" id="d-tl"></div></section>
    <section class="blk"><div class="label">Jury</div>
      <p class="verdict ${vclass(jv)}"><i></i>${esc(jv || "no jury yet")}</p>
      ${run.jury && run.jury.summary_md ? `<div class="md">${md(run.jury.summary_md)}</div>` : ""}</section>
    ${run.open_problems_md ? `<section class="blk"><div class="label">Open problems</div><div class="md">${md(run.open_problems_md)}</div></section>` : ""}
    ${run.handed_on_md ? `<section class="blk"><div class="label">Handed on</div><div class="md">${md(run.handed_on_md)}</div></section>` : ""}
  </div>`;
  Site.timeline(el.querySelector("#d-tl"), run, { detailed: true });
}

Site.page("dash", {
  async mount(el, run) {
    el.scrollTop = 0;
    if (run) summary(el, run);
    else await dashboard(el);
  },
  unmount() {
    cleanup.forEach(f => f());
    cleanup = [];
  },
});
