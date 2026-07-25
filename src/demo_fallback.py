"""Live-demo safety net: if the OpenAI API is unavailable and the current draft matches
one of the resumes bundled in sample_data/, serve its pre-generated cached rewrite
instead of a bare error.

Works for any resume dropped into sample_data/ - .txt, .pdf, or .docx - not just one
hardcoded file. A draft file "foo.docx" pairs with a cached response at "foo.cached.txt"
in the same folder; see generate_cached_fallback.py for how that pairing is produced.

This only ever matches an exact bundled sample. There is no valid cached output for
arbitrary input, so a genuine failure on a real user's own resume (typed in live, not one
of the bundled files) still surfaces as an error (see FR16 in the PRD).
"""
from pathlib import Path

from src.document_parser import parse_uploaded_file

DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"
CACHE_SUFFIX = ".cached.txt"
DRAFT_EXTENSIONS = (".txt", ".pdf", ".docx")


def _normalize(text: str) -> str:
    return "\n".join(line.strip() for line in text.strip().splitlines())


def draft_sample_paths() -> list[Path]:
    """Every candidate draft resume in sample_data/, excluding cached-response files."""
    if not DATA_DIR.exists():
        return []
    return sorted(
        p for p in DATA_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in DRAFT_EXTENSIONS
        and not p.name.endswith(CACHE_SUFFIX)
    )


def cached_path_for(draft_path: Path) -> Path:
    return draft_path.with_suffix(CACHE_SUFFIX)


def extract_draft_text(draft_path: Path) -> str:
    """Text a draft file resolves to, using the same parser the app uses for uploads,
    so a cached sample matches whatever the app sees whether pasted or uploaded."""
    if draft_path.suffix.lower() == ".txt":
        return draft_path.read_text(encoding="utf-8")
    return parse_uploaded_file(draft_path.name, draft_path.read_bytes()).text


def find_cached_rewrite(draft: str) -> str | None:
    """Returns the cached rewrite for `draft` if it matches a known sample_data draft, else None."""
    normalized = _normalize(draft)
    for draft_path in draft_sample_paths():
        try:
            sample_text = extract_draft_text(draft_path)
        except Exception:
            continue
        if _normalize(sample_text) == normalized:
            cached_path = cached_path_for(draft_path)
            if cached_path.exists():
                return cached_path.read_text(encoding="utf-8")
    return None
