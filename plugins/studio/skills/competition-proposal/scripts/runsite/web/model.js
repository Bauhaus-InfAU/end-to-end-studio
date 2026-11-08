/*
 * Model page: one run's geometry in 3D (deck.gl, no basemap), every layer
 * switchable in a right-hand panel, the run's timeline along the bottom.
 * Uses only the shell's API (see app.js, timeline.js).
 *
 * Data: Site.geo("shared") and Site.geo(run.key), each {group: {layer: FC}}.
 * A run's group replaces the shared group's layer of the same name (a run
 * keeps its own copy of the project's climate).
 * Time: a group appears when its skill's first bar ends; shared groups at 0.
 * A switch turned by hand wins over the time and the defaults.
 */

const DEFAULT_ON = new Set(["site", "streets", "massing", "open-space", "structure-plan"]);
// layers coloured by class: "group/layer" -> the property that sets the class
const CLASS_KEYS = { "climate/noise": "db_min", "climate/sun-hours": "hours_min",
  "climate/radiation": "kwh_min", "climate/heat": "index_min" };
const ORDER = { sealing: ["unsealed", "partly", "fully"] };
// grey to ink, light to dark
const RAMP = [[226, 225, 221], [196, 195, 190], [160, 159, 154], [120, 119, 115], [78, 78, 75], [30, 30, 30]];
const CLASS_A = 190;
const RISE = 2;                    // minutes a group takes to fade in, buildings to rise

const C = {
  newB: [255, 255, 255, 255],
  oldB: [234, 233, 230, 150],
  quiet: [214, 212, 206, 70],
  street: [225, 224, 220, 170],
  green: [207, 220, 196, 140],
  water: [196, 214, 228, 160],
  line: [110, 110, 106, 200],
  point: [70, 70, 68, 200],
  tree: [140, 170, 128, 200],
  outline: [20, 20, 20, 255],
  newFlat: [255, 255, 255, 230],
  oldFlat: [234, 233, 230, 200],
  none: [0, 0, 0, 0],
};
const GREEN = /^(park|forest|wood|grass|grassland|meadow|garden|allotments|green|green-link|corridor|open-space|orchard|recreation_ground|scrub|heath|cemetery|village_green|playground|play)$/;
const WATER = /^(water|retention|basin|reservoir|pond|river|stream|canal|wetland)$/;

const MATERIAL_NEW = { ambient: 0.62, diffuse: 0.6, shininess: 24, specularColor: [255, 255, 255] };
const MATERIAL_OLD = { ambient: 0.8, diffuse: 0.3, shininess: 4, specularColor: [255, 255, 255] };

const CHEVRON = '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2.5 3.75L5 6.25l2.5-2.5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>';

let cur = null;   // the mounted page's state

/* ---------- small helpers ---------- */
const num = v => (typeof v === "number" && isFinite(v) ? v : (typeof v === "string" && v.trim() && isFinite(+v) ? +v : null));
const pad = n => String(n).padStart(2, "0");
function clock(run, t) {
  if (!run.start || !/^\d{1,2}:\d{2}$/.test(run.start)) return `${Math.round(t)} min`;
  const [h, m] = run.start.split(":").map(Number);
  const x = ((h * 60 + m + Math.round(t)) % 1440 + 1440) % 1440;
  return `${pad(Math.floor(x / 60))}:${pad(x % 60)}`;
}
function fmtDate(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || "");
  return m ? `${m[3]}.${m[2]}.${m[1]}` : (d || "");
}
const fmtN = (v, digits = 0) => v.toLocaleString("en-US", { maximumFractionDigits: digits });
function show(v) {
  if (v === null || v === undefined) return "–";
  if (Array.isArray(v)) return v.map(show).join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
const cut = (s, n = 80) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
const rgba = c => `rgba(${c[0]},${c[1]},${c[2]},${(c[3] === undefined ? 255 : c[3]) / 255})`;

/* ---------- data: groups, layers, features by role ---------- */
function flatten(f) {
  const g = f && f.geometry;
  if (!g) return [];
  if (g.type === "GeometryCollection") {
    return (g.geometries || []).flatMap(geometry => flatten({ ...f, geometry }));
  }
  return [f];
}
function polyFill(group, name, p) {
  const words = [p.kind, p.landuse, p.use, p.natural, p.leisure, p.cover, p.class, p.role]
    .filter(x => typeof x === "string").map(x => x.toLowerCase());
  if (words.some(w => WATER.test(w))) return C.water;
  if (words.some(w => GREEN.test(w))) return C.green;
  if (/street/.test(name) || words.some(w => /^(street|road|square|plaza)$/.test(w))) return C.street;
  return C.quiet;
}
function wrap(group, name, f) {
  const p = f.properties || {};
  const w = { type: "Feature", geometry: f.geometry, properties: p, layer: `${group} › ${name}` };
  const t = f.geometry.type;
  if (t === "Polygon" || t === "MultiPolygon") {
    const siteB = group === "site" && name === "buildings";
    const floors = num(p.floors);
    const h = num(p.height_m) ?? num(p.height) ?? (floors !== null ? floors * 3 : null);
    if (p.kind === "building" && h === null && group !== "massing") {
      // a footprint with no height (phasing, plans): flat, filled and outlined
      w.role = "poly";
      w.building = true;
      w.existing = p.existing === true;
      w.c = w.existing ? C.oldFlat : C.newFlat;
      w.outline = C.line;
    } else if (p.kind === "building" || siteB) {
      w.building = true;
      w.existing = p.existing === true || siteB;
      w.h = h ?? 3;
      w.c = w.existing ? C.oldB : C.newB;
      // a skill's copy of an existing building doubles the site's buildings
      w.role = !w.existing ? "building" : siteB ? "old" : "dup";
    } else {
      w.role = "poly";
      w.c = polyFill(group, name, p);
      if (p.kind === "site") { w.outline = C.outline; w.dash = true; }
    }
  } else if (t === "LineString" || t === "MultiLineString") {
    w.role = "line";
    w.c = C.line;
  } else if (t === "Point" || t === "MultiPoint") {
    w.role = "point";
    w.tree = p.kind === "tree" || p.natural === "tree";
    w.c = w.tree ? C.tree : C.point;
  } else return null;
  return w;
}

// Colour the features of a classed layer by the ramp; returns its legend entries.
function classify(feats, key) {
  const vals = [...new Set(feats.map(f => f.properties[key]).filter(v => v !== null && v !== undefined && v !== ""))];
  if (!vals.length) return null;
  const order = ORDER[key];
  if (order && vals.every(v => order.includes(v))) vals.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  else if (vals.every(v => num(v) !== null)) vals.sort((a, b) => num(a) - num(b));
  else vals.sort((a, b) => String(a).localeCompare(String(b)));
  const n = vals.length, nb = Math.min(RAMP.length, n);
  const step = i => RAMP[nb === 1 ? RAMP.length - 1 : Math.round(i * (RAMP.length - 1) / (nb - 1))];
  const bins = Array.from({ length: nb }, (_, i) => ({ color: [...step(i), CLASS_A], labels: [] }));
  const binOf = v => Math.floor(vals.indexOf(v) * nb / n);
  vals.forEach(v => {
    const f = feats.find(x => x.properties[key] === v);
    const label = f && typeof f.properties.label === "string" && f.properties.label ? f.properties.label : String(v);
    bins[binOf(v)].labels.push(label);
  });
  let missing = null;
  feats.forEach(f => {
    const v = f.properties[key];
    if (v === null || v === undefined || v === "") { if (!missing) missing = f.c; return; }
    f.c = bins[binOf(v)].color;
  });
  const entries = bins.map(b => ({ color: b.color, label: b.labels.join(" · ") }));
  if (missing) entries.push({ color: missing, label: "no value" });
  return entries;
}

const fc = features => ({ type: "FeatureCollection", features });
function byRole(feats) {
  const r = { poly: [], line: [], old: [], dup: [], building: [], point: [] };
  feats.forEach(f => r[f.role].push(f));
  return Object.fromEntries(Object.entries(r).map(([k, v]) => [k, fc(v)]));
}

function makeLayer(group, name, coll, origin) {
  const id = `${group}/${name}`;
  const feats = ((coll && coll.features) || []).flatMap(flatten).map(f => wrap(group, name, f)).filter(Boolean);
  const L = { id, group, name, origin, variants: null, variant: 0, roles: null, entries: null };
  const key = CLASS_KEYS[id] || (feats.some(f => f.properties.sealing !== null && f.properties.sealing !== undefined) ? "sealing" : null);
  if (key) {
    const keyed = feats.filter(f => f.properties[key] !== null && f.properties[key] !== undefined);
    const periods = [...new Set(keyed.map(f => f.properties.period).filter(p => typeof p === "string" && p))];
    if (periods.length > 1) {
      // day and night bands overlap: show one period at a time
      L.variants = periods.map(p => {
        const sub = feats.filter(f => f.properties.period === p || f.properties.period === undefined || f.properties.period === null);
        const copy = sub.map(f => ({ ...f }));
        return { name: p, entries: classify(copy, key), roles: byRole(copy) };
      });
    } else {
      L.entries = classify(feats, key);
    }
  }
  if (!L.variants) L.roles = byRole(feats);
  L.outline = feats.some(f => f.outline);
  L.count = feats.length;
  return L;
}

function buildLayers(shared, own) {
  const groups = new Map();   // group -> {origin, layers: Map(name -> coll)}
  const add = (g, origin) => Object.entries(g || {}).forEach(([group, layers]) => {
    if (!layers || typeof layers !== "object") return;
    const entry = groups.get(group) || { origin, layers: new Map() };
    entry.origin = origin;   // a run's group takes the run's timing
    Object.entries(layers).forEach(([name, coll]) => entry.layers.set(name, coll));
    groups.set(group, entry);
  });
  add(shared, "shared");
  add(own, "run");
  const out = [];
  groups.forEach((entry, group) => {
    entry.layers.forEach((coll, name) => out.push(makeLayer(group, name, coll, entry.origin)));
  });
  return out;
}

/* ---------- time ---------- */
function appearTimes(run, layers) {
  const at = Object.create(null);
  layers.forEach(L => {
    if (L.group in at) return;
    const s = run.skills && run.skills[L.group];
    const bars = L.origin === "run" && s && s.runs ? s.runs.filter(b => num(b.t1) !== null) : [];
    // the group is there when its last first or second run ends; reruns only redraw
    const made = bars.filter(b => b.kind === "first" || b.kind === "second");
    const ends = (made.length ? made : bars.slice().sort((a, b) => a.t0 - b.t0).slice(0, 1)).map(b => num(b.t1));
    at[L.group] = ends.length ? Math.max(...ends) : 0;
  });
  return at;
}
function allBars(run) {
  return Object.entries(run.skills || {}).flatMap(([skill, s]) =>
    (s.runs || []).map(b => ({ skill, ...b })));
}
function lastDone(bars, t) {
  let best = null;
  bars.forEach(b => {
    if (b.t1 > t + 1e-6) return;
    if (!best || b.t1 > best.t1 || (b.t1 === best.t1 && b.t0 >= best.t0)) best = b;
  });
  return best;
}

/* ---------- view ---------- */
function bbox(geom) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const walk = c => {
    if (typeof c[0] === "number") {
      x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]);
      y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]);
    } else c.forEach(walk);
  };
  if (geom && geom.coordinates) walk(geom.coordinates);
  if (geom && geom.geometries) geom.geometries.forEach(g => g.coordinates && walk(g.coordinates));
  return isFinite(x0) ? [[x0, y0], [x1, y1]] : null;
}
function siteBox(shared, layers) {
  const site = shared && shared.site && shared.site.site;
  const f = site && site.features && site.features.find(x => x.geometry);
  let box = f && bbox(f.geometry);
  if (box) return box;
  // no site polygon: frame every new building, else everything
  const pick = layers.flatMap(L => (L.roles ? [L.roles.building, L.roles.poly] : []).flatMap(c => c.features));
  pick.forEach(x => {
    const b = bbox(x.geometry);
    if (!b) return;
    box = box ? [[Math.min(box[0][0], b[0][0]), Math.min(box[0][1], b[0][1])], [Math.max(box[1][0], b[1][0]), Math.max(box[1][1], b[1][1])]] : b;
  });
  return box;
}
function viewFor(box, w, h) {
  const base = { pitch: 55, bearing: -28 };
  if (!box) return { longitude: 0, latitude: 0, zoom: 2, ...base };
  const D = window.deck;
  try {
    const vp = new D.WebMercatorViewport({ width: Math.max(w, 200), height: Math.max(h, 200) });
    const pad = Math.min(60, Math.max(w, 200) / 8, Math.max(h, 200) / 8);
    const { longitude, latitude, zoom } = vp.fitBounds(box, { padding: pad });
    return { longitude, latitude, zoom: zoom + 0.25, ...base };
  } catch (e) {
    return { longitude: (box[0][0] + box[1][0]) / 2, latitude: (box[0][1] + box[1][1]) / 2, zoom: 14.5, ...base };
  }
}

/* ---------- state ---------- */
function visible(st, L) {
  if (L.id in st.hand) return st.hand[L.id];
  return DEFAULT_ON.has(L.group) && st.t >= st.at[L.group];
}
function arrived(st, group) {
  return st.t >= st.at[group];
}
function fade(st, L) {
  if (L.id in st.hand) return 1;
  const a = st.at[L.group];
  if (!a) return 1;
  return Math.max(0, Math.min(1, (st.t - a) / RISE));
}
const rolesOf = L => (L.variants ? L.variants[L.variant].roles : L.roles);
const entriesOf = L => (L.variants ? L.variants[L.variant].entries : L.entries);

function deckLayers(st) {
  const D = window.deck;
  const out = [];
  const on = st.layers.filter(L => visible(st, L));
  const common = { pickable: true, autoHighlight: false };
  const make = {
    poly: (L, data, k) => new D.GeoJsonLayer({ ...common, id: `${L.id}:poly:${L.variant}`, data, opacity: k,
      filled: true, extruded: false, getFillColor: f => f.c,
      // the site's edge: a dashed ink line
      ...(L.outline ? { stroked: true, getLineColor: f => f.outline || C.none, getLineWidth: f => (f.dash ? 1.4 : 1), lineWidthUnits: "pixels",
        getDashArray: f => (f.dash ? [6, 4] : [0, 0]), dashJustified: true, extensions: [new D.PathStyleExtension({ dash: true })] } : { stroked: false }) }),
    line: (L, data, k) => new D.GeoJsonLayer({ ...common, id: `${L.id}:line`, data, opacity: k,
      filled: false, stroked: true, getLineColor: f => f.c, getLineWidth: 1.5, lineWidthUnits: "pixels",
      lineWidthMinPixels: 1 }),
    dup: (L, data, k) => make.old(L, data, k, "dup"),
    old: (L, data, k, role = "old") => new D.GeoJsonLayer({ ...common, id: `${L.id}:${role}`, data, opacity: k,
      filled: true, stroked: false, extruded: true, getElevation: f => f.h, elevationScale: k,
      getFillColor: f => f.c, material: MATERIAL_OLD }),
    building: (L, data, k) => new D.GeoJsonLayer({ ...common, id: `${L.id}:building`, data, opacity: Math.min(1, k * 2),
      filled: true, stroked: false, extruded: true, getElevation: f => f.h, elevationScale: Math.max(k, 0.001),
      getFillColor: f => f.c, material: MATERIAL_NEW }),
    point: (L, data, k) => new D.GeoJsonLayer({ ...common, id: `${L.id}:point`, data, opacity: k,
      filled: true, stroked: false, pointType: "circle", getPointRadius: f => (f.tree ? 3.2 : 1.6),
      pointRadiusUnits: "meters", pointRadiusMinPixels: 1.5, getFillColor: f => f.c }),
  };
  // flat ground first, then lines, then volumes and points
  const siteB = st.layers.find(L => L.id === "site/buildings");
  const siteOn = siteB && visible(st, siteB);
  ["poly", "line", "old", "dup", "building", "point"].forEach(role => {
    if (role === "dup" && siteOn) return;
    on.forEach(L => {
      const data = rolesOf(L)[role];
      if (!data.features.length) return;
      const k = fade(st, L);
      if (k <= 0) return;
      out.push(make[role](L, data, k));
    });
  });
  return out;
}

/* ---------- DOM ---------- */
function factsHtml(run) {
  const { esc } = window.Site;
  const h = run.headline || {};
  const rows = [];
  const n = num(h.new_buildings), homes = num(h.homes), gfa = num(h.gfa_m2), green = num(h.green_ha);
  if (n !== null) rows.push(["New buildings", fmtN(n)]);
  if (homes !== null) rows.push(["Homes", fmtN(homes)]);
  if (gfa !== null) rows.push(["Floor area", `${fmtN(gfa)} m²`]);
  if (green !== null) rows.push(["Green", `${fmtN(green, 1)} ha`]);
  if (num(run.usd) !== null) rows.push(["Cost", `$${num(run.usd).toFixed(2)}`]);
  if (run.verdict) rows.push(["Jury", run.verdict]);
  const top = [run.label, fmtDate(run.date)].filter(Boolean).map(esc).join(" · ");
  return `<div class="m-kicker mono">${top}</div>
    <h1>${esc(run.title || run.label || "")}</h1>
    ${rows.length ? `<div class="m-kv num">${rows.map(([k, v]) => `<span>${esc(k)}</span><span>${esc(v)}</span>`).join("")}</div>` : ""}`;
}

function legendHtml(L) {
  const { esc } = window.Site;
  const entries = entriesOf(L);
  if (!entries) return "";
  const periods = L.variants
    ? `<div class="m-periods" role="group" aria-label="Period">${L.variants.map((v, i) =>
      `<button type="button" class="seg seg-sm" data-v="${i}" aria-pressed="${i === L.variant}">${esc(v.name)}</button>`).join("")}</div>`
    : "";
  return periods + entries.map(e =>
    `<div class="m-key" title="${esc(e.label)}"><i style="background:${rgba(e.color)}"></i><span>${esc(e.label)}</span></div>`).join("");
}

function panelHtml(st) {
  const { esc } = window.Site;
  const groups = [];
  st.layers.forEach(L => {
    let g = groups.find(x => x.name === L.group);
    if (!g) groups.push(g = { name: L.group, layers: [] });
    g.layers.push(L);
  });
  st.groups = groups;
  return groups.map((g, gi) => {
    const single = g.layers.length === 1;
    const when = st.at[g.name] ? clock(st.run, st.at[g.name]) : "";
    const gid = `m-g${gi}`;
    const head = `<div class="m-row m-grow">
        <input type="checkbox" class="switch m-sw" data-g="${gi}" id="${gid}">
        <label for="${gid}" class="m-nm">${esc(g.name)}${single && g.layers[0].name !== g.name ? ` <span class="muted">› ${esc(g.layers[0].name)}</span>` : ""}</label>
        <span class="m-when mono num">${esc(when)}</span>
        ${single ? `<span class="m-open-sp"></span>` : `<button type="button" class="m-open btn btn-icon btn-ghost btn-sm" data-g="${gi}" aria-expanded="false" aria-label="Show the layers of ${esc(g.name)}">${CHEVRON}</button>`}
      </div>`;
    const legendSingle = single ? `<div class="m-legend" data-l="${esc(g.layers[0].id)}"></div>` : "";
    const rows = single ? "" : `<div class="m-sub" hidden>${g.layers.map((L, li) => {
      const lid = `m-l${gi}-${li}`;
      return `<div class="m-row m-lrow">
          <input type="checkbox" class="switch m-sw" data-l="${esc(L.id)}" id="${lid}">
          <label for="${lid}" class="m-nm">${esc(L.name)}</label>
        </div>
        <div class="m-legend" data-l="${esc(L.id)}"></div>`;
    }).join("")}</div>`;
    return `<div class="m-grp" data-g="${gi}">${head}${legendSingle}${rows}</div>`;
  }).join("");
}

function syncPanel(st) {
  const body = st.ui.lbody;
  st.groups.forEach((g, gi) => {
    const box = body.querySelector(`.m-grp[data-g="${gi}"]`);
    const vis = g.layers.map(L => visible(st, L));
    const sw = box.querySelector(`.m-grow .m-sw`);
    const all = vis.every(Boolean), some = vis.some(Boolean);
    sw.checked = all;
    sw.indeterminate = some && !all;
    box.classList.toggle("later", !arrived(st, g.name));
    g.layers.forEach((L, li) => {
      const lsw = g.layers.length > 1 ? box.querySelectorAll(".m-lrow .m-sw")[li] : null;
      if (lsw) lsw.checked = vis[li];
      const leg = [...box.querySelectorAll(".m-legend")].find(x => x.dataset.l === L.id);
      if (!leg) return;
      const want = vis[li] && entriesOf(L) ? `${L.variant}` : "";
      if (leg.dataset.shown !== want) {
        leg.dataset.shown = want;
        leg.innerHTML = want ? legendHtml(L) : "";
      }
    });
  });
}

function caption(st) {
  const { esc } = window.Site;
  const b = lastDone(st.bars, st.t);
  const el = st.ui.caption;
  if (!st.bars.length) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = b
    ? `<span class="mono num muted">${esc(clock(st.run, b.t1))}</span> <b>${esc(b.skill)}</b>${b.kind && b.kind !== "first" ? ` <span class="muted">${esc(b.kind)}</span>` : ""}${b.line ? ` · ${esc(b.line)}` : ""}`
    : `<span class="mono num muted">${esc(clock(st.run, 0))}</span> start · the site as it is`;
  el.title = b ? [clock(st.run, b.t1), b.skill, b.line].filter(Boolean).join(" · ") : "";
}

function render(st) {
  if (!st.deck) return;
  const list = deckLayers(st);
  const sig = list.map(l => `${l.id}@${l.props.opacity.toFixed(2)}`).join("|");
  if (sig !== st.sig) {
    st.sig = sig;
    if (st.ui.tip) st.ui.tip.classList.remove("on");
  }
  st.deck.setProps({ layers: list });
  syncPanel(st);
  caption(st);
}

function tipHtml(f) {
  const { esc } = window.Site;
  const p = f.properties || {};
  if (f.building) {
    const h = num(p.height_m) ?? num(p.height);
    const bits = [];
    if (num(p.floors) !== null) bits.push(`${p.floors} floors`);
    if (h !== null) bits.push(`${fmtN(h, 1)} m`);
    return `<b>${esc(p.use || (f.existing ? "existing building" : "building"))}</b>` +
      (bits.length ? `<br>${esc(bits.join(" · "))}` : "") +
      (p.type ? `<br>${esc(show(p.type))}` : "") +
      `<br><span class="tip-dim">${esc(f.layer)}</span>`;
  }
  const keys = Object.keys(p).slice(0, 3);
  return `<span class="tip-dim">${esc(f.layer)}</span>` +
    keys.map(k => `<br>${esc(k)}: <b>${esc(cut(show(p[k])))}</b>`).join("");
}

/* ---------- page ---------- */
async function mount(el, run) {
  const Site = window.Site;
  if (!run) { el.innerHTML = '<p class="view-msg">Pick a run to see its model.</p>'; return; }
  if (!window.deck) { el.innerHTML = `<p class="view-msg">The 3D viewer didn't load.</p>`; return; }

  el.innerHTML = `
    <div class="m-stage">
      <div class="m-deck"></div>
      <p class="m-loading">Loading the model…</p>
    </div>
    <div class="m-tl"></div>`;
  const stage = el.querySelector(".m-stage");

  let shared = null, own = null;
  try {
    [shared, own] = await Promise.all([
      Site.geo("shared"),
      run.has && run.has.geo ? Site.geo(run.key) : Promise.resolve(null),
    ]);
  } catch (e) {
    console.error(e);
    if (el.isConnected) stage.querySelector(".m-loading").textContent = "The model's geometry didn't load.";
    return;
  }
  if (!el.isConnected) return;
  if (!shared && !own) {
    stage.querySelector(".m-loading").textContent = "This run has no geometry on the site.";
    return;
  }

  const layers = buildLayers(shared, own);
  const st = {
    run, layers, hand: {}, t: Infinity, at: appearTimes(run, layers), bars: allBars(run),
    deck: null, ui: {}, groups: [], el,
  };
  cur = st;

  stage.querySelector(".m-loading").remove();
  stage.insertAdjacentHTML("beforeend", `
    <div class="float m-facts">${factsHtml(run)}</div>
    <div class="float m-layers">
      <button type="button" class="m-lhead" aria-expanded="true"><span class="label">Layers</span>${CHEVRON}</button>
      <div class="m-lbody">${panelHtml(st)}</div>
    </div>
    <div class="float m-caption" hidden></div>
    <div class="tip m-tip"></div>`);
  st.ui = {
    lbody: stage.querySelector(".m-lbody"),
    lhead: stage.querySelector(".m-lhead"),
    panel: stage.querySelector(".m-layers"),
    caption: stage.querySelector(".m-caption"),
    tip: stage.querySelector(".m-tip"),
  };

  // panel: collapse, open a group, switches, periods
  const setOpen = open => {
    st.ui.panel.classList.toggle("closed", !open);
    st.ui.lhead.setAttribute("aria-expanded", String(open));
  };
  setOpen(!window.matchMedia("(max-width: 720px)").matches);
  st.ui.lhead.addEventListener("click", () => setOpen(st.ui.panel.classList.contains("closed")));
  st.ui.lbody.addEventListener("click", e => {
    const open = e.target.closest(".m-open");
    if (open) {
      const sub = open.closest(".m-grp").querySelector(".m-sub");
      sub.hidden = !sub.hidden;
      open.setAttribute("aria-expanded", String(!sub.hidden));
      return;
    }
    const pb = e.target.closest(".m-periods button");
    if (pb) {
      const L = layers.find(x => x.id === pb.closest(".m-legend").dataset.l);
      L.variant = +pb.dataset.v;
      render(st);
    }
  });
  st.ui.lbody.addEventListener("change", e => {
    const sw = e.target.closest(".m-sw");
    if (!sw) return;
    if (sw.dataset.l) st.hand[sw.dataset.l] = sw.checked;
    else st.groups[+sw.dataset.g].layers.forEach(L => { st.hand[L.id] = sw.checked; });
    render(st);
  });

  // deck.gl
  const D = window.deck;
  const deckEl = stage.querySelector(".m-deck");
  const lighting = new D.LightingEffect({
    ambient: new D.AmbientLight({ color: [255, 255, 255], intensity: 1.0 }),
    sun: new D.DirectionalLight({ color: [255, 250, 240], intensity: 1.4, direction: [-2, -3, -4] }),
  });
  const tip = st.ui.tip;
  st.deck = new D.DeckGL({
    container: deckEl,
    controller: true,
    effects: [lighting],
    initialViewState: viewFor(siteBox(shared, layers), deckEl.clientWidth, deckEl.clientHeight),
    layers: [],
    onHover: info => {
      const f = info.object;
      if (!f || !f.properties) { tip.classList.remove("on"); return; }
      tip.innerHTML = tipHtml(f);
      tip.classList.add("on");
      const r = deckEl.getBoundingClientRect();
      const cx = r.left + info.x, cy = r.top + info.y;
      const w = tip.offsetWidth, h = tip.offsetHeight;
      const x = cx + 12 + w > innerWidth ? cx - 12 - w : cx + 12;
      const y = cy + 12 + h > innerHeight ? cy - 12 - h : cy + 12;
      tip.style.left = Math.max(4, x) + "px";
      tip.style.top = Math.max(4, y) + "px";
    },
  });
  deckEl.addEventListener("pointerleave", () => tip.classList.remove("on"));
  // deck.gl's camera lags its box by one update when only the box changes (the timeline resized), which stretches
  // the view: repeat over a few frames until the camera has the box's size
  const follow = frames => {
    const width = deckEl.clientWidth, height = deckEl.clientHeight;
    if (!st.deck || !width || !height) return;
    st.deck.setProps({ width, height });
    const v = st.deck.getViewports()[0];
    if (frames > 0 && !(v && v.width === width && v.height === height)) requestAnimationFrame(() => follow(frames - 1));
  };
  st.ro = new ResizeObserver(() => follow(8));
  st.ro.observe(deckEl);

  // timeline: the cursor starts at the end without calling onTime
  Site.timeline(el.querySelector(".m-tl"), run, {
    onTime: t => { st.t = t; render(st); },
  });
  render(st);
}

function unmount() {
  const st = cur;
  cur = null;
  if (!st) return;
  if (st.ro) st.ro.disconnect();
  if (st.deck) {
    // deck.gl 9.0 finalize() leaves the WebGL context alive: lose it by hand
    const cv = st.el.querySelector(".m-deck canvas");
    try { st.deck.finalize(); } catch (e) { console.error(e); }
    try {
      const gl = cv && (cv.getContext("webgl2") || cv.getContext("webgl"));
      const ext = gl && gl.getExtension("WEBGL_lose_context");
      if (ext) ext.loseContext();
    } catch (e) { /* the context is gone already */ }
    st.deck = null;
  }
  if (st.ui && st.ui.tip) st.ui.tip.classList.remove("on");
}

window.Site.page("model", { mount, unmount });
