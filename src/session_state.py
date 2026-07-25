"""Session state helpers for the Streamlit chat flow."""
import streamlit as st

STAGE_KEYS = (
    "stage", "draft", "gaps", "current_gap_index", "answers", "result", "error",
    "draft_prefill", "upload_warnings", "last_uploaded_name", "used_fallback",
)


def init_state() -> None:
    defaults = {
        "stage": "intake",  # intake -> quiz -> rewriting -> done
        "draft": "",
        "gaps": [],
        "current_gap_index": 0,
        "answers": {},
        "result": "",
        "error": "",
        "draft_prefill": "",
        "upload_warnings": [],
        "last_uploaded_name": "",
        "used_fallback": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_state() -> None:
    for key in STAGE_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    init_state()
