# Design Document: ResumeFit

**Course:** MSAI631-M92, Artificial Intelligence for Human-Computer Interaction
**Project:** Residency Group Project, Conversational ATS Resume Converter
**Status:** Reflects the current state of `code/` as of Day 1 evening, 07/24/2026.

## 1. Purpose and Scope

ResumeFit takes a messy resume draft and turns it into a clean, ATS-standard rewrite through a short conversation. A user pastes text or uploads a PDF or DOCX file, answers a handful of targeted questions about what the draft is missing, and receives a rewritten resume they can download as plain text, DOCX, or PDF. The project exists to satisfy a specific course requirement: build a chatbot that integrates a traditional, rule-based layer with an AI-as-a-service layer, and use that integration to demonstrate prompt engineering, accessibility, and applied AI ethics.

This document describes what was built and why, not what was originally proposed. It explains the architecture, the reasoning behind each design decision, and the tradeoffs the team weighed while building it.

Two things were deliberately left out of scope. The tool does not build a resume from a blank page; it only improves an existing draft. It also does not score a resume against a specific job posting. Both are natural extensions of the same architecture and are noted in Section 7.

## 2. System Architecture

The application runs as a single Streamlit process (`app.py`) that steps a user through five stages: intake, analyzing, quiz, rewriting, and done. Each stage hands off to one of two processing layers. The traditional layer is plain Python: regex-based parsing and rule checks, with no network calls. The AI-as-a-service layer makes two separate calls to the OpenAI Chat Completions API, one to generate content-specific quiz questions and one to produce the final rewrite. Figure 1 shows the intake and stage-tracking UI that drives this flow.

![Figure 1: Streamlit UI stages, from intake through done](design/01-streamlit-ui.png)

Intake accepts either pasted text or an uploaded PDF/DOCX file. `src/document_parser.py` extracts plain text from an upload and separately flags formatting that breaks ATS parsing (tables, embedded images, text boxes), surfacing those as warnings before the user even starts the quiz. Figure 2 shows this stage alongside the rule-based gap detector it feeds into.

![Figure 2: Document parsing and rule-based gap detection, entirely local](design/02-traditional-nlp-layer.png)

`src/gap_detection.py` is the traditional chatbot layer proper. It splits the draft into lines and runs three independent checks: missing or inconsistent dates near a role header, vague job titles ("Team Member," "Associate"), and bullet points with no quantified result. Each check produces a `Gap` object carrying the offending line and a question to ask about it. The three categories are interleaved round-robin before a cap of five questions is applied, so a resume with many missing dates and no vague titles still gets a mixed question set rather than five date questions in a row. If rule-based detection turns up fewer than two gaps, generic questions (add a summary, name a target role, list additional achievements or skills) top up the queue, so the quiz step always runs even against an already well-formatted resume.

The rule-based questions alone were the original design. During testing against a real, already-decent resume, the checks found nothing to flag, and the app skipped the quiz entirely, silently dropping the feature the course asks the project to demonstrate. `src/question_generator.py` was added to fix this: it sends the draft plus the rule-based questions already queued to the OpenAI API and asks for additional questions specific to what that particular resume actually says, an ambiguous scope of responsibility, an unexplained gap between roles, a title that seems to mismatch its described duties. Figure 3 shows this stage.

![Figure 3: Content-specific question generation via the OpenAI API](design/03-ai-question-generation.png)

The two question sources are merged the same way the rule-based categories are, interleaved and capped, so neither source can crowd out the other. If the API call fails, `build_quiz_queue` catches the exception and falls back to rule-based-only questions, padded with the same generic top-up used when rule-based detection alone comes up short. The quiz never blocks on this call being available.

Once the queue is built, the app presents one question at a time in a chat interface (Figure 4), tracks each answer against the gap it resolves, and lets the user skip a question rather than force a fabricated answer.

![Figure 4: One question at a time, with answer tracking and skip support](design/04-quiz-clarify-loop.png)

When the quiz is complete, the draft and every collected answer go to `src/rewriter.py`, the second AI-as-a-service call (Figure 5). Its system prompt fixes the ATS constraints directly: single-column layout, the four standard section headers, consistent date formatting, and an explicit instruction not to invent employers, titles, dates, or achievements beyond what the draft or the quiz answers actually contain. `rewrite_resume_with_retry` wraps the call with one automatic retry on failure, since the most common live-demo failure mode is a transient rate limit or network blip rather than an actual outage.

![Figure 5: The ATS rewrite call, with a structured prompt and one retry](design/05-ai-ats-rewrite.png)

If both attempts fail, the app falls back to a cached response rather than showing a bare error, described in Section 4. The final text is rendered in a before/after view and made available for download in three formats, covered in Section 3.6.

## 3. Component Design and Rationale

### 3.1 Why two rounds of AI-as-a-service, not one

The architecture calls the OpenAI API twice: once to help generate questions, once to rewrite. An earlier version of the design called it only once, for the rewrite. That version worked, but it made the "traditional chatbot" half of the project do all the interesting work and left the AI-as-a-service half doing something a single well-crafted static prompt could have done just as well. Splitting question generation into its own API call gives the AI layer a job the rule-based layer structurally cannot do: reading the actual content of a specific resume and asking about what's ambiguous in it, as opposed to matching fixed patterns like missing dates or vague titles. The two calls also demonstrate two different prompting problems: one that must produce a short, bounded list of novel questions without repeating a supplied list, and one that must produce a long, structurally constrained document while inventing nothing. That contrast is part of the intended prompt-engineering material for the course discussion.

### 3.2 Gap detection thresholds and the round-robin cap

Capping the question queue at five and flooring it at two were both judgment calls, not derived from user testing. Five was chosen as an upper bound on how many questions a user would tolerate answering before the "let a chatbot fix my resume" pitch starts to feel like homework. Two was chosen as the minimum needed for the quiz to feel like it did something, rather than a single throwaway question. The round-robin interleaving across the three rule-based categories exists because an early version of the detector, tested against a resume with several missing dates and only one vague title, produced a queue of four consecutive date questions and cut off before reaching the vague-title or unquantified-bullet checks at all. Interleaving before capping fixed that without changing any individual detector's logic.

### 3.3 The Markdown-stripping fix

During testing, the rewrite output started showing up with literal `**` characters around job titles and company names in every export format: TXT, DOCX, and PDF. The cause was the model defaulting to Markdown bold syntax in its response, a habit picked up from chat-formatted training data, despite the system prompt never asking for it. None of the three export paths interpret Markdown, so the asterisks passed through as literal text, exactly the kind of artifact a real ATS parser would also choke on. The fix has two parts. The system prompt in `rewriter.py` now explicitly forbids Markdown formatting and states why: the output is exported as-is and literal formatting characters will appear in the final resume. A regex-based `strip_markdown_emphasis` function also runs on every API response before it reaches session state, removing any `**bold**` or `__bold__` markers that get through anyway. Prompt instructions alone were not treated as sufficient, since instruction-following on a single stylistic constraint is not guaranteed on every call, and the cost of a defensive regex pass is small next to the cost of a visibly broken resume during a live demo.

### 3.4 Output formats: TXT, DOCX, and a LaTeX-rendered PDF

The output layer (Figure 6) originally supported plain text and DOCX. A third format, PDF, was added afterward, and it required resolving a real tension in the requirement itself.

![Figure 6: Output layer, including the LaTeX-rendered PDF export added after the initial build](design/07-output-layer.png)

"Clean, professional PDF" and "ATS-safe" pull in different directions. Most polished-looking LaTeX resume templates use multi-column layouts, custom fonts, or graphical elements, exactly the formatting choices that break automated resume parsers. Rather than pick a visually rich template and lose ATS safety, `src/latex_export.py` generates a deliberately minimal, single-column LaTeX `article` document: bold section headers, plain `itemize` bullets, no packages beyond basic margins and font substitution. The same plain-text structure that `resume_export.py` already parses for DOCX (section headers, `- ` bullets, plain paragraph lines) feeds both exporters, so all three download formats stay in sync without duplicating the parsing logic three times.

Compilation happens by shelling out to a local `pdflatex`, run with `-no-shell-escape` to keep the compiled input from being able to execute arbitrary commands, since the LaTeX source is built from model output that the team does not fully control. This was a deliberate choice among three options considered: a local LaTeX engine (chosen), Tectonic (a self-contained LaTeX binary that still requires an external dependency and a first-run network fetch), and a pure-Python PDF library with no system dependency at all. The team picked the local-engine approach because MiKTeX was already installed on the development machine and produced real LaTeX-typeset output (not an approximation), at the cost of adding a system dependency the demo environment must have. That cost is mitigated two ways: the PDF button is wrapped in a try/except in `app.py`, so a missing `pdflatex` degrades to a caption explaining the PDF is unavailable rather than crashing the page, and `README.md` documents per-OS installation steps (MiKTeX, MacTeX/BasicTeX, or the `texlive` packages on Linux) for anyone setting up the project fresh.

One design decision was made deliberately conservative: LaTeX generation stays entirely in application code, not in the model. The rewriter's output is still plain text; `build_latex` is the only thing that ever produces `.tex` source. Letting the LLM emit raw LaTeX directly would risk malformed commands breaking compilation and would turn the PDF export into a code-injection surface, since compiling LLM-authored LaTeX means compiling unvalidated input.

## 4. Reliability Design: The Live-Demo Fallback

A live demo depends on a network call to a third-party API succeeding at a specific moment in front of an audience, so the system was built with three layers of degradation instead of one path that either works or doesn't (Figure 7).

![Figure 7: Retry once, then serve a cached response, clearly labeled and never silent](design/06-live-demo-fallback.png)

The first layer is the automatic retry already described in Section 2. The second, `src/demo_fallback.py`, activates only if both attempts fail: it scans every draft file bundled in `sample_data/`, using the same parser the app uses for uploads, and checks whether the current draft text matches one of them. On a match, it serves that file's pre-generated cached rewrite instead of an error, and the UI displays a visible banner stating the response is cached, not a fresh live rewrite. This fallback is intentionally narrow. It only ever fires for a file the team actually bundled ahead of time; a real resume typed in live by an audience member has no cached counterpart and still surfaces an error if the API is down. That narrowness matters for demo honesty as much as for engineering correctness, since the project's own ethics discussion argues for AI transparency, and a fallback that silently pretended to be live would contradict that stance in the same demo meant to illustrate it. A third layer, a recorded backup video of a full successful run, is planned but not yet captured as of this writing; it remains the last resort if the entire environment, not just the API, fails during the presentation.

## 5. Data Handling, Accessibility, and Ethics

Nothing in the application persists beyond the active browser session. Session state lives entirely in Streamlit's in-memory store; there is no database and no external storage of resume content. The API key is read from an environment variable via `python-dotenv`, kept out of the repository through `.gitignore`.

Accessibility was treated as a design constraint rather than an afterthought, largely because it overlaps almost exactly with the ATS-safety requirement the project already needed to satisfy. A single-column, table-free, plain-text-structured resume is close to what a screen reader also needs to parse a document correctly, so the same rewrite prompt serves both goals. On the interface side, `app.py` injects CSS for a larger base font size and a visible keyboard focus outline, and `.streamlit/config.toml` sets a high-contrast theme.

The ethics discussion the course asks for has concrete hooks in this specific build, not just abstract principles. Privacy is a live concern because `sample_data/` currently contains one real resume with real personal details, added during testing; the team still needs to decide whether to gitignore that file or replace it with a synthetic example before the repository is shared or submitted. Transparency is handled directly through the fallback banner described in Section 4, which never lets a cached response pass as a live one. Accountability against fabrication is handled at the prompt level: the rewrite instructions explicitly forbid inventing employers, titles, dates, or achievements not present in the draft or the quiz answers, and any gap the user skips is passed through as unresolved rather than guessed. Biased resume-screening AI has real precedent, most visibly Amazon's internal screening model, scrapped in 2018 after it penalized resumes containing the word "women's." This project builds a resume rewriter rather than a screening or ranking tool, which sidesteps that particular failure mode, but the team treats it as a reason to be deliberate rather than a reason the risk doesn't apply here.

## 6. Implementation Status

All functional requirements for this project are implemented and smoke-tested as of this writing, with two exceptions still open ahead of the Day 2 and Day 3 milestones.

| Area | Status |
|---|---|
| Intake (paste and file upload) | Done |
| Rule-based gap detection, interleaved and capped | Done |
| Content-specific question generation via API, with fallback | Done |
| Quiz loop (one question at a time, skip support, answer tracking) | Done |
| ATS rewrite prompt and retry | Done |
| Markdown-stripping fix (Section 3.3) | Done |
| Output: TXT, DOCX, and PDF (Section 3.4) | Done |
| Live-demo fallback, Layers 1 and 2 (Section 4) | Done |
| Live-demo fallback, Layer 3 (recorded backup) | Not yet done |
| Live browser walkthrough of the full flow | Not yet done |
| End-to-end timing against the two-minute target (NFR1) | Not yet formally timed |

## 7. Limitations and Future Work

Three limitations are deliberate scope cuts rather than defects: the tool does not build a resume from nothing, it does not score a draft against a job description, and it does not detect true multi-column page layout in an upload, since the PDF and DOCX parsing libraries in use do not expose that cleanly, only tables, embedded images, and text boxes. Both scope cuts are compatible with the existing architecture if picked up later; the quiz-and-rewrite pipeline does not need to change shape to add a job-description-matching step, only a new comparison stage after the rewrite.

Two things are open questions rather than firm decisions. The five-question cap and two-question floor described in Section 3.2 have not been validated against how an actual user reacts to the quiz length, only against the team's own judgment during testing. And the recorded backup video for the third fallback layer, needed before the live presentation, has not yet been captured.

## 8. Conclusion

ResumeFit demonstrates the specific integration the course assignment asks for: a rule-based chatbot layer that runs entirely locally, coupled to an AI-as-a-service layer that makes two distinct, purpose-built calls to an external API. The two-layer split is not just structurally present but functionally load-bearing, since the rule-based layer catches known patterns the AI layer would be redundant at checking, while the AI layer catches resume-specific issues no fixed rule set could anticipate. The reliability work in Section 4 and the accessibility overlap in Section 5 were both treated as first-class design constraints, not late additions, because a live, in-person demo has zero tolerance for a bare stack trace or an inaccessible interface. What remains before the Sunday presentation is testing under real conditions rather than new functionality: a live browser walkthrough, timing validation, and the recorded fallback video.
