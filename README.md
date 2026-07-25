# ResumeFit: Quick Start

## Setup
A `.venv` with all dependencies already exists in this folder. To use it directly:
```
.venv\Scripts\activate
```
If you need to rebuild it from scratch instead:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Either way, copy the env file and add a real key:
```
copy .env.example .env
```
Then open `.env` and set `OPENAI_API_KEY` to a real key. `RESUFIT_MODEL` defaults to `gpt-4o-mini`. See `compare_models.py` below if you want to compare against `gpt-4o` before the demo.

PDF export additionally requires a LaTeX distribution with `pdflatex` on PATH. This is a separate system install, not a pip package - if it isn't installed, TXT and DOCX downloads still work; the PDF button just reports it's unavailable instead of failing the whole page. To enable it:

- **Windows**: install [MiKTeX](https://miktex.org/download) (the free "Basic MiKTeX Installer"). Default settings are fine - it installs `pdflatex` on PATH and fetches any missing packages automatically the first time it compiles.
- **macOS**: install [MacTeX](https://tug.org/mactex/) (full, several GB) or [BasicTeX](https://tug.org/mactex/morepackages.html) (smaller; if you use BasicTeX, also run `sudo tlmgr install geometry fontenc lmodern enumitem` for the packages this app's template needs).
- **Linux**: `sudo apt install texlive-latex-base texlive-latex-recommended texlive-latex-extra` (Debian/Ubuntu), or the equivalent `texlive` packages for your distro.

After installing, open a **new** terminal (PATH changes don't apply to already-open ones) and confirm it worked with `pdflatex --version`. No app code or `requirements.txt` changes are needed either way - PDF generation shells out to whatever `pdflatex` it finds on PATH.

## Run
```
streamlit run app.py
```

## Try it
Paste the contents of `sample_data/messy_resume_example.txt` into the app, or upload it as a PDF/DOCX, to see the gap-detection, formatting-risk warnings, and quiz flow in action. The final result can be downloaded as TXT, DOCX, or PDF.

## How the quiz questions are chosen
After you click Start, there's a brief "Analyzing your resume" step before the quiz begins. This makes a live API call, so it takes a couple seconds. The question queue blends two sources:
- Rule-based (`src/gap_detection.py`, no API call): fixed checks for missing dates, vague titles, unquantified bullets.
- LLM-generated (`src/question_generator.py`, calls OpenAI): reads the actual draft and proposes questions specific to its content, an ambiguous scope of responsibility, an unexplained gap between roles, a claim that could be more specific, and so on. It's told what the rule-based layer already asked, so it won't repeat those.

If the LLM call fails, it falls back to rule-based-only questions (still topped up to at least 2 questions with generic prompts if needed), so the quiz step never breaks even if the API is briefly unavailable.

## Compare models
```
python compare_models.py
```
Runs the ATS rewrite against `gpt-4o-mini` and `gpt-4o` on the sample resume with a fixed set of quiz answers, and prints both outputs side by side. Makes real, billed API calls.

## Live-demo fallback
If the OpenAI API fails during the presentation, the app retries once automatically. If that still fails while running any resume that's bundled in `sample_data/`, it falls back to a pre-generated cached response instead of showing a bare error (the UI clearly labels it as cached, and never silently pretends it's live). This works for any `.txt`, `.pdf`, or `.docx` file dropped into `sample_data/`, not one hardcoded filename. A draft `foo.docx` pairs with a cached response at `foo.cached.txt` alongside it. It only matches files actually bundled there, and it never fires for a real resume someone hands over live.

To (re)generate the cache for everything currently in `sample_data/`:
```
python generate_cached_fallback.py
```
or for just one file:
```
python generate_cached_fallback.py "some_resume.docx"
```
Run this again whenever you add, remove, or edit a file in `sample_data/`. See `PRD.md` Section 13 for the full three-layer plan, including the manual video-backup step that still needs to be recorded before the demo.

Heads up: `sample_data/` currently includes a real resume (`Michael O Eniolade.docx`) with real personal details. Worth deciding as a group whether that should be gitignored before this repo is shared with teammates or submitted, or swapped for a synthetic one like `messy_resume_example.txt`.

## Project layout
- `app.py`: Streamlit UI and the state machine driving the flow (intake, then analyzing, then quiz, then rewrite, then done). Includes the accessibility CSS pass and the sidebar step tracker.
- `src/gap_detection.py`: traditional chatbot layer. Tokenizes the draft, flags missing dates, vague titles, and unquantified bullets, and provides the generic-question fallback (see How the quiz questions are chosen above).
- `src/question_generator.py`: AI-as-a-service layer. Reads the draft and proposes content-specific quiz questions, blended with the rule-based ones, with a graceful fallback if the API call fails.
- `src/document_parser.py`: parses uploaded PDF/DOCX resumes into plain text and flags ATS-risky formatting (tables, images, text boxes).
- `src/rewriter.py`: AI-as-a-service layer. Builds the prompt, calls the OpenAI API for the ATS-safe rewrite, and retries once on failure.
- `src/demo_fallback.py`: scans `sample_data/` for any draft resume matching the current input and serves its cached response if the live API is down (see Live-demo fallback above).
- `src/resume_export.py`: converts the plain-text rewrite into a downloadable DOCX with proper headings and bullets.
- `src/latex_export.py`: renders the same plain-text rewrite as a minimal single-column LaTeX document and compiles it to PDF via a local `pdflatex` (see PDF export above).
- `src/session_state.py`: Streamlit session state setup and reset.
- `src/sample_answers.py`: fixed quiz answers for `messy_resume_example.txt` specifically, used by `compare_models.py` for a realistic model comparison (unrelated to the generic fallback cache, which uses no quiz answers).
- `sample_data/`: one or more sample or real resumes plus their cached fallback responses (`*.cached.txt`), used for testing, model comparison, and the live-demo fallback.
- `.streamlit/config.toml`: high-contrast theme for the accessibility pass.
- `compare_models.py`: side-by-side model comparison script on `messy_resume_example.txt` specifically (see above).
- `generate_cached_fallback.py`: regenerates cached fallback responses for everything in `sample_data/` (see Live-demo fallback above).

See `../PRD.md` for the full requirements and weekend milestone plan.
