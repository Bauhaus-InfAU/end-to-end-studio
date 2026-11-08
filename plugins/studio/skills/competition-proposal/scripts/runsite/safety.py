"""What may go onto the public runs site, and the names that may not.

The reference entries (a competition's winners, say) are other people's work: their names stay off the site.
The names come from the reference folder's entry folders at build time, so none is written here.
"""
import re
from pathlib import Path, PurePosixPath

# the only run files the site may copy, relative to the run folder
ALLOWED = ["README.md", "version.md", "log.md", "cost.csv", "usage.csv", "*/summary.md", "jury/report.md",
           "narrative/text.md", "panel-layout/panel-*.png", "panel-layout/layout.json", "panel-layout/issues.md",
           "art-direction/fixes.json", "*/*.geojson", "*/*.png", "*/*.jpg", "massing/stats.json"]
BANNED_PARTS = {"references", "winners", ".compare"}
# words too common to blank on their own; a names file can still name them
COMMON = {"city", "park", "field", "fields", "green", "puzzle", "town", "house", "garden", "line", "lines",
          "river", "north", "south", "east", "west", "new", "the", "and"}
REPLACEMENT = "a reference"
ENTRY = re.compile(r"^\d+_[a-z]+(?:-[a-z]+)*_(.+)$", re.I)  # 3_special-mention_<name>


def is_allowed(rel: Path) -> bool:
    """True for a run file on the allow list; never for a reference, a comparison sheet or a key."""
    p = PurePosixPath(Path(rel).as_posix())
    if any(part in BANNED_PARTS for part in p.parts) or any(part.startswith(".env") for part in p.parts):
        return False
    for pat in ALLOWED:
        if len(p.parts) == len(PurePosixPath(pat).parts) and p.match(pat):
            return True
    return False


def _entry_folders(references: Path):
    """Folders of reference entries: those under winners/, and any folder of references holding board images."""
    seen = []
    for d in sorted(references.glob("winners/*")) + sorted(references.glob("*")):
        if d.is_dir() and d.name != "winners" and d not in seen:
            if d.parent.name == "winners" or any(d.glob("board-*")):
                seen.append(d)
    return seen


def forbidden_names(references: Path | None, extra: Path | None = None) -> list[str]:
    """Names to keep off the site, longest first: each entry's folder name, its name, and its last word."""
    names = set()
    if references is not None and Path(references).is_dir():
        for d in _entry_folders(Path(references)):
            names.add(d.name)
            m = ENTRY.match(d.name)
            name = m.group(1) if m else d.name
            names.add(name)
            words = [w for w in re.split(r"[-_\s]+", name) if w]
            last = words[-1] if words else ""
            if len(last) >= 4 and last.lower() not in COMMON:
                names.add(last)
    if extra is not None and Path(extra).is_file():
        names.update(line.strip() for line in Path(extra).read_text(encoding="utf-8").splitlines() if line.strip())
    return sorted(names, key=lambda s: (-len(s), s.lower()))


def _pattern(name: str) -> str:
    """A name with any of '-', '_' or space between its words, as whole words."""
    words = [re.escape(w) for w in re.split(r"[-_\s]+", name) if w]
    return r"(?<![A-Za-z0-9])" + r"[-_\s]+".join(words) + r"(?![A-Za-z0-9])"


def scrub(text: str, names: list[str]) -> str:
    """The text with every name, in any case and spelling of its separators, replaced by 'a reference'."""
    if not text or not names:
        return text
    return re.sub("|".join(_pattern(n) for n in names), REPLACEMENT, text, flags=re.I)
