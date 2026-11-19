# Process

## Planning
- Before any code, read every document in `docs/`. If anything is unclear, missing or contradictory,
  ask me first. When my answer changes a decision, update the relevant document, so the docs stay the
  single source of truth.
- Write the plan in `docs/PLAN.md`, in phases small enough to review in one sitting. For each, say what
  it builds, why at that point, and the approach and why.
- Each phase ends with a checklist of things that can be checked, not general goals.
- Wait for me to approve the plan before building.

### Improvements after pilot
- Phases 1–13 are the pilot record. Later work goes under "Improvements after pilot" in `docs/PLAN.md`,
  with new phase numbers.
- Each selected feature is its own task/phase. Subtasks have objective checkpoints and the test or manual
  check that evidences them. State dependencies and why the order was chosen.
- Mark proposals as awaiting approval in the plan, spec and status. Pilot approval doesn't approve new
  phases. Once approved, build one phase at a time.
- A documentation-only planning turn ends with a reviewable diff and summary: no implementing, paid calls
  or committing the proposal. Check document consistency, links and `git diff --check`.
- Record actual test results and platform coverage. Windows tests with a simulated Mac user agent don't
  prove macOS support. Keep unperformed MacBook checks explicitly open, and phase 13's check separate from
  new feature checks.

## Building
- One phase at a time, in plan order, carrying on without waiting unless I interrupt.
- Write each feature's tests alongside it, following `docs/CODE_STANDARDS.md`.
- Build only what the docs ask for, nothing ahead for later phases.
- When creating a folder for converted notes, the notes database, uploads or the chat database, add it
  to `.gitignore` in the same phase.

## The quality gate
Run these three levels at the end of each implementation phase only, not after each edit or subtask. If
verification finds a defect, fix it and recheck the affected results within that review, without repeating
unrelated successful checks.

**1. Automated checks**, for the whole app, all passing: all backend tests; the end-to-end tests that exist
so far; Ruff with no errors, and the frontend's linting and type checks; the frontend build; every item on
the phase's checklist ticked.

**2. Visual inspection.**
- Capture and actually view screenshots of the main states affected, with made-up content and fake models,
  including open menus/dialogs and relevant loading, stopped or error states.
- Check icons and symbols (including unexpected `?` or replacement characters), text, spacing, clipping,
  overlap, equations and readable controls. For UI changes, check 1280px and a wider desktop viewport.
- Keep screenshots in ignored `data/`. A saved screenshot isn't evidence unless the agent has viewed it.

**3. Interactive browser walkthrough.**
- Use the running app through the changed journeys, with Playwright or browser tools, exercising controls
  and inspecting the screens rather than relying on assertions.
- Cover the normal path and relevant edge cases, including keyboard focus, scrolling, menus and transitions.
  For a backend-only phase, walk through the affected journey.
- Headless with inspected screenshots is acceptable. Use fake models and isolated test data inside the repo.
- Record journeys, screenshots, results and actual platform in PLAN/STATUS. If a check can't be performed,
  record it as unperformed and explain why; never claim it passed.

All three are required before declaring a phase verified; they don't need a fresh audit of unrelated
features. Documentation-only updates use consistency checks and `git diff --check`, without launching the
app. This policy applies prospectively; don't rewrite old verification records as though these checks had
been performed.

Never commit while any of these fail. Never make a check pass by weakening it: don't delete, skip or loosen
a test, or change what it expects, unless the test itself is wrong. If you believe one is wrong, stop and
explain why.

## Finishing a phase
When the gate passes:
1. Tick the phase's checklist in `docs/PLAN.md`.
2. Update `docs/STATUS.md`: what's built, and how to run the app, tests and evaluation.
3. Commit, naming the phase, such as "Phase 2: chat storage".
4. Summarise: what it built, key decisions and why, which files matter most, and what to check by hand.
   Detailed but focused, not a line-by-line tour.

## When to stop and ask
Stop, explain and wait for me when a check still fails after a few genuine attempts; something in the docs
is impossible, contradictory or much harder than expected; you'd need to change a decision in the docs; or
you'd need a major new dependency not covered by `docs/TECH_STACK.md`. Say what you tried, the options, and
which you'd recommend.

## The evaluation
Never run it unless I ask, because it uses real models and costs money. When a phase changes the notes
database, search or agent instructions, remind me in the summary that it's a good time to run it.
