"""AI-as-a-service layer: sends the draft plus quiz answers to the OpenAI API for an ATS-safe rewrite."""
import os
import time

from openai import OpenAI

MODEL = os.environ.get("RESUFIT_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are a resume editor that rewrites resumes into a clean, ATS-safe format.
Rules:
- Single column layout, plain text only. No tables, graphics, or text boxes.
- Standard section headers: Summary, Experience, Education, Skills.
- Consistent date format: Mon YYYY - Mon YYYY (or Present).
- Do not invent employers, titles, dates, or achievements. If information is missing and was not
  provided in the clarifying answers, leave it out rather than guessing.
- Use plain bullet points ("- ") for achievements, each starting with an action verb.
"""

TEMPLATE_PROMPT = """Original draft:
{draft}

Clarifying answers collected from the user:
{answers}

Rewrite this into an ATS-safe resume following the system rules exactly."""


def format_answers(answers: dict[str, str]) -> str:
    if not answers:
        return "(none provided)"
    return "\n".join(f"- {question}: {answer}" for question, answer in answers.items())


def build_messages(draft: str, answers: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TEMPLATE_PROMPT.format(draft=draft, answers=format_answers(answers))},
    ]


def rewrite_resume(
    draft: str,
    answers: dict[str, str],
    client: OpenAI | None = None,
    model: str | None = None,
) -> str:
    client = client or OpenAI()
    response = client.chat.completions.create(
        model=model or MODEL,
        messages=build_messages(draft, answers),
        temperature=0.3,
    )
    return response.choices[0].message.content


def rewrite_resume_with_retry(
    draft: str,
    answers: dict[str, str],
    client: OpenAI | None = None,
    model: str | None = None,
    retries: int = 1,
    retry_delay_seconds: float = 1.5,
) -> str:
    """Wraps rewrite_resume with one short retry, to absorb transient rate limits or
    network blips during a live demo without immediately falling back."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return rewrite_resume(draft, answers, client=client, model=model)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, this is a live-demo safety net
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay_seconds)
    raise last_error
