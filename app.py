"""ResumeFit: conversational ATS resume converter. Streamlit entry point."""
from dotenv import load_dotenv
import streamlit as st

from src.demo_fallback import find_cached_rewrite
from src.document_parser import parse_uploaded_file
from src.question_generator import build_quiz_queue
from src.resume_export import build_docx
from src.rewriter import rewrite_resume_with_retry
from src.session_state import init_state, reset_state

load_dotenv()

st.set_page_config(page_title="ResumeFit", page_icon="📝", layout="wide")
init_state()

# Accessibility + visual pass: readable base font, visible keyboard focus ring,
# and a touch of spacing polish beyond Streamlit's defaults.
st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-size: 17px; }
    *:focus { outline: 3px solid #1a5276 !important; outline-offset: 2px; }
    h1, h2, h3 { letter-spacing: -0.01em; }
    div[data-testid="stChatMessage"] { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

STEP_LABELS = {
    "intake": "1. Provide your resume",
    "analyzing": "2. Analyze your resume",
    "quiz": "3. Answer a few questions",
    "rewriting": "4. Generate ATS-safe version",
    "done": "4. Generate ATS-safe version",
}
STEP_ORDER = ["intake", "analyzing", "quiz", "rewriting"]

with st.sidebar:
    st.header("📝 ResumeFit")
    st.caption("Conversational ATS resume converter")
    st.divider()
    current = st.session_state.stage
    current_index = STEP_ORDER.index(current) if current in STEP_ORDER else len(STEP_ORDER) - 1
    for i, key in enumerate(STEP_ORDER):
        label = STEP_LABELS[key]
        if i < current_index:
            st.markdown(f"✅ ~~{label}~~")
        elif i == current_index:
            st.markdown(f"**➡️ {label}**")
        else:
            st.markdown(f"⬜ {label}")
    st.divider()
    st.caption(
        "MSAI631 - Artificial Intelligence for Human-Computer Interaction. "
        "Rule-based gap detection runs locally; question analysis and the final rewrite "
        "both call the OpenAI API."
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
    with st.spinner("Reading your resume and preparing questions specific to its content..."):
        st.session_state.gaps = build_quiz_queue(st.session_state.draft)
        st.session_state.current_gap_index = 0
        st.session_state.answers = {}
        st.session_state.stage = "quiz"
    st.rerun()

elif st.session_state.stage == "quiz":
    st.subheader(STEP_LABELS["quiz"])

    gaps = st.session_state.gaps
    idx = st.session_state.current_gap_index
    st.progress(idx / len(gaps), text=f"Question {min(idx + 1, len(gaps))} of {len(gaps)}")

    with st.container(border=True):
        for question, answer in st.session_state.answers.items():
            with st.chat_message("assistant"):
                st.write(question)
            with st.chat_message("user"):
                st.write(answer)

        if idx < len(gaps):
            gap = gaps[idx]
            with st.chat_message("assistant"):
                st.write(gap.question)

    if idx < len(gaps):
        answer = st.chat_input("Your answer (or type 'skip')")
        if answer:
            if answer.strip().lower() != "skip":
                st.session_state.answers[gap.question] = answer
            st.session_state.current_gap_index += 1
            st.rerun()
    else:
        st.success("All questions answered.", icon="✅")
        st.button("Generate ATS-safe resume ➔", type="primary", on_click=lambda: st.session_state.update(stage="rewriting"))

elif st.session_state.stage == "rewriting":
    st.subheader(STEP_LABELS["rewriting"])
    with st.spinner("Rewriting into ATS-safe format..."):
        st.session_state.used_fallback = False
        try:
            st.session_state.result = rewrite_resume_with_retry(st.session_state.draft, st.session_state.answers)
            st.session_state.error = ""
        except Exception as exc:
            cached = find_cached_rewrite(st.session_state.draft)
            if cached:
                st.session_state.result = cached
                st.session_state.used_fallback = True
                st.session_state.error = ""
            else:
                st.session_state.result = ""
                st.session_state.error = str(exc)
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
        col1, col2 = st.columns(2, gap="medium")
        with col1:
            st.markdown("**Original draft**")
            with st.container(border=True, height=420):
                st.text(st.session_state.draft)
        with col2:
            st.markdown("**ATS-safe rewrite**")
            with st.container(border=True, height=420):
                st.text(st.session_state.result)

        st.write("")
        dl_col1, dl_col2, _ = st.columns([1, 1, 2])
        with dl_col1:
            st.download_button(
                "⬇ Download as TXT",
                data=st.session_state.result,
                file_name="resufit_resume.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                "⬇ Download as DOCX",
                data=build_docx(st.session_state.result),
                file_name="resufit_resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

    st.divider()
    st.button("Start over", on_click=lambda: reset_state())
