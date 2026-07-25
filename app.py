"""ResumeFit: conversational ATS resume converter. Streamlit entry point."""
from dotenv import load_dotenv
import streamlit as st

from src.demo_fallback import find_cached_rewrite
from src.diff_view import render_diff
from src.document_parser import parse_uploaded_file
from src.latex_export import build_pdf
from src.question_generator import build_quiz_queue
from src.resume_export import build_docx
from src.rewriter import rewrite_resume_with_retry
from src.session_state import init_state, reset_state

load_dotenv()

st.set_page_config(page_title="ResumeFit", page_icon="📝", layout="wide")
init_state()

# The app defines both a light and a dark palette in .streamlit/config.toml
# ([theme.light] / [theme.dark]); Streamlit's own Settings menu (top-right menu
# button) switches between them and re-themes every native widget. Our own
# injected CSS below doesn't get that for free, so it reads the currently
# active theme from st.context and picks a matching accent palette.
_active_theme = (st.context.theme.type or "light")
if _active_theme == "dark":
    _accent = "#6fa8d8"
    _line = "#333c46"
    _dot_border = "#333c46"
    _dot_bg = "#1a1e24"
    _dot_idle = "#9aa7b4"
    _label = "#eaf1f9"
    _label_upcoming = "#7a828b"
    _dock_bg = "#1a1e24"
    _diff_removed_bg = "rgba(248, 113, 113, 0.18)"
    _diff_removed_text = "#fca5a5"
    _diff_added_bg = "rgba(74, 222, 128, 0.18)"
    _diff_added_text = "#86efac"
else:
    _accent = "#1a5276"
    _line = "#d8dde3"
    _dot_border = "#c7ccd2"
    _dot_bg = "#ffffff"
    _dot_idle = "#7a828b"
    _label = "#3a3a3a"
    _label_upcoming = "#8a929c"
    _dock_bg = "#f2f2f2"
    _diff_removed_bg = "rgba(211, 47, 47, 0.12)"
    _diff_removed_text = "#b3261e"
    _diff_added_bg = "rgba(46, 125, 50, 0.12)"
    _diff_added_text = "#1b5e20"

# Accessibility + visual pass: readable base font, visible keyboard focus ring,
# and a professional polish pass on buttons, the status widget, and the sidebar stepper.
st.markdown(
    f"""
    <style>
    html, body, [class*="css"] {{ font-size: 17px; }}
    *:focus {{ outline: 3px solid {_accent} !important; outline-offset: 2px; }}
    h1, h2, h3 {{ letter-spacing: -0.01em; }}
    div[data-testid="stChatMessage"] {{ border-radius: 10px; }}

    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {{
        border-radius: 8px;
        font-weight: 600;
    }}
    @media (prefers-reduced-motion: no-preference) {{
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {{
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }}
        div[data-testid="stButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 10px rgba(26, 82, 118, 0.18);
        }}
    }}
    div[data-testid="stDownloadButton"] button[kind="primary"] {{
        box-shadow: 0 2px 6px rgba(26, 82, 118, 0.25);
    }}
    div[data-testid="stStatusWidget"] {{
        border-radius: 10px;
    }}

    .rf-stepper {{ padding-left: 2px; margin-top: 4px; }}
    .rf-step {{ position: relative; padding: 4px 0 4px 32px; }}
    .rf-step:not(:last-child)::before {{
        content: "";
        position: absolute;
        left: 11px;
        top: 26px;
        bottom: -4px;
        width: 2px;
        background: {_line};
    }}
    .rf-step.done:not(:last-child)::before {{ background: {_accent}; }}
    .rf-step-dot {{
        position: absolute;
        left: 0;
        top: 3px;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.72rem;
        font-weight: 700;
        border: 2px solid {_dot_border};
        background: {_dot_bg};
        color: {_dot_idle};
    }}
    .rf-step.done .rf-step-dot {{ background: {_accent}; border-color: {_accent}; color: #ffffff; }}
    .rf-step.active .rf-step-dot {{
        border-color: {_accent};
        color: {_accent};
        box-shadow: 0 0 0 3px rgba(111, 168, 216, 0.25);
    }}
    .rf-step-label {{ font-size: 0.92rem; color: {_label}; line-height: 1.6; }}
    .rf-step.active .rf-step-label {{ font-weight: 700; color: {_accent}; }}
    .rf-step.upcoming .rf-step-label {{ color: {_label_upcoming}; }}

    div.st-key-theme_dock {{
        position: sticky;
        bottom: 0;
        background: {_dock_bg};
        padding-top: 10px;
        margin-top: 12px;
    }}

    .rf-diff-text {{
        white-space: pre-wrap;
        font-family: "Cascadia Code", Consolas, monospace;
        font-size: 0.85rem;
        line-height: 1.55;
    }}
    .rf-diff-removed {{
        background: {_diff_removed_bg};
        color: {_diff_removed_text};
        text-decoration: line-through;
        border-radius: 3px;
        padding: 0 1px;
    }}
    .rf-diff-added {{
        background: {_diff_added_bg};
        color: {_diff_added_text};
        border-radius: 3px;
        padding: 0 1px;
    }}
    .rf-diff-legend {{
        display: flex;
        gap: 18px;
        font-size: 0.82rem;
        color: {_label};
        margin-bottom: 10px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

STEP_LABELS = {
    "intake": "Provide your resume",
    "analyzing": "Analyze your resume",
    "quiz": "Answer a few questions",
    "rewriting": "Generate ATS-safe version",
    "done": "Generate ATS-safe version",
}
STEP_ORDER = ["intake", "analyzing", "quiz", "rewriting"]

with st.sidebar:
    st.header("📝 ResumeFit")
    st.caption("Conversational ATS resume converter")
    st.divider()
    current = st.session_state.stage
    current_index = STEP_ORDER.index(current) if current in STEP_ORDER else len(STEP_ORDER) - 1
    stepper_html = ['<div class="rf-stepper">']
    for i, key in enumerate(STEP_ORDER):
        label = STEP_LABELS[key]
        if i < current_index:
            status_class, dot = "done", "✓"
        elif i == current_index:
            status_class, dot = "active", str(i + 1)
        else:
            status_class, dot = "upcoming", str(i + 1)
        stepper_html.append(
            f'<div class="rf-step {status_class}">'
            f'<div class="rf-step-dot">{dot}</div>'
            f'<div class="rf-step-label">{label}</div>'
            f"</div>"
        )
    stepper_html.append("</div>")
    st.markdown("".join(stepper_html), unsafe_allow_html=True)
    st.divider()
    st.caption(
        "MSAI631 - Artificial Intelligence for Human-Computer Interaction. "
        "Rule-based gap detection runs locally; question analysis and the final rewrite "
        "both call the OpenAI API."
    )

    with st.container(key="theme_dock"):
        with st.popover("⚙️ Theme", use_container_width=True):
            st.caption(f"Currently viewing: **{_active_theme.capitalize()} mode**")
            st.write(
                "Switch it from the menu in the top-right corner of the app "
                "(⋮ → Settings → Choose app theme). Streamlit re-themes every "
                "widget automatically from there."
            )

st.title("ResumeFit")
st.caption("Paste a messy resume draft. ResumeFit asks a few questions, then rewrites it into ATS-safe format.")
st.divider()

if st.session_state.stage == "intake":
    st.subheader(STEP_LABELS["intake"])

    with st.container(border=True):
        uploaded = st.file_uploader("Upload a resume (PDF or DOCX)", type=["pdf", "docx"])
        if uploaded is not None and st.session_state.last_uploaded_name != uploaded.name:
            try:
                parsed = parse_uploaded_file(uploaded.name, uploaded.getvalue())
                st.session_state.draft_prefill = parsed.text
                st.session_state.upload_warnings = parsed.warnings
                st.session_state.last_uploaded_name = uploaded.name
            except Exception as exc:
                st.error(f"Could not read that file: {exc}")

        for warning in st.session_state.upload_warnings:
            st.warning(warning, icon="⚠️")

        st.caption("or paste it directly below")
        draft = st.text_area(
            "Resume draft",
            value=st.session_state.draft_prefill,
            height=300,
            label_visibility="collapsed",
            placeholder="Paste your resume text here...",
        )

    def _start_intake(draft_text: str) -> None:
        st.session_state.draft = draft_text
        st.session_state.stage = "analyzing"

    st.button(
        "Start ➔",
        type="primary",
        disabled=not draft.strip(),
        on_click=_start_intake,
        args=(draft,),
    )

elif st.session_state.stage == "analyzing":
    st.subheader(STEP_LABELS["analyzing"])
    with st.status("Analyzing your resume...", expanded=True) as status:
        st.write("Scanning locally for missing dates, vague titles, and unquantified results.")
        st.write("Calling the OpenAI API for questions specific to your resume's content...")
        st.session_state.gaps = build_quiz_queue(st.session_state.draft)
        st.session_state.current_gap_index = 0
        st.session_state.answers = {}
        st.session_state.stage = "quiz"
        status.update(label="Analysis complete", state="complete", expanded=False)
    st.rerun()

elif st.session_state.stage == "quiz":
    st.subheader(STEP_LABELS["quiz"])

    gaps = st.session_state.gaps
    idx = st.session_state.current_gap_index
    st.progress(idx / len(gaps), text=f"Question {min(idx + 1, len(gaps))} of {len(gaps)}")

    with st.container(border=True):
        for i, gap in enumerate(gaps[:idx]):
            with st.chat_message("assistant"):
                st.write(gap.question)
            with st.chat_message("user"):
                ans_col, edit_col = st.columns([6, 1])
                with ans_col:
                    st.write(st.session_state.answers.get(gap.question, "_(skipped)_"))
                with edit_col:
                    if st.button("✎", key=f"edit_{i}", help="Edit this answer"):
                        st.session_state.current_gap_index = i
                        st.rerun()

        if idx < len(gaps):
            gap = gaps[idx]
            with st.chat_message("assistant"):
                st.write(gap.question)

    if idx < len(gaps):
        answer = st.chat_input("Your answer")
        if answer:
            st.session_state.answers[gap.question] = answer
            st.session_state.current_gap_index += 1
            st.rerun()

        nav_col1, nav_col2, _ = st.columns([1, 1, 3])
        with nav_col1:
            if st.button("◀ Back", disabled=idx == 0, use_container_width=True):
                st.session_state.current_gap_index -= 1
                st.rerun()
        with nav_col2:
            if st.button("Skip ➔", use_container_width=True):
                st.session_state.answers.pop(gap.question, None)
                st.session_state.current_gap_index += 1
                st.rerun()
    else:
        st.success("All questions answered.", icon="✅")
        end_col1, end_col2, _ = st.columns([1, 2, 2])
        with end_col1:
            if st.button("◀ Back", use_container_width=True):
                st.session_state.current_gap_index -= 1
                st.rerun()
        with end_col2:
            st.button(
                "Generate ATS-safe resume ➔",
                type="primary",
                on_click=lambda: st.session_state.update(stage="rewriting"),
                use_container_width=True,
            )

elif st.session_state.stage == "rewriting":
    st.subheader(STEP_LABELS["rewriting"])
    with st.status("Generating your ATS-safe resume...", expanded=True) as status:
        st.write("Assembling your draft and quiz answers into the rewrite prompt.")
        st.write("Calling the OpenAI API (with one automatic retry if it's briefly unavailable)...")
        st.session_state.used_fallback = False
        try:
            st.session_state.result = rewrite_resume_with_retry(st.session_state.draft, st.session_state.answers)
            st.session_state.error = ""
            status.update(label="Resume ready", state="complete", expanded=False)
        except Exception as exc:
            cached = find_cached_rewrite(st.session_state.draft)
            if cached:
                st.write("Live rewrite unavailable, serving a cached example response instead.")
                st.session_state.result = cached
                st.session_state.used_fallback = True
                st.session_state.error = ""
                status.update(label="Resume ready (cached fallback)", state="complete", expanded=False)
            else:
                st.session_state.result = ""
                st.session_state.error = str(exc)
                status.update(label="Rewrite failed", state="error", expanded=False)
        st.session_state.stage = "done"
    st.rerun()

elif st.session_state.stage == "done":
    st.subheader("Your ATS-safe resume")

    if st.session_state.get("error"):
        st.error(f"Rewrite failed: {st.session_state.error}", icon="🚫")
    else:
        if st.session_state.get("used_fallback"):
            st.info(
                "The live OpenAI API was unavailable, so this is a cached example response "
                "prepared in advance for the demo, not a fresh live rewrite.",
                icon="ℹ️",
            )
        diff_before, diff_after = render_diff(st.session_state.draft, st.session_state.result)
        st.markdown(
            '<div class="rf-diff-legend">'
            '<span><span class="rf-diff-removed">removed</span> from the original</span>'
            '<span><span class="rf-diff-added">added</span> in the rewrite</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2, gap="medium")
        with col1:
            st.markdown("**Original draft**")
            with st.container(border=True, height=420):
                st.markdown(f'<div class="rf-diff-text">{diff_before}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown("**ATS-safe rewrite**")
            with st.container(border=True, height=420):
                st.markdown(f'<div class="rf-diff-text">{diff_after}</div>', unsafe_allow_html=True)

        st.write("")
        with st.container(border=True):
            st.markdown("**Export your resume**")
            dl_col1, dl_col2, dl_col3 = st.columns(3)
            with dl_col1:
                st.download_button(
                    "📄 TXT",
                    data=st.session_state.result,
                    file_name="resumefit_resume.txt",
                    mime="text/plain",
                    use_container_width=True,
                    on_click=lambda: st.toast("Downloading TXT...", icon="📄"),
                )
                st.caption("Plain text, works everywhere")
            with dl_col2:
                st.download_button(
                    "📝 DOCX",
                    data=build_docx(st.session_state.result),
                    file_name="resumefit_resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    on_click=lambda: st.toast("Downloading DOCX...", icon="📝"),
                )
                st.caption("Editable in Word or Google Docs")
            with dl_col3:
                try:
                    pdf_bytes = build_pdf(st.session_state.result)
                except Exception as exc:
                    st.caption(f"PDF unavailable: {exc}")
                else:
                    st.download_button(
                        "🧾 PDF (recommended)",
                        data=pdf_bytes,
                        file_name="resumefit_resume.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                        on_click=lambda: st.toast("Downloading PDF...", icon="🧾"),
                    )
                    st.caption("Print-ready, LaTeX-typeset, ATS-safe")

    st.divider()

    def _confirm_and_reset() -> None:
        reset_state()
        st.session_state.confirm_reset = False

    if st.session_state.get("confirm_reset"):
        st.warning("This clears your draft, answers, and result. Are you sure?", icon="⚠️")
        confirm_col1, confirm_col2, _ = st.columns([1, 1, 3])
        with confirm_col1:
            st.button("Yes, start over", type="primary", on_click=_confirm_and_reset)
        with confirm_col2:
            st.button("Cancel", on_click=lambda: st.session_state.update(confirm_reset=False))
    else:
        st.button("Start over", on_click=lambda: st.session_state.update(confirm_reset=True))
