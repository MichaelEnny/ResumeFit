"""Traditional chatbot layer: rule-based scan of a resume draft for missing or weak information."""
import re
from dataclasses import dataclass
from itertools import zip_longest

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
PRESENT_RE = re.compile(r"\bpresent\b", re.IGNORECASE)
METRIC_RE = re.compile(r"\d+%|\$\d+|\b\d+[kKmM]?\+?\b")
VAGUE_TITLES = {"team member", "staff", "associate", "employee", "worker"}
ROLE_KEYWORDS = (
    "manager", "engineer", "analyst", "coordinator", "director",
    "specialist", "developer", "lead", "intern", "consultant",
)

MAX_QUESTIONS = 5
MIN_QUESTIONS = 2

# Used to top up the queue when rule-based detection finds fewer than MIN_QUESTIONS
# issues (e.g. an already well-formatted resume, or one the heuristics don't catch
# anything on) - the quiz-and-clarify step should still run rather than being skipped.
GENERIC_QUESTIONS = (
    "Would you like to add a short professional summary at the top of your resume?",
    "Is there a specific job title or industry you're targeting with this resume?",
    "Are there any additional measurable achievements (numbers, percentages, awards) "
    "you'd like to include that aren't already listed?",
    "Are there any skills or certifications relevant to the roles you're applying for "
    "that aren't currently listed?",
)


@dataclass
class Gap:
    kind: str
    line_index: int
    evidence: str
    question: str


def split_lines(draft: str) -> list[str]:
    return [line.strip() for line in draft.splitlines() if line.strip()]


def looks_like_bullet(line: str) -> bool:
    return line.lstrip().startswith(("-", "*", "•"))


def looks_like_role_header(line: str) -> bool:
    return not looks_like_bullet(line) and len(line.split()) <= 12


DATE_LOOKAHEAD = 2  # dates are often on the line(s) right after the title, not on it


def _has_nearby_date(lines: list[str], index: int) -> bool:
    window = lines[index:index + 1 + DATE_LOOKAHEAD]
    return any(YEAR_RE.search(line) or PRESENT_RE.search(line) for line in window)


def detect_missing_dates(lines: list[str]) -> list[Gap]:
    gaps = []
    for i, line in enumerate(lines):
        if not looks_like_role_header(line):
            continue
        if _has_nearby_date(lines, i):
            continue
        if any(keyword in line.lower() for keyword in ROLE_KEYWORDS):
            gaps.append(Gap(
                kind="missing_date",
                line_index=i,
                evidence=line,
                question=f"What were the start and end dates for \"{line}\"?",
            ))
    return gaps


VAGUE_TITLE_RE = re.compile(
    r"\b(" + "|".join(re.escape(title) for title in VAGUE_TITLES) + r")\b",
    re.IGNORECASE,
)


def detect_vague_titles(lines: list[str]) -> list[Gap]:
    gaps = []
    for i, line in enumerate(lines):
        if not looks_like_role_header(line):
            continue
        if VAGUE_TITLE_RE.search(line):
            gaps.append(Gap(
                kind="vague_title",
                line_index=i,
                evidence=line,
                question=f"\"{line}\" is a general title. What was your actual job title?",
            ))
    return gaps


def detect_unquantified_bullets(lines: list[str]) -> list[Gap]:
    gaps = []
    for i, line in enumerate(lines):
        if looks_like_bullet(line) and not METRIC_RE.search(line):
            cleaned = line.lstrip("-*• ").strip()
            gaps.append(Gap(
                kind="unquantified",
                line_index=i,
                evidence=line,
                question=f"Can you quantify the result for \"{cleaned}\"? (a number, percentage, or measurable outcome)",
            ))
    return gaps


def rule_based_gaps(draft: str) -> list[Gap]:
    """Gaps found by the local, API-free rule set only - capped, not yet padded with
    generic questions. Exposed separately from detect_gaps so other layers (e.g.
    src/question_generator.py) can blend these with LLM-generated questions before
    the generic padding step is applied."""
    lines = split_lines(draft)
    categories = (
        detect_missing_dates(lines),
        detect_vague_titles(lines),
        detect_unquantified_bullets(lines),
    )
    # Round-robin across categories so one prolific category (e.g. many missing
    # dates) can't crowd out the others before the MAX_QUESTIONS cap is applied.
    return [
        gap
        for round_ in zip_longest(*categories)
        for gap in round_
        if gap is not None
    ][:MAX_QUESTIONS]


def pad_with_generic(gaps: list[Gap]) -> list[Gap]:
    """Tops up a gap list to MIN_QUESTIONS with generic questions, if needed."""
    if len(gaps) >= MIN_QUESTIONS:
        return gaps
    needed = MIN_QUESTIONS - len(gaps)
    return gaps + [
        Gap(kind="general", line_index=-1, evidence="", question=question)
        for question in GENERIC_QUESTIONS[:needed]
    ]


def detect_gaps(draft: str) -> list[Gap]:
    """Rule-based-only gap detection (no external API calls), padded with generic
    questions if fewer than MIN_QUESTIONS are found. Used standalone, and as the
    fallback if LLM-based question generation (src/question_generator.py) fails."""
    return pad_with_generic(rule_based_gaps(draft))
