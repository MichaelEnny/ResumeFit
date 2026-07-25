"""Converts the ATS-safe plain-text rewrite into a LaTeX-typeset PDF.

Mirrors the same plain-text structure resume_export.py already parses
(SECTION_HEADERS, "- " bullets, plain paragraphs) into a minimal, single-column
LaTeX article - no multi-column templates, tables, or graphics - so the
compiled PDF stays as ATS-parseable as the DOCX/TXT exports. Compilation shells
out to a local pdflatex; there is no pure-Python LaTeX engine, and this keeps
LaTeX generation in our own code rather than the LLM's, since LLM-authored
LaTeX would be an unvalidated compilation input.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

SECTION_HEADERS = {"summary", "experience", "education", "skills"}

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{enumitem}
\setlist[itemize]{leftmargin=1.2em, itemsep=2pt, topsep=2pt}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\begin{document}
"""

POSTAMBLE = r"\end{document}" "\n"


def escape_latex(text: str) -> str:
    return "".join(LATEX_ESCAPES.get(char, char) for char in text)


def build_latex(resume_text: str) -> str:
    """Renders the rewriter's plain-text output as a minimal single-column
    LaTeX document: bold section headers, itemized bullets, one paragraph per
    plain line - the same structure resume_export.py uses for DOCX, so all
    three export formats stay in sync."""
    body_lines = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            body_lines.append(r"\end{itemize}")
            in_list = False

    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            close_list()
            continue
        if stripped.rstrip(":").lower() in SECTION_HEADERS:
            close_list()
            body_lines.append(r"\section*{%s}" % escape_latex(stripped.rstrip(":")))
        elif stripped.startswith("- "):
            if not in_list:
                body_lines.append(r"\begin{itemize}")
                in_list = True
            body_lines.append(r"\item %s" % escape_latex(stripped[2:]))
        else:
            close_list()
            body_lines.append(escape_latex(stripped) + r"\par")

    close_list()
    return PREAMBLE + "\n".join(body_lines) + "\n" + POSTAMBLE


def render_pdf(latex_source: str, timeout_seconds: int = 30) -> bytes:
    """Compiles `latex_source` with a local pdflatex and returns the PDF bytes.
    Raises RuntimeError, with the compiler log tail on a compile failure, if
    pdflatex is missing or the source fails to compile - the caller decides
    how to surface that to the user."""
    if shutil.which("pdflatex") is None:
        raise RuntimeError(
            "pdflatex was not found on PATH. Install a LaTeX distribution "
            "(e.g. MiKTeX or TeX Live) to enable PDF export."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(latex_source, encoding="utf-8")

        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-no-shell-escape",
                "-output-directory", tmpdir,
                str(tex_path),
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        pdf_path = Path(tmpdir) / "resume.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            log_tail = "\n".join(result.stdout.splitlines()[-20:])
            raise RuntimeError(f"pdflatex compilation failed:\n{log_tail}")

        return pdf_path.read_bytes()


def build_pdf(resume_text: str) -> bytes:
    return render_pdf(build_latex(resume_text))
