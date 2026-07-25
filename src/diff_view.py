"""Word-level diff between the original draft and the ATS-safe rewrite, rendered
as HTML spans so the 'done' screen can highlight what was removed vs. added."""
import html
import re
from difflib import SequenceMatcher

TOKEN_RE = re.compile(r"\S+|\s+")


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def render_diff(original: str, rewritten: str) -> tuple[str, str]:
    """Returns (original_html, rewritten_html): each text with the words that
    differ from the other wrapped in a highlight span. Both are HTML-escaped,
    safe to render with unsafe_allow_html."""
    original_tokens = _tokenize(original)
    rewritten_tokens = _tokenize(rewritten)
    matcher = SequenceMatcher(a=original_tokens, b=rewritten_tokens, autojunk=False)

    original_html: list[str] = []
    rewritten_html: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        removed = html.escape("".join(original_tokens[i1:i2]))
        added = html.escape("".join(rewritten_tokens[j1:j2]))
        if tag == "equal":
            original_html.append(removed)
            rewritten_html.append(added)
        else:
            if removed:
                original_html.append(f'<span class="rf-diff-removed">{removed}</span>')
            if added:
                rewritten_html.append(f'<span class="rf-diff-added">{added}</span>')

    return "".join(original_html), "".join(rewritten_html)
