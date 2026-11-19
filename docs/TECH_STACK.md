# Tech stack

Big choices are fixed here. For smaller libraries, choose what fits and explain it in the plan.

- **Frontend:** React, Vite and TypeScript. Replies render as Markdown with KaTeX maths, streamed
  from the backend.
- **Backend:** Python and FastAPI; uv manages Python and packages; Pydantic models define and check
  every request and response.
- **Chat storage:** SQLite in one file, with its built-in full-text search for chats. Uploaded images
  are files in a project folder; the database records where.

## Models
- All model calls go directly to OpenAI; no other provider. The key and model names are in `.env`.
- Replies, titles and the evaluation judge use GPT-6 Luna. Notes use text-embedding-3-large.
- Before building on GPT-6 Luna, one small real call checks streaming, tool calling and image input.
- `.env.example` lists every setting `.env` needs, with no real values, and is committed.

## Agent
- A LangChain agent using GPT-6 Luna. `search_notes` searches the notes database; the agent decides
  when. Phases 20–25 added web search, a calculator and Python.
- `search_notes` takes an optional list of module short names; otherwise all modules are searched.
- Chat history is in SQLite, not LangChain; the agent gets the earlier messages each turn.
- Replies stream from the agent through the backend to the frontend.
- Instructions live in their own Markdown file, so behaviour changes without code changes.

## Notes database
- Chroma, in a project folder. Each slide or PDF page is one chunk; only unusually long pages split.
- Each chunk stores module, file name and slide or page number.
- Notes folders are in a settings file, with each module's full and short name; the evaluation uses
  this to match the test set's full names.
- The real settings file isn't committed; an example with placeholders is.

## Converting slides
- A library converts to Markdown, keeping slide and page numbers: MarkItDown for PowerPoint,
  `pymupdf4llm` for PDF.
- `.ppt` goes to `.pptx` first with LibreOffice (installed by me), headless, writing a copy in a project
  folder that's in `.gitignore`. The original is never touched.
- LibreOffice isn't on PATH, so its `soffice.exe` (Windows) or `soffice` (macOS) path is in settings. It
  uses a profile folder inside the project, creating nothing in my user folder.
- A library must not download AI models into my user folders; any it needs stay in the project.

## Testing
- Phase-end verification has three levels (`docs/PROCESS.md`), using the existing Playwright tools.
- Test what matters: spec rules and anything that could fail silently, such as folder sync, the module
  filter, saving chats and streaming. Not trivial code.
- Backend: pytest. End to end: Playwright for the main journeys (send and see a streamed reply, reopen a
  chat, a notes answer with sources), with browsers inside the project. No separate component tests.
- Tests never call paid models; a fake model returns fixed replies.

## Evaluation
Measures the real app with real models. Run by hand after any phase changing the notes database, search
or agent instructions. Never part of normal tests.

**Test sets.**
- `evaluation/tests_small.jsonl`: 10 per module, 50 in all. BL, FR and IMA from my previous project,
  trimmed, keeping a mix of categories and at least one not_covered each. AFA and IPA: 10 new each,
  drafted from the converted slides for my review. Each line has a question, keywords, a reference
  answer, a category (direct_fact, definition, calculation, spanning, paraphrased, not_covered) and a
  module by full name.
- `evaluation/tests_behaviour.jsonl`: checks section 4's rules: unrelated questions don't search, added
  outside knowledge uses the label, one-module requests return only that module.

**Measured.** (1) Retrieval: MRR, nDCG, keyword coverage. (2) Answer quality: a GPT-6 Luna judge compares
with the reference and scores accuracy, completeness and relevance 1–5, on information not wording. (3)
Not covered: whether the answer says "Your notes don't cover this". (4) Behaviour: pass or fail.

**Results.** Printed on finishing: overall, by category and by module, with the change in each headline
score. Saved in `evaluation/results/`: a dated detailed file per run (every question's scores, answer and
sources) and `history.csv` (date and time, optional note, model names, headline scores, time taken).
Committed to git. Never slide text, only references.

## Running it
One command starts backend and frontend and opens the browser. `docs/STATUS.md` has the commands.

## Improvements after pilot

No new external service for phases 14–16.

- **Navigation:** React Router message fragments (`#message-123`), stable DOM targets, existing Radix
  menus. FTS already stores message ids; expose the best match's as nullable API data.
- **Selected excerpts:** Selection/Range APIs and the existing renderer, preserving equations through
  original LaTeX. Optional quoted context on the user message via an additive, repeatable migration.
- **Model context:** quoted context is in user messages, token estimates and summary input, as quoted
  text. No additional model call.
- **Editing:** a validated endpoint reuses the streamed reply pipeline. One transaction updates the
  question, removes the old reply and invalidates an affected summary. Per-chat coordination and a
  stale-state check; no job queue.
- **Desktop shortcut (phase 17):** a `.lnk` from `WScript.Shell` running `uv run askmynotes`; a committed
  `.ico` made once with Playwright Chromium and Pillow. No new dependency.
- **Document uploads (phase 18):** existing converters plus MarkItDown's `docx` and `xlsx` extras. Old
  `.doc`, `.ppt`, `.xls` through LibreOffice with their own profile in `data/`. Base64 in the send
  request. Originals in `data/uploads/`, extracted text in SQLite, sent with the question. Nothing touches
  Chroma. Default budget 200,000 tokens.
- **Cost and context (phase 19):** `ChatOpenAI(stream_usage=True)`; titles and summaries read usage from
  their reply. `notes/embeddings.py` calls the endpoint through the `openai` package to read token counts,
  vectors unchanged. One SQLite row per call, priced from `[prices]`. The context readout reuses
  `chats/history.py`'s estimate.
- **Tools and richer answers (phases 20–25):**
  - Still OpenAI only. Replies use the Responses API,
    `ChatOpenAI(use_responses_api=True, output_version="responses/v1")`, with `store=False`, because
    OpenAI's web search and Code Interpreter only work there.
  - Tools: `search_notes`; hosted `web_search`; local `calculate` and `solve_equation`; hosted
    `code_interpreter`, offered only when Python is switched on.
  - New libraries, approved 2026-10-29: `sympy`, `rehype-highlight`, `mermaid` (on demand), `recharts`.
    Python's containers and files use the installed `openai` package. Generated files go under `data/uploads/`.
  - Web search detail (phase 26): `watch_web_searches` wraps the OpenAI client's reply call to announce
    a search's start through LangGraph's custom stream. Requests ask for `web_search_call.action.sources`.
  - Not adopted: Tavily (the fallback), running Python locally, SymPy's `eval`-based parser, Shiki,
    Vega-Lite, Chart.js.
- **The redesign (phases 29–35; built):** frontend only.
  - **Still plain CSS Modules and tokens.** No CSS framework and no animation
    library. Themes are sets of CSS variables switched by a `data-theme`
    attribute on the page.
  - **Fonts, approved by you on 2026-11-09 and installed in phase 29:** `@fontsource-variable/bricolage-grotesque`,
    `@fontsource-variable/geist` and `@fontsource-variable/geist-mono` replaced
    the pilot's three font packages. They ship with the app, so nothing is
    fetched online. Bricolage Grotesque is imported from its
    `standard.css`, the file that includes the width axis.
  - **A contrast test** (`frontend/e2e/contrast.spec.ts`) reads `tokens.css`
    and checks each theme's text against the brightest the backdrop can be.
    It needs no package.
  - **Browser features, no package:** `backdrop-filter` for the glass, the View
    Transitions API for the moving message box (skipped where the browser lacks
    it), and the browser's `localStorage` for the appearance choices and the
    sidebar's state. In use since phase 30: `backdrop-filter`, and `mask-image`
    for the fades at the edges of scrolling areas. In use since phase 34:
    - **View Transitions** (`document.startViewTransition`, in
      `frontend/src/design/glide.ts`). Only the message box takes part, so the
      rest of the page changes at once and stays usable. React's `flushSync`
      makes the change inside the transition.
    - **`localStorage`**, under the one key `askmynotes-appearance`
      (`frontend/src/design/appearance.ts`): the theme, the effects level and
      whether the sidebar is open. A few lines in `frontend/index.html` read it
      before the page first draws.
    - **Two attributes on `<html>`** switch the styles: `data-theme` (none for
      Volt) and `data-effects="calm"` (none for Full). `data-thinking` on the
      app's root marks a reply in progress.
  - **One shared glass style** (`frontend/src/design/glass.module.css`), which
    other stylesheets take with CSS Modules' `composes`. No package.
  - **Icons** stay Lucide. Mermaid and Recharts stay, and take their colours
    from the tokens.
  - **Not adopted:** Tailwind, a component library, Framer Motion or any other
    animation library, and WebGL for the backdrop.
- **Tests:** pytest covers data, model context and request rules; Playwright
  covers selection, navigation and editing with the fake model. There is no
  new frontend component-test framework. Existing databases must upgrade without
  rebuilding chats or notes. Windows and macOS retain separate local data.

