# Build plan

> **Condensed 2026-11-11.** Phases 1–28 are built, so their entries keep the
> decisions, reasons, findings, limits and open checks. Ticked checklists, test
> lists and screenshot lists are in git: `git show 604e90c:docs/PLAN.md`.
> Phases 29–36 are unabridged.

Each phase says what it builds, why then, the approach and why, and ends with a
checklist that must be fully ticked before it counts as done.

**Status.** Pilot (1–13) approved 2026-10-27; 1–12 built; 13 built and tested on
Windows. Phases 14–16 approved 2026-10-28 (phase 15, then 16, authorised one at a
time). Phases 17–19 and 20–25 approved and built 2026-10-29; 26 built 2026-10-29
and 27 and 28 on 2026-10-30, each on your instruction. All Windows-verified; see
"Open checks".

**Phases 29–35 (the redesign: a new look for the whole app, with every feature
kept): proposed on 2026-11-09; you confirmed its main decisions the same day.
Phases 29 (foundations), 30 (the shell), 31 (the new chat screen and the
message box), 32 (the conversation), 33 (panels and pictures), 34 (motion
and appearance) and 35 (the finish) are built and Windows-verified, on your
instructions of 2026-11-09, 2026-11-10 and 2026-11-11.** See
"Phases 29–35" near the end of this document.

**Phase 36 (four small fixes to existing behaviour, found in phase 30's
review): planned on 2026-11-10 on your instruction; not built and not yet
authorised.** See "Phase 36" at the end of this document.

## Open checks (phases 13–28)

Each stays open until actually done; Windows tests with a simulated Mac don't count.

- [ ] **Phase 13, on the MacBook, checked by you:** `uv sync`, `npm install` and the
      Playwright browser install complete; `uv run pytest`, `uv run ruff check`,
      `npm run lint`, `npm run typecheck`, `npm run build` and `npx playwright test`
      pass; `uv run askmynotes-convert-notes` converts every file, including the
      `.ppt` ones through LibreOffice; `uv run askmynotes` opens the browser and
      brings the notes up to date ("Updating notes", then 53 files); a notes
      question shows its sources, and a chat is still there after a restart; the
      ⌘ K and ⌘ ⇧ O shortcuts work in your browser, or I'm told which don't.
- [ ] **Phase 14:** real MacBook quality gate and navigation/keyboard checks,
      including Back/Forward.
- [ ] **Phase 15:** real MacBook gate and selection/formula/Command-key walkthrough.
- [ ] **Phase 16:** MacBook gate and Mac keyboard/browser check of editing and
      replacement streaming.
- [ ] **Phase 18, MacBook:** the gate passes on the Mac, and a real `.docx` and
      `.xls` convert there (the second needs LibreOffice).
- [ ] **Phase 19, one small real check, only with your permission** (well under a
      cent): GPT-6 Luna reports usage while streaming with `stream_usage=True`, and
      the new embeddings class works against the real endpoint. If usage doesn't
      arrive, every reply would be estimated; I'd stop and tell you.
- [ ] **Phase 19, checked by you:** after a day of use, the all-chats total is close
      to the usage on your OpenAI dashboard.
- [ ] **Phase 19, MacBook:** add the `[prices]` section to its `settings.toml`, then
      the gate passes and the readouts show.
- [ ] **Phase 20, MacBook:** pull the code; then the gate passes. No settings change.
- [ ] **Phase 21, MacBook:** add the `[web_search]` settings and the new price to its
      `settings.toml`; then the gate passes.
- [ ] **Phase 22, MacBook:** run `uv sync`; then the gate passes.
- [ ] **Phases 23 and 24, MacBook:** pull the code and run
      `(cd frontend && npm install)`; then the gate passes.
- [ ] **Phase 25, MacBook:** add the new settings; then the gate passes.
- [ ] **Phase 26, MacBook:** `uv sync`, then the app starts and a web answer shows the
      status and the panel.
- [ ] **Phase 27, MacBook:** the same check in a narrow window (new chat screen
      centred, no sideways scrollbar).
- [ ] **Phase 28, MacBook:** quality gate and a walkthrough of streaming, reopening,
      Copy and sources pass on the Mac.

A commit needed to reach the Mac may precede its manual checks (as in phase 13) but
must keep the check open. Phase 17 is Windows-only, so has no MacBook check.

## Overview of the pilot

| # | Phase | Visible result |
|---|---|---|
| 1 | Foundations and model check | `uv run askmynotes` opens a page; GPT-6 Luna confirmed |
| 2 | The look | Real screens with sample data, approved by you |
| 3 | Chat storage | Chats in SQLite through a tested API |
| 4 | Streaming chat | Streaming, stop, copy, regenerate, retry, errors |
| 5 | Chat history | Sidebar groups, titles, pin, rename, delete, search, shortcuts |
| 6 | Image uploads | Attach, drag or paste images |
| 7 | Long chats | Over-long chats keep working |
| 8 | Converting slides | Every slide and page as Markdown |
| 9 | Notes database and sync | Indexing, start-up sync, progress, Refresh notes |
| 10 | Searching notes in chat | Sources, "Beyond your notes", module filter |
| 11 | Evaluation | Test sets and a runnable evaluation |
| 12 | Final check | Every spec success criterion checked |
| 13 | macOS | Same code on the MacBook, with its own data |

**Why this order.** Chat is the backbone and can be built free with a fake model.
The look came second so you could approve it first (the one planned pause, after
phase 2). The notes pipeline is independent of chat; phase 10 joins them. The
evaluation measures the finished whole.

## Project layout

```
pyproject.toml, uv.lock       Python project at the root, so `uv run` works from here
settings.toml                 real settings: folders, name, LibreOffice path (not committed)
settings.example.toml         the same with placeholder paths (committed)
.env / .env.example           OpenAI key and model names / the list of names (only the example is committed)
backend/askmynotes/           chats/ agent/ notes/ evaluation/ and later feature folders
backend/tests/                pytest tests and the fake models
frontend/src/                 one folder per feature: sidebar, chat, markdown, notes, design
frontend/e2e/                 Playwright tests
evaluation/                   test sets, and results/ with each run and history.csv
data/                         everything generated (not committed)
```

`data/` holds `app.db` (chats, messages, synced-file records), `notes_markdown/`,
`pptx_copies/`, `chroma/`, `uploads/` and `libreoffice_profile/`. One ignored
folder keeps "never commit lecture content" easy; each subfolder is still added to
`.gitignore` by name in the phase that creates it.

## Settings

- **`.env`:** `OPENAI_API_KEY`, `CHAT_MODEL`, `EMBEDDING_MODEL`. Nothing else.
- **`settings.toml`:** greeting name, modules (full name, short name, folder),
  LibreOffice path, example prompts, port, tuning numbers. TOML because it allows
  comments, needs no library, and takes Windows paths as-is in single quotes.
- Both load through `pydantic-settings` at start-up. A missing or misspelled setting
  stops the app with a message naming it.

## Libraries and why

- **Backend:** `fastapi`/`uvicorn`; `pydantic-settings`; `langchain`,
  `langchain-openai` (`create_agent`); `chromadb` directly (the LangChain wrapper
  saves no code); `markitdown[pptx]` (writes a slide-number marker, keeps speaker
  notes, no AI models); `pymupdf4llm` (one block per page with its number; AGPL,
  fine for a personal undistributed app); `langchain-text-splitters`; `pytest`, `ruff`.
- **Rejected:** Docling (needs PyTorch and downloads layout models into user
  folders); MarkItDown for PDFs (doesn't keep page boundaries).
- **Frontend:** `react-markdown`, `remark-gfm`; `remark-math`, `rehype-katex`, `katex`;
  `react-router` (one URL per chat); `@tanstack/react-query` (keeps the sidebar in
  sync); Radix dialog and dropdown (keyboard and focus); `lucide-react`; `@fontsource`
  (fonts ship with the app, so offline); ESLint, `typescript-eslint`, React hooks
  rules, Prettier; `@playwright/test` (browsers in `node_modules` through
  `PLAYWRIGHT_BROWSERS_PATH=0`). Plain CSS Modules with CSS-variable tokens.
- **`:::beyond` needs no library.** I first chose `remark-directive`, but it turns
  ordinary text such as `Note:This` into directives and eats words from answers.

## How tests avoid paid models

The app is created by a function given its chat model and embeddings, so tests pass
fakes. A fake chat model in `backend/tests/` plays back a script (text, tool call,
error, slow stream), because LangChain's own fakes can't make tool calls. Embeddings
use `DeterministicFakeEmbedding`. Tests generate small made-up PDFs and PowerPoints,
so no binaries or lecture content enter the repo. Playwright starts the app with the
fake model and a temporary data folder. The gate's commands are in `docs/STATUS.md`.

---

## Pilot phases (1–13)

### 1. Foundations and model check
Settings, `GET /api/health`, frontend scaffold, `uv run askmynotes`, Playwright,
`uv run askmynotes-check-model`.
- The start command builds the frontend, serves on `127.0.0.1` only, and opens the
  browser. Chosen over two dev servers: one process, one address, no stale frontend.
- The model check makes four tiny calls (stream, tool, image, embedding), because
  GPT-6 Luna's features couldn't be confirmed from knowledge.

### 2. The look
Tokens, fonts, mark and real layout components with sample data, approved by you.
Real components, so approval carried into the working app.
- Pilot palette (replaced by the redesign): near-black `#0A0B10`, violet `#8B5CF6`
  and aqua `#22D3EE`, red `#FB7185` reserved for "Beyond your notes", amber
  `#F59E0B` for errors. Fonts: Space Grotesk, Inter, JetBrains Mono.
- The mark: two offset rounded slides, the front one cut by a diagonal lightning
  bolt. The slides are your notes, the bolt the AI boost.

### 3. Chat storage
`data/app.db` and the chat API (list, open, rename, pin, delete, search).
- Plain SQL with `sqlite3` and one `schema.sql`: short queries, FTS needs raw SQL
  anyway, and you see what's stored.
- Tables: `chats`, `messages` (role, text, status `complete`/`stopped`/`error`,
  error, sources JSON), `message_images`, `chat_search` (FTS5, kept by triggers).
- Search uses prefix matching. Deleting a chat removes messages, search entries and
  image files together.

### 4. Streaming chat
The agent, send endpoint, Stop, Regenerate, Retry, Copy, amber errors.
- Newline-delimited JSON events (`token`, `status`, `sources`, `done`, `error`, each
  a Pydantic model), because `EventSource` can't POST a body.
- The message is saved before the model is called. A failure is saved as the reply
  with plain English; the real error goes to the server log, never the key.
- Retry and Regenerate share one path. Stop: the browser cancels, the server saves
  the partial reply as `stopped`, then lets cancellation finish.
- Maths: `\( \)` and `\[ \]` only, single-dollar maths off, so "$5" stays "$5".

### 5. Chat history
Real sidebar, titles, shortcuts, opens on an empty chat.
- Titles run in parallel with the first reply and arrive as a `title` event; the
  prompt is its own Markdown file.
- Shortcuts: Enter send, Shift+Enter newline, Ctrl+Shift+O new chat, Ctrl+K search,
  Esc close. Grouping uses each chat's last message in local time.

### 6. Image uploads
Base64 in the JSON request, so it stays one Pydantic model. Saved under
`data/uploads/{chat}/`. PNG, JPEG, WebP and GIF. Limits in `settings.toml`. Upload
code never touches the notes database.

### 7. Long chats
Rolling summary: over the budget, older messages are summarised once and saved on
the chat; later turns send the summary plus newer messages; it's updated when the
recent part exceeds the budget. Dropping messages would make the model forget
silently. Size is estimated at four characters a token (an exact counter would
download encoding files into your user folder). Earlier search results aren't resent.

### 8. Converting slides
Scans the module folders to `data/notes_markdown/{module}/`; separate from indexing
so you can review what the app reads, at no cost.
- `.pptx`: MarkItDown; keeps speaker notes and native chart data tables; removes only
  image placeholders.
- PDF: pymupdf4llm. `.ppt`: LibreOffice headless to `data/pptx_copies/`, profile in
  `data/libreoffice_profile/`; sources cite the original `.ppt` name. The duplicate
  `- Copy.ppt` is converted, as you asked.
- A file that fails or has no text is skipped and listed with its reason.
- `pymupdf4llm` is pinned below 2 (`2.0` on PyPI is an empty placeholder). Picture
  text in PDFs is kept without its comment wrapping and `<br>`. Test scratch files
  stay in `data/test_tmp`.
- Real run: all 53 files converted (44 PowerPoint, 6 PDF, 3 old `.ppt`), numbers
  matched, notes folders unchanged. About a minute.

### 9. Notes database and sync
Chunks into Chroma, syncing on start and "Refresh notes".
- Changes by SHA-256 stored in `app.db`: new path, changed hash, or gone. A removed
  module counts as deleted files. About 590MB hashes in seconds.
- Crash-safe: a file is marked synced only after its chunks are written; a redo
  deletes half-written chunks first.
- One chunk per slide or page with module, file, number and part metadata; long pages
  split by the text splitter and keep their number; empty slides skipped. Each chunk
  is embedded with a short header (module, file, slide number).
- Chroma: telemetry off; its built-in embedding function is never used (it would
  download a model). The embedding model's name is stored; changing it stops the app
  rather than mixing vectors.
- Sync runs in the background; the frontend polls once a second; send is refused while
  it runs, with a clear reason.
- If embedding fails, the update stops, shows the reason in amber and chat is allowed;
  undone files retry next time. An unreadable file is recorded by fingerprint and only
  retried when it changes.
- `tiktoken` length checks are off because it downloads encoding files to Windows temp.
  (The phase 1 check had already created `%TEMP%\data-gym-cache`; left for you to delete.)
- E2E uses `askmynotes.e2e_setup` to write made-up notes and settings into `data/e2e`.
  `create_app` takes the whole settings object.
- First real update: 53 files, 2,498 chunks (46 parts of long pages), 91 seconds,
  about 340,000 tokens (about 4.5 cents).

### 10. Searching notes in chat
`search_notes`, instructions, "Beyond your notes", "Your notes don't cover this",
sources, status line.
- The agent decides from its instructions; `{modules}` is filled from `settings.toml`.
  The tool accepts only known short names; empty means all; a misspelling is refused
  and the agent told which exist. No modules means no tool.
- `:::beyond` blocks: the most reliable way to tell, line by line, what came from
  notes, and exactly checkable by the evaluation.
- Sources used only: results get ids (S1…, numbered across one reply, a repeat slide
  keeps its first id); the agent ends with `Sources used: S1, S4` (or `none`). The
  backend removes that line and saves those results; the frontend hides it while
  streaming. If missing, all results are listed and a warning logged. Each page is
  listed once, sorted. A stopped reply keeps sources (named, or all shown, no warning).
- `notes_search_results` (8) is the count per search; the agent judges relevance,
  rather than a similarity cut-off needing per-module tuning.
- A fresh agent per reply (about 1ms) so its tool records that reply's results.
- Hand-checked with GPT-6 Luna on a copy of your data. The model first wrote `[S8]`
  inline; a firmer instruction with the reason stopped it.
- **After the first evaluation:** the sources line is read at the end of any line
  (the model glued it to its last sentence), and partial ends (`Sources us`) are
  removed. It's mandatory in the instructions. Related-topic results don't count as
  covering a specific question. `SEARCH_EFFORT` 500 in `notes/store.py` (Chroma's
  default missed the best slide and varied between starts; applied on each open, no
  rebuild). Searches fetch three times the results and keep the first of each
  identical text (145 of 2,498 chunks are exact copies).

### 11. Evaluation
`uv run askmynotes-eval --note "..."`, report, per-run files and `history.csv`.
- BL 16→10, FR 14→10, IMA 14→10 questions, wording unchanged, keywords checked against
  the notes. AFA and IPA: 2 `direct_fact`, 2 `definition`, 3 `calculation`, 1
  `spanning`, 1 `paraphrased`, 1 `not_covered` each (IPA's `13.06%` swapped for
  `0.0170784`; `not_covered` topics are IFRS 11 joint operations and Black-Scholes).
  All reviewed by you.
- Behaviour set: exact checks `searches`, `sources_listed`, `source_modules`,
  `beyond_label`, `not_covered`, so no judge. A misspelled check is refused on load.
- Retrieval goes straight to search; relevant means any keyword (case-insensitive).
  MRR, nDCG (worth = keywords matched, ordering only), keyword coverage.
- Each question is a fresh one-message chat, saving nothing to your chats. A failed
  question is saved, left out of averages and listed. `--concurrency` default 4.
  Changes shown for headline scores from `history.csv`'s last row. Run with the app
  closed, because both open the notes database.
- The judge replies in JSON checked by Pydantic (JSON mode couldn't be confirmed).
- **Changed after first runs:** a stricter judge (`evaluation/judge_prompt.md`) lists
  key points, fixes the completeness scale, ignores `:::beyond` text; scores are **not
  comparable with earlier runs** (about 0.6 lower on completeness; re-judging agrees
  within one point 49 times in 50). Temperature 0 isn't accepted. Results record every
  search and whether the sources line was present. The agent is told to search again
  for "all", "every", full breakdowns and comparisons.

### 12. Final check
Every spec section 7 criterion was checked (tests, Playwright or the eval run
`evaluation/results/run_2026-10-27_145338.json`). Added tests for sidebar groups and a
whole-app restart. Two gaps accepted as you said the app is good enough: the FR
borrowing costs answer said "not covered" in other words, and 1 reply in 57 left out
its sources line, so listed every result.

### 13. macOS
Same code, each machine with its own `settings.toml`, `.env` and `data/`. Windows-only
parts were few: `default_soffice_path()` by platform; both paths in
`settings.example.toml`; sidebar hints show ⌘ when the user agent contains "Mac".
Lockfiles, `as_posix` ids, `pathlib` and LF endings were already portable. `~` is
deliberately not expanded. Committed before the Mac checks because the code reaches
the Mac through git. Mac notes are in STATUS.

### Pilot decisions at review
Pause after phase 2; chart data and speaker notes kept, only image placeholders
removed; a missing sources line lists all results with a warning; build on each
start; add the "Searching your notes…" status and one URL per chat.

---

## Improvements after pilot (14–28)

Scope is in `SPEC.md` section 8, the look in `DESIGN.md`. Boundaries: no source
previews, module selection, general draft storage, new RAG algorithms, new models or
conversation branches. Order 14→16: navigation introduces message targets, quotes
reuse them, editing must preserve images and quotes.

### 14. Conversation navigation
Jump to latest, search to the matching message, Questions menu.
- `SearchResult` gains nullable `message_id` (FTS already stores it; title-only hits
  have none; one best match per chat, deterministic ties). Stable DOM ids and
  `/chat/<id>#message-<id>`.
- Explicit navigation beats auto-scroll. Same-chat jumps don't abort generation;
  late events from a previous chat are ignored. A missing target shows a notice,
  never a substitute. The Questions menu comes from loaded saved messages, no model.
- No timers as a substitute for content readiness; content resizing is handled.
- Follow-up: replaced a literal `?` in Jump to latest with Lucide ArrowDown.
- Verified: 139 pytest, 33 Playwright, then a separate three-level review.

### 15. Ask about selected text
- `quoted_context` nullable JSON on the user message (source id, excerpt snapshot),
  repeatable additive migration. Source must be an eligible saved assistant message in
  the same chat. Empty refused; over 8,000 characters refused, never truncated. The
  excerpt is user context, not evidence.
- Question and excerpt stay separate; the HumanMessage holds a labelled passage plus
  the question. Counted in the budget and summary input. Retry and Regenerate rebuild
  from storage. The snapshot survives loss of the original. Excerpts don't enter FTS.
- Selection/Range APIs, captured before focus moves. Touching maths expands to the
  whole expression, preserving original LaTeX. No selected-table reconstruction.
- Keyboard: focus an answer, Ctrl+A or Command+A, Tab, Enter; the Tab handler commits
  the action before focus moves.
- Verified: 154 pytest, 44 Playwright, review. Inspection caught a default blue link
  and a stray `?` (fixed).

### 16. Edit and resend the latest question
- `POST /api/chats/{chat_id}/messages/{message_id}/edit` returns the NDJSON stream,
  with expected latest id and original text to detect stale views.
- Send, regenerate, edit and delete are coordinated per chat: reserved before
  preparation, released on completion, failure, cancellation or early disconnect.
- One transaction updates the text in place (id, images, quote preserved), deletes the
  old answer, updates last-used, and clears a summary that covers changed content.
  Summaries of only earlier messages stay.
- An acceptance event carries the saved message before tokens. After acceptance,
  failure saves an error for the corrected question. Interrupted streams reload saved
  state. Save is disabled for unchanged text.
- Verified: 164 pytest, 51 Playwright, review.

### 17. Windows desktop shortcut
`assets/askmynotes.ico` and `AskMyNotes.lnk` on the Desktop.
- Your decisions: the visible PowerShell window; **a one-off exception** to the "outside
  this repo" rule for that one `.lnk`, not carrying over to other phases or later
  changes; Windows only; nothing else changes.
- Your Desktop is redirected to OneDrive, so the shortcut asks Windows for it.
- `.ico` because shortcuts can't use PNG or SVG: seven sizes (16–256) each rendered
  directly from `frontend/src/design/Mark.tsx` by Playwright and combined with Pillow; a tile so it shows on any wallpaper.
  Generation code isn't committed; Pillow isn't added as a dependency.
- `-NoExit` keeps errors readable; `-NoProfile` starts faster; the title reminds you
  closing stops it. Full recreation commands and limits are in STATUS. If the Desktop
  syncs elsewhere, the `.lnk` appears there too and is harmless on a Mac.
- Verified on a test copy with fake model; closing the window and the second-launch
  message were confirmed by your hand test, as this session can't read a console.
- Fixed a test bug: the "Used yesterday" chat failed before noon (with your approval).

### 18. Document uploads and a larger context budget
Option A: read the whole document as text, reusing the converters; no extra embedding
or second database. Its limit is size. Option B (searchable per-chat documents) stays
possible later.
- **Budget 200,000** stays below the 272,000 long-context price threshold that
  third-party listings report for GPT-6 Luna (about 1,050,000 window; OpenAI's own page
  wasn't found).
- Limits: 5 documents, 25 MB each, 100,000 tokens together; the last must be at most
  half the budget, enforced by settings, because long chats keep the newest messages
  within half the budget.
- A document is your own material, like a quote: not notes, not outside knowledge, not
  under Sources. The agent says "Your attached file says…".
- `markitdown[pptx,docx,xlsx]`. `chats/documents.py`; `convert_with_libreoffice` (was
  `convert_ppt_to_pptx`); uploads use `data/libreoffice_profile_uploads/` and
  `data/upload_tmp/`. Text joined with markers such as `--- Page 3 ---`.
- Base64 in the send request; all checks and conversion before saving; refusals are a
  422 naming the file, keeping the draft. `message_documents` table; originals under
  `data/uploads/<chat id>/`. `MessageDocument.text` is excluded from API responses.
- Titles use file names, not text. The summary prompt keeps key document facts. Edit,
  Regenerate and Retry keep documents. A `.docx` chip says "Word document".
- A corrupt PDF holds its file open on Windows, so scratch cleanup ignores errors.
- Verified: 178 pytest, 59 Playwright. **Not performed:** how a real model uses
  documents; pasting a copied file in a real browser (Playwright can't reach the
  clipboard).

### 19. API cost and context indicators
- Your decisions: one total per chat, a grand total in the sidebar, the context readout
  is the long-chat budget, both chat readouts in the header, US dollars, everything
  counts. Six confirmed recommendations: replies, titles, summaries, search embeddings
  and notes updates count, the evaluation and model check don't; deleted chats stay in
  the total; prices in `settings.toml` (GPT-6 Luna $0.10 / cached $0.01 / output $0.50;
  `text-embedding-3-large` $0.13, from knowledge, worth a glance), stored per call; a
  stopped reply is estimated; older chats show only new spending; format `$0.012`,
  `<$0.001`, `$1.24`.
- `api_usage` ledger, no foreign key to `chats`, so deletion keeps spending.
  `stream_usage=True` for replies. A small `Embeddings` class through the `openai`
  package reads token counts: same model, text and vectors, so no rebuild; batches of
  100, because OpenAI also caps tokens per request. Embedding usage goes to a
  context-variable "usage log" set by the caller, avoiding changes to the store.
- `GET /api/chats/{id}/usage` and `GET /api/usage`. The context estimate shares
  `chats/history.py`'s measure, so it can't disagree with what's sent.
- A failed reply is estimated only if it had written text. A title cancelled by Stop
  isn't counted. Readouts wait while a reply streams (a walkthrough found a very fast
  reply showing only the title's cost).
- `playwright.config.ts` reads `E2E_PORT` (default 8765), as another program held 8765.
- Verified: 202 pytest, 69 Playwright; all dollar figures seen were fake.

## Phases 20–25: tools and richer answers

**Order:** the date first (tiny, needed by search); web search moves the agent to the
Responses API that Python also needs; the calculator adds the Working panel; display
phases precede Python so simple charts are free; Python last (paid, most work).

**Your decisions (2026-10-29):** OpenAI's own web search (Tavily as the fallback); a
blue "From the web" block and a separate sources list; the agent decides, and always
searches when asked, with **no button** (first chosen, then dropped); searches count
in costs; a free local calculator always on, Code Interpreter only by a per-message
button; Python gets original Excel files; all four display improvements; the date.

**Confirmed recommendations:** Python gets `.xlsx`/`.xls` from this question and earlier
in the chat, up to 5 most recent; web location `country = "GB"`, `Europe/London`, no
city; `--color-web` `#60a5fa` reserved; flat fees `web_search_call = 0.01` and
`python_session = 0.03`; `store=False` (standard retention still applies); three new
behaviour cases.

**Settings:** `[web_search]` `country`, `timezone`; `[prices]` `web_search_call`,
`python_session`; `max_generated_files_per_reply` 10; `max_generated_file_mb` 25.
**Packages:** `sympy`, `rehype-highlight`, `mermaid`, `recharts`.

### 20. Today's date
`{today}` in `agent/instructions.md`, worked out per reply so it stays right overnight;
the clock is injected for tests. Titles and summaries don't get it. 206 pytest, 69
Playwright.

### 21. Web search
- `ChatOpenAI(use_responses_api=True, output_version="responses/v1")`, `store=False`,
  hosted `{"type": "web_search"}`, default context size.
- Instructions: search what may have changed; always when asked; not for notes topics
  or stable knowledge unless asked; web pages are material, never instructions; don't
  copy notes or documents into queries.
- `:::web` blocks; citations are Markdown links drawn as site pills, as OpenAI requires
  visible, clickable citations; every reply link opens in a new tab with
  `rel="noopener noreferrer"`. `messages.web_sources` JSON. Status event gains a kind.
  `web_search` usage rows; the older `api_usage` table is rebuilt to widen its check.
- Behaviour checks gain `web_searches`.
- **Real check** (`--web`, about 4 cents, all six passed): one `web_search_call` block
  (`id`, `status`, `action.query`), then text with `url_citation` annotations (`url`,
  `title`, `start_index`, `end_index`); the text already holds Markdown links ending
  `?utm_source=openai`; page reads count in the reply's tokens (19 input tokens without
  a search, 8,455 with). Raw events recorded in `backend/tests/fixtures/responses_events.json`.
- 231 pytest, 78 Playwright. Limits: citations arrive after the text, so a stopped
  reply has paid but lists none; the real model wasn't seen following the instructions
  (the evaluation would show it). `quotes.spec.ts` "oversized excerpts…" timed out once,
  unexplained.

### 22. Calculator
`calculate` and `solve_equation`, local and free. SymPy does the maths, but expressions
are read with Python's `ast` allowing only numbers, operators and listed functions:
never `eval`, and not SymPy's parser (which uses it), because the model may have read
web pages. Huge exponents and long expressions are refused. Conventions: `npv`'s cf0 is
undiscounted, annuities pay in arrears, statistics are sample. A failure goes back to
the model as the tool's answer. `messages.tool_runs` JSON. Not included: units,
currency conversion, matrices. 303 pytest, 85 Playwright.

### 23. Code blocks and callouts
`rehype-highlight` over Shiki (heavier, needs WebAssembly). `src/markdown/replyBlocks.ts`
replaced `beyondBlocks.ts`: one level of nesting, so a formula inside "Beyond your
notes" stays labelled; only markers on their own line count. Callouts are `:::formula`,
`:::tip`, `:::mistake` and `:::example`, closed by `:::`. Copy copies the reply as
written. A selection spanning a Copy button is refused. Not included: line numbers,
running code. 304 pytest, 109 Playwright.

### 24. Diagrams and charts
Mermaid with `securityLevel: "strict"`, loaded on demand. ` ```chart ` holds small JSON
(type, title, axes, format, rows, up to 500 rows and 6 series), checked by a type guard
and drawn with Recharts. Vega-Lite rejected as heavy and easy to get subtly wrong;
Chart.js fits React poorly. New files in `src/markdown/`: `chartSpec.ts`, `Chart.tsx`,
`Diagram.tsx`, `openFence.ts`. Not included: editing, export, zoom. 305 pytest, 130
Playwright. `Ctrl+Shift+O starts a new chat` flaked under full-suite load (later 36E).

### 25. Python (Code Interpreter)
`backend/askmynotes/interpreter/`: `sandbox.py`, `reply.py`, `files.py`, `api.py`.
- Only when the button is on, so ordinary replies never pay. The request's `usePython`
  is saved as `messages.python_requested`, which repeats it on Retry, Regenerate and Edit. One explicit 1 GB container per reply,
  deleted however the reply ends; memory doesn't carry over, the cost of paying only
  on use. A stop during creation still deletes and charges. If it can't be made, the
  reply fails without a charge.
- Files saved to `data/uploads/<chat id>/generated/`, in `message_files`, served only by
  `GET /api/files/{id}` as attachments with `nosniff`; `/api/uploads` refuses
  `generated`; SVG and HTML are never shown, so they can't run scripts. Later turns
  don't see the images. Output cut to 200 lines.
- **Real-check findings** (`--python`, about 10 cents, with two follow-up probes):
  - A run arrives as one finished block: `{type: code_interpreter_call, id, code,
    container_id, status, outputs}`, read by `PythonReply.read` as `FoundWeb` reads
    searches.
  - Output needs `include=["code_interpreter_call.outputs"]`; otherwise `outputs` is
    `None`. Added only for Python replies.
  - Presented files are `container_file_citation` annotations (`file_id`, `filename`,
    `container_id`). The listing may give no size, so limits apply to what's downloaded.
  - `[name](sandbox:/mnt/data/name)` links are removed; instructions forbid them.
  - Uploads get a code before their name (`/mnt/data/<code>-returns.xlsx`), so the model
    is told to list the folder.
  - A delete may need repeating; the app checks and retries up to 3 times. Containers
    expire after 20 minutes idle, so a failed delete can't cost for long.
  - The model explored the sandbox first (10 runs for a tiny question).
- 337 pytest, 145 Playwright. The real model and sandbox weren't run through the app end
  to end: your first use is the first.

## Phase 26: web search fixes

Three problems you found (missing sources, search plus calculation, no visible
searching) shared one cause: LangChain passes on very little about a search.

**Your decisions:** the globe stays for web and the magnifying glass for notes; status
visible for the whole search; panel collapsed by default; uncited pages listed as
"Searched, not cited"; queries shown; heading "Found online (3 cited, 5 searched)",
where the second number is searched pages *not* cited.

**Real check** (`--web-detail`, two runs, about 15 cents; the first hit a bug in my
check code):
- Events: `response.output_item.added` (started, `action: null`),
  `…web_search_call.in_progress`, `…searching`, `…completed`, `response.output_item.done`.
  The start came 1.5 and 2.3 seconds before the finish.
- With `include=["web_search_call.action.sources"]`, the finished search has
  `action.queries`, `action.query` and `action.sources` (18 and 22 pages), each
  `{"type": "url", "url": ...}`: no title, no `api` sources, some duplicated with a
  final slash. So uncited pages show a shortened address (70 characters) and site.
- Search then calculate works when sent back with pages and reasoning. Of three questions
  needing both, all searched first; one had one citation and no block, one had **no
  citation, link or block**, and one had a `:::web` link but no `url_citation`.
- Same page: addresses differing only by a final slash, `www.` or tracking parameters.

**Built:**
- `watch_web_searches` in `web/search.py` wraps the OpenAI client and announces the
  start through LangGraph's `get_stream_writer`; `Agent.stream_reply` streams
  `["messages", "custom"]`. No private patching, no rewrite of the agent, and a test
  fails if a LangChain upgrade bypasses it. The finished block still counts the cost.
- `FoundWeb` keeps queries, every page read, and cited pages from `url_citation` and
  links in `:::web` boxes (code ignored). `WebSource` gains `cited`;
  `messages.web_searches` JSON. The include list is built together with Python's.
  `chat/FoundOnline.tsx` replaced `WebSources.tsx`. Old answers show only a cited count.
- Instructions: search first, then calculate; never take a changing figure from memory;
  every web answer has a `:::web` block linking each page. No other code cause existed.
- 354 pytest, 152 Playwright. One unexplained `test_python.py` flake. After Stop the
  status lingers about 0.8 seconds, as every status did before. The wrapper was tested
  on recorded events; your first real web answer is its first live stream.

## Phase 27: narrow windows

**Cause:** `min-width: var(--app-min-width)` (1024px) laid narrower windows out at 1024px;
zoom made it worse, and checks only ran at 1280px and up.

**Approved 2026-10-30:** no minimum width at all (any minimum brings this back), 600px the
narrowest designed and checked; below 900px the sidebar floats over the conversation.

- `--text-greeting: clamp(28px, 4vw + 8px, 40px)`, unchanged at 800px up. Long titles
  ellipsise and header controls don't shrink.
- `src/useNarrowWindow.ts` holds 900px once. `wideSidebarOpen` and `floatingSidebarOpen`
  are separate, so wide-window choices survive. Floating layer `z-index: 35`; chat menu
  and dialogs `z-index: 40`. No `data-narrow`.
- **No hover with the full title:** a `title` attribute broke 7 tests, as `getByTitle("Stop")`
  matches any title containing "stop". The full title is in the sidebar.
- The centring test was tightened after it passed on the old code; it then failed there
  (212px off centre) and passes on the new.
- 354 pytest, 162 Playwright. Wide layout measured identical before and after, at 1280px
  and 1600px with the sidebar open and collapsed. Two older faults left: Rename by mouse
  doesn't focus the box; the edit box overflowed 8px at 1600px. You confirmed the look on
  Windows on 2026-10-30.

## Phase 28: unsupported citation markers

**Why:** literal tokens in saved answers (`Screenshots2000/image.png`, the CAPM Formula
chat). Repetition from history is plausible; the first occurrence's cause is not
established, and a URL can't be recovered from a marker.

- `chats/citation_markers.py` matches only the reserved syntax: U+E200, `cite`, U+E202,
  payload, U+E201, including repeats, multiple references, partial opening prefixes and
  unclosed tokens. Ordinary text and links are untouched; whitespace isn't collapsed.
- Applied in `Conversation._save_reply` (before source and link extraction) and
  `repository._message_from_row` (read-time, so older answers are fixed without rewriting
  rows, migrating or reindexing). Search snippets may still show original text.
- `ModelHistory` cleans summaries on use and new ones before saving. User text, attachments
  and quote snapshots are preserved. One short instruction forbids the tokens.
- `frontend/src/chat/citationMarkers.ts` recomputes from accumulated text, because chunks
  can split a marker. `fixtures/citation_markers.json` is shared with the browser tests.
- 371 pytest (one new test corrected: it expected a trailing space the existing pipeline
  trims), 166 Playwright. Headless with fake models only. A review script made a `%20`
  sibling folder; with approval its PNGs were moved in and it was removed.

---

## Phases 29–35: the redesign (built)

**Status: proposed on 2026-11-09. You confirmed five decisions the same day and
asked for the plan to be updated, not started. You then said "Start phase 29.
Just phase 29". Phase 29 is built and Windows-verified (see its verification
record). On 2026-11-10 you said "start the next phase"; phase 30 is built and
Windows-verified too. The same day you said "then start phase 31"; phase 31 is
built and Windows-verified. Later that day you said "Do phases 32 and 33 then
stop"; phases 32 and 33 are built and Windows-verified. On 2026-11-11 you said
"Complete phase 34 and phase 35"; both are built and Windows-verified.** Scope is in `SPEC.md` section 8P, the look
in `DESIGN.md` ("Redesign") and the libraries in `TECH_STACK.md`.

**What it builds:** a new look for the whole app, taken from the first preview
you chose on 2026-11-09 ("design 1"). Every feature in `SPEC.md` keeps working
exactly as it does now. The preview is `data/ui-preview/index.html`; phase 29
commits a copy as `docs/redesign-preview.html`, so the reference travels with
the code.

**The idea in one paragraph.** The app sits on a slow field of coloured light.
The sidebar, the chat header and the message box are panes of dark glass
floating over it. When a reply is being written the app "charges up": the light
brightens and a band of it runs round the edge of the message box. Your notes'
sources are drawn as the slides they came from. The accent colour behaves like
a highlighter. The greeting is set large, like a poster.

**What does not change**
- **Behaviour.** Every feature, shortcut, message, label and accessible name
  stays as it is, except where this plan says otherwise.
- **The backend.** No Python, settings, database or agent-instruction changes,
  so no evaluation is needed. No paid calls at any point.
- **The reserved colours.** Red still means "Beyond your notes", blue "From the
  web", amber errors, violet "Key formula" and aqua "Exam tip", in every theme.
- **Dark only.** All three colour themes are dark.
- **Your uncommitted change** to `agent/instructions.md` is left alone.

### Decisions

**You confirmed five on 2026-11-09** (numbers 1, 3, 6, 7 and 8 below). **Four
were my recommendations, not answered by you** (2, 4, 5 and 9). I build those as
recommended unless you say otherwise before the phase that needs them: 9 was
built in phase 29, 4 in phase 33, and 2 and 5 in phase 34.

1. **Three colour themes, Volt by default. Confirmed.** Volt is lime on deep
   plum, the one the preview opens in. Aurora (violet and aqua, close to today's
   colours) and Ice (monochrome) come too, chosen from a small "Appearance" menu.
2. **An effects setting: Full or Calm (recommended, not yet answered; needed by
   phase 34).** Calm stops the moving
   light and the animated edge and removes the glass blur. It is for long study
   sessions, and for a laptop on battery. Your computer's "reduce motion" setting
   always wins and stops the motion by itself.
3. **Three new font packages, replacing the three current ones. Approved.** Bricolage
   Grotesque (headings and the greeting), Geist (everything else) and Geist Mono
   (code). They ship with the app, as fonts do now. Space Grotesk, Inter and
   JetBrains Mono are removed.
4. **Sources become slide cards, still collapsed by default (recommended, not
   yet answered; needed by phase 33).**
   "Sources (3)" opens into a row of small slide-shaped cards, each with the
   file, the module and the slide or page number. The same information as now.
5. **The app remembers two things in the browser (recommended, not yet
   answered; needed by phase 34):** your
   appearance choices, and whether the sidebar was open in a wide window. Each
   browser on each computer keeps its own. Phase 27 left the sidebar's memory
   out; it costs little here because the storage is being added anyway.
6. **Example prompts are cards without module tags. Confirmed** ("keep how it
   is": I've taken that to mean the prompts and `settings.toml` stay as they
   are, so no tags). The preview showed "IPA", "Web" and "Everyday" tags on
   them. Your settings file holds only each prompt's text, so real tags would
   need a settings change on both computers. If you meant "keep the tags as the
   preview shows them", say so and I'll add an optional tag to each prompt in
   `settings.toml` to phase 31.
7. **The browser tab and the desktop icon get the new colours. Confirmed.**
   A small icon for the browser tab is added (there is none today), and
   `assets/askmynotes.ico` is redrawn in Volt colours. The shortcut file on your
   Desktop is not touched. Windows may show the old icon until it refreshes its
   icon cache.
8. **A small number of existing tests change. Confirmed.** They are listed
   under "Tests that change" below, each because this plan deliberately changes
   what it measures.
9. **The preview is committed as `docs/redesign-preview.html` (recommended, not
   yet answered; needed by phase 29),** trimmed to
   design 1. It holds made-up content only. The other two previews are deleted.

### What is added beyond the preview

Each is small, and each can be dropped without affecting the rest.

| Addition | Why | Phase |
|---|---|---|
| Colour themes and the Appearance menu | The preview's switch becomes a real setting | 34D |
| Calm effects | Comfort and battery life | 34D |
| Sidebar open or closed is remembered | No need to collapse it on every visit | 34E |
| A blinking caret at the end of a streaming reply | Shows where text is arriving | 34C |
| Diagrams and charts follow the theme | Today their colours are fixed in the code | 33C |
| The "message is no longer available" notice is styled | It is unstyled text today | 32C |
| The edit box fits its bubble at every width | Fixes the 8px overflow found in phase 27 | 32A |
| A browser tab icon | The tab currently shows a blank page icon | 35A |
| Text contrast is tested for every theme | Glass over moving colour is easy to get wrong | 29B |

**Not included:** a light theme, phone layouts, touch gestures, sound, new
animations libraries, any change to what the app says or does, per-chat themes,
and syncing your appearance choices between the two computers.

### The design tokens

Phase 29 defines these once, in `design/tokens.css`. Values are from the
preview; the contrast test in 29B may adjust the muted and faint text colours
(I estimate the preview's faint text at about 3.7:1, below the 4.5:1 the test
requires).

| Token | Volt | Aurora | Ice | Used for |
|---|---|---|---|---|
| Base | `#0c0814` | `#07090f` | `#08090b` | page background |
| Panel | `rgba(24,16,38,.66)` | `rgba(15,17,28,.68)` | `rgba(18,20,25,.70)` | glass panes |
| Accent | `#ccff33` | `#a78bfa` | `#f2f6ff` | send button, highlights, the mark |
| Accent 2 | `#3dffc0` | `#22d3ee` | `#a9bce0` | the other end of the accent gradient |
| On accent | `#121900` | `#0a0714` | `#0a0c10` | text and icons on the accent |
| Glow 1, 2, 3 | `#a6f000` `#6d3bff` `#00b89c` | `#7c3aed` `#0e9bbd` `#4338ca` | `#53648a` `#2b3554` `#8198c4` | the backdrop's light |

Shared by all themes:

| Token | Value | Used for |
|---|---|---|
| Text, muted, faint | `#f4f0fb`, `#b5aec6`, `#958ea8` (as built in phase 29) | text |
| Hairline, strong hairline | white at 9% and 16% | borders |
| Beyond your notes | `#fb7185` | reserved, unchanged |
| From the web | `#60a5fa` | reserved, unchanged |
| Error | `#f59e0b` | reserved, unchanged |
| Key formula, Exam tip | `#a78bfa`, `#22d3ee` | reserved, unchanged |
| Radii | 24px panes, 26px message box, 16px cards, 11px controls | corners |
| Sizes | 12px gutter, 284px sidebar, 60px rail, 760px column, 46px header | layout |
| Fonts | Bricolage Grotesque, Geist, Geist Mono | display, body, code |
| Greeting size | `clamp(34px, 6.2vw, 84px)` | new chat screen |

**Why semantic names.** Today the accent is called `--color-violet`, which
would be untrue in Volt. Phase 29 adds `--color-accent`, `--color-accent-2` and
`--color-on-accent`, and moves every "accent" use onto them. `--color-violet`
and `--color-aqua` stay, but only for their reserved meanings.

### Tests that change, and why

`docs/PROCESS.md` forbids weakening a test. These change because the plan
changes the thing they measure; nothing else in the existing suite may change.

| Test | Today | After | Why |
|---|---|---|---|
| `narrow-window.spec.ts`: greeting size | 40px at 1280 and 1600 | 84px at 1600, about 79px at 1280, at least 34px at 600 | The greeting is deliberately larger |
| Any test that finds the Sources list by its internal structure | a plain list | the same text, in cards | Only if one exists; the visible text is unchanged |
| `navigation.spec.ts`: layout follows resized content (added in phase 34, approved by you 2026-11-11) | each width loads with the sidebar open | each width clears the saved appearance first, so it loads like a first visit; every check unchanged | The browser now remembers a closed sidebar (34E), and the test closes it at each width |

Everything else must pass as written. Two design choices exist to keep it so:
- **The main area still reaches the window's right edge.** The 12px gutter
  belongs to the sidebar, not the whole app, so "centred beside the sidebar"
  is measured exactly as in phase 27.
- **No new `title` attributes that contain another control's name.** Playwright's
  `getByTitle("Stop")` matches any title containing "stop" (found in phase 27).
  New controls use `aria-label`.

### Overview

| Phase | What you can see at the end | Depends on |
|---|---|---|
| 29: Foundations | The whole app in the new colours and fonts, on the moving backdrop; shapes unchanged | Nothing |
| 30: The shell | Floating glass sidebar and rail, the header pill, menus and dialogs | 29 |
| 31: New chat screen and message box | The poster greeting, prompt cards and the glass message box | 29, 30 |
| 32: The conversation | Your bubbles, answers, callouts, code, status lines, errors and actions | 29–31 |
| 33: Panels and pictures | Sources as slides, Found online, Working, files, diagrams and charts | 32 |
| 34: Motion and appearance | The charge-up, the moving message box, the Appearance menu, Calm, memory | 29–33 |
| 35: Finish | Icons, clean-up, the full review in every theme and width, final docs | 29–34 |

**Why this order.**
- **Foundations first,** because every component reads its colours and fonts
  from the tokens. After phase 29 the whole app is already recoloured, so it is
  never half one palette and half another.
- **Then outside in:** the shell, then the two screens, then what sits under an
  answer. Each phase restyles one area you can review in one sitting, and the
  app stays fully usable between phases.
- **Motion after the shapes.** The charge-up and the moving message box animate
  parts built in 30 to 33, and are the riskiest for test stability, so they come
  once everything they touch is settled.
- **Themes are defined in 29 but chosen in 34.** Defining all three early means
  every later phase is checked in all three as it is built, instead of
  discovering problems at the end.

**The branch.** Work continues on `new-ui`. Each phase is committed when its
gate passes, as `docs/PROCESS.md` describes. Nothing is pushed with force and
history is not rewritten.

### Rules for every redesign phase

**Verification** (the three levels in `docs/PROCESS.md`, at phase end only):
1. **Automated:** the whole-app gate from `STATUS.md`, plus the phase's new
   tests. Fake models and made-up content only.
2. **Screenshots, viewed:** the phase's states in Volt at 800px, 1280px and
   1600px, and one representative screenshot each in Aurora and Ice at 1280px.
   Kept under ignored `data/phase<N>-check/`.
3. **Walkthrough:** the phase's journeys in headless Chromium, including
   keyboard focus, with the results recorded.

**Documents, updated in the same phase, before its commit:**
- `PLAN.md`: tick the checklist; add the verification record and "What was
  decided while building it", including any difference from this plan.
- `STATUS.md`: the phase's row, and a short "what changed" paragraph.
- `DESIGN.md`: move that area's description from "proposed" to "built", and
  correct it to what was actually built.
- `SPEC.md` section 8P and `AGENTS.md`: the status line.
- `TECH_STACK.md`: only when a package or browser feature lands (29, 34).
- If building shows that a decision in the docs must change, stop and ask
  first, as `docs/PROCESS.md` requires.

**Stop and ask** if an existing test fails for a reason not listed under
"Tests that change", after a few genuine attempts to fix the code.

---

### Phase 29 / Task 16: Foundations

**Status: built on 2026-11-09 and 2026-11-10; Windows-verified. MacBook check
open.** See the verification record at the end of this phase.

**What it builds:** the tokens for three themes, the new fonts, the moving
backdrop and the committed preview. The app's shapes and layout don't change
yet; its colours and type do, everywhere at once.

**Why first:** see "Why this order".

#### 29A. The reference
- Copy the preview to `docs/redesign-preview.html`, with the links to designs 2
  and 3 removed. Delete `data/ui-preview/b.*` and `c.*` (ignored scratch files).
- It needs the internet for its fonts and icons. It is a picture of the target,
  not code to copy: the app is built from its own components.

**Checkpoints**
- [x] `docs/redesign-preview.html` opens from the file, shows design 1 in all
      three themes, and contains no link to `b.html` or `c.html` (grep).
- [x] It contains no lecture content: its text is the made-up CAPM conversation
      only (read through before committing).

#### 29B. Tokens and themes
- Rewrite `design/tokens.css` with the tables above. Volt is the default on
  `:root`; Aurora and Ice override it under `[data-theme="aurora"]` and
  `[data-theme="ice"]` on the `<html>` element.
- Add the semantic accent tokens and move every accent use in the CSS Modules
  onto them. This is a careful find-and-replace, file by file, not a rewrite.
- Move the colours written directly in code into tokens: the chart colours in
  `markdown/Chart.tsx` and the highlight in `chat/Conversation.tsx`. (Charts
  only start following the theme in 33C; here they just stop holding colours.)
- A small contrast checker in TypeScript, run as a plain test like
  `reply-blocks.spec.ts`. It works out each text colour against the panel laid
  over the base, and over the base lit by the strongest glow at its charged
  strength, which is the worst case.

**Why a contrast test:** on solid surfaces you can judge contrast once by eye.
On glass over moving colour, it changes with what is behind it.

**Checkpoints**
- [x] Test: for each theme, setting `data-theme` gives the base, panel, accent,
      accent 2 and on-accent values in the table (read with
      `getComputedStyle`).
- [x] Test: the red, blue, amber, violet and aqua reserved colours are
      identical in all three themes, and equal to today's values.
- [x] Test (contrast, each theme, worst case): text at least 7:1; muted text,
      on-accent on accent, and each reserved colour's label on its tint at
      least 4.5:1; faint text at least 4.5:1.
- [x] `grep` finds no colour literal (`#rgb`, `rgb(`, `rgba(`) in any `.ts` or
      `.tsx` file under `frontend/src`, nor in any CSS Module; only
      `tokens.css` holds colours.
- [x] `grep` shows `--color-violet` and `--color-aqua` used only by the callout,
      context-ring and message-highlight styles; the list of files is recorded
      here.
- [x] `usage.spec.ts`'s amber ring test passes unchanged.

#### 29C. Fonts
- Install `@fontsource-variable/bricolage-grotesque` (the file that includes
  its width axis), `@fontsource-variable/geist` and
  `@fontsource-variable/geist-mono`. Remove the three current font packages.
  Update `main.tsx` and the font tokens.
- Keep equal-width digits, so figures still line up in tables.

**Checkpoints**
- [x] `package.json` lists the three new packages and none of the three old
      ones; `npm run build` passes.
- [x] Playwright: after loading, `document.fonts.check` is true for all three
      families, and a heading's computed `font-family` starts with Bricolage
      Grotesque, body text with Geist and code with Geist Mono.
- [x] Playwright: loading the new chat screen and a conversation makes no
      network request to any host other than the app's own.
- [x] Playwright: a table cell's computed `font-variant-numeric` includes
      `tabular-nums`.

#### 29D. The backdrop and the glass
- A `Backdrop` component in `design/`: three large, blurred, slowly drifting
  shapes in the glow colours, with a fine grain over them. It is fixed behind
  everything, hidden from screen readers and ignores the pointer.
- Only `transform` is animated, so the browser can move the shapes without
  redrawing them.
- A shared glass style (panel colour, blur, hairline, soft shadow) for later
  phases to use. The scrolling message column never gets a blur of its own,
  because blurring behind scrolling text is slow.
- The mark takes its gradient from the accent tokens.

**Checkpoints**
- [x] Playwright: the backdrop has `aria-hidden="true"`, `pointer-events: none`
      and sits behind the app (`elementFromPoint` at the centre of the window
      never returns it).
- [x] Playwright: every running animation on the backdrop animates `transform`
      only (read from `getAnimations()`).
- [x] Playwright, with reduced motion emulated: the backdrop has no running
      animation.
- [x] Playwright: in each theme the mark's two gradient stops resolve to that
      theme's accent and accent 2.
- [x] The existing no-sideways-scroll tests pass at 600 to 1600px.

#### Phase 29 checklist
- [x] Every 29A to 29D checkpoint above.
- [x] The whole-app quality gate passes, with no test changed.
- [x] Screenshots viewed, per "Rules for every redesign phase": the new chat
      screen, a conversation with a table, maths, code, both labelled blocks
      and an error, the search dialog and a menu.
- [x] Walkthrough: send a message, open a chat, search, collapse the sidebar,
      with each theme set by hand through `data-theme`.
- [x] Documents updated as listed under "Rules for every redesign phase",
      including the new font packages in `TECH_STACK.md`.
- [ ] **MacBook (open until you run it):** `(cd frontend && npm install)`, then
      the gate passes.

**Rough size:** medium. Mostly careful token work across 23 style files.

#### Verification record (Windows, 2026-11-09 and 2026-11-10; fake models, no paid calls)

**What was built, and where it's tested.**
- **29A.** `docs/redesign-preview.html`: design 1 with its three themes, the
  links to the other designs removed (`grep` finds none). Its text is the
  made-up CAPM conversation I wrote for the mock-up. The other two previews
  and their screenshots are deleted from ignored `data/ui-preview/`.
- **29B.** `design/tokens.css` holds the three themes. Accent uses in 19 files
  moved to `--color-accent`, `--color-accent-2`, `--color-accent-tint`,
  `--color-accent-2-tint` and `--color-on-accent`. `Chart.tsx` and
  `Conversation.tsx` hold no colours any more. Tests:
  `e2e/contrast.spec.ts` (13, no browser; the colour maths is in
  `e2e/contrast.ts`) and `e2e/design-foundations.spec.ts` (the theme and
  reserved-colour tests).
- **29C.** `package.json` has the three new font packages and none of the old.
  `main.tsx` imports them. Test: "the three fonts ship with the app and are
  used" (families, the code font, equal-width digits, and no request to any
  other host).
- **29D.** `design/Backdrop.tsx` and its styles, rendered first in `App.tsx`.
  `Mark.tsx` uses the accent tokens. Tests: the three backdrop tests and "the
  mark takes the … accent" for each theme.

**The grep checkpoints.**
- No colour literal in any `.ts`, `.tsx` or CSS Module under `frontend/src`:
  `grep -rnE "#[0-9a-fA-F]{3,8}\b|rgba?\(" frontend/src`, leaving out
  `design/tokens.css`, prints nothing.
- `--color-violet` and `--color-aqua` are used only in
  `markdown/Markdown.module.css` (the Key formula and Exam tip callouts) and
  `usage/ChatUsage.module.css` (the context ring). The flash on a message you
  jumped to has its own token, `--color-highlight`, with the same aqua value.

**Quality gate.**
- Frontend: lint and Prettier, TypeScript and the build passed. Playwright: 192
  passed (the 166 existing tests, none changed, and 26 new), on port 8792.
- Backend: Ruff lint and format passed. The first full `pytest` run gave 370
  passed and 1 failed:
  `test_python.py::test_a_sandbox_that_cant_be_made_fails_the_reply_without_a_charge`.
  It passed alone, and the second full run passed all 371. This is the same
  unexplained flake recorded in phase 26. No backend file changed in this
  phase.
- The existing build-size and Chroma warnings remain.

**Screenshots** (in `data/phase29-check/screens/`, 48 captured by
`data/phase29-check/shots.cjs`). **Viewed, 22 of them:**
- Volt at 1280px: the new chat screen; the conversation at its top, second,
  third and fourth screens and its end; search; a chat's menu; the rail;
  keyboard focus.
- Volt at 800px: the new chat screen and the third screen of the conversation.
- Volt at 1600px: the new chat screen and the end of the conversation.
- Aurora at 1280px: the top and third screens of the conversation, search, and
  a message just sent.
- Ice at 1280px: the new chat screen, the second screen of the conversation, a
  chat's menu, and keyboard focus.

Between them they show a table, a fraction, both code blocks, all four
callouts and a nested one, "Beyond your notes", "From the web" with its pills,
Sources and Found online collapsed, three diagrams, the amber error, the
search dialog and the menu. Text, icons, the mark, the accent and the focus
ring rendered correctly in each theme, with no clipping, overlap or stray
symbols. Seven of the Volt 1280px screenshots were viewed before the fade fix
below and not again after it; the top of the conversation, the rail and the
focus screenshots were viewed after it. The other 26 were captured, not
viewed.

**Walkthrough** (headless Chromium, fake model on port 8795, throwaway data in
`data/phase29-check/app/`): built a six-message conversation; opened the new
chat screen and the conversation in each theme, set by hand through
`data-theme`; scrolled through it; opened search with Ctrl+K and typed;
opened a chat's menu; collapsed and reopened the sidebar; moved keyboard focus;
sent a new message in Aurora and watched it finish. No console or page errors.

**Found while checking, and fixed.** The fade above the message box was
painted in the base colour, which showed as a dark band across the backdrop.
It is now a mask on the scrolling area (`Conversation.module.css`).

**Found while checking, and left.**
- Flowchart labels and timeline boxes in diagrams sit on black. The timeline's
  are in a phase 24 screenshot, so they predate this phase. Phase 33C redraws
  diagrams from the theme.
- The latest question's bubble is taller than its text, to leave room for
  Edit. Phase 32A restyles it.

**Not done.** The MacBook check. No paid calls and no evaluation.

#### What was decided while building it
- **The backdrop is dimmer than the preview.** The contrast test set the
  strengths. Volt rests at 0.16 and charges to 0.28 (the preview used 0.2 and
  0.36); Aurora 0.24 and 0.42; Ice 0.22 and 0.42. Volt is lowest because lime
  is the lightest colour of any theme's lights.
- **Muted and faint text are lighter than the preview:** `#b5aec6` and
  `#958ea8` (the preview had `#a9a1bb` and `#6f6782`).
- **What the contrast test measures,** more exactly than the plan said:
  - text and muted text straight on the backdrop at charged strength, because
    answers sit there;
  - text, muted and faint text on a pane over the backdrop at charged strength;
  - each reserved colour's label on its tint, on a pane at charged strength,
    and straight on the backdrop at rest.
- **Two things later phases must keep to,** which follow from that:
  - faint text only ever goes on a solid surface or a pane, never straight on
    the backdrop (it is used that way today);
  - from phase 32, "Beyond your notes", "From the web" and the callouts need a
    pane behind them, because their labels don't reach 4.5:1 straight on the
    backdrop at charged strength. Until phase 34 adds the charged state, the
    backdrop only ever shows at rest, where they pass.
- **Surfaces are still solid in this phase.** The sidebar, message box and
  cards keep their solid colours, retinted for each theme. They become glass in
  phases 30 to 33. `--color-panel` is defined now because the contrast test
  needs it.
- **No shared glass style yet.** The plan put one in 29D. Nothing would use it
  until phase 30, so it is added there instead of sitting unused.
- **Charts already follow the theme.** Their colours are now written as
  `var(--chart-1)` and so on, which the browser resolves, so they change with
  the theme without any more code. All three themes share today's six chart
  colours; phase 33C still chooses and tests a set for each theme, and makes
  diagrams follow the theme.
- **Violet keeps its two shades,** `#8b5cf6` and `#a78bfa`, as today. Both are
  reserved for "Key formula".
- **Code keywords and strings have their own tokens** (`--code-keyword`,
  `--code-string`), with the values they had, so code looks the same in every
  theme and doesn't borrow the reserved violet and aqua.
- **Selected text** uses the full accent with dark text, like a highlighter.
  **Keyboard focus** is a ring of the accent at 45%.
- **Links and small highlights that were aqua** use accent 2: mint in Volt,
  aqua in Aurora, pale blue-grey in Ice.
- **The theme-colour test paints each token on a throwaway element** and reads
  the result, because the built stylesheet rewrites `rgba(…)` as an
  eight-digit hex and rounds the opacity.
- **The backdrop has a `data-backdrop` attribute** so tests can find it; CSS
  Module class names are not stable.
- **Bricolage Grotesque is imported from `standard.css`,** the file with its
  width axis. Geist's italic file is imported too, so italics are real ones.
- **`--gradient-glow` is gone.** The new chat screen's own glow is replaced by
  the backdrop.

---

### Phase 30 / Task 17: The shell

**Status: built on 2026-11-10; Windows-verified. MacBook check open.** See the
verification record at the end of this phase.

**What it builds:** the parts that frame every screen: the sidebar, its rail,
the floating sidebar in a narrow window, the chat header, and the menus and
dialogs.

**Why now:** the two screens in phases 31 and 32 are laid out inside it.

#### 30A. Sidebar and rail
- The sidebar becomes a glass pane with rounded corners, 12px in from the
  window's left, top and bottom. The main area still reaches the right edge.
- Inside it, unchanged in content: the mark and name, New chat (now the one
  tinted button), Search chats, the groups, the chat rows with their menu,
  inline rename, the notes status with Refresh, and the API cost.
- The open chat is marked like a highlighted line: an accent wash fading to the
  right, with a glowing bar at its left.
- A soft light follows the pointer across the pane.
- The notes status keeps all its states: up to date, updating with progress,
  failed (amber), and the list of unreadable files.
- The rail is the same pane, 60px wide.
- In a narrow window the sidebar floats exactly as phase 27 built it.

**Checkpoints**
- [x] `history.spec.ts`, `notes.spec.ts`, `usage.spec.ts` and
      `narrow-window.spec.ts` pass unchanged (apart from the greeting size,
      which belongs to 31A).
- [x] Playwright, at 1280px: the sidebar's box is 12px from the window's left,
      top and bottom; `main`'s right edge equals the window's width.
- [x] Playwright, each theme: the open chat's row has a background and a left
      marker that an unselected row doesn't (computed styles differ).
- [x] Playwright: a 120-character chat title in the sidebar ends in "…" and its
      menu button appears on hover and on keyboard focus.
- [x] Playwright: the notes status shows progress while updating and its
      failure text in the error colour.
- [x] Playwright, 600 to 1600px: the API cost tooltip is wholly inside the
      window.

#### 30B. The chat header
- A centred glass pill: the title, the cost, the context ring and Questions.
  The conversation scrolls under it and fades out before reaching it.
- A long title still ends in "…"; the readouts and Questions never shrink.

**Checkpoints**
- [x] The existing title, cost, ring and Questions tests pass unchanged,
      including at 600px.
- [x] Playwright, 600 to 1600px: the pill is wholly inside `main`, and its
      centre is within 1px of the centre of the visible area.
- [x] Playwright: with the conversation scrolled to the top, the first
      message's top is below the pill's bottom.
- [x] Playwright: the scrolling area has a top fade (its computed `mask-image`
      is not `none`), so text passing under the pill can't be read through it.
- [x] Playwright: the Questions menu opens under the pill, inside the window,
      and Escape returns focus to its button.

#### 30C. Menus and dialogs
- The chat menu, the Questions menu, the search dialog and the delete dialog
  become glass panes with the new type. Search matches are marked with the
  accent, like a highlighter.
- The layers from phase 27 are kept: menus and dialogs open above the floating
  sidebar.

**Checkpoints**
- [x] The existing search, rename, pin, delete and keyboard tests pass
      unchanged.
- [x] Playwright, each theme: a search match's background is that theme's
      accent and its text the on-accent colour.
- [x] Playwright, at 600px: the search and delete dialogs are wholly inside the
      window, and the delete dialog opens above the floating sidebar.

#### Phase 30 checklist
- [x] Every 30A to 30C checkpoint above.
- [x] The whole-app quality gate passes.
- [x] Screenshots viewed: sidebar open, collapsed and floating; a chat's menu;
      rename in progress; notes updating and failed; the header with each
      tooltip; Questions; search with results and with none; the delete dialog.
- [x] Walkthrough: keyboard only through the sidebar, a chat's menu, search and
      delete; resize from 1600px to 600px and back.
- [x] Documents updated.
- [ ] **MacBook (open until you run it):** the gate passes; the ⌘ hints show.

**Rough size:** medium.

#### Verification record (Windows, 2026-11-10; fake models, no paid calls)

**What was built, and where it's tested.**
- **The shared glass style:** `design/glass.module.css`, a pane (the panel
  colour, a hairline edge, the blur and a shadow) and the light that follows
  the pointer. Other stylesheets take it with CSS Modules' `composes`.
  `design/spotlight.ts` tells the light where the pointer is.
- **30A.** `sidebar/Sidebar.module.css` and `Sidebar.tsx`: the sidebar and
  the rail as panes, New chat tinted, the open chat's wash and glowing bar.
  `notes/NotesStatus.module.css` and `usage/Readout.module.css` moved to the
  pane's hairlines and washes. `App.module.css`: the floating sidebar keeps
  its gutter, so it lands exactly over the rail.
- **30B.** `chat/Conversation.module.css`: the header pill, the fade at the top
  of the conversation, and where a message you jump to stops.
- **30C.** The chat menu, the Questions menu and `sidebar/Dialogs.module.css`
  as panes. `sidebar/SearchDialog.tsx` marks the matches.
- **Tests:** `e2e/shell.spec.ts` (14 new) covers every 30A to 30C checkpoint.
  `e2e/contrast.spec.ts` gained one test per theme (3 new), for text on a
  pane under the pointer's light.

**The grep checkpoint from phase 29 still holds:** no colour is written
outside `design/tokens.css`.

**Quality gate.**
- Frontend: lint and Prettier, TypeScript and the build passed. Playwright: 209
  passed (the 192 existing tests, none changed, and 17 new), on port 8792.
- Backend: Ruff lint and format passed; `pytest` passed all 371 on the first
  run. No backend file changed.
- The existing build-size and Chroma warnings remain.

**Screenshots** (in `data/phase30-check/screens/`, 94 captured by
`data/phase30-check/shots.cjs`). **Viewed, 25 of them:**
- Volt at 1280px: the conversation at its top and as opened; the sidebar with
  the pointer on a chat; the header's cost tooltip; the sidebar's cost
  tooltip; Questions; rename in progress; the delete dialog; search with
  results and with none; the rail; keyboard focus; notes updating and failed.
- Volt at 800px: the conversation at its top; the floating sidebar with the
  pointer on a chat; its chat menu; the delete dialog; notes failed with the
  unreadable-files list open.
- Volt at 1600px: the context tooltip; the new chat screen.
- Aurora at 1280px: a chat's menu; search with results.
- Ice at 1280px: Questions; search with results.

Text, icons, panes, the pill, the fades and the accent rendered correctly in
each, with no clipping, overlap or stray symbols. Three more (Volt at 1280px:
the conversation scrolled under the pill, a chat's menu and search results)
were viewed from an earlier build, before the pill's width, the fade and the
match highlight were adjusted. Of those, only search results was viewed again
afterwards; the other two are not counted. The other 69 were captured, not
viewed.

**Walkthrough** (headless Chromium, fake model on port 8795, throwaway data in
`data/phase30-check/app/`, by `data/phase30-check/walk.cjs`), with no pointer:
- **Passed:** Tab reaches Close sidebar, New chat, Search chats and a chat;
  Enter opens the chat; Tab reaches its "…" button; Enter opens the menu on
  Rename; Down moves to Pin; Escape closes it. Ctrl+K opens search with the
  cursor in it; typing marks the match; Enter opens the chat at the matching
  message; Escape closes search. From the menu, Down twice reaches Delete; the
  dialog opens on Cancel; Tab moves to Delete; Enter deletes the chat and
  returns to the new chat screen.
- **Passed:** resizing 1600, 1280, 1024, 900, 899, 800, 600, 800, 1024 and
  1600px. At each: no sideways scroll, the sidebar from 900px and the rail
  below, and the pill inside the window.
- **Failed, and not caused by this phase:** choosing Rename by keyboard does
  not put the cursor in the title box. See "Found, and left".
- One console error, a 404, when the open chat is deleted. Also below.

**Found while checking, and left** (fixes are now planned as phase 36)**.** None is caused by this phase: each was
checked against phase 29's build (`git stash`, rebuild, the same script) and
happens there too. None is a look, so none belongs to the redesign. They need
your decision.
- **A chat that ends in diagrams doesn't open at its end.** It opens a few
  hundred pixels short, showing "Jump to latest". Four tries of four on this
  build, three of four on phase 29's. The diagrams are drawn after the
  conversation has scrolled down, and make it longer.
- **Rename chosen by keyboard doesn't put the cursor in the title box.** The
  box appears, but the focus is on the page. Phase 27's test recorded the same
  for the mouse.
- **Escape on a chat's menu leaves the focus on the page,** not on the "…"
  button.
- **Deleting the chat you have open logs one 404** in the browser's console,
  from a last request for that chat's cost. Nothing shows on screen.

**Not done.** The MacBook check. No paid calls and no evaluation.

#### What was decided while building it
- **The light that follows the pointer is much fainter than the preview.** The
  preview used 13% of the accent. The contrast test allows 4% in Volt and Ice
  and 8% in Aurora, because the sidebar's faint text (the group labels and the
  shortcut hints) must stay at 4.5:1 with the brightest backdrop light behind
  the pane as well. At 4% it is barely visible. Making it stronger would mean
  lightening the faint text, or accepting less than 4.5:1 under the pointer.
- **The pill is never wider than the conversation's column (760px).** The
  preview let it grow to the window's width less 96px, which made a long title
  into a bar across the page. It sits 12px from the top (the preview had 4px),
  level with the sidebar.
- **The fade starts at the pill's bottom edge.** The conversation is fully
  see-through from the top of the window down to there, and fully visible
  24px below. A message you jump to stops below the pill, where the first
  message starts.
- **The shortcut hints beside New chat and Search chats always show,** as in
  the preview. They used to appear only on hover.
- **The chat title in the pill is in the main text colour,** not muted.
- **Tooltips stay solid.** Their text is small, so they keep a solid surface
  with a hairline edge instead of becoming glass.
- **Search matches are marked in the browser, with no backend change.** A word
  is marked wherever a word in the title or snippet starts with what you typed,
  which is how the search matches. One limit: the search ignores accents, so
  "cafe" finds "café", but that match is not marked.
- **The chosen search result has a white wash, not an accent tint,** so the
  accent marks stand out.
- **No gap between the sidebar and the main area.** The gutter is the
  sidebar's margin. Main starts at the sidebar's right edge and reaches the
  window's right edge, so centring is measured as in phase 27.
- **New tokens:** `--color-hairline`, `--color-hairline-strong`,
  `--color-wash`, `--color-wash-strong`, `--blur-pane`, `--shadow-pane`,
  `--spotlight-strength`, `--gutter`, `--radius-pane` and `--radius-control`.
  The sidebar is 284px wide (was 280px) and the header 46px (was 52px).
- **The "message is no longer available" notice sits under the pill,** centred
  and muted, so the pill doesn't cover it. Phase 32C still styles it properly.
- **Menus don't animate yet.** Easing open belongs to phase 34C.
- **"Jump to latest" and the message box are untouched;** they belong to
  phases 31 and 32.

---

### Phase 31 / Task 18: The new chat screen and the message box

**Status: built on 2026-11-10; Windows-verified. MacBook check open.** See the
verification record at the end of this phase.

**What it builds:** the screen the app opens on, and the message box used on
both screens.

#### 31A. The new chat screen
- The mark, glowing, beside the greeting in large display type on two lines
  ("Happy Monday," then "Matt"). The heading's text is still "Happy Monday,
  Matt", so it reads and tests as before.
- Once, as the screen loads, a band of accent light sweeps across the greeting.
- The example prompts are cards in two columns, one column below 700px. They
  lift slightly on hover and are disabled, visibly, while the notes update.

**Checkpoints**
- [x] `narrow-window.spec.ts`'s greeting test, changed as listed: 84px at
      1600px, at least 34px at 600px.
- [x] The phase 27 centring tests pass unchanged at 600, 800 and 1024px.
- [x] Playwright, at 600px: the mark, both lines of the greeting and every
      prompt are wholly inside the window.
- [x] Playwright: the heading's text is exactly the greeting from
      `dailyGreeting`, with no extra characters.
- [x] Playwright: three seconds after loading, the greeting has no running
      animation; with reduced motion it never has one.
- [x] Playwright: prompts carry `disabled` while the notes update, and clicking
      one sends it otherwise (existing behaviour).

#### 31B. The message box
- A glass box with 26px corners. Its edge is a hairline at rest and the accent
  gradient when the cursor is in it.
- Everything in it is kept and restyled: the growing text area, the paperclip,
  the Python toggle and its "Python on" chip, the send and stop button, image
  previews, document chips, the "Regarding" excerpt with its three buttons,
  "Reading files…", the amber messages, and the waiting state during a notes
  update.
- The Python toggle fills with the accent when on. `DESIGN.md` said violet; in
  Volt the accent is lime, and violet stays reserved for "Key formula".

**Checkpoints**
- [x] `chat.spec.ts`, `images.spec.ts`, `documents.spec.ts`, `python.spec.ts`,
      `quotes.spec.ts` and `notes.spec.ts` pass unchanged.
- [x] Playwright: the send button keeps its "Send" and "Stop" names and is at
      least 36px in each direction.
- [x] Playwright: typing 30 lines grows the box to its maximum height and no
      further; the text then scrolls inside it.
- [x] Playwright, at 600px: four images and five documents attached wrap onto
      new lines with no sideways scroll.
- [x] Playwright: the Python toggle has `aria-pressed`, and when on its
      background is the theme's accent.
- [x] Playwright: an attachment refusal and a send error show in the error
      colour.

#### 31C. Dropping files
- The cover shown while dragging files over the chat becomes a glass pane with
  an accent outline. Its text is unchanged.

**Checkpoints**
- [x] The existing drag-and-drop tests pass unchanged.
- [x] Playwright: the cover covers the main area only, not the sidebar.

#### Phase 31 checklist
- [x] Every 31A to 31C checkpoint above.
- [x] The whole-app quality gate passes.
- [x] Screenshots viewed: the new chat screen; the message box empty, focused,
      with long text, with images and documents, with an excerpt, with Python
      on, with each error, reading files and waiting for notes; the drop cover.
- [x] Walkthrough: attach by button and by drop, remove a chip by keyboard,
      toggle Python by keyboard, send by Enter, new line by Shift+Enter.
- [x] Documents updated.
- [ ] **MacBook (open until you run it):** the gate passes.

**Rough size:** medium.

#### Verification record (Windows, 2026-11-10; fake models, no paid calls)

**What was built, and where it's tested.**
- **31A.** `chat/NewChatScreen.tsx` and its styles: the glowing mark, the
  greeting on two lines with its one sweep of light, and the prompt cards.
  `chat/greeting.ts` now gives the greeting as its two lines. The greeting's
  size token changed in `design/tokens.css`.
- **31B.** `chat/MessageBox.module.css`: the glass box, its drawn edge, the
  Python button, the send button, previews, errors and the excerpt's buttons.
  `chat/DocumentChip.module.css` and `chat/QuotedPassage.module.css` moved to
  the pane's hairlines and washes. `MessageBox.tsx` did not change.
- **31C.** `chat/DropZone.module.css`: the cover as a pane with a dashed
  accent outline.
- **Tests:** `e2e/new-chat.spec.ts` (18 new) covers every 31A to 31C
  checkpoint. `e2e/contrast.spec.ts` gained one test per theme (3 new), for
  muted text on a hovered or chosen row on a pane.
- **One existing test changed, as this plan listed:** the greeting's size in
  `narrow-window.spec.ts` (84px at 1600px, 79.36px at 1280px, at least 34px at
  600px). Its other assertions are as they were.
- **Three assertions added to phase 30's `e2e/shell.spec.ts`,** for the fault
  described under "Found, and fixed".

**The grep checkpoint from phase 29 still holds:** no colour is written
outside `design/tokens.css`.

**Quality gate.**
- Frontend: lint and Prettier, TypeScript and the build passed.
- Playwright, on port 8792: three full runs. The first and third passed all
  230 (209 existing, one of them changed as listed, and 21 new). The second
  had one failure, `history.spec.ts` "Ctrl+Shift+O starts a new chat". See
  "Found, and left".
- Backend: Ruff lint and format passed; `pytest` passed all 371 on the first
  run. No backend file changed.
- The existing build-size and Chroma warnings remain.

**Screenshots** (in `data/phase31-check/screens/`, 72 captured: 70 by
`data/phase31-check/shots.cjs` and two one-offs). **Viewed, 19 of them:**
- Volt at 1280px: the new chat screen 0.9 seconds after loading; the sweep
  paused part-way, with the accent band on the greeting; the message box
  focused; with 30 lines of text; with four images and three documents; with
  Python on; reading files; a refused file; a failed send; waiting for notes;
  with Stop; with an excerpt, in a conversation; the drop cover.
- Volt at 600px: the new chat screen (one column of prompts).
- Volt at 800px: images and documents; the excerpt in a conversation.
- Volt at 1600px: the new chat screen with the box not focused.
- Aurora at 1280px: Python on. Ice at 1280px: images and documents.

Text, the mark, the greeting, the box's edge, chips, errors and the accent
rendered correctly in each, with no clipping, overlap or stray symbols. The
other 53 were captured, not viewed.

**Walkthrough** (headless Chromium, fake model on port 8795, throwaway data in
`data/phase31-check/app/`, by `data/phase31-check/walk.cjs`). All 13 steps
passed, with no console errors:
- the paperclip opens the file chooser and adds a chip;
- dragging a file over the chat shows the cover, and dropping it adds a chip;
- a chip's remove button takes keyboard focus, and Enter removes that chip;
- Shift+Enter starts a new line;
- Tab moves from the message field to the paperclip, Python, then Send;
- Space switches Python on and Enter switches it off;
- Enter in the message field sends, and the box is empty at the bottom of the
  conversation that opens.

The screenshot run logged five 422 responses, one for each time it attached
the made-up document that is too long, on purpose.

**Found, and fixed: a fault from phase 30.** The Questions menu and the search
and delete dialogs were meant to have the stronger edge (white at 16%) and had
the ordinary one (9%). Each set its edge colour over the shared glass style's,
which only works if its stylesheet comes later in the built app, and theirs
came earlier. A pane now names its edge through `--pane-edge`, which doesn't
depend on the order. `shell.spec.ts` now checks the edge of both menus and the
dialog.

**Found, and left: "Ctrl+Shift+O starts a new chat" fails now and then.** The
address changes to the new chat screen, but the conversation stays on screen.
Run alone and repeated, it failed 2 times in 25 on this phase's code and 5
times in 50 on phase 30's committed code, so it is older than this phase. The
test presses the shortcut the moment the reply appears, so it is likely a real
fault: starting a new chat just as a reply finishes can leave you in the old
one. The cause is not yet found. It is added to phase 36 as 36E, for you to
confirm.

**Interrupted once.** The review server was stopped when the PC ran critically
low on memory, before the screenshots. You told me to finish, and it was
started again; nothing was lost.

**Not done.** The MacBook check. No paid calls and no evaluation.

#### What was decided while building it
- **Prompt cards are dark glass, not the preview's faint white wash.** They sit
  straight on the backdrop, where a white wash under muted text gave about
  4:1 with the brightest light behind it. They use the panel colour without
  the blur.
- **The greeting is one sentence in the page, on two lines by styling.** The
  name is in a `span` set as a block, with no line break, so the heading still
  reads and tests as "Happy Tuesday, Matt". `dailyGreeting` became
  `greetingLines`, which returns the two lines.
- **The sweep ends as plain text.** The accent band rests off to one side, so
  with reduced motion, and after the sweep, the letters are the text colour.
  It takes 2.6 seconds including its short delay.
- **The box's edge is a separate layer,** not a border: a border can't be a
  gradient on a rounded box. Phase 34's travelling band will use the same
  layer.
- **The send button is 40px,** a little larger than the 36px controls beside
  it. Disabled, it is a faint wash.
- **The Python button is a pill with a hairline outline when off,** and 32px
  high. There is no separate "Python on" chip in the app (the plan mentioned
  one from the preview); the filled button is the sign.
- **Document chips and the excerpt changed everywhere they appear,** including
  in sent messages, because they share one style. Phase 32 restyles the
  messages around them.
- **The drop cover's outline is dashed,** as before, to keep saying "drop
  here". It is an outline, not a border, so it doesn't fight the glass style.
- **New tokens:** `--radius-card` (16px) and `--radius-box` (26px).
- **The "muted text on a wash over a pane" contrast test** was added because
  chips, hovered rows and the chosen search result all put muted text there.
  It passes in every theme.

---

### Phase 32 / Task 19: The conversation

**Status: built on 2026-11-10, on your instruction "Do phases 32 and 33 then
stop"; Windows-verified. MacBook check open.** See the verification record at
the end of this phase.

**What it builds:** everything between the header and the message box, except
the panels under an answer (phase 33).

#### 32A. Your messages
- A soft glass bubble on the right, with one tight corner. Images, document
  chips, the quoted excerpt and its "Original answer" link sit inside it.
- Edit appears on hover and on keyboard focus. The inline editor now fits
  inside its bubble at every width.

**Checkpoints**
- [x] The existing edit, image, document and quote tests pass unchanged.
- [x] Playwright, at 600, 1280 and 1600px: the editor's text area and its
      buttons are wholly inside the bubble (the 8px overflow from phase 27 is
      gone).

#### 32B. Answers
- Body text in Geist at 15px; headings in Bricolage Grotesque.
- Tables with hairlines; a wide table scrolls sideways inside itself.
- Maths, lists and links as now. Links still open in a new tab.
- Code blocks: a darker inset, the language at the top left and Copy at the top
  right, with highlighting colours from the tokens.
- The four callouts, "Beyond your notes" and "From the web" keep their reserved
  colours and labels. A callout can still sit inside either block.
- Citation pills stay blue.

**Checkpoints**
- [x] `code-and-callouts.spec.ts`, `web-search.spec.ts`,
      `reply-blocks.spec.ts` and `citation-markers.spec.ts` pass unchanged.
- [x] Playwright, each theme: the "Beyond your notes" label is the red token,
      "From the web" the blue, "Key formula" the violet and "Exam tip" the
      aqua.
- [x] Playwright, at 600px: a 12-column table scrolls inside its own box and
      the page has no sideways scroll.
- [x] Playwright: a link in an answer has `target="_blank"` and
      `rel="noopener noreferrer"` (existing behaviour).

#### 32C. States and actions
- "Searching your notes…", "Searching the web…", "Calculating…" and "Running
  Python…" keep their icons and text, with a light passing through the words.
- The typing dots, the "Stopped" marker, and the amber error with Retry.
- Copy and Regenerate appear on hover and on keyboard focus.
- "Jump to latest" is a glass pill above the message box.
- The "This message is no longer available in this chat" notice gets a proper
  style; today it is unstyled text.
- The flash on a message you jumped to uses a token.
- "Ask about this" is an accent pill, kept inside the window.

**Checkpoints**
- [x] `navigation.spec.ts`, `chat.spec.ts`, `quotes.spec.ts`,
      `calculator.spec.ts` and `long-chat.spec.ts` pass unchanged.
- [x] Playwright, at 600 and 1280px: "Jump to latest" doesn't overlap the
      message box (its bottom is at or above the box's top).
- [x] Playwright: tabbing to Copy makes the actions visible (opacity 1).
- [x] Playwright: the missing-message notice sits inside the message column,
      below the header pill, and is styled (it has a border or background).
- [x] Playwright, with reduced motion: a status line has no running animation.
- [x] Playwright, at 600px: "Ask about this" is wholly inside the window
      (existing test).

#### Phase 32 checklist
- [x] Every 32A to 32C checkpoint above.
- [x] The whole-app quality gate passes.
- [x] Screenshots viewed: a long answer with every kind of block; a nested
      callout; each status line; typing dots; stopped; error; the editor; a
      jumped-to message; the missing-message notice; "Ask about this". (Two
      status lines, "Running Python…" and "Searching your notes…", pass too
      quickly with the fake model to be caught; see the record.)
- [x] Walkthrough: stream a reply, Stop, Retry, Regenerate, Edit, Copy, scroll
      up and Jump to latest, select text and ask about it, by mouse and by
      keyboard.
- [x] Documents updated.
- [ ] **MacBook (open until you run it):** the gate passes.

**Rough size:** medium to large. The most style files of any phase.

#### Verification record (Windows, 2026-11-10; fake models, no paid calls)

**What was built, and where it's tested.**
- **32A.** `chat/Message.module.css`: your bubble (the panel colour under a
  soft white gradient, a hairline edge, 24px corners with one 8px corner);
  Edit just left of the bubble's bottom corner; the editor, which asks for
  560px but never more than its bubble has; Cancel and Save & resend, the
  second in the accent.
- **32B.** `markdown/Markdown.module.css`: headings in Bricolage Grotesque at
  88% width; tables with hairlines whose cells don't break words; inline code
  on a wash; "Beyond your notes" and "From the web" as a coloured left edge
  and a tint fading to the right; the four callouts as rounded outlines in
  their colour. `markdown/CodeBlock.module.css`: the darker inset.
- **32C.** `chat/Message.module.css`: status lines with a band of the accent
  passing through the words; Stopped and the error on the panel colour.
  `chat/Conversation.module.css`: Jump to latest as a glass pill; the missing
  message notice as a quiet pill under the header; rounded jump targets.
  `chat/SelectionAction.module.css`: Ask about this as an accent pill.
- **One new token:** `--color-inset` (black at 34%), for code and the edit
  box.
- **Tests:** `e2e/conversation.spec.ts` (16 new) covers every 32A to 32C
  checkpoint that isn't an existing test. No existing test changed.

**The grep checkpoint from phase 29 still holds:** no colour is written
outside `design/tokens.css`.

**Quality gate.**
- Frontend: lint and Prettier, TypeScript and the build passed.
- Playwright, on port 8792, four full runs of 246 tests (230 existing, none
  changed, and 16 new):
  - run 1: 245 passed. The failure was a new test of mine that assumed its
    message was the first in the shared test database; corrected.
  - run 2 (with the rounded jump targets): 245 passed. The failure was the
    new Ask about this test: any scroll hides the action, and at 600px the
    chat was still settling at its end when the test selected text. The test
    now selects again until the action stays; the app is unchanged.
  - run 3: 245 passed. The failure was the known "Ctrl+Shift+O starts a new
    chat" fault, planned as phase 36E.
  - run 4: all 246 passed.
- Backend: Ruff lint and format passed; `pytest` passed all 371. No backend
  file changed.
- The existing build-size and Chroma warnings remain.

**Screenshots** (in `data/phase32-check/screens/`, 61 captured by
`data/phase32-check/shots.cjs`, plus four from the walkthrough and one
one-off). The made-up chats are served by routes, so the cost readout's
requests for them got 404s; those are the console errors the script logged.
**Viewed, 16 of them:**
- Volt at 1280px: a long made-up answer with every kind of block, at its top,
  second and third screens and its end with the actions showing (a heading, a
  list, a link, a table, maths, inline code, a code block, all four callouts,
  a Key formula inside "Beyond your notes", "From the web" with its pills);
  "Searching the web…"; "Calculating…"; the typing dots; Stopped with the
  actions; the error with Retry; a jumped-to question, before and after the
  fix below.
- Volt at 800px: the missing-message notice; Ask about this.
- Volt at 1600px: the editor.
- Aurora at 1280px: the third screen of the answer. Ice at 1280px: its top.
- The walkthrough's sent question with its excerpt.

Text, labels, the reserved colours, the panes behind the blocks, the pills
and the accent rendered correctly in each, with no clipping, overlap or stray
symbols. The other 46 were captured, not viewed.

**Not caught: two status lines.** "Running Python…" and "Searching your
notes…" show for less time than the screenshot script needs with the fake
model, so neither was captured. They use the same style as the two that were.

**Walkthrough** (headless Chromium, fake model on port 8795, throwaway data in
`data/phase32-check/app/`, by `data/phase32-check/walk.cjs`). All eight steps
passed, with no console errors:
- a slow reply streams, and Stop keeps it as Stopped;
- Tab from the answer reaches Copy, then Regenerate, and Enter regenerates;
- Copy by mouse copies the answer;
- Shift+Tab back from the answer reaches Edit, which shows on focus; Enter
  opens the editor with the cursor in it; Save & resend replaces the answer;
- a failed reply shows the amber error, and Retry tries again;
- scrolling up shows Jump to latest, and Enter on it returns to the end;
- selecting with the mouse shows Ask about this, which attaches the excerpt
  and puts the cursor in the message box;
- Ctrl+A in an answer, Tab to Ask about this and Enter attach the whole
  answer; the question sends with its "Original answer" link.

The first run's Edit step failed because the script read Edit's opacity
before its 120ms fade had finished; with the script waiting for the fade, it
passed.

**Found while checking, and fixed: a square ring round a rounded bubble.** The
focus ring and the flash on a message you jump to follow the message's box,
which was square. The boxes now have rounded corners, a bubble's own for your
messages (`Conversation.module.css`).

**Not done.** The MacBook check. No paid calls and no evaluation.

#### What was decided while building it
- **Everything with a label sits on the panel colour,** without a blur:
  "Beyond your notes", "From the web", the callouts, code, the error and the
  Stopped marker. Phase 29's contrast test requires it, so their labels and
  muted text stay readable when phase 34 brightens the backdrop. The
  scrolling column itself still has no blur.
- **Callouts are rounded outlines in their colour, without a left edge.** The
  redesign describes them that way; the left edge stays the sign of "Beyond
  your notes" and "From the web".
- **"Beyond your notes" and "From the web" lost their outer border.** The
  coloured left edge and the tint are enough, as in the preview.
- **Edit sits just left of the bubble's bottom corner,** not inside it, so
  the bubble is only as tall as its text (phase 29 noted the extra height)
  and the button never covers the answer below.
- **Save & resend takes the accent,** as the editor's main action.
- **Words in a table cell aren't broken,** so a wide table scrolls inside its
  box instead of squeezing its words apart.
- **The missing-message notice stays in place under the header,** not
  floating over the conversation, so it never covers a message. It is a quiet
  pill in muted text, not amber, because it isn't an error.
- **Jump to latest stays where it was,** just above the message box, now a
  glass pill.
- **With reduced motion,** status lines are plain muted text and their icons
  and the typing dots stop pulsing.
- **The flash on a message you jumped to already used a token**
  (`--color-highlight`, from phase 29), so that checkpoint needed no change.

---

### Phase 33 / Task 20: Panels and pictures

**Status: built on 2026-11-10, on your instruction "Do phases 32 and 33 then
stop"; Windows-verified. MacBook check open.** Decision 4 (Sources as slide
cards, still collapsed) was built as recommended. See the verification record
at the end of this phase.

**What it builds:** what sits under an answer, and the pictures inside one.

#### 33A. Sources as slides
- Collapsed, as now: a small stack-of-slides glyph and "Sources (3)".
- Open: a row of slide-shaped cards (4 by 3). Each shows the module as a tag,
  the file name, and "Slide 8" or "Page 4" in display type.
- With many sources the row scrolls sideways inside itself, by mouse, touchpad
  or keyboard. A long file name is cut after three lines.
- It stays a list for screen readers, and each card reads as file, module,
  slide.

**Why cards:** they say what a source is at a glance (a slide from a deck), and
they tie the app's mark, which is two slides, to the thing it stands for.

**Checkpoints**
- [x] The existing sources tests pass unchanged: "Sources (n)", each file name,
      module and "Slide n" or "Page n" are found as text.
- [x] Playwright: the panel is closed until clicked, and opens by keyboard.
- [x] Playwright: the cards are list items, and each card's text reads file,
      then module, then "Slide n" with a space.
- [x] Playwright, at 600px, with 12 sources: the row scrolls inside itself, can
      be scrolled with the arrow keys once focused, and the page has no
      sideways scroll.
- [x] Playwright: an 80-character file name leaves the card the same height as
      a short one.

#### 33B. Found online, Working and files
- "Found online" and "Working" keep their headings, counts, groups and
  contents, as glass panels. Long addresses wrap.
- Python's pictures, the full-size viewer and the download chips are restyled.

**Checkpoints**
- [x] `web-search.spec.ts`, `calculator.spec.ts` and `python.spec.ts` pass
      unchanged.
- [x] Playwright, at 600px: a 200-character address in "Searched, not cited"
      wraps inside the panel.
- [x] Playwright: the viewer closes with Escape and returns focus (existing).

#### 33C. Diagrams and charts follow the theme
- The Mermaid theme is built from the tokens of the theme in use, and a diagram
  redraws when the theme changes.
- Chart colours, axes and tooltips come from the tokens: six series colours per
  theme, none of them the red, amber or web blue.

**Checkpoints**
- [x] `pictures.spec.ts` and `chart-spec.spec.ts` pass unchanged.
- [x] Test: each theme has six chart colours, none equal to the red, amber or
      blue tokens, each at least 3:1 against the panel.
- [x] Playwright: changing `data-theme` redraws a diagram with that theme's
      accent as its node border, and a chart's first line in that theme's first
      chart colour.
- [x] `grep` finds no colour literal in `Chart.tsx` or `Diagram.tsx`.

#### Phase 33 checklist
- [x] Every 33A to 33C checkpoint above.
- [x] The whole-app quality gate passes.
- [x] Screenshots viewed: Sources closed, open, with 12 sources and with a long
      name; Found online in each of its states; Working with a calculation, a
      refusal and Python code; a picture, the viewer and a file chip; a
      diagram and each chart type in all three themes.
- [x] Walkthrough: open each panel by mouse and keyboard, scroll the slide row,
      download a file, open and close the viewer, reopen the chat.
- [x] Documents updated.
- [ ] **MacBook (open until you run it):** the gate passes.

**Rough size:** medium.

#### Verification record (Windows, 2026-11-10; fake models, no paid calls)

**What was built, and where it's tested.**
- **33A.** `chat/Sources.tsx` and `chat/Sources.module.css`: the pill with a
  small two-slide glyph, opening into a row of slide cards (176px wide, 4 by
  3) that scrolls sideways and takes keyboard focus, so the arrow keys scroll
  it. Each card reads file, module, slide; the module is drawn first as an
  accent tag, the file name is cut after three lines, and "Slide 8" is in
  display type.
- **33B.** The same stylesheet: the shared pill and the glass panel that
  "Found online" and "Working" open into; long titles and addresses wrap.
  `chat/Working.module.css`: the panel, and Python's output on the darker
  inset. `chat/GeneratedFiles.module.css`: pictures and file chips on the
  panel colour, and the viewer as a glass pane over a blurred page, like the
  dialogs.
- **33C.** `design/useTheme.ts` (new): a small hook that reads `data-theme`
  and updates when it changes. `markdown/Diagram.tsx` uses it to redraw, sets
  the node edge to the plain accent, the line labels' background, and the
  timeline's section colours. `markdown/Chart.tsx`: grid lines are hairlines
  and the axis label has room below it. `design/tokens.css`: six chart
  colours for each theme. The diagram and chart boxes are on the panel
  colour.
- **Tests:** `e2e/panels.spec.ts` (7 new) and three new contrast tests (one
  per theme: six chart colours, none of them the red, amber or web blue, each
  at least 3:1 on a pane). No existing test changed.

**The grep checkpoints.** No colour is written outside `design/tokens.css`,
so `Chart.tsx` and `Diagram.tsx` hold none.

**Quality gate.**
- Frontend: lint and Prettier, TypeScript and the build passed.
- Playwright, on port 8792: two full runs, both passing all 256 (246 before
  this phase, none changed, and 10 new). The second was after the timeline
  and axis-label fixes below. Prettier then reflowed one line in `Chart.tsx`;
  lint and TypeScript passed again after it.
- Backend: Ruff lint and format passed; `pytest` passed all 371. No backend
  file changed.
- The existing build-size and Chroma warnings remain.

**Screenshots** (in `data/phase33-check/screens/`, 56 captured by
`data/phase33-check/shots.cjs` and six by `pictures.cjs`). As in phase 32,
the made-up chat is served by a route, so the cost readout's requests for it
got 404s. **Viewed, 15 of them:**
- Volt at 1280px: Sources open with twelve cards, one with a long name;
  Working with a calculation and a refusal; Working with Python's code and
  output, its picture and file chip; the viewer; the flowchart; the timeline
  before and after the fix; the bar chart; the line chart after the fix.
- Volt at 800px: the slide row scrolled; Found online open, with a 200
  character address wrapped.
- Aurora at 1280px: the pie chart; the timeline after the fix. Ice at 1280px:
  the line chart.

Cards, panels, the viewer, chips, diagrams and charts rendered correctly in
each, with the theme's colours, no clipping, overlap or stray symbols,
except the two faults below. The other 47 were captured, not viewed.

**Walkthrough** (headless Chromium, fake model on port 8795, throwaway data in
`data/phase33-check/app/`, by `data/phase33-check/walk.cjs`). All seven steps
passed:
- Tab from a notes answer reaches "Sources (1)"; Enter opens it, and the card
  reads "Lecture 1.pdf", "TM", "Page n"; Enter closes it;
- reopening the chat keeps its Sources, closed until clicked;
- Python's file chip downloads `summary.csv`;
- the viewer opens by keyboard, and Escape closes it and returns the focus to
  the picture;
- Working opens by mouse and shows the code and output;
- "Found online" opens by keyboard and lists its three groups;
- with twelve sources, the arrow keys scroll the focused slide row.

The first run's viewer step failed because the script read the focus the
moment the dialog left the page; the focus returns a moment later (traced by
`viewer-focus.cjs`, and the existing test waits for it). With the script
waiting 300ms, it passed.

**Found while checking, and fixed.**
- **Timelines were black boxes in every theme** (noted in phase 29). Mermaid
  colours a timeline's sections from its own colour scale, which the app
  didn't set. It now uses the theme's raised surface and text colour.
- **A line chart's x-axis label was cut off at the bottom.** This phase
  didn't change the chart's layout, so it is older. The line and bar charts
  now leave 12px below the label.

**Not done.** The MacBook check. No paid calls and no evaluation.

#### What was decided while building it
- **Diagram node edges are the plain accent.** Mermaid 12 draws them as a
  gradient from the accent to grey unless told not to; the plan asks for the
  accent.
- **Each theme's chart colours:** Volt lime, mint, lavender, pink, silver and
  violet; Aurora keeps the colours charts had before; Ice near-white, two
  blue-greys, silver, lavender and pale teal. None is the red, amber or web
  blue, and each is at least 3:1 on a pane with the backdrop at its brightest.
- **The slide row takes keyboard focus** (`tabIndex=0`), which is how the
  arrow keys scroll it. Its list is named "Sources".
- **Panels, pictures and chips are on the panel colour without a blur,** like
  everything else in the scrolling column. Only the viewer, which floats over
  the page, is real glass.
- **The viewer now matches the dialogs:** the same blurred, dimmed page
  behind it, 24px corners and the stronger edge.
- **A small hook, `useTheme`,** is the only new code file. Phase 34's
  Appearance menu will set the same attribute it reads.

---

### Phase 34 / Task 21: Motion and appearance

**Status: built on 2026-11-10 and 2026-11-11; Windows-verified. Your check and
the MacBook check are open.** See the verification record at the end of this
phase.

**What it builds:** the charge-up, the moving message box, the small motions,
and the Appearance menu with its memory.

**Why now:** it animates what phases 30 to 33 built.

#### 34A. The charge-up
- While a reply is in progress the app's root carries `data-thinking`. That
  covers the whole reply: searching, calculating, running Python and writing.
  It ends when the reply finishes, is stopped or fails. A notes update doesn't
  set it.
- CSS does the rest: the backdrop brightens, and a band of the accent travels
  round the message box's edge.
- The cost readouts still don't animate (phase 19's rule).

**Why one attribute:** the state already exists (`conversation.busy`). One
attribute lets the styles respond without any component knowing about another.

**Checkpoints**
- [x] Playwright, slow fake reply: `data-thinking` is present from the moment
      the reply starts, through a search, and gone within half a second of the
      reply finishing.
- [x] Playwright: it is gone after Stop and after a failed reply, and is never
      set by a notes update alone.
- [x] Playwright: the message box's edge has a running animation only while
      `data-thinking` is set.

#### 34B. The moving message box
- On the first message of a new chat, the message box glides from the middle of
  the screen to the bottom, using the browser's View Transitions.
- The page stays usable during the half-second it takes. Browsers without the
  feature, reduced motion and Calm all skip it and switch instantly, as now.

**The risk, and the fallback.** View Transitions briefly lay a picture of the
page over the page. If that makes any existing test unreliable after genuine
attempts, I stop and report, and the fallback is the instant switch the app
has today.

**Checkpoints**
- [x] Playwright: the first send starts exactly one view transition, and typing
      into the message box 100ms later works.
- [x] Playwright, with reduced motion: no view transition starts.
- [x] Playwright: sending in an existing chat starts none.
- [x] The whole Playwright suite passes three times in a row.

#### 34C. Small motions
- Slide cards deal in when Sources opens; menus and dialogs ease in; a caret
  blinks at the end of a streaming reply; prompt cards lift on hover.
- Each lasts half a second or less and animates only `transform` and `opacity`.

**Checkpoints**
- [x] Playwright: the caret shows while a reply streams and is gone when it
      finishes or is stopped.
- [x] Playwright, with reduced motion: after loading, opening a menu and
      opening Sources, the page has no running animation.
- [x] `grep` over the keyframes shows only `transform`, `opacity` and
      background-position being animated.

#### 34D. The Appearance menu
- A button at the bottom of the sidebar, and on the rail, opens a small menu:
  **Theme** (Volt, Aurora, Ice) and **Effects** (Full, Calm).
- The choice is saved in the browser's storage under one key, and applied by a
  few lines in `index.html` before the page first draws, so a saved theme never
  flashes the default one first.
- A missing, damaged or unreadable saved value falls back to Volt and Full.
- Calm: no backdrop motion, no travelling edge (the edge simply brightens while
  a reply is written), no glass blur and no moving message box.

**Why the browser's storage and not `settings.toml`:** it is a preference about
this screen, it changes with one click, and it needs no restart and no backend
change. The cost is that each browser remembers its own.

**Checkpoints**
- [x] Playwright: choosing Aurora sets `data-theme="aurora"` and the accent
      token changes; after a reload it is still Aurora, and was already Aurora
      when the page's content first loaded.
- [x] Playwright: the menu opens with Enter, the arrow keys move between
      choices, the chosen ones are marked as checked, and Escape returns focus
      to the button.
- [x] Playwright, Calm: the backdrop has no running animation, panes have no
      `backdrop-filter`, and no view transition starts on a first send.
- [x] Playwright: with reduced motion and Effects set to Full, motion is still
      off.
- [x] Playwright: a damaged saved value, and storage that refuses to be read,
      both leave the app loading in Volt with no console error.
- [x] Playwright: the menu is reachable from the rail and from the floating
      sidebar at 800px.

#### 34E. Remembering the sidebar
- Whether the sidebar is open in a wide window is saved with the appearance
  choices. Narrow windows behave as phase 27 built them.

**Checkpoints**
- [x] Playwright: collapse at 1280px, reload: still collapsed. Open, reload:
      still open.
- [x] `narrow-window.spec.ts` passes unchanged.

#### Phase 34 checklist
- [x] Every 34A to 34E checkpoint above.
- [x] The whole-app quality gate passes.
- [x] Screenshots viewed: mid-reply (charged) in each theme; the Appearance
      menu; Calm; a streaming caret; Sources mid-deal.
- [x] Walkthrough: first send with the moving box; Stop mid-charge; switch
      theme mid-reply; Calm on and off; reload; reduced motion emulated.
- [x] Documents updated, including View Transitions and browser storage in
      `TECH_STACK.md`.
- [ ] **Your check:** the charge-up and the moving box feel right on your
      screen, and Full effects scroll smoothly on the Windows PC.
- [ ] **MacBook (open until you run it):** the gate passes, and the same check
      there.

**Rough size:** medium. The least code, the most care.

#### Verification record (Windows, 2026-11-10 and 2026-11-11; fake models, no paid calls)

**What was built, and where it's tested.**
- **34A.** `App.tsx` sets `data-thinking` on the app's root from
  `conversation.busy`. `design/Backdrop.module.css` raises the lights to their
  charged strength over 1.2 seconds; `chat/MessageBox.module.css` has a `.charge`
  rim in which a large conic sweep of the accent turns (a transform), so only the
  part crossing the 1.5px edge shows.
- **34B.** `design/glide.ts` wraps the first message's change in
  `document.startViewTransition` with `flushSync`, unless Calm, reduced motion or
  a browser without the feature. `useConversation.ts` awaits it, so later stream
  events stay in order. Only the message box has a `view-transition-name`; the
  page's root has none, and `::view-transition` ignores the pointer, so the rest
  of the page changes at once and stays usable.
- **34C.** Slide cards deal in (`Sources.module.css`); menus, dialogs and the
  viewer fade in through a shared `fadeIn` class (`design/glass.module.css`); the
  caret is a `::after` on the last paragraph, heading or list item of a
  `data-streaming` reply (`markdown/Markdown.module.css`).
- **34D.** `design/appearance.ts` (load, save, apply, with every damaged or refused
  value falling back to Volt and Full), `sidebar/AppearanceMenu.tsx` (Radix radio
  items that keep the menu open), a few lines in `index.html` that apply the saved
  theme before the first draw, and `[data-effects="calm"]` rules that remove the
  blur, the drift and the travelling band.
- **34E.** The wide sidebar's open state is part of the same saved value.
- **Tests:** `e2e/motion.spec.ts` (11) and `e2e/appearance.spec.ts` (10), covering
  every 34A–34E checkpoint, including the keyframes check over every stylesheet.
  `narrow-window.spec.ts` is unchanged.

**One existing test changed, with your approval (2026-11-11).** `navigation.spec.ts`
"layout follows resized content…" failed on every full run: it closes the sidebar
at 1280px, and at 1600px the remembered state (34E) left no "Close sidebar"
button. Shown by the 1280px screenshot being rewritten while the error page held
"Open sidebar". Each width now clears the saved appearance before loading; every
check is as written. It is listed under "Tests that change".

**One new test fixed.** `appearance.spec.ts` "Calm stops the backdrop…" failed once
with `null` from `querySelector("[data-backdrop]")`: it counted the backdrop's
animations straight after loading, before React had drawn it. It now waits for
the backdrop to exist.

**Quality gate.**
- Frontend lint and Prettier, TypeScript and the build passed.
- Backend: `pytest` passed all 371; Ruff lint and format passed. No backend file
  changed.
- Playwright, port 8792: after both fixes, three full runs in a row each passed
  all 277 (256 before this phase, plus 21 new), as 34B asks
  (`data/phase34-check/final2-{1,2,3}.log`). The run before the second fix had
  that one failure; the two after it passed.
- The existing build-size and Chroma warnings remain.

**Screenshots** (`data/phase34-check/screens/`, 29 captured by `shots.cjs`).
**Viewed, 10:** mid-reply charged in Volt, Aurora and Ice at 1280px and a close-up
of the box's edge; the Appearance menu in the sidebar (Aurora), in the floating
sidebar at 800px (Volt) and on the rail (Ice, Calm); Calm mid-reply; Sources
mid-deal; the box mid-glide with the caret. The band, the brighter backdrop, the
caret, the ticks and headings rendered as planned, with no clipping, overlap or
stray symbols. In the Sources shot the box is still gliding, because the fake
reply finished inside the half-second glide. A streaming reply shows raw
`\frac{1}{2}` until its maths delimiter closes; that predates this phase.

**Walkthrough** (headless Chromium, fake model on port 8795, data in
`data/phase34-check/app/`, by `walk.cjs`). All ten steps passed: the first send
glides once from the middle to the bottom and typing works during it; mid-reply
the backdrop is brighter, the edge travels and the caret blinks; Stop ends all
three; switching to Aurora mid-reply applies at once while the reply carries on;
Calm stills the backdrop, removes the blur and the travelling band, and Full
restores them; the menu by keyboard (Enter, arrows, Escape back to the button);
a reload keeps Aurora and the collapsed sidebar, and the rail's menu works;
Sources deal in and the dialogs still work; with reduced motion nothing moves and
the first send doesn't glide; no browser console errors.

**Not done.** Your check on your own screen, and the MacBook check. No paid calls
and no evaluation.

#### What was decided while building it
- **The band is a turning conic sweep inside a masked rim,** so the browser moves a
  ready-made picture rather than repainting each frame.
- **Calm keeps the backdrop brightening** for a reply and shows the whole edge in the
  accent gradient instead of the travelling band.
- **Only the message box takes part in the view transition,** so nothing else is
  covered by a picture of the page during the glide.
- **Menus and dialogs fade without moving:** a dialog's transform is what centres it,
  and a menu must be in place from the first moment.
- **A stopped reply drops its caret at once,** in the moment before its saved version
  arrives.

---

### Phase 35 / Task 22: Finish

**Status: built on 2026-11-11; Windows-verified. Your check and the MacBook
check are open.** See the verification record at the end of this phase.

**What it builds:** no new screens. The icons, the clean-up, one review of the
whole app, and the final documents.

**Why last:** the review only means something once everything is in place.

#### 35A. Icons
- A browser tab icon: the mark on the base-colour tile, as an SVG in the
  frontend.
- `assets/askmynotes.ico` redrawn in Volt colours at the same seven sizes, the
  way phase 17 made it. The shortcut on your Desktop is not touched.

**Checkpoints**
- [x] Playwright: the page has an icon link, and requesting it returns an SVG.
- [x] The `.ico` holds the 16, 24, 32, 48, 64, 128 and 256 pixel sizes (read
      back with Pillow), and a preview of every size has been viewed.
- [x] `git status` shows nothing outside the repo was created or changed.

#### 35B. Clean-up
- Remove tokens, classes and styles that nothing uses any more, and the scratch
  previews in `data/ui-preview/`.

**Checkpoints**
- [x] A check lists every token defined in `tokens.css` and every class in a
      CSS Module that no file refers to: none remain.
- [x] `grep` finds no reference to Space Grotesk, Inter or JetBrains Mono.

#### 35C. The whole-app review
- Every core state, in three themes, at 600, 800, 1024, 1280 and 1600px. The
  states: the new chat screen; a long conversation at its top, middle and end;
  the floating sidebar; search; a chat's menu; the editor; each panel open; an
  error; mid-reply.

**Checkpoints**
- [x] Playwright: no sideways scroll in any of those states, themes and widths.
- [x] Playwright: in each of those states every button has an accessible name.
- [x] Screenshots viewed: all of them in Volt; Aurora and Ice at 600px and
      1280px. Each is checked for clipping, overlap, unreadable text and stray
      symbols, and the list viewed is recorded.
- [x] Walkthrough: one full session by keyboard only, from a new chat to a
      deleted one, in Volt.
- [x] A scroll check in headless Chromium: a 40-message chat scrolled for two
      seconds with Full effects, with the time between frames recorded here.
      It is a guide only; your own check is what counts.

#### 35D. Final documents
- `DESIGN.md` is rewritten so the new design is the one description of the
  look. The old palette and layout text is removed; its history stays in this
  plan.
- `SPEC.md` 8P, `STATUS.md`, `TECH_STACK.md` and `AGENTS.md` say "built".
- `README.md` is checked for anything that describes the old look.

**Checkpoints**
- [x] `grep` over `docs/` finds no remaining "proposed" or "awaiting approval"
      for phases 29 to 35, and no mention of the old fonts or `#8B5CF6` as the
      app's accent outside the historical phases of this plan.
- [x] `git diff --check` is clean.

#### Phase 35 checklist
- [x] Every 35A to 35D checkpoint above.
- [x] The whole-app quality gate passes.
- [ ] **Your check:** an ordinary study session on the Windows PC, with
      anything that looks or feels wrong reported.
- [ ] **MacBook (open until you run it):** the gate passes; the new chat
      screen, a conversation and the Appearance menu look right in Safari or
      Chrome there.

**Rough size:** small to medium.

#### Verification record (Windows, 2026-11-11; fake models, no paid calls)

**35A. Icons.** `frontend/public/favicon.svg` is the mark in Volt colours (lime to
mint) on a rounded tile of Volt's base `#0c0814`, linked from `index.html`.
`assets/askmynotes.ico` was rendered from the same SVG with the project's
Playwright Chromium (`data/phase35-check/icon.cjs`), each of the seven sizes drawn
directly, and combined with Pillow (`icon.py`). Read back: 16, 24, 32, 48, 64, 128
and 256; the 16, 32 and 256 frames are pixel-identical to their own renders, so
none was shrunk from another. `icon/preview.png` was viewed: the mark is clear from
48px, and at 16 and 32 the gradient and the bolt (a dark notch) still read; the
back slide's outline shows through the bolt, as it does in the app's mark. The
shortcut on your Desktop wasn't touched; Windows may show the old icon until it
refreshes its icon cache. Nothing outside the repo was created or changed.

**35B. Clean-up.** `data/phase35-check/unused.cjs` lists unused tokens and CSS
Module classes (it allows tokens built from a prefix in code, such as
`var(--chart-${series})`, and leaves out third-party classes styled through
`:global`). It found five unused tokens, all removed: `--color-accent-tint`,
`--color-accent-2-tint`, `--color-beyond-edge`, `--space-7` and `--radius-l`. It
now finds none, and no unused class. No reference to the old fonts remains in the
frontend. `data/ui-preview/` was deleted.

**35C. The review.** `e2e/review.spec.ts` (new, 4 tests): the tab icon; and, in each
theme at 600, 800, 1024, 1280 and 1600px, the new chat screen, mid-reply, the review
chat at its end (with an error), top and middle, every panel open, the editor,
search, the floating sidebar (below 900px) and a chat's menu. In each state: no
sideways scroll, and no button without an accessible name. All pass.
- **The name check was changed twice while building.** Checking buttons one by one
  broke when Jump to latest appeared mid-check. Playwright's aria snapshot then gave
  a false "unnamed" in the full run: it drops names over a few hundred characters,
  and the full suite leaves a chat titled with one 5,000-character word (shown on a
  plain test page: the snapshot left the name out while the browser's own check
  found it). The final check asks for buttons whose real accessible name is empty,
  in one query; it was proven on a page with two unnamed, one hidden and one
  5,000-character button.
- **Screenshots** (`REVIEW_SCREENSHOTS=1`, 85 in `data/phase35-check/screens/`):
  every state in Volt at all five widths, and Aurora and Ice at 600 and 1280px.
  **All 85 were viewed**, as one sheet per theme and width at half size
  (`sheets.py`), with the chat menu at 1280px and the floating sidebar at 800px also
  viewed full size. No clipping, overlap, unreadable text or stray symbols. The first
  set caught the chat menu and the floating sidebar mid-fade, so the script now waits
  400ms before each picture. Two things are from the test, not the app: the made-up
  chat's header reads "New chat", because a chat served by a route isn't in the
  sidebar's list; and a reply caught mid-stream shows a half-written table or
  formula until it closes, as before.
- **Keyboard-only session** (`data/phase35-check/walk.cjs`, Volt, fake model on port
  8795), all passed: type and send from the focused message box; Tab to Copy and copy
  the reply; Ctrl+Shift+O to a new chat; Ctrl+K, type and Enter to reopen the chat;
  the Appearance menu to Ice and back, with the focus returned; the chat's "…" menu,
  Delete, and confirming in the dialog, which deletes it; no console errors. My
  script's own mistakes along the way (searching a title another run had left,
  reading the focus before Radix returns it, tabbing to the wrong chat's menu, which
  deleted an older made-up chat) were fixed in the script; none was an app fault.
- **Found: an older fault, recorded, not fixed.** After the first message of a new
  chat, the keyboard focus is on the page, not the message box (`focus.cjs`; the
  same with reduced motion, so not the glide). The conversation's message box has no
  `autoFocus`, unlike the new chat screen's, since phase 5. Added to phase 36 as 36F,
  for you to confirm.
- **Scroll check** (headless Chromium, Full effects, a 40-message chat scrolled from
  end to top over two seconds): 98 frames; between frames, median 16.7ms (60 a
  second), 95th percentile 33.4ms, slowest 33.5ms. A guide only; your check is what
  counts.

**35D. Documents.** `DESIGN.md` is rewritten as the one description of the look,
from the redesign's as-built details and the feature rules that still apply; the
pilot's palette and fonts are gone from it (their history is in this plan's phase 2).
SPEC 8P, STATUS, TECH_STACK and AGENTS say built; TECH_STACK no longer names the old
fonts. `README.md` is empty, so it describes no look. Outside the historical phases
of this plan, `#8b5cf6` remains only as the reserved violet's darker shade and a
Volt chart colour, never the accent.

**Quality gate.**
- Frontend lint and Prettier, TypeScript and the build passed.
- Backend: `pytest` passed all 371; Ruff lint and format passed. No backend file
  changed.
- Playwright, port 8792: the first full run had 278 of 281 passing; the three
  failures were the review's false "unnamed" above. After the fix, a full run passed
  all 281 (277 before this phase, plus 4).
- The existing build-size and Chroma warnings remain.

**Not done.** Your study-session check on the Windows PC, and the MacBook check. No
paid calls and no evaluation.

### Planning review (2026-11-09)

Documentation only. `SPEC.md` section 8P, `DESIGN.md` ("Redesign"),
`TECH_STACK.md`, `STATUS.md` and `AGENTS.md` mark these phases as proposed and
awaiting approval. No app code, test, package, setting or stored data was
changed in this planning turn, and nothing was committed. Later the same day you confirmed five decisions
(three themes, the fonts, prompts without tags, the changed test and the
icons), and this plan and the other documents were updated to record them;
again no app code changed. The three previews in
ignored `data/ui-preview/` were made earlier the same day as throwaway
mock-ups.

---

## Phase 36: small fixes (planned 2026-11-10; not built, not yet authorised)

**Status: planned on 2026-11-10, on your instruction to add fixes for the four
problems found in phase 30's review; 36E (phase 31's review) and 36F (phase
35's review) were added for you to confirm. Nothing is built.** Building waits for
your go-ahead. Scope is in `SPEC.md` section 8Q.

**What it builds:** fixes for four small faults in how the app behaves. None
is part of the redesign's look, and each was shown to exist before it (in
phase 29's build). They are in phase 30's verification record.

**Why a phase of its own:** the redesign phases promise that behaviour doesn't
change. Keeping the fixes apart keeps that promise checkable, and lets each
fix have a test that fails before it and passes after.

**When:** any time from now. It depends on nothing after phase 30. I recommend
building it before phase 32, which restyles the conversation, and at the
latest before phase 34B, which changes how a new chat scrolls.

**What does not change:** the backend, the settings, the agent instructions
and the look. Frontend only; no paid calls; no evaluation.

**How each fix is made** (the root cause first, proven with evidence):
1. Write a Playwright test that shows the fault. It must fail.
2. Find the cause and record the evidence. The causes below are my best
   reading of the code today, marked as proven or likely.
3. Make the smallest fix. The new test passes, and every existing test passes
   unchanged.

#### 36A. A chat that ends in diagrams opens at its end
- **The fault.** A chat whose last answer has diagrams opens a few hundred
  pixels short of its end, showing "Jump to latest".
- **Likely cause.** The conversation scrolls to its end, then the diagrams are
  drawn and make it longer. Something in between marks the conversation as
  "scrolled away", so it stops following. Not yet proven.
- **The fix.** The conversation keeps following its end while its content is
  still growing after it opens, unless you have scrolled away yourself.

**Checkpoints**
- [ ] Playwright, ten times in a row: a chat ending in three diagrams opens
      within 1px of its end, and "Jump to latest" is not shown.
- [ ] Playwright: the same for a chat ending in a chart, and in an image.
- [ ] Playwright: if you scroll up while a reply is being written, the
      conversation still stays where you put it (existing behaviour).
- [ ] `navigation.spec.ts` and `long-chat.spec.ts` pass unchanged, including
      opening a chat at a searched message.

#### 36B. Rename puts the cursor in the title box
- **The fault.** Choosing Rename from a chat's menu, by keyboard or mouse,
  shows the title box but leaves the focus on the page.
- **Likely cause.** The box asks for the focus as it appears, while the menu
  is still closing and still holds it. Not yet proven.
- **The fix.** The box takes the focus once the menu has closed, with its
  text selected, as it was meant to.

**Checkpoints**
- [ ] Playwright, by keyboard: Enter on "…", Enter on Rename; the title box
      has the focus and its text is selected; typing and Enter renames the
      chat.
- [ ] Playwright, by mouse: the same after clicking Rename, without clicking
      into the box.
- [ ] Playwright: Escape cancels and leaves the old title; clicking elsewhere
      saves, as now.
- [ ] Playwright, at 800px: all of the above in the floating sidebar, which
      stays open.
- [ ] `narrow-window.spec.ts` passes. Its rename step clicks into the box
      first, which is still allowed, so it need not change.

#### 36C. Escape on a chat's menu returns the focus to its button
- **The fault.** Closing a chat's menu with Escape leaves the keyboard focus
  on the page, so the next Tab starts from the top.
- **Cause, proven by reading the code.** `ChatItem.tsx` stops the menu from
  returning the focus every time it closes. That was added so the rename box
  could keep the focus, but it applies to every way of closing.
- **The fix.** The menu returns the focus to the "…" button, except when
  Rename was chosen.

**Checkpoints**
- [ ] Playwright: Escape on the open menu puts the focus on that chat's "…"
      button, in the docked and the floating sidebar.
- [ ] Playwright: choosing Pin returns the focus to the same chat's "…"
      button.
- [ ] Playwright: in the floating sidebar, Escape closes the menu first and
      the sidebar on the next press (existing behaviour).

#### 36D. Deleting the open chat asks for nothing afterwards
- **The fault.** Deleting the chat you have open logs one 404 in the browser
  console. Nothing shows on screen.
- **Likely cause.** After a delete, every cost readout is told to reload,
  including the deleted chat's own, which is still on screen for a moment.
  Not yet proven.
- **The fix.** The deleted chat's cost is dropped, not reloaded. The total
  still reloads, so "Deleted chats" still goes up.

**Checkpoints**
- [ ] Playwright: deleting the open chat produces no failed request and no
      console error.
- [ ] Playwright: the sidebar's total still moves the chat's cost to "Deleted
      chats" (the existing `usage.spec.ts` test passes unchanged).
- [ ] Playwright: deleting a chat that is not open still works and leaves the
      open chat's cost showing.

#### 36E. A new chat started as a reply finishes stays a new chat
- **Added on 2026-11-10, from phase 31's review, for you to confirm.**
- **The fault.** Pressing Ctrl+Shift+O (or New chat) at the moment a reply
  appears sometimes changes the address to the new chat screen but leaves the
  old conversation showing. The existing test "Ctrl+Shift+O starts a new
  chat" fails about one time in ten because of it, on phase 30's code as well.
- **Likely cause.** Something that happens when a reply finishes puts the
  conversation back after the new chat screen was asked for. Not yet proven.
- **The fix.** Once you ask for a new chat, you get one, whatever the reply
  you left was doing.

**Checkpoints**
- [ ] Playwright: `history.spec.ts` "Ctrl+Shift+O starts a new chat" passes
      100 times in a row, unchanged.
- [ ] Playwright: the same by clicking New chat, during a slow reply and just
      as a reply finishes; the reply you left is complete when you reopen its
      chat.
- [ ] `chat.spec.ts` and `navigation.spec.ts` pass unchanged.

#### 36F. The first message of a new chat keeps the focus in the message box
- **Added on 2026-11-11, from phase 35's review, for you to confirm.**
- **The fault.** After sending the first message of a new chat, the keyboard
  focus is on the page, not the message box, so typing does nothing and Tab
  starts from the top. Later messages keep the focus in the box. It happens
  with reduced motion too, when nothing glides.
- **Proven cause.** The new chat screen and the conversation each draw their
  own message box (`NewChatScreen.tsx`, `Conversation.tsx`). Only the first has
  `autoFocus`, so when the screens swap, the focused box goes and nothing takes
  its place. This is as old as phase 5.
- **The fix.** The conversation's box takes the focus when it replaces a box
  that had it.

**Checkpoints**
- [ ] Playwright: after the first message of a new chat, with and without
      reduced motion, the message box has the focus and typing goes into it.
- [ ] Playwright: opening a chat from the sidebar or search doesn't move the
      focus into the box (it stays where the user put it).
- [ ] `motion.spec.ts` passes unchanged.

#### Phase 36 checklist
- [ ] Every 36A to 36F checkpoint above.
- [ ] Each new test was seen to fail before its fix, and that is recorded.
- [ ] The whole-app quality gate passes.
- [ ] Screenshots viewed: a diagram chat as opened; rename in progress with
      the text selected; the menu's button focused after Escape.
- [ ] Walkthrough: the four journeys by keyboard, in a wide window and at
      800px, with no console errors.
- [ ] Documents updated: this plan, `STATUS.md`, `SPEC.md` 8Q and `AGENTS.md`.
- [ ] **MacBook (open until you run it):** the gate passes.

**Rough size:** small.

## Phase 37: notes open in another app (2026-11-18; built)

**Status: built and Windows-verified on 2026-11-18; MacBook check open.** You
chose option 1 below the same day. Scope: `SPEC.md` section 8R.

### Investigation: notes update stops with PermissionError

**The fault.** The sidebar shows "Your notes didn't finish updating ...
(PermissionError)". The whole update stops, so no file is checked after it.

**Root cause (proven).** PowerPoint had
`AFA/Lecture 7.2.pptx` open (opened 11:41;
the app started 11:52). PowerPoint holds an OneDrive file with a lock that only
lets other programs read it if they also allow "share delete". Python's
`open()` does not, so Windows refuses with error 32 ("being used by another
process"), and Python reports it as `PermissionError` (errno 13).
`notes/sync.py` `fingerprint()` opens every file in `find_all_note_files()`,
outside any per-file `try`, so one open file stops the whole update. The
per-file safety net in `_index()` only covers conversion.

**Evidence** (read-only; nothing in the notes folders was changed):
- The app's own `find_note_files` + `fingerprint`, run on all 62 files: 61
  read; only Lecture 7.2 failed, `PermissionError(13)`.
- Raw `CreateFileW` on Lecture 7.2: share read+write (as Python's `open()`)
  fails with winerror 32; share read+write+delete opens it. Lecture 7.1, not
  open in PowerPoint, opens both ways.
- The two files have the same ACL and attributes, so it is not a permission
  setting. `POWERPNT` window title: "Lecture 7.2".
- `app.db`: all 62 files indexed, none unreadable. No data was lost.
- The same failure was reproduced with a made-up file held open the way
  PowerPoint does (`data/phase37-check/lock.py`); releasing it lets the file be
  read. The real counter-test (close PowerPoint, press retry) is yours to do.

**Who it affects.** Windows only. macOS has no such locks. It happens whenever
a lecture is open in PowerPoint (or another app that locks it) while the app
starts or you press "Refresh notes".

**Fix options** (each with a test that fails first):
1. **Skip a file that is in use, keep its old record (recommended).** Catch
   `PermissionError` per file when fingerprinting. Keep the file's existing
   record and chunks, so it is never treated as deleted. The status area says
   "1 file was open in another app; close it and refresh". About 15 lines in
   `sync.py`, one status field, a small frontend line. Small.
2. **Read files with "share delete" on Windows.** A Windows-only open helper
   (ctypes) used for fingerprinting and conversion, so files open in
   PowerPoint are read anyway. No message is needed, but it is platform code,
   and `.ppt` files go through LibreOffice, which may still be refused. Medium.
3. **No code change; a clearer message.** Map `PermissionError` to "a notes
   file is open in another app; close it and try again". The whole update
   still stops. Smallest, but the fault remains.

Trap for every option: simply leaving the file out of `found` would mark it
deleted and remove it from the notes database.

### What was built (option 1)
- `notes/sync.py`: `find_all_note_files()` catches `PermissionError` per file,
  logs a warning and returns those file ids as `in_use`. `_sync()` does not
  count an in-use file as deleted, so its record and chunks stay. A new or
  changed file that is in use is picked up by the next update. `NotesStatus`
  gains `in_use` (`inUse` in the API).
- `NotesStatus.tsx`: under the status line, "Skipped because it's open in
  another app: <module/file>. Close it, then refresh." (plural wording for
  several files). Not an alert: the update itself succeeded.
- Tests: `test_a_file_open_in_another_app_is_skipped_and_keeps_its_notes`
  (simulates the error, because macOS has no such locks), an `inUse`
  assertion in `test_the_app_updates_the_notes_when_it_starts`, and the
  Playwright test "a file open in another app is named, with what to do". Three
  other Playwright status mocks gained `inUse: []` to match the API; their
  assertions are unchanged.

#### Phase 37 checklist
- [x] The new backend test failed before the fix (`PermissionError` from
      `find_all_note_files`, the same traceback as the real fault) and passes after.
- [x] The new Playwright test failed before the fix (message not shown) and
      passes after.
- [x] An in-use file keeps its chunks and record, is not counted as deleted,
      and the other files still update (backend test).
- [x] The whole-app quality gate passes.
- [x] Screenshots viewed: in-use line at 1280 and 1600; after closing; long
      real-style names at 1280.
- [x] Walkthrough with a real Windows lock: skip, keyboard refresh, release,
      refresh.
- [x] Documents updated: this plan, `SPEC.md` 8R, `STATUS.md`, `AGENTS.md`.
- [ ] **MacBook (open until you run it):** the gate passes.
- [ ] **Yours:** with a lecture open in PowerPoint, press "Refresh notes": the
      update finishes and names the file; close it and refresh: the line goes.

#### Verification record (Windows, 2026-11-18; fake models, no paid calls)
- `uv run pytest`: **372 passed**. `uv run ruff check`: passed.
  `uv run ruff format --check`: 97 files already formatted.
- `npm run lint`, `npm run typecheck`, `npm run build`: passed.
  `npx playwright test`: **282 passed**.
- Walkthrough (`data/phase37-check/walkthrough.cjs`, headless Chromium,
  isolated app on port 8793 with made-up notes): with `Lecture 1.pdf` held open,
  "Refresh notes" finished with `inUse: ["TM/Lecture 1.pdf"]`, no error,
  `deleted: 0`, 1 file still indexed, the message box enabled and no alert;
  refresh by keyboard (Enter) kept the line; after release and refresh,
  `inUse: []` and the line was gone. No console errors.
- Screenshots viewed (`data/phase37-check/`): `in-use-1280.png`,
  `in-use-1600.png`, `after-close-1600.png`, `long-name-1280.png` (two long
  names wrap within the sidebar, no clipping or overlap).
- Not checked: macOS; the real PowerPoint counter-test on your notes.
