# Code standards

## Priorities
1. **It works**: the code does what the spec says, and the tests prove it.
2. **It's readable**: someone learning Python and TypeScript can follow
   what each part does and why.
3. **It's short**: no more code than the job needs.

When these conflict, the higher one wins.

## Readability
- Names say what things are and do: `search_notes`, `chats_by_day`,
  not `process`, `data` or `x`.
- Functions do one job and are short enough to read in one go.
- Prefer plain, step-by-step code over clever one-liners.
- Every module, class and public function has a docstring saying what
  it's for.
- Comments explain *why*, not *what*: the reason for a decision or a
  non-obvious step, not a repeat of the line below.
- Code is grouped by feature, so related code lives together.
- Each file starts with a short comment or docstring explaining what
  it does and how it fits into the app, because I'm learning from this
  code. Beyond that, comment only where it helps; don't comment every
  line.

## Correctness
- Python uses type hints everywhere. TypeScript uses strict mode.
- Data coming in from outside, such as API requests, files and model
  output, is checked at the boundary with Pydantic models. Inside the
  app, code trusts its own functions.
- No overly defensive code: no `try`/`except` that hides errors, no
  silent fallback values, no checks for things that can't happen.
- Errors surface clearly, with a message that says what went wrong.

## Settings and secrets
- API keys and model names live in `.env`, and nowhere else.
- Paths, module lists and other settings live in settings files, not
  in the code.
- Secrets are never printed, logged or committed.

## Tests
- Tests follow `docs/TECH_STACK.md`: they cover what matters, and are
  written alongside the code, not afterwards.
- Tests are named after the behaviour they check, such as
  `test_deleting_a_chat_deletes_its_messages`.
- At phase end only, follow the three verification levels in `docs/PROCESS.md`.
  Passing tests alone does not establish visual correctness.

## Style
- Python is formatted and linted with Ruff.
- TypeScript is formatted and linted with the tools that fit the
  frontend; choose them in the plan.
- No unused code, imports or commented-out code is left behind.
