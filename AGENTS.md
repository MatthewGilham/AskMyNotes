# AskMyNotes

## What this is
A personal AI chatbot for one user, a university student: frontier-
chatbot features, plus agentic RAG over my university lecture slides.
It runs locally on my PC and is used in the browser.

## Your role
I direct the work and review it. You plan, build and check it, as
`docs/PROCESS.md` describes.

I'm also here to learn. Write plans I can review: say what each phase
builds and why you chose that approach. Explain your work when I ask,
at the level I ask for.

## Start here
Before planning, building or changing anything, or answering questions
about the app, read each of these files in full:

1. `docs/SPEC.md`: what the app must do
2. `docs/TECH_STACK.md`: the tech choices
3. `docs/CODE_STANDARDS.md`: how to write the code
4. `docs/PROCESS.md`: how to plan, build and check the work
5. `docs/DESIGN.md`: the look and layout
6. `docs/STATUS.md`: what's built so far and how to run it
7. `docs/PLAN.md`: the build plan, once it exists

## Improvements after pilot
The pilot is phases 1–13 of `docs/PLAN.md`; later phases are scoped in
`docs/SPEC.md` section 8. Phases 14–28 are built and Windows-verified:
navigation (14), selected-text questions (15), editing the latest question
(16), Windows desktop shortcut (17), document uploads and a larger context
budget (18), cost and context indicators (19), today's date, web search,
calculator, code blocks and callouts, diagrams and charts, and Python (20–25),
web search fixes (26), narrow windows (27, also checked by you) and citation
markers (28). Their MacBook checks stay open, except phase 17, which is
Windows-only.
Phases 29–35, the redesign (`docs/SPEC.md` section 8P), were planned on
2026-11-09 and their main decisions confirmed the same day. All seven are built
and Windows-verified (35, the finish, on 2026-11-11); their MacBook checks stay
open, as do my own checks for phases 34 and 35.
Phase 36, small fixes (`docs/SPEC.md` section 8Q), was planned on
2026-11-10; it is not built and waits for my go-ahead.
Phase 37, notes open in another app (`docs/SPEC.md` section 8R), was found,
built and Windows-verified on 2026-11-18; its MacBook check and my PowerPoint
check stay open.
Writing a plan does not authorise implementation. Preserve the pilot's history and distinguish
planned work from built features in `docs/STATUS.md`. The outstanding MacBook
checks for phases 13–16 remain outstanding.

## My system
Two computers, each with its own copy of the app, its own chats and its own
notes database: a Windows PC, with PowerShell as the terminal in VS Code, and a
MacBook (Apple silicon), with zsh. Give commands for both, or say which one a
command is for. Code must work on both. Python is managed with uv and the
frontend with npm.

## Rules
- At the end of each implementation phase, perform the three checks in
  `docs/PROCESS.md`: automated quality gate, screenshot inspection, and an
  interactive browser walkthrough. Run this review at phase completion only,
  not after each edit or subtask. Record evidence and any limitations honestly.
- Never change, move or delete anything in my notes folders. Only
  read them.
- Never create, change or delete files outside this repo. The only
  exception is uv's and npm's own package caches. Anything else a tool
  would download into my user folders, such as Playwright's browsers or
  AI models, is kept inside the project instead.
- Never install anything globally on my PC. Project packages go in the
  project, through uv or npm. The one exception is LibreOffice, which
  I've installed myself. The app uses it to convert `.ppt` files to
  `.pptx`.
- Never print, log or commit secrets. Keys live only in `.env`, which
  is never committed.
- Never run the evaluation unless I ask, because it costs money.
- Never use `git push --force`, and never rewrite git history.
- Never commit anything containing my lecture content: the converted
  Markdown notes, the `.pptx` copies made from `.ppt` files, the notes
  database, or uploaded images. They are
  listed in `.gitignore`. Check before every commit.

## Folders
What each top-level folder is for:

- `backend/askmynotes/`: the Python app (API, settings, start command),
  one folder per feature as they are added
- `backend/tests/`: pytest tests
- `frontend/`: the React + TypeScript app; `frontend/e2e/` holds the
  Playwright tests
- `assets/`: files that belong to neither backend nor frontend, such as the
  desktop shortcut's icon
- `docs/`: the specification, plan and other project documents
- `evaluation/`: evaluation test sets and, later, results
- `data/`: everything the app generates, including lecture content
  (created when first needed, never committed)
