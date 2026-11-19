# AskMyNotes: Specification

## 1. Purpose and users

A personal AI chatbot for one user, a university student. It should feel as capable
as a frontier chatbot such as ChatGPT or Claude, and can also search my university
notes in a vector database. It is both **a study tool** (questions on my modules from
my own lecture material) and **a general assistant**.

One user, so no sign-in or accounts. It runs locally on my PC, in my browser. My
university folders stay on my PC; when an answer needs my notes, the relevant extracts
are sent to the model provider.

## 2. Chat features

- **Streaming**: replies appear word by word.
- **Formatting**: rendered Markdown, including headings, bold, lists, tables and code
  blocks. Maths renders as proper equations with real fractions, not raw LaTeX.
- **Model**: every reply uses GPT-6 Luna. No model picker.
- **Message actions**: copy any reply; regenerate the latest reply, replacing it (the
  old version is not kept); stop a reply, keeping the partial reply marked as stopped.
- **Uploads**: images and screenshots, which the model takes into account, and Word,
  Excel, PowerPoint and PDF documents (section 8E). An upload belongs only to its chat
  and is never added to my notes database.
- **Web search**: section 8H.
- **Errors**: if a reply fails (provider down, internet drops), a clear error says what
  went wrong, under my message, with Retry. My message is never lost.
- **Keyboard shortcuts**: Enter sends, Shift+Enter starts a new line, plus shortcuts for
  a new chat and for searching chats.
- **Long chats**: chats too long to send in full still work.

## 3. Chat history

Every chat is saved.

- **Sidebar**: past chats grouped by last use: Today, Yesterday, Last 7 days, Last 30
  days, then older. Pinned chats sit above the groups.
- **Titles**: a short title written by the model from my first message; I can rename it.
- **Managing chats**: rename, delete, pin, unpin.
- **Search**: by titles and message text.
- **What is saved**: everything: my messages, replies, uploaded images and the note
  sources used. A reopened chat looks exactly as it did, sources included.
- **Deleting**: gone permanently, after I confirm.
- **Opening the app**: on a new, empty chat. A new chat is only saved once I send its
  first message.

## 4. Notes RAG

The chatbot searches a vector database built from the folders in section 5.

**When to search.** Whenever a question could be covered in my modules, even if I don't
mention university. Not for clearly unrelated questions, such as recipes or football.
When unsure, it searches.

**Outside knowledge.** After a notes search, the answer is based on my notes first. It
may add knowledge from beyond them, always clearly marked with the label **"Beyond your
notes"**. When no notes search was done, no label is needed.

**When my notes don't cover it.** It says clearly "Your notes don't cover this", then
answers from general knowledge, labelled "Beyond your notes".

**Sources.** Every answer using my notes lists its sources underneath: file name, module,
and slide or page number. Only the slides and pages actually used, not everything
returned. If nothing relevant was found, no list. Sources are for reference; they don't
need to open the file.

**Module filter.** By default, all modules. If I clearly ask for one or more only, by
name or short name ("only from my AFA notes", "from my AFA and FR notes"), only those.

**Personality.** A neutral, helpful assistant in this version.

## 5. Folder sync

### Notes folders
The notes database is built only from these lecture-slide folders:

| Module | Short name | Folder |
|---|---|---|
| Investment and Portfolio Analysis | IPA | Its `Lecture Slides` folder in my university OneDrive |
| Advanced Financial Accounting | AFA | Its `Lecture Slides` folder in my university OneDrive |
| Business Law | BL | Its `Lecture Slides` folder in my university OneDrive |
| Intermediate Management Accounting | IMA | Its `Lecture Slides` folder in my university OneDrive |
| Financial Reporting | FR | Its `Lecture Slides` folder in my university OneDrive |

Folders, module names and short names are in a settings file, not code, so I can add or
remove a module there alone. The app only reads these folders, and never changes, moves
or deletes anything in them.

### File types
- PDFs, `.pptx` and older `.ppt`, all indexed.
- Text is extracted to Markdown with slide or page numbers kept, so answers cite the
  exact slide or page. The Markdown is saved, so I can see what the app read.
- Only text is extracted: images, charts and diagrams in slides are not read. Native
  PowerPoint chart data is kept, as it's stored as text.
- A file that can't be read is skipped, and the app tells me which one.

### Keeping the database up to date
- On every start, it checks for new, changed or deleted files, by contents, not size.
- It updates only what changed: adds new, re-indexes changed, removes deleted.
- It shows progress, for example "Updating notes: 3 new, 1 changed, 0 deleted".
- I can't chat until the update has finished.
- "Refresh notes" runs the same check at any time.

## 7. Success criteria

**Answer quality.** Evaluated on `evaluation/tests_small.jsonl`: 10 questions per module,
50 in all, kept small because every run costs money. `docs/TECH_STACK.md` says where the
questions come from. Results are recorded for comparison with future versions.

**Behaviour.**
- Everyday questions, such as a recipe, do not search my notes.
- Questions on module topics search my notes, even without mentioning university.
- A finance question not covered by my slides gets "Your notes don't cover this", then a
  general answer labelled "Beyond your notes".
- Any knowledge from beyond my notes, after a notes search, is labelled "Beyond your notes".
- "Only from my AFA notes" returns AFA sources only; "from my AFA and FR notes" those two only.
- Every notes answer lists the file, module and slide or page of each source used.

**Chat and history.** Every feature in sections 2 and 3 works in the browser. Restarting
keeps all chats exactly as they were. One command starts the app and opens it in my browser.

**Folder sync.** Adding, changing or deleting a slide file is picked up on the next start
or refresh, and only that file is re-indexed.

## 8. Improvements after pilot

Sections 1–7 describe the pilot. Sections A–O (phases 14–28) are built and
Windows-verified; MacBook checks remain open as recorded in STATUS and PLAN (phase 17 is
Windows-only). There are no conversation branches or retained message versions.
Phases 29–35 (P), the redesign, were planned on 2026-11-09 and their main
decisions confirmed the same day. All seven are built and Windows-verified:
29 (the colours, fonts and backdrop), 30 (the shell), 31 (the new chat screen
and the message box), 32 (the conversation), 33 (panels and pictures), 34
(motion and appearance) and 35 (icons, clean-up and the whole-app review).
Phase 36 (Q), small fixes, was planned on 2026-11-10 and is not built.

### A. Conversation navigation (phase 14)
- "Jump to latest" appears when scrolled away from the bottom; it returns to the latest
  message and resumes following streamed text. Reading earlier messages isn't interrupted.
- Chat search opens the matching message and briefly highlights it. A title match with no
  message target opens the chat normally. One best match per chat, with a snippet.
- Message links survive refresh and support Back/Forward. A removed message gives a clear
  notice in its chat rather than jumping elsewhere. An unknown chat follows the existing
  missing-chat behaviour.
- A compact "Questions" menu lists my questions in order and jumps to the selected one.
  Image-only messages have a useful label.
- Navigating within a chat doesn't stop a reply; opening a different chat stops it, as before.

### B. Questions about selected text (phase 15)
- Select an excerpt in one saved assistant answer and choose "Ask about this". The composer
  shows it separately from the question.
- Type a question or use "Explain this" / "Show an example" to fill it; sending is always
  explicit, in the same chat.
- One excerpt at a time, removable before sending. Changing chats clears it; choosing one
  preserves typed text.
- Saved questions keep their excerpt and original-answer reference on reopening. The excerpt
  is conversational context, not a lecture citation or a higher-authority instruction.
- The model receives it even when the original answer has been summarised. Notes-search and
  "Beyond your notes" rules still apply.
- Selections may include prose and complete equations; selecting any part of an equation
  quotes all of it, shown before sending. Cross-message selections and selections of
  controls or source lists are not accepted.
- Keyboard access to the action. Empty, streaming and failed answers are excluded; saved
  stopped answers with text are eligible.

### C. Edit and resend the latest question (phase 16)
- Only the latest saved user message; its images and excerpt stay attached, and only its
  text is edited.
- "Edit" opens an inline editor with "Cancel" and "Save & resend". Cancelling changes
  nothing. Saving replaces the question and its latest answer, including the old answer's
  error/stopped state and sources.
- The replacement streams normally. The old answer isn't supplied to the model, including
  through a saved summary.
- If saving is refused, the old conversation and editable text remain. If generation fails
  after saving, the corrected question stays with an error and Retry. Stop keeps the new
  partial reply as stopped.
- Unavailable during generation or notes updates. The server rejects stale edits and
  conflicting operations from another tab.
- Earlier messages, images, pinned status and title are preserved. Success updates last-used
  time and the search index. Editing the first question doesn't rename the chat.
- Empty text is allowed only when existing images satisfy the normal send rule; a quote alone
  isn't enough.

### D. Windows desktop shortcut (phase 17)
- On the Windows PC only, a desktop icon showing the app's mark starts the app with a
  double-click, running the start command in a visible PowerShell window; the app opens in
  the browser as usual.
- Closing the window stops the app. If it can't start, the window stays open with the error.
- No backend, frontend, settings or start-command changes. Nothing new for the MacBook.
- One-off exception (granted 2026-10-29): the agent may create this one shortcut file in the
  Windows Desktop folder. No other file outside the repo is created or changed.
- Not included: a hidden window, an "already running" check, faster starts, Start menu or
  taskbar entries, a Mac launcher.

### E. Document uploads (phase 18)
- Attach Word (`.docx`, `.doc`), Excel (`.xlsx`, `.xls`), PowerPoint (`.pptx`, `.ppt`) and PDF
  files, with or without text and images, by button, drag-and-drop, or paste where allowed.
- The model reads the text in full, including tables, every Excel sheet and speaker notes,
  with page, slide and sheet numbers. Pictures and scanned pages aren't read.
- A document belongs only to its chat, never my notes database, and shows on its message
  when reopened.
- Answers say when something comes from an attached file. Document content isn't labelled
  "Beyond your notes" or listed under Sources. Section 4 otherwise applies.
- A wrong type, oversized file, or one with no readable text or too much text is refused with
  a message naming it, keeping my draft. Limits are in settings.
- Editing the latest question keeps its documents.
- The long-chat budget is 200,000 tokens (was 60,000), in settings.
- Not included: searching inside documents, reading pictures or scans, opening an attached
  file from the chat, chat search over document text, CSV or plain text.

### F. API cost and context-window indicators (phase 19)
- Each chat's header shows, discreetly, its total API cost in US dollars and how full its
  long-chat budget is. Hover or focus gives the detail: cost by replies, titles, summaries
  and searches; roughly how many tokens are used and whether older messages are summarised.
- The bottom of the sidebar shows the app's total: all chats (including deleted) and notes
  updates, each in its detail.
- Everything counts: every model call in a reply, titles, summaries, notes search queries and
  notes updates. The evaluation and model check are separate and not counted.
- Prices are in settings, in dollars per million tokens, applied to OpenAI's token counts.
  When a stopped reply has no count, the cost is estimated and marked so. OpenAI's dashboard
  remains the authority.
- Older chats show only new spending and say earlier costs weren't recorded.
- Not included: cost per reply, request size, other currencies, limits or alerts, charts.

### G–L. Tools and richer answers (phases 20–25; built)

#### G. Today's date (phase 20)
The agent knows the date and weekday from the computer's clock, checked at each reply's start.

#### H. Web search (phase 21)
- **Searching.** Through OpenAI's own tool. It decides for itself for things that may have
  changed since training (rates, prices, news, new standards, deadlines); always when I ask in
  my message ("search the web for…"). No button. Not for questions my notes cover, unless I
  ask. Section 4 still applies.
- **Labelling.** Web content is in a blue block labelled "From the web", with clickable
  citations. Notes content stays plain; outside knowledge after a notes search stays in "Beyond
  your notes"; web content is never labelled that.
- **Sources** are saved with the answer (see section M for the panel). **Costs** include searches.
- **Not included:** pages needing a login, choosing or blocking sites, image search, deep research.

#### I. Calculator (phase 22)
- A free, local calculator for arithmetic, algebra, statistics and finance formulas (NPV, IRR,
  PV, FV, PMT), which can solve an equation for one unknown.
- "Calculating…" shows while it works. A collapsed "Working (n)" panel under the answer lists
  each calculation and result, saved with the answer.
- A result from my own numbers or figures in my notes isn't outside knowledge. A formula not in
  my notes is still labelled "Beyond your notes".

#### J. Code blocks and callout boxes (phase 23)
- Code blocks have syntax highlighting, a language label and Copy.
- Four callouts: "Key formula", "Exam tip", "Common mistake", "Worked example". They can sit
  inside "Beyond your notes" and "From the web" blocks and never replace those labels.

#### K. Diagrams and charts (phase 24)
Replies can include Mermaid diagrams (flowcharts, timelines, sequence diagrams, structures) and
line, bar and pie charts drawn in the app. One that can't be drawn shows its source and a short
note. They're saved as reply text, so redraw on reopening.

#### L. Python (phase 25)
- A "Python" button in the message box lets OpenAI's Code Interpreter run Python for one reply,
  then switches off. Without it, Python is never used and costs nothing. Retry, Regenerate and
  Edit repeat it.
- Python receives Excel files attached to the question and earlier in the chat, up to the 5 most
  recent.
- Code and output appear in "Working". Charts show under the answer; other files can be
  downloaded; everything is saved with it. Costs include each session.
- **Not included:** memory between messages, reading my lecture notes, sending CSV, Word, PDF or
  image files to Python.

#### M. Web search fixes (phase 26)
- **Visible searching.** "Searching the web…" with the globe shows for the whole search, from
  its start, and again for each further search. The notes search keeps its magnifying glass.
- **Found online.** Every answer that searched has a collapsed panel with the globe, "Found
  online (n cited, m searched)": *n* pages cited, *m* read but not cited. It shows whenever a
  search ran, even if nothing was cited, and is saved with the answer. Opened, it lists what was
  searched for, cited pages and "Searched, not cited" pages, each with a link. It replaced "Web
  sources (n)". Older answers show only their cited pages.
- **Searching and calculating.** A current figure plus a calculation: search first, then
  calculate; the answer shows the "From the web" block, with links, and Working.
- **Not included:** choosing or blocking sites, opening pages in the app, changing when it searches.

### N. Narrow windows (phase 27)
- Works in any desktop window from 600px wide (CSS pixels, so zoom counts), with no sideways
  scrolling.
- The new chat screen and conversation stay centred beside the sidebar at every width.
- The greeting shrinks slightly when narrow. A long title ends in "…", so cost, context and
  Questions stay visible.
- Below 900px the sidebar starts as its rail; opened, it floats over the conversation; choosing a
  chat, Escape or a click outside closes it; widening restores it as you had it.
- At 900px and wider, nothing changes.
- **Not included:** phone layouts, touch gestures, remembering the sidebar's state between visits.

### O. Unsupported citation markers (phase 28)
- Answers don't show raw internal tokens such as `citeturn0search0`, including while streaming
  and after Stop or an error.
- Affected older answers reopen and copy without them, with stored text not rewritten. New
  answers are saved without them.
- They're removed from assistant history and summaries sent to the model.
- Real links, recorded web sources, lecture Sources and source labels are unchanged. A token alone
  never creates a URL, a source entry or a claim that a search occurred.
- User messages, uploads and quote snapshots are preserved. Ask about this works on cleaned text.
- A targeted cleanup of the reserved syntax, not a general rewrite or a check of accuracy.

### P. Redesign (phases 29–35; built)

Built so far (phase 29): the three themes' colours, with Volt showing; the new
fonts; the moving backdrop; the reserved colours unchanged; and the contrast
test. Phase 30: the glass sidebar and rail, the chat header as a glass pill
the conversation scrolls under, glass menus and dialogs, and search matches
marked with the accent. Phase 31: the poster greeting with its sweep of light,
the prompt cards, the glass message box and the glass drop cover. Phase 32:
the conversation's bubbles, answers, callouts, code, status lines, errors and
actions, and the edit box fitting its bubble and the styled "message is no
longer available" notice from the small fixes. Phase 33: Sources as slides,
Found online and Working as glass panels, and diagrams and charts in the
colours of the theme in use. Phase 34: the charging up, the moving message
box, the small motions, the Appearance menu with its three themes and two
effects levels, and what the browser remembers. Phase 35: the browser tab icon,
the desktop icon redrawn in Volt colours, the clean-up and the whole-app review.

- **A new look, the same app.** The whole app takes the look of the preview
  chosen on 2026-11-09 (`docs/redesign-preview.html`).
  Every feature in sections 1–8O keeps working as it does now, with the same
  wording, shortcuts and accessible names.
- **Glass over light.** The sidebar, chat header and message box are dark glass
  panes over a slowly moving backdrop of coloured light.
- **Charging up.** For the whole time a reply is in progress, the backdrop
  brightens and a band of light travels round the message box. It stops when the
  reply finishes, is stopped or fails.
- **Sources as slides.** "Sources (n)" stays collapsed by default. Opened, each
  source is a slide-shaped card showing the file, the module and the slide or
  page number.
- **The message box moves.** On the first message of a new chat, the message box
  glides from the centre of the screen to the bottom.
- **Appearance.** A menu in the sidebar offers three dark colour themes (Volt,
  the default, Aurora and Ice) and two effects levels (Full and Calm). Calm
  removes the motion and the blur. The computer's "reduce motion" setting always
  stops the motion.
- **What the browser remembers.** The appearance choices, and whether the
  sidebar was open in a wide window. Each browser on each computer keeps its
  own.
- **Reserved colours are unchanged in every theme:** red for "Beyond your
  notes", blue for "From the web", amber for errors, violet for "Key formula"
  and aqua for "Exam tip".
- **Pictures follow the theme.** Diagrams and charts are drawn in the colours of
  the theme in use.
- **Readable in every theme.** Text contrast is tested for each theme against
  the brightest the backdrop can be behind it.
- **Small fixes included:** the edit box fits its bubble at every width; the
  "message is no longer available" notice is styled; the browser tab gets an
  icon; the desktop icon is redrawn in the new colours.
- **Fits the window as before:** from 600px wide, with no sideways scrolling
  (section 8N).
- **Not included:** a light theme, phone layouts, any backend, settings or
  agent-instruction change, module tags on the example prompts, and sharing
  appearance choices between the two computers.

### Q. Small fixes (phase 36; planned 2026-11-10, not built)

Faults found in the reviews of phases 30 and 31, each older than the redesign. Frontend
only.
- **Opening a chat.** A chat opens at its end even when its last answer has
  diagrams, charts or images that are drawn after it opens.
- **Rename.** Choosing Rename from a chat's menu, by keyboard or mouse, puts
  the cursor in the title box with the title selected.
- **A chat's menu.** Closing it with Escape, or choosing Pin or Unpin, returns
  the keyboard focus to that chat's "…" button.
- **Starting a new chat** always shows the new chat screen, even at the moment
  a reply finishes (added from phase 31's review; to be confirmed).
- **Deleting the open chat** makes no failed request afterwards. The total
  cost still moves the chat's cost to "Deleted chats".
- **Sending the first message of a new chat** leaves the keyboard focus in the
  message box, as later messages do (added from phase 35's review; to be
  confirmed).

### R. Notes open in another app (phase 37; built 2026-11-18)

Found on 2026-11-18: on Windows, a lecture open in PowerPoint stopped the whole notes
update with "PermissionError". Now:
- A notes file that another app has open is skipped. Every other file still updates.
- The skipped file keeps its notes from the last update. It is never treated as
  deleted.
- The notes status names the skipped files and says to close them, then refresh.
  The next update reads them as usual.

### Completion evidence
At the end of each implementation phase only, require automated checks,
inspection of screenshots and an interactive browser walkthrough, following
`docs/PROCESS.md`. Record what was actually checked and any unperformed checks.
Each phase has testable checkpoints in `docs/PLAN.md`, including persistence,
keyboard interaction, failure paths and the existing whole-app quality gate.
All automated checks use fake models and made-up content. Real-model evaluation
still requires a separate explicit request.
