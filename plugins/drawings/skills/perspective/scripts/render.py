#!/usr/bin/env python3
"""Renders each base view of a proposal with an image model, keeping its geometry.

    python render.py <proposal folder> [--model NAME] [--image-size 2K] [--env DIR_OR_FILE] [--options FILE]
                     [--only view-1] [--provider auto|google|replicate] [--references IMAGE ...]

For every view in <proposal>/perspective/views.json it sends <stem>_base.png and <stem>_depth.png, and any style
reference images, to Gemini with a prompt built from the view's reason, the idea in narrative/narrative.md and
the look in drawing-graphics/standard.md, and writes <stem>.png next to them, and render.json with each prompt,
the provider, the model and the reference images.
Gemini is reached directly with GEMINI_API_KEY or GOOGLE_API_KEY, else through Replicate with REPLICATE_API_TOKEN,
each from the first .env found walking up from the proposal folder (or only the one --env names), else the
environment. No key is ever printed or written down. The reference images are only read, never changed.
Needs: pip install pillow python-dotenv, and google-genai for the direct route
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

DEFAULTS = {
    "model": "gemini-3.1-flash-image-preview",
    "replicate_model": "google/nano-banana-2",   # Gemini 3.1 Flash Image on Replicate
    "provider": "auto",    # auto: Google with a Gemini key, else Replicate with its token
    "references": [],      # style reference images: paths, read only
    "image_size": "2K",
    "send_depth": True,
    "fit_to_base": True,   # a result with the base's proportions but another size is resampled to the base's size
    "look": ("Soft daylight under a lightly clouded sky, late spring, trees in fresh leaf. Materials on the facades "
             "and the ground drawn in flat, simple colour. People of all ages walking, sitting and cycling, at their true size for where they stand. "
             "No lens flare, no sunset sky, no glow; the buildings are not lit brighter than the street."),
}
RENDER_STYLE = ("Render it as an illustrated architectural perspective at a pedestrian's eye height, not a photograph: a "
                "clean line drawing with flat areas of colour, in the manner of a vector or watercolour collage. Simple "
                "textured planes for facades and ground, cut-out trees and people, a pale painted sky, no photographic "
                "detail, no gloss, no lens effects.")
KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
REPLICATE_KEYS = ("REPLICATE_API_TOKEN",)
REPLICATE_API = "https://api.replicate.com/v1"
USER_AGENT = "perspective-render/1.0"   # Replicate's firewall refuses Python's default agent
REPLICATE_WAIT_S = 300
LOOK_HEADING = r"render|perspective|atmospher|mood|people|material|season"
KEEP_GEOMETRY = (
    "IMAGE 1 is the base view. Keep its geometry exactly: every building, roof line, edge, street, tree and the ground "
    "stay where they are and at the same size. Add no building, move none, remove none, and do not change their heights "
    "or outlines. Keep the same camera, the same horizon line, the same lens and the same framing, so the result lies "
    "over IMAGE 1 line for line. Only give the surfaces their materials, light, planting, sky and people.")
DEPTH_NOTE = ("IMAGE 2 is the depth map of the same view: lighter is nearer, black is the sky. Use it only to tell "
              "near from far; do not draw it.")
CLOSING = "No text, no labels, no frame, no watermark in the image."


def reference_note(first, last):
    """What the style reference images are for, and what they must not bring in."""
    which = f"IMAGE {first} is a style reference" if first == last else f"IMAGES {first} to {last} are style references"
    return (f"{which} only, from other projects. Take from them the drawing technique, the atmosphere, the colour "
            "palette and how they draw vegetation, landscape, people and architecture. Copy nothing from them: no "
            "particular building, structure, walkway, deck, railing, figure, composition, viewpoint or text. People "
            "appear as the look below asks, drawn in the references' manner. They don't change what the buildings are "
            "made of. Use their accent colour sparingly: never across a whole building, and never on an element "
            "IMAGE 1 doesn't have. The geometry and the design come from IMAGE 1 alone.")
ASPECTS = {"1:1": 1.0, "2:3": 2 / 3, "3:2": 3 / 2, "3:4": 3 / 4, "4:3": 4 / 3, "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9}


def stop(message):
    print(message)
    sys.exit(1)


def find_key(start, env=None, environ=None, keys=KEYS):
    """(key, where) or (None, None). Reads one .env: the one --env names, else the first walking up from start."""
    environ = os.environ if environ is None else environ
    if env:
        p = Path(env)
        candidates = [p / ".env" if p.is_dir() else p]
    else:
        candidates = [d / ".env" for d in [Path(start).resolve(), *Path(start).resolve().parents]]
    found = next((c for c in candidates if c.is_file()), None)
    if found:
        from dotenv import dotenv_values
        values = dotenv_values(found)
        for k in keys:
            if values.get(k):
                return values[k], f"{k} from {found}"
    for k in keys:
        if environ.get(k):
            return environ[k], f"{k} from the environment"
    return None, None


def plain(text):
    text = re.sub(r"[*`>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def section(md, pattern):
    """The text under the first heading that matches pattern, up to the next heading of the same or a higher level."""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"(#+)\s+(.*)", line)
        if m and re.search(pattern, m.group(2), re.I):
            body = []
            for nxt in lines[i + 1:]:
                n = re.match(r"(#+)\s", nxt)
                if n and len(n.group(1)) <= len(m.group(1)):
                    break
                body.append(nxt)
            return "\n".join(body).strip()
    return ""


def first_paragraph(text):
    return plain(next((p for p in re.split(r"\n\s*\n", text) if p.strip()), ""))


def narrative_idea(proposal):
    path = proposal / "narrative" / "narrative.md"
    if not path.exists():
        return None, None
    md = path.read_text(encoding="utf-8")
    title = plain(next((ln for ln in section(md, r"^title").splitlines() if ln.strip()), ""))
    idea = first_paragraph(section(md, r"^(the )?idea"))
    return (title or None), (idea or None)


def look_from_standard(proposal):
    path = proposal / "drawing-graphics" / "standard.md"
    if not path.exists():
        return None
    md = path.read_text(encoding="utf-8")
    lines = section(md, LOOK_HEADING).splitlines()
    return " ".join(plain(ln.lstrip("-* ")) for ln in lines if ln.strip() and not ln.startswith("#")) or None


def trimmed(text, n=400):
    text = plain(text)
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def render_style_from(proposal):
    """render_style in drawing-graphics/style.json, else None."""
    try:
        value = json.loads((proposal / "drawing-graphics" / "style.json").read_text(encoding="utf-8")).get("render_style")
    except (OSError, ValueError, AttributeError):
        return None
    return plain(value) if isinstance(value, str) and value.strip() else None


def build_prompt(view, title, idea, look, send_depth=True, style=None, references=0):
    tell = []
    if view.get("why"):
        tell.append(f"This eye-level view shows {view['why']}" + (f" ({view['situation']})." if view.get("situation") else "."))
    if title or idea:
        tell.append("The idea of the project" + (f", \"{title}\"" if title else "") + (f": {trimmed(idea)}" if idea else "."))
    first = 3 if send_depth else 2
    parts = [KEEP_GEOMETRY, DEPTH_NOTE if send_depth else "",
             reference_note(first, first + references - 1) if references else "",
             style or RENDER_STYLE,
             " ".join(tell), f"The look: {look}", CLOSING]
    return "\n\n".join(p for p in parts if p)


def aspect_of(size):
    return min(ASPECTS, key=lambda k: abs(ASPECTS[k] - size[0] / size[1]))


def image_from(response):
    """(PIL image, the model's text) from a generate_content response."""
    from PIL import Image
    text = []
    for part in getattr(response, "parts", None) or []:
        data = getattr(getattr(part, "inline_data", None), "data", None)
        if data:
            return Image.open(io.BytesIO(data)), " ".join(text)
        if getattr(part, "text", None):
            text.append(part.text)
    return None, " ".join(text)


def load_references(paths):
    """(images, their absolute paths, warnings) for the style references. Each file is only read, never changed."""
    from PIL import Image
    images, used, warnings = [], [], []
    for p in paths or []:
        path = Path(p).expanduser().resolve()
        try:
            img = Image.open(path)
            img.load()
        except (OSError, ValueError) as e:
            warnings.append(f"The reference {p} can't be read ({type(e).__name__}): left out.")
            continue
        images.append(img)
        used.append(str(path))
    return images, used, warnings


def data_uri(img):
    """An image as a data URI: the file's own bytes when it was opened from a file and not converted, else a PNG."""
    path = getattr(img, "filename", "")
    if path and Path(path).is_file():
        raw, mime = Path(path).read_bytes(), mimetypes.guess_type(path)[0] or "image/png"
    else:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw, mime = buf.getvalue(), "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


class ReplicateClient:
    """Gemini through Replicate, behind the same models.generate_content call as Google's client. The images go in
    the order given, the text parts become the prompt, and web and image search stay off."""

    def __init__(self, token, opener=urllib.request.urlopen):
        self._token, self._open = token, opener
        self.models = SimpleNamespace(generate_content=self.generate_content)
        self.last_prediction = None
        self._inputs = {}

    def _call(self, method, url, body=None, headers=None, auth=True):
        h = {"User-Agent": USER_AGENT, **(headers or {})}
        if auth:   # the token goes only to Replicate's API, never to the download of the result
            h["Authorization"] = "Bearer " + self._token
        data = None
        if body is not None:
            data, h["Content-Type"] = json.dumps(body).encode("utf-8"), "application/json"
        try:
            with self._open(urllib.request.Request(url, data=data, headers=h, method=method), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:   # Replicate's own message, which names no token
            raise RuntimeError(f"Replicate answered {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from None

    def inputs_of(self, model):
        """The input names the model takes, so that an option it doesn't have is left out."""
        if model not in self._inputs:
            d = json.loads(self._call("GET", f"{REPLICATE_API}/models/{model}"))
            schema = (d.get("latest_version") or {}).get("openapi_schema") or {}
            self._inputs[model] = set(schema.get("components", {}).get("schemas", {}).get("Input", {}).get("properties", {}))
        return self._inputs[model]

    def generate_content(self, model, contents, config=None):
        self.last_prediction = None
        known = self.inputs_of(model)
        if "image_input" not in known:
            raise RuntimeError(f"{model} on Replicate takes no input images.")
        wanted = {"prompt": "\n\n".join(c for c in contents if isinstance(c, str)),
                  "image_input": [data_uri(c) for c in contents if not isinstance(c, str)],
                  "output_format": "png", "google_search": False, "image_search": False, **(config or {})}
        body = {"input": {k: v for k, v in wanted.items() if k in known}}
        p = json.loads(self._call("POST", f"{REPLICATE_API}/models/{model}/predictions", body, {"Prefer": "wait=60"}))
        self.last_prediction = p.get("id")
        start = time.monotonic()
        while p.get("status") not in ("succeeded", "failed", "canceled"):
            if time.monotonic() - start > REPLICATE_WAIT_S:
                raise RuntimeError(f"Replicate prediction {p.get('id')} is still {p.get('status')} after {REPLICATE_WAIT_S} s.")
            time.sleep(2)
            p = json.loads(self._call("GET", p["urls"]["get"]))
        if p["status"] != "succeeded":
            raise RuntimeError(f"Replicate prediction {p.get('id')} {p['status']}: {str(p.get('error'))[:300]}")
        out = p.get("output")
        data = self._call("GET", out[0] if isinstance(out, list) else out, auth=False)
        return SimpleNamespace(parts=[SimpleNamespace(text=None, inline_data=SimpleNamespace(data=data))])


def render(proposal, client, opts, only=None, key_source=None, types=None, provider="google"):
    from PIL import Image
    out = proposal / "perspective"
    spec = json.loads((out / "views.json").read_text(encoding="utf-8"))
    title, idea = narrative_idea(proposal)
    notes = []
    if not (title or idea):
        notes.append("narrative/narrative.md is missing or has no Title or Idea heading: the prompts carry only each view's reason.")
    look, look_source = opts.get("look_given"), "options"
    if not look:
        look, look_source = look_from_standard(proposal), "drawing-graphics/standard.md"
    if not look:
        look, look_source = opts["look"], "default"
        notes.append("drawing-graphics/standard.md has no section on renders, perspectives or atmosphere: the prompts use the script's default look.")
    style = render_style_from(proposal)
    refs, ref_paths, ref_warnings = load_references(opts.get("references"))
    notes += ref_warnings
    record = {"provider": provider, "model": opts["model"], "image_size": opts["image_size"], "key": key_source,
              "references": ref_paths, "look_source": look_source, "notes": notes, "views": []}
    for view in spec["views"]:
        stem = view.get("stem") or view["name"]
        if only and view["name"] not in only and stem not in only:
            continue
        files = view.get("files", {})
        base_path = out / files.get("base_png", f"{stem}_base.png")
        depth_path = out / files.get("depth_png", f"{stem}_depth.png")
        entry = {"name": view["name"], "base": base_path.name, "output": f"{stem}.png", "model": opts["model"], "warnings": []}
        if not base_path.exists():
            entry["warnings"].append(f"{base_path.name} is missing: nothing rendered.")
            record["views"].append(entry)
            continue
        base = Image.open(base_path).convert("RGB")
        send_depth = opts["send_depth"] and depth_path.exists()
        entry["depth"] = depth_path.name if send_depth else None
        entry["prompt"] = build_prompt(view, title, idea, look, send_depth, style, len(refs))
        contents = [base] + ([Image.open(depth_path)] if send_depth else []) + refs + [entry["prompt"]]
        config = None
        if types is not None:
            config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"],
                                                 image_config=types.ImageConfig(imageSize=opts["image_size"], aspectRatio=aspect_of(base.size)))
        elif provider == "replicate":
            config = {"aspect_ratio": aspect_of(base.size), "resolution": opts["image_size"]}
        print(f"Rendering {stem} with {opts['model']} ({provider}, {len(refs)} references)...")
        try:
            response = client.models.generate_content(model=opts["model"], contents=contents, config=config)
        except Exception as e:  # the API's own message, which names no key
            entry["warnings"].append(f"The image model failed: {type(e).__name__}: {str(e)[:300]}")
            record["views"].append(entry)
            continue
        finally:
            if getattr(client, "last_prediction", None):   # Replicate's id, to find its cost on the dashboard
                entry["prediction"] = client.last_prediction
        img, said = image_from(response)
        if said:
            entry["model_text"] = said[:500]
        if img is None:
            entry["warnings"].append("The image model sent no image back.")
            record["views"].append(entry)
            continue
        entry["returned_size"] = list(img.size)
        if img.size != base.size:
            same_shape = abs(img.size[0] / img.size[1] - base.size[0] / base.size[1]) < 0.01
            if same_shape and opts["fit_to_base"]:
                img = img.convert("RGB").resize(base.size, Image.LANCZOS)
                entry["warnings"].append(f"{stem}.png came back {img_size(entry)}, not {base.size[0]}x{base.size[1]}; same proportions, so it was resampled to the base's size.")
            else:
                entry["warnings"].append(f"{stem}.png is {img_size(entry)}, the base is {base.size[0]}x{base.size[1]}: other proportions, so the framing changed. It doesn't lie over the base view.")
        img.save(out / f"{stem}.png")
        entry["size"] = list(img.size)
        record["views"].append(entry)
    (out / "render.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    return record


def img_size(entry):
    return "x".join(map(str, entry["returned_size"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proposal")
    ap.add_argument("--model", help=f"the image model (default {DEFAULTS['model']})")
    ap.add_argument("--image-size", help=f"1K, 2K or 4K (default {DEFAULTS['image_size']})")
    ap.add_argument("--env", help="the folder or file of the .env to read, instead of walking up from the proposal folder")
    ap.add_argument("--options", help="JSON overriding DEFAULTS; 'look' there replaces the look read from standard.md")
    ap.add_argument("--only", nargs="*", help="view names or stems to render, else all")
    ap.add_argument("--provider", choices=("auto", "google", "replicate"),
                    help="where Gemini is reached (default auto: Google with a Gemini key, else Replicate with its token)")
    ap.add_argument("--references", nargs="*", help="style reference images, sent after the base and depth images; only read")
    args = ap.parse_args()
    proposal = Path(args.proposal).resolve()
    views = proposal / "perspective" / "views.json"
    if not views.exists():
        stop(f"No {views}: run perspective.py first. No image was written.")
    given = json.loads(Path(args.options).read_text(encoding="utf-8")) if args.options else {}
    opts = {**DEFAULTS, **{k: v for k, v in given.items() if k in DEFAULTS}}
    if "look" in given:
        opts["look_given"] = given["look"]
    if args.references is not None:
        opts["references"] = args.references
    opts["image_size"] = args.image_size or opts["image_size"]
    provider = args.provider or opts["provider"]

    missing = []
    for mod, name in (("PIL", "pillow"), ("dotenv", "python-dotenv")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(f"the {name} package")
    key = where = None
    if "the python-dotenv package" not in missing:
        if provider in ("auto", "google"):
            key, where = find_key(proposal, args.env)
            provider = "google" if key else provider
        if key is None and provider in ("auto", "replicate"):
            key, where = find_key(proposal, args.env, keys=REPLICATE_KEYS)
            provider = "replicate" if key else provider
        if key is None:
            missing.append("a GEMINI_API_KEY or GOOGLE_API_KEY, or a REPLICATE_API_TOKEN, in .env or the environment")
    if key and provider == "google":
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            missing.append("the google-genai package")
    if missing:
        packages = [m[4:-8] for m in missing if m.endswith(" package")]
        fix = ([f"pip install {' '.join(packages)}"] if packages else []) \
            + (["put a key in the project's .env"] if any("KEY" in m for m in missing) else [])
        stop("Not rendered, no image written: missing " + " and ".join(missing) + ". To render: " + " and ".join(fix) + ".")

    if provider == "google":
        opts["model"] = args.model or opts["model"]
        client, kinds = genai.Client(api_key=key), types
    else:
        opts["model"] = args.model or opts["replicate_model"]
        client, kinds = ReplicateClient(key), None
    del key
    record = render(proposal, client, opts, args.only, where, kinds, provider)
    made = [v for v in record["views"] if "size" in v]
    print(f"{len(made)} of {len(record['views'])} views rendered with {record['model']} ({provider}, "
          f"{len(record['references'])} references) into {proposal / 'perspective'}; prompts in render.json.")
    for w in record["notes"] + [w for v in record["views"] for w in v["warnings"]]:
        print(" -", w)


if __name__ == "__main__":
    main()
