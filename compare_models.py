"""Run the ATS rewrite against multiple models on the sample resume, side by side."""
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.rewriter import rewrite_resume  # noqa: E402
from src.sample_answers import SAMPLE_ANSWERS  # noqa: E402

load_dotenv()

MODELS_TO_COMPARE = ["gpt-4o-mini", "gpt-4o"]


def main() -> None:
    draft_path = Path(__file__).resolve().parent / "sample_data" / "messy_resume_example.txt"
    draft = draft_path.read_text(encoding="utf-8")

    for model in MODELS_TO_COMPARE:
        print("=" * 80)
        print(f"MODEL: {model}")
        print("=" * 80)
        try:
            result = rewrite_resume(draft, SAMPLE_ANSWERS, model=model)
            print(result)
        except Exception as exc:
            print(f"Failed: {exc}")
        print()


if __name__ == "__main__":
    main()
