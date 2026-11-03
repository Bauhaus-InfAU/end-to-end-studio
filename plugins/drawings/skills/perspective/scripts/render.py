#!/usr/bin/env python3
"""Renders each base view of a proposal with an image model, keeping its geometry.

    python render.py <proposal folder> [--model NAME] [--image-size 2K] [--env DIR_OR_FILE] [--options FILE] [--only view-1]

For every view in <proposal>/perspective/views.json it sends <stem>_base.png and <stem>_depth.png to Google
Gemini with a prompt built from the view's reason, the idea in narrative/narrative.md and the look in
drawing-graphics/standard.md, and writes <stem>.png next to them, and render.json with each prompt and model.
The key is GEMINI_API_KEY or GOOGLE_API_KEY, from the first .env found walking up from the proposal folder
(or only the one --env names), else the environment. It is never printed or written down.
Needs: pip install google-genai pillow python-dotenv
"""
import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

DEFAULTS = {
    "model": "gemini-3.1-flash-image-preview",
    "image_size": "2K",
    "send_depth": True,
    "fit_to_base": True,   # a result with the base's proportions but another size is resampled to the base's size
    "look": ("Soft daylight under a lightly clouded sky, late spring, trees in fresh leaf. Real materials on the facades "
             "and the ground. People of all ages walking, sitting and cycling, at their true size for where they stand. "
             "No lens flare, no sunset sky, no glow; the buildings are not lit brighter than the street."),
}
KEYS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
LOOK_HEADING = r"render|perspective|atmospher|mood|people|material|season"
KEEP_GEOMETRY = (
    "IMAGE 1 is the base view. Keep its geometry exactly: every building, roof line, edge, street, tree and the ground "
    "stay where they are and at the same size. Add no building, move none, remove none, and do not change their heights "
    "or outlines. Keep the same camera, the same horizon line, the same lens and the same framing, so the result lies "
    "over IMAGE 1 line for line. Only give the surfaces their materials, light, planting, sky and people.")
DEPTH_NOTE = ("IMAGE 2 is the depth map of the same view: lighter is nearer, black is the sky. Use it only to tell "
              "near from far; do not draw it.")
CLOSING = "No text, no labels, no frame, no watermark in the image."
ASPECTS = {"1:1": 1.0, "2:3": 2 / 3, "3:2": 3 / 2, "3:4": 3 / 4, "4:3": 4 / 3, "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9}


def stop(message):
    print(message)
    sys.exit(1)


def find_key(start, env=None, environ=None):
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
        for k in KEYS:
            if values.get(k):
                return values[k], f"{k} from {found}"
    for k in KEYS:
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


def build_prompt(view, title, idea, look, send_depth=True):
    tell = []
    if view.get("why"):
        tell.append(f"This eye-level view shows {view['why']}" + (f" ({view['situation']})." if view.get("situation") else "."))
    if title or idea:
        tell.append("The idea of the project" + (f", \"{title}\"" if title else "") + (f": {trimmed(idea)}" if idea else "."))
    parts = [KEEP_GEOMETRY, DEPTH_NOTE if send_depth else "",
             "Render it as a photorealistic architectural perspective at a pedestrian's eye height.",
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


def render(proposal, client, opts, only=None, key_source=None, types=None):
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
    record = {"model": opts["model"], "image_size": opts["image_size"], "key": key_source,
              "look_source": look_source, "notes": notes, "views": []}
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
        entry["prompt"] = build_prompt(view, title, idea, look, send_depth)
        contents = [base] + ([Image.open(depth_path)] if send_depth else []) + [entry["prompt"]]
        config = None
        if types is not None:
            config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"],
                                                 image_config=types.ImageConfig(imageSize=opts["image_size"], aspectRatio=aspect_of(base.size)))
        print(f"Rendering {stem} with {opts['model']}...")
        try:
            response = client.models.generate_content(model=opts["model"], contents=contents, config=config)
        except Exception as e:  # the API's own message, which names no key
            entry["warnings"].append(f"The image model failed: {type(e).__name__}: {str(e)[:300]}")
            record["views"].append(entry)
            continue
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
    args = ap.parse_args()
    proposal = Path(args.proposal).resolve()
    views = proposal / "perspective" / "views.json"
    if not views.exists():
        stop(f"No {views}: run perspective.py first. No image was written.")
    given = json.loads(Path(args.options).read_text(encoding="utf-8")) if args.options else {}
    opts = {**DEFAULTS, **{k: v for k, v in given.items() if k in DEFAULTS}}
    if "look" in given:
        opts["look_given"] = given["look"]
    opts["model"] = args.model or opts["model"]
    opts["image_size"] = args.image_size or opts["image_size"]

    missing = []
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        missing.append("the google-genai package")
    for mod, name in (("PIL", "pillow"), ("dotenv", "python-dotenv")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(f"the {name} package")
    key, where = (None, None) if "the python-dotenv package" in missing else find_key(proposal, args.env)
    if key is None and "the python-dotenv package" not in missing:
        missing.append("a GEMINI_API_KEY or GOOGLE_API_KEY in .env or the environment")
    if missing:
        fix = (["pip install google-genai pillow python-dotenv"] if any("package" in m for m in missing) else []) \
            + (["put the key in the project's .env"] if any("KEY" in m for m in missing) else [])
        stop("Not rendered, no image written: missing " + " and ".join(missing) + ". To render: " + " and ".join(fix) + ".")

    record = render(proposal, genai.Client(api_key=key), opts, args.only, where, types)
    del key
    made = [v for v in record["views"] if "size" in v]
    print(f"{len(made)} of {len(record['views'])} views rendered into {proposal / 'perspective'}; prompts in render.json.")
    for w in record["notes"] + [w for v in record["views"] for w in v["warnings"]]:
        print(" -", w)


if __name__ == "__main__":
    main()
