"""One-off/maintenance script: regenerate cached fallback responses in sample_data/.

For every resume file in sample_data/ (.txt, .pdf, or .docx, excluding files already
ending in .cached.txt), calls the OpenAI API once and writes the ATS-safe rewrite to
<name>.cached.txt alongside it. This is the static safety net app.py falls back to if
the live API is unavailable during a demo - see src/demo_fallback.py for how the match
is made at runtime.

No quiz answers are used here (the cache is a plain rewrite of the draft alone, not
personalized) - it's a last-resort fallback, not expected to match what a live run with
real quiz answers would produce.

Usage:
    python generate_cached_fallback.py             # regenerate every sample in sample_data/
    python generate_cached_fallback.py some.docx    # regenerate just that one file
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.demo_fallback import (  # noqa: E402
    DATA_DIR,
    cached_path_for,
    draft_sample_paths,
    extract_draft_text,
)
from src.rewriter import rewrite_resume  # noqa: E402

load_dotenv()


def generate_for(draft_path: Path) -> None:
    draft = extract_draft_text(draft_path)
    result = rewrite_resume(draft, answers={})
    cached_path = cached_path_for(draft_path)
    cached_path.write_text(result, encoding="utf-8")
    print(f"Wrote {cached_path.relative_to(DATA_DIR.parent)}")


def main() -> None:
    if len(sys.argv) > 1:
        target = DATA_DIR / sys.argv[1]
        if not target.exists():
            raise SystemExit(f"No such file: {target}")
        generate_for(target)
        return

    paths = draft_sample_paths()
    if not paths:
        print("No draft resumes found in sample_data/.")
        return
    for path in paths:
        generate_for(path)


if __name__ == "__main__":
    main()
