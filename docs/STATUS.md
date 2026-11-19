# Status

## Renamed to AskMyNotes, prepared for a public repo (2026-11-19)

The app, package (`askmynotes`), page title and sidebar wordmark are now
"AskMyNotes". `README.md` describes the project, with screenshots of made-up
sample notes in `docs/screenshots/`. Personal paths were removed from the docs.
The public copy is the `public` branch: one commit without the evaluation's
question set and run files, which are based on course material. Your Desktop
shortcut keeps its old name until you recreate it (see "Desktop shortcut").

## Notes open in another app: built (phase 37)

Built and Windows-verified on 2026-11-18; your PowerPoint check and the MacBook
check are open. Before, a lecture open in PowerPoint stopped the whole notes
update with "PermissionError". Now that file is skipped and keeps its notes from
the last update, every other file still updates, and the notes status names it:
close it, then refresh. Backend `notes/sync.py` and the notes status in the
sidebar; no settings or agent-instruction changes. Cause, evidence and checks:
`docs/PLAN.md`, "Phase 37". Scope: `SPEC.md` section 8R.

## The redesign: built (phases 29 to 35)

**Phases 29–35: the redesign**, planned on 2026-11-09. You confirmed its main
decisions the same day: three themes, the new fonts, example prompts without
tags, the one changed test and the new icons. **All seven phases are built**
(below); phases 34 and 35 were completed on 2026-11-11 at your request. The redesign
gives the whole app the look of the preview you chose (design 1): glass panes
over moving light, the "charging up" while a reply is written, sources drawn as
slides, three dark colour themes and a Calm setting. Every feature stays. It is
frontend only: no backend, settings or agent-instruction changes, no paid calls
and no evaluation.

- The preview: open `docs/redesign-preview.html` in your browser (it needs the
  internet for its fonts and icons).
- The plan, with its decisions (five confirmed; the four recommendations are
  all built, the last two, Calm and what the browser remembers, in phase 34):
  `docs/PLAN.md`,
  "Phases 29–35". Scope: `SPEC.md` section 8P. Look: `DESIGN.md`, "Redesign".

| Phase | What it would build | Status |
|---|---|---|
| 29 | Foundations: tokens for three themes, new fonts, the backdrop | Implemented; Windows gate passed; MacBook check open |
| 30 | The shell: sidebar, rail, header pill, menus and dialogs | Implemented; Windows gate passed; MacBook check open |
| 31 | The new chat screen and the message box | Implemented; Windows gate passed; MacBook check open |
| 32 | The conversation: bubbles, answers, states and actions | Implemented; Windows gate passed; MacBook check open |
| 33 | Panels and pictures: Sources as slides, Found online, Working, charts | Implemented; Windows gate passed; MacBook check open |
| 34 | Motion and appearance: charge-up, moving message box, Appearance menu | Implemented; Windows gate passed; your check and MacBook check open |
| 35 | Finish: icons, clean-up, full review, final documents | Implemented; Windows gate passed; your check and MacBook check open |

**Phase 35 (built):** the finishing touches, and one review of the whole app.
- **Icons.** The browser tab now shows the mark, in Volt colours on a dark tile.
  The Windows desktop icon (`assets/askmynotes.ico`) is redrawn the same way, at
  all seven sizes. Your Desktop shortcut wasn't touched; Windows may show the old
  icon until it refreshes its icon cache (signing out and in again does it).
- **Clean-up.** Five unused colour and size tokens are gone, and the scratch
  previews in `data/ui-preview/` are deleted.
- **The whole-app review.** A new test visits every core screen and state in all
  three themes at five widths (600px to 1600px): no sideways scrolling, and every
  button has a name a screen reader can say. All 85 review screenshots were
  viewed, and a keyboard-only session went from a new chat to deleting it.
- **`DESIGN.md` is rewritten** as the one description of the new look.
- **One older fault found, not fixed:** after the first message of a new chat,
  the keyboard focus leaves the message box, so you have to click back into it.
  It dates from phase 5. It's in phase 36's plan as 36F, for you to confirm.
- **Restart the app** to see the tab icon.

No backend, settings or agent-instruction changes; no paid calls; the evaluation
isn't needed.

Windows verification: all 281 Playwright tests (277 before this phase, plus 4
new), frontend lint/Prettier, TypeScript, the build, Ruff and all 371 backend
tests passed. A headless scroll check of a 40-message chat ran at a median of 60
frames a second (see PLAN).

Still open: **your check** (an ordinary study session on the Windows PC, telling me
anything that looks or feels wrong) and **the MacBook check for phase 35** (the
gate, and the new chat screen, a conversation and the Appearance menu in Safari or
Chrome there).

**Phase 34 (built):** motion, and the Appearance menu.
- **Charging up.** For the whole of a reply the backdrop brightens and a band of
  light travels round the message box. It ends when the reply finishes, is stopped
  or fails.
- **The moving message box.** On the first message of a new chat the box glides from
  the middle to the bottom in half a second; you can type during it.
- **Small motions.** A caret blinks where a reply is arriving; slide cards deal in;
  menus and dialogs fade in.
- **Appearance**, at the foot of the sidebar (or the palette icon on the rail): Theme
  (Volt, Aurora, Ice) and Effects (Full, Calm). Calm stops the drifting light, the
  travelling band, the glide and the glass blur. Your computer's "reduce motion"
  setting always stops the motion.
- **Remembered by this browser:** the theme, the effects level and whether the
  sidebar is open in a wide window. Each browser on each computer keeps its own.
- **Restart the app** to see it.
- **One existing test changed, as you approved:** the resized-layout test now starts
  each width like a first visit, because the browser remembers a closed sidebar.

No backend, settings or agent-instruction changes; no paid calls; the evaluation
isn't needed.

Windows verification: three full Playwright runs in a row each passed all 277 (256
before this phase plus 21 new), with frontend lint/Prettier, TypeScript, the build,
Ruff and all 371 backend tests. Ten screenshots were viewed across the three themes,
and the ten-step walkthrough passed (see PLAN).

Still open: **your check** (the charge-up and the glide feel right, and Full effects
scroll smoothly on the Windows PC) and **the MacBook check for phase 34.**

**Phase 33 (built):** what sits under an answer, and the pictures in it.
- **Sources as slides.** "Sources (3)" is still collapsed, now with a small
  two-slide glyph. Opened, each source is a slide-shaped card: the module as a
  tag at the top, the file name (cut after three lines), and "Slide 8" or
  "Page 4" in large type. Many sources make a row that scrolls sideways; click
  it and the arrow keys scroll it too. A screen reader still hears a list,
  each card as file, module, slide.
- **Found online and Working** open from the same pill into a dark glass
  panel. A very long address now wraps instead of running off.
- **Python's pictures and file chips** are restyled, and the full-size viewer
  looks like the other dialogs.
- **Diagrams and charts follow the theme.** Diagrams redraw when the theme
  changes, with the theme's accent on their boxes; each theme has its own six
  chart colours, never the red, amber or web blue.
- **Two older faults fixed while checking:** timelines were black boxes in
  every theme, and a line chart's bottom axis label was cut off.
- **Restart the app** to see it. To see the other themes before phase 34's
  menu, set `data-theme="aurora"` or `"ice"` on `<html>` in the developer
  tools.

No backend, settings or agent-instruction changes; no paid calls; the
evaluation isn't needed.

Windows verification: 256 Playwright tests passed (246 before this phase,
none changed, plus 10 new) in both full runs, with frontend lint/Prettier,
TypeScript, the build, Ruff and all 371 backend tests. Fifteen screenshots were
viewed across the three themes, and the panels were walked through by mouse
and keyboard (see PLAN).

Still open: **the MacBook check for phase 33.**

**Phase 32 (built):** the conversation itself.
- **Your messages** are soft glass bubbles with one tight corner. Edit appears
  just to the left of the bubble on hover or Tab, so the bubble is only as tall
  as its text. The edit box now fits inside its bubble at every width (it stuck
  out by about 8px at 1600px before), and Save & resend is in the accent.
- **Answers:** tables have hairlines and a wide one scrolls inside itself;
  code sits in a darker inset; "Beyond your notes" and "From the web" are a
  coloured left edge with a tint fading to the right; the four callouts are
  rounded outlines in their colours. Each of these sits on dark glass, so its
  label stays readable when the backdrop brightens in phase 34.
- **States:** a band of light passes through "Searching the web…" and the other
  status lines (plain text with reduced motion). Stopped, the amber error and
  Retry are restyled. Jump to latest is a glass pill. The "no longer
  available" notice is a quiet pill under the header. Ask about this is an
  accent pill.
- **Small fix found while checking:** the ring round a message you jump to was
  square around a rounded bubble; it now follows the bubble's corners.
- **Not changed yet:** Sources, Found online, Working and pictures. That is
  phase 33.
- **Restart the app** to see it.

No backend, settings or agent-instruction changes; no paid calls; the
evaluation isn't needed.

Windows verification: 246 Playwright tests passed (230 existing, none changed,
plus 16 new) on the fourth full run, with frontend lint/Prettier, TypeScript,
the build, Ruff and all 371 backend tests. The earlier runs each had one
failure: two from my new tests (fixed) and one the known "Ctrl+Shift+O" fault
planned as 36E. Sixteen screenshots were viewed across the three themes, and
the conversation's journeys were walked through by mouse and keyboard (see
PLAN). Two status lines ("Running Python…" and "Searching your notes…") pass
too quickly with the fake model to be screenshotted.

Still open: **the MacBook check for phase 32.**

**Phase 31 (built):** the screen the app opens on, and the message box.
- **The greeting** is set large, like a poster, on two lines beside the glowing
  mark. A band of accent light sweeps across it once as the screen loads.
- **The example prompts** are cards, two to a row, one to a row below 700px.
- **The message box** is glass with rounder corners. Its edge is a hairline at
  rest and the accent gradient while the cursor is in it. The Python button
  fills with the accent when it is on, and the send button is a little larger.
- **The cover shown while you drag files in** is glass with a dashed accent
  outline.
- **Not changed yet:** the messages themselves. That is phase 32.
- **Restart the app** to see it.

No backend, settings or agent-instruction changes; no paid calls; the
evaluation isn't needed.

Windows verification: 230 Playwright tests passed (209 existing, one of them
the greeting-size test changed as planned, plus 21 new), with frontend
lint/Prettier, TypeScript, the build, Ruff and all 371 backend tests. Nineteen
screenshots were viewed across the three themes, and the message box was
walked through by button, drop and keyboard (see PLAN).

**Two things to know.**
- One of three full test runs had a failure: the existing test "Ctrl+Shift+O
  starts a new chat" fails now and then. It does so on phase 30's code too, so
  it is not from this phase. It looks like a real fault (starting a new chat
  just as a reply finishes can leave you in the old one), so I added it to
  phase 36's plan as 36E, for you to confirm.
- I found and fixed a small fault from phase 30: the Questions menu and the
  dialogs had the ordinary edge instead of the stronger one.

Still open: **the MacBook checks for phases 29, 30 and 31.**

**Phase 30 (built):** the parts that frame every screen are now glass.
- **The sidebar** is a pane with rounded corners, floating 12px in from the
  window's left, top and bottom. Its rail is the same pane, 60px wide. New
  chat is tinted, the shortcut hints always show, and the open chat is marked
  with a wash of the accent and a glowing bar.
- **The chat header** is a pill floating at the top of the conversation, only
  as wide as what it holds. The conversation scrolls under it and fades out
  before it gets there.
- **Menus and dialogs** (a chat's menu, Questions, search and delete) are
  glass. Search marks the words you typed, like a highlighter.
- **Below 900px** the sidebar still floats over the conversation, as before.
- **Fainter than the preview:** the soft light that follows the pointer across
  the sidebar. The contrast test allows very little of it; see PLAN.
- **Not changed yet:** the new chat screen, the message box and the messages.
  Those are phases 31 and 32.
- **Restart the app** to see it.

No backend, settings or agent-instruction changes; no paid calls; the
evaluation isn't needed.

Windows verification: 209 Playwright tests passed (the 192 existing ones
unchanged, plus 17 new), with frontend lint/Prettier, TypeScript, the build,
Ruff and all 371 backend tests. Twenty-five screenshots were viewed across the
three themes, and the shell was walked through by keyboard and resized from
1600px to 600px and back (see PLAN).

**Four things found while checking.** None is caused by the
redesign; each also happens in phase 29's build. They are behaviour, not look,
so I left them:
- a chat that ends in diagrams opens a little short of its end;
- choosing Rename by keyboard doesn't put the cursor in the title box;
- Escape on a chat's menu leaves the keyboard focus on the page;
- deleting the chat you have open logs one harmless 404 in the browser console.

On 2026-11-10 you asked for fixes to be planned. They are **phase 36, planned
and not built** (`docs/PLAN.md`, "Phase 36"; `SPEC.md` section 8Q). Building it
waits for your go-ahead; I recommend before phase 32.

Still open: **the MacBook check.**

**Phase 29 (built):** the whole app is in the new colours and fonts, on the
moving backdrop. Its shapes and layout are as before; those change in phases
30 to 33.
- **Colours.** Volt (lime on deep plum) is what you see. Aurora and Ice are
  defined too, but there is no menu to choose them until phase 34. To look at
  one now, open the browser's developer tools and set `data-theme="aurora"` or
  `"ice"` on the `<html>` element.
- **Fonts.** Bricolage Grotesque for headings, Geist for text and Geist Mono
  for code replace the three old fonts. They ship with the app.
- **The backdrop.** Three soft lights drift slowly behind everything. They stop
  if your computer is set to reduce motion.
- **Small changes you may notice:** selected text looks highlighted; keyboard
  focus is a lime ring; links are mint.
- **Dimmer than the preview.** A new test checks that text stays readable in
  every theme with the brightest light behind it, and it set the lights lower
  than the preview had them. The details are in PLAN.
- **Restart the app** to see it. On the MacBook run
  `(cd frontend && npm install)` first, for the new fonts.

No backend, settings or agent-instruction changes; no paid calls; the
evaluation isn't needed.

Windows verification: 192 Playwright tests passed (the 166 existing ones
unchanged, plus 26 new), with frontend lint/Prettier, TypeScript, the build and
Ruff. The backend's first full run had one failure, the unexplained
`test_python.py` flake recorded in phase 26; it passed alone and the second
full run passed all 371. Twenty-two screenshots were viewed across the three
themes and the journeys walked through (see PLAN).

Still open: **the MacBook check.**

## Built before the redesign

Condensed 2026-11-11. Evidence for each phase is in `docs/PLAN.md`, and in full in
`git show 604e90c:docs/STATUS.md`. All of it was verified on Windows with fake
models, except where a paid real check is named. Run the evaluation only on request.

### The pilot (phases 1–13)
Built: settings and `GET /api/health`; the screens; chats in `data/app.db` with the
`/api/chats` API; the LangChain agent (`agent/instructions.md`) with one JSON event
per line from `POST /api/chats/send` and `/{id}/regenerate`; the sidebar, Ctrl+K,
Ctrl+Shift+O and `/chat/<id>`; images in `data/uploads/<chat id>/`; long-chat
summaries (`agent/summary_prompt.md`, `context_budget_tokens`); slide conversion to
`data/notes_markdown/<module>/` with `<!-- slide N -->` or `<!-- page N -->` markers;
Chroma (`data/chroma/`) synced by content on start and "Refresh notes"; `search_notes`,
"Beyond your notes", "Your notes don't cover this", collapsed Sources and the module
filter (`notes_search_results` sets results per search); the evaluation; macOS support.
End-to-end tests use `--fake-model` and a throwaway `data/e2e` folder.

**Phases 1–12 are built.** Phase 13 is implemented and tested on Windows; its real
MacBook checks remain open in `docs/PLAN.md`. The last evaluation (50 notes questions
with a strict judge) scored retrieval MRR 0.915 and, out of 5, accuracy 4.98,
completeness 4.10 and relevance 4.92; all 10 behaviour checks passed. See
`evaluation/results/history.csv`.

### Improvements (phases 14–28)

| Phase | Separate task | Status |
|---|---|---|
| 14 | Jump to latest, search to message, Questions menu | Implemented; Windows gate passed; MacBook checks open |
| 15 | Ask about selected answer text | Implemented; Windows gate/review passed; MacBook checks open |
| 16 | Edit and resend the latest question | Implemented; Windows gate passed; MacBook checks open |
| 17 | Windows desktop shortcut | Implemented; Windows gate passed; double-click check done by you |
| 18 | Document uploads and a 200,000-token context budget | Implemented; Windows gate passed; MacBook checks open |
| 19 | API cost and context-window indicators | Implemented; Windows gate passed; MacBook and real-model checks open |
| 20 | Today's date | Implemented; Windows gate passed; MacBook check open |
| 21 | Web search ("From the web", Web sources, costs; no button) | Implemented; Windows gate passed; real check passed; MacBook check open |
| 22 | Calculator and the "Working" panel | Implemented; Windows gate passed; MacBook check open |
| 23 | Code blocks and callout boxes | Implemented; Windows gate passed; MacBook check open |
| 24 | Diagrams and charts | Implemented; Windows gate passed; MacBook check open |
| 25 | Python (Code Interpreter) button | Implemented; Windows gate and real check passed; MacBook check open |
| 26 | Web search fixes (visible searching, "Found online" panel, search then calculate) | Implemented; Windows gate passed; MacBook check open |
| 27 | Narrow windows (no minimum width, centred from 600px, floating sidebar below 900px) | Implemented; Windows gate passed; your check done; MacBook check open |
| 28 | Unsupported citation markers | Implemented; Windows checks passed; MacBook check open |

What each does for you, and what to know (full behaviour is in `SPEC.md` section 8):

- **14 Navigation.** Message links are `/chat/<id>#message-<id>`, surviving refresh and
  Back/Forward. Same-chat navigation keeps a reply streaming; changing chats stops it.
- **15 Ask about this.** By keyboard: focus an answer, Ctrl+A or Command+A, Tab, Enter;
  Escape dismisses. Passages over 8,000 characters are refused.
- **16 Edit.** Stale edits and overlapping same-chat operations are refused. Existing
  Chroma deprecation and build-size warnings remain, and don't fail anything.
- **18 Documents.** Limits in `settings.toml`: `max_documents_per_message` (5),
  `max_document_size_mb` (25), `max_document_tokens` (100,000 per message, at most half
  of `context_budget_tokens`, now 200,000; was 60,000). Pasting a copied file wasn't
  exercised in a real browser. How a real model uses documents hasn't been checked.
- **19 Costs.** Prices in `[prices]`, dollars per million tokens: GPT-6 Luna input 0.10,
  cached 0.01, output 0.50; embeddings 0.13. A stopped reply is estimated (about four
  characters a token) and says so. Figures are close, not exact: OpenAI's dashboard is
  the authority. Evaluation and `askmynotes-check-model` aren't counted. **Not yet
  done:** a real check (well under a cent, needs your permission) that the model
  reports usage while streaming and the embeddings class works on the real API, and
  comparing the total with your dashboard after a day of use.
- **20 Date.** "Today is Thursday 29 October 2026." is added at the start of each reply.
- **21 Web search.** Each search is a flat $0.01, shown in the cost tooltip's "Web
  searches" line; pages read are in the reply's tokens. Replies use the Responses API
  with `store=False` (OpenAI doesn't keep them for retrieval; standard retention still
  applies). Citations arrive after the text, so a reply stopped part-way has paid for
  its search but lists none. The evaluation runs with web search available, each search
  about 1 cent. The real model hasn't been seen following the web instructions.
- **22 Calculator.** `calculate` handles arithmetic, `^`, `sqrt`, `ln`, `log`, `exp`,
  `round`, `sum`, `mean`, sample `variance` and `stdev`, `npv`, `irr`, `pv`, `fv`, `pmt`;
  `solve_equation` gives real solutions for one unknown. Results are exact where possible
  (`0.5 (exact 1/2)`). A refused calculation (`1/0`) is listed with its reason. Nothing is
  run with `eval`.
- **23 Code and callouts.** Copy on a reply copies it as written, markers included.
- **24 Pictures.** Drawn in the app from text, free; `mermaid` and `recharts` load only
  when a reply needs them. Charts have keyboard tooltips and a hidden data table.
- **25 Python.** Runs in a private 1 GB OpenAI sandbox made for one reply and deleted
  when it ends; nothing runs on this computer. Reads the 5 most recent Excel files in the
  chat. Output cut to 200 lines. Files are only ever downloaded, never opened as pages.
  Each sandbox is one cost line. The app's path with the real model and sandbox hasn't
  been run end to end: your first use is the first.
- **26 Found online.** A page both read and cited is listed once, even when its address
  differs by a final slash, `www.` or `?utm_source=openai`. Uncited pages are listed by
  address, as OpenAI gives no title. After Stop, the status stays about 0.8 seconds
  until the saved reply loads. The wrapper is tested on recorded events; your first real
  web answer is its first live stream.
- **27 Narrow windows.** Below 900px Escape, a click outside, choosing a chat, New chat
  or Search closes the floating sidebar. You confirmed it on 2026-10-30.
- **28 Citation markers.** Raw tokens are hidden while streaming, removed before saving
  and cleaned when reading older answers. Stored older rows are preserved. Restart the
  app to load it. All browser checks were headless with fake models.

The agent's instructions changed in phases 18, 20–26 and 28, and notes search embeds
through a new class since phase 19, so an evaluation would be informative, only on your
request. It would also show how the real model uses the newer tools.

Known intermittent test failures, causes unknown when recorded: `Ctrl+Shift+O starts a
new chat` under full-suite load (later planned as 36E); `test_python.py`
`test_a_sandbox_that_cant_be_made_fails_the_reply_without_a_charge`; once,
`quotes.spec.ts` "oversized excerpts…".

### MacBook catch-up (phases 18–25)
The app stops at start-up naming a missing setting. In the MacBook's own
`settings.toml`, copying from `settings.example.toml`, with sections above the
`[[modules]]` blocks:
- `max_documents_per_message`, `max_document_size_mb`, `max_document_tokens`, and
  `context_budget_tokens = 200000`
- the `[prices]` section, including `web_search_call = 0.01` and `python_session = 0.03`
- `[web_search]` with `country = "GB"` and `timezone = "Europe/London"`
- at the top, `max_generated_files_per_reply = 10` and `max_generated_file_mb = 25`

Then run `uv sync` and `(cd frontend && npm install)`, and the gate. The phase-by-phase
open checks are in `docs/PLAN.md`, "Open checks".

## Desktop shortcut (Windows PC only)
- Double-click **AskMyNotes** on the Desktop. It runs `uv run askmynotes` in
  a PowerShell window titled "AskMyNotes (close to stop)", with the icon
  `assets/askmynotes.ico`. Close that window to stop the app. If it fails to start, the
  window stays open with the error.
- Limits: a second double-click while it runs should show a port error; every start
  rebuilds the frontend and checks your notes; closing the browser tab doesn't stop the
  app; moving the repo folder breaks the shortcut.
- Recreate it in PowerShell if deleted:

```
$repo = (Get-Location).Path  # run this from the repo folder
$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'AskMyNotes.lnk'))
$s.TargetPath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$s.Arguments = '-NoProfile -NoExit -Command "$Host.UI.RawUI.WindowTitle = ''AskMyNotes (close to stop)''; uv run askmynotes"'
$s.WorkingDirectory = $repo
$s.IconLocation = "$repo\assets\askmynotes.ico,0"
$s.Description = 'Start AskMyNotes'
$s.Save()
```

## First-time setup
Commands are for PowerShell on Windows, with the macOS (zsh) version beneath.
The Mac needs more installing first: see "Setting up on macOS" below.

1. Install the Python packages: `uv sync`
2. Install the frontend packages:
   - Windows: `cd frontend; npm install; cd ..`
   - macOS: `(cd frontend && npm install)`
3. Install Playwright's browser inside the project (once):
   - Windows: `cd frontend; $env:PLAYWRIGHT_BROWSERS_PATH=0; npx playwright install chromium; cd ..`
   - macOS: `(cd frontend && PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install chromium)`
4. Copy `.env.example` to `.env` and add your OpenAI key.
   - Windows: `Copy-Item .env.example .env`
   - macOS: `cp .env.example .env`
5. Copy `settings.example.toml` to `settings.toml` and edit it.
   - Windows: `Copy-Item settings.example.toml settings.toml`
   - macOS: `cp settings.example.toml settings.toml`

## Convert the notes to Markdown (free; no model is called)
`uv run askmynotes-convert-notes`

## Run the app
`uv run askmynotes` builds the frontend, starts the server on
`http://127.0.0.1:8000` and opens it in your browser. Your notes are
brought up to date in the background; the first time, embedding every slide
takes about a minute and a half and costs a few pence.

Options: `--no-browser` doesn't open a tab, `--port 9000` overrides the port.

## Check the real models (costs a fraction of a penny)
`uv run askmynotes-check-model`

`uv run askmynotes-check-model --web` checks the Responses API and web search
instead (about 4 cents).

`--python` checks Code Interpreter (about 10 cents with follow-up probes), and
`--web-detail` checks search events and searched pages (5 to 10 cents a run).

## Run the tests and checks (the quality gate)
At the end of each implementation phase only, complete all three verification levels
in `docs/PROCESS.md` and record the results in PLAN/STATUS. Fake models and isolated
data only; screenshots go in ignored `data/`.

```
uv run pytest
uv run ruff check
uv run ruff format --check
cd frontend; npm run lint; npm run typecheck; npm run build; npx playwright test; cd ..
```
On macOS, use `(cd frontend && npm run lint && npm run typecheck && npm run build && npx playwright test)` for the last line.

The browser tests use port 8765. If another program on the computer is using it,
set `E2E_PORT` to a free port first (`$env:E2E_PORT=8792` on Windows,
`E2E_PORT=8792` before the command on macOS).

## Run the evaluation (costs money: about 100 model calls)
Close the app first, and make sure it has indexed your notes at least once.

`uv run askmynotes-eval --note "what changed"`

It answers every question in both test sets with the real models, then prints
a report: overall, by category and by module, with the change in each headline
score since the last run, and which behaviour checks failed. `--concurrency 4`
sets how many questions run at once.

Each run is saved in `evaluation/results/`: a file named with its date and time
(every question's scores, answer and sources), and a row in `history.csv`. These
hold references to slides, never slide text, and are committed to keep the
history.

## Setting up on macOS
The MacBook is a separate copy of the app. It keeps its own chats, uploads and
notes database (in its own `data/` folder), its own `settings.toml` and its own
`.env`. The only things shared are the code, through git, and your OneDrive
lecture folders, which the app only reads. Never copy `.env`, `settings.toml`
or `data/` between the computers.

### 1. Install (once)
Open Terminal and install [Homebrew](https://brew.sh) if you don't have it, then:

```
brew install git uv node
brew install --cask libreoffice
```

- `uv` installs the right Python (3.13) by itself.
- LibreOffice converts the old `.ppt` slide files. **Open it once by hand**
  (Applications, then LibreOffice) and approve it if macOS asks, or the app's
  background conversions will fail.

### 2. Get the code
```
git clone <your repository address> "AskMyNotes"
cd "AskMyNotes"
```
Keep this folder outside OneDrive, as `data/` holds a database that shouldn't
be synced. Then follow "First-time setup" above, using the macOS lines.

### 3. OneDrive
Install OneDrive on the Mac and sign in. For each of your five `Lecture Slides`
folders, right-click it in Finder and choose "Always Keep on This Device".
Otherwise the first start has to download about 590MB of slides one at a time.

### 4. `settings.toml`
Edit your copy (`open -e settings.toml`):
- Keep `user_name`, `port` and the numbers as they are, and copy the `[prices]`
  section from `settings.example.toml` (it goes above the `[[modules]]` blocks).
- Use the macOS line for `libreoffice_path`:
  `/Applications/LibreOffice.app/Contents/MacOS/soffice`
- Give each module its macOS folder. To find the exact path, right-click the
  folder in Finder and hold the Option key: "Copy ... as Pathname". It will look
  like `/Users/yourname/Library/CloudStorage/OneDrive-UniversityofKent/...`.
  Write it in full, inside single quotes; `~` isn't expanded.
- The module names and short names must match the Windows copy, or the
  evaluation won't match its questions to modules.

### 5. `.env`
Open `.env` and put in your OpenAI key. Create it on the Mac itself rather than
sending it from the PC. `CHAT_MODEL` and `EMBEDDING_MODEL` stay as in the
example.

### 6. First start
```
uv run askmynotes
```
This builds the frontend, starts the server and opens your browser (Chrome, if
it is your default). The notes are embedded from scratch on this computer, which
takes about a minute and a half and costs 4 to 5 pence. The sidebar shows
"Updating notes" until it says "Notes up to date · 53 files". On later starts
it only checks for changes.

If something fails:
- *"The folder for ... doesn't exist"*: a path in `settings.toml` is wrong.
- A `.ppt` file listed as unreadable with "LibreOffice was not found": check
  `libreoffice_path`; with "could not convert": open LibreOffice once by hand.
- `uv run askmynotes-convert-notes` converts the notes to Markdown without
  calling any model, which is a free way to test the folders and LibreOffice.

### Shortcuts
The sidebar shows ⌘ K (search chats) and ⌘ ⇧ O (new chat). If Chrome keeps ⌘ ⇧ O
for its bookmarks manager, use Ctrl ⇧ O, which also works on a Mac.
