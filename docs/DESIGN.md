# Design

The app should look professionally designed: dark, slick and premium, with bold colour.
Layout and behaviour take inspiration from ChatGPT and Claude; the look is original,
copying no product's logo, name, colours or branding. The reference picture is
`docs/redesign-preview.html` (made-up content; it needs the internet for its fonts).
The pilot's look (violet and aqua on near-black) is recorded in `docs/PLAN.md`.

## The idea
- The app sits on a slow field of coloured light. Its sidebar, chat header and message
  box are panes of dark glass floating over it.
- While a reply is being written the app charges up: the light brightens and a band of
  it travels round the message box.
- The accent behaves like a highlighter: the open chat, search matches and selected text
  are marked with it.
- One bold thing at a time. The backdrop and the greeting are loud; everything you read
  is calm, on quiet surfaces.

## Colour
- **Dark only.** Three themes, chosen in the Appearance menu:
  - **Volt** (the default): lime `#ccff33` on deep plum `#0c0814`; accent 2 mint.
  - **Aurora**: violet `#a78bfa` and aqua `#22d3ee` on blue-black `#07090f`.
  - **Ice**: near-white `#f2f6ff` on near-black `#08090b`.
- **The accent** is for the send button, the mark, focus rings, the open chat,
  highlights and switched-on toggles; text on it uses the theme's "on accent" colour.
  Accent 2 is the other end of the accent gradient, and the colour of links.
- **Text:** `#f4f0fb`, muted `#b5aec6`, faint `#958ea8`. Faint text is only for panes and
  solid surfaces, never straight on the backdrop.
- **Reserved colours, the same in every theme:** red `#fb7185` for "Beyond your notes",
  blue `#60a5fa` for "From the web", amber `#f59e0b` for errors, violet `#a78bfa` for
  "Key formula", aqua `#22d3ee` for "Exam tip" and the context ring. None is used for
  anything else.
- **Contrast.** Text is at least 7:1, muted text, faint text and labels at least 4.5:1,
  against the brightest the backdrop can be behind a pane. `frontend/e2e/contrast.spec.ts`
  checks every theme and sets the backdrop's strength: Volt 0.16 at rest and 0.28
  charged, Aurora 0.24 and 0.42, Ice 0.22 and 0.42.
- **Selected text** is the full accent with dark text. **Keyboard focus** is a ring of the
  accent at 45%. **Code** keeps one set of highlighting colours in every theme.
- Every colour is a token in `frontend/src/design/tokens.css`; nothing else holds one.

## Type
- **Bricolage Grotesque** for the greeting, headings and titles (headings at weight 650
  and 88% width).
- **Geist** for everything you read, at 15px, with equal-width digits.
- **Geist Mono** for code. All three ship with the app.

## Glass
- One shared style (`design/glass.module.css`): the theme's panel colour, a hairline edge
  of white at 9%, a 28px blur of what is behind it, and a soft shadow. Menus and dialogs
  use the stronger hairline, white at 16%.
- The scrolling column is never blurred: bubbles, panels, pictures and chips sit on the
  panel colour without a blur. Labelled blocks are laid on the panel colour so their
  labels stay at 4.5:1 when the backdrop is charged.
- Tooltips stay solid with a hairline, so their small text is always readable.
- Dialogs and the picture viewer have 24px corners, over a dimmed page blurred by 6px.

## Layout
- **Sidebar:** a glass pane 284px wide with 24px corners, 12px in from the window's left,
  top and bottom; it collapses to a 60px rail of the same pane. New chat is the one tinted
  button; shortcut hints always show; the chat list fades out at its bottom; hovered rows
  get a faint white wash. The open chat has an accent wash fading right and a 3px glowing
  accent bar. A faint light follows the pointer (4% of the accent in Volt and Ice, 8% in
  Aurora). Notes status, "Refresh notes", the API cost and the Appearance button sit at
  its foot.
- **Main area:** reaches the window's right edge. The conversation and message box are a
  centred column up to 760px wide.
- **Chat header:** a glass pill 46px high, 12px from the top, centred and never wider than
  the column: the title (ending in "…" when long), the cost, the context ring and
  Questions. The conversation is see-through down to the pill's bottom edge and fully
  visible 24px below it; the first message, and any message you jump to, starts there.
- **Narrow windows:** no minimum width; designed and checked from 600px to 1600px, never
  scrolling sideways. Below 900px the sidebar starts as the rail; opened, it slides in from
  the left edge over the rail, above a `--color-overlay` backdrop, keeping its 12px gutter;
  its menu and dialogs open above it.

## New chat screen
- The mark (7% of the window's width, 52px to 92px, with a soft accent glow) beside the
  greeting, "Happy Tuesday," then the name from settings, on two lines but one sentence to a
  screen reader. Bricolage Grotesque at weight 750 and 82% width, 6.2% of the window's width
  between 34px and 84px.
- A band of the accent sweeps across the greeting once, over 2.6 seconds, as the screen loads.
- Example prompts, including one about my modules, are cards: 16px corners, a hairline and
  the panel colour, two columns (one below 700px). A card lifts 2px on hover and its edge
  takes the accent; disabled, it is at half strength. After the first message the
  conversation takes over.

## The message box
- A glass pane with 26px corners. Its edge is a separate 1px layer: white at 16% at rest,
  the accent gradient with a soft glow while the cursor is in the box, and a travelling
  band while a reply is written.
- The Python button sits beside the paperclip: a 32px pill, a hairline outline when off and
  filled with the accent when on, with `aria-pressed`, a tooltip and a small "Python on"
  chip above the input. It switches off after sending. There is no web search button.
- The send button is 40px, the accent gradient, glowing on hover; disabled, a faint wash. It
  becomes Stop while a reply is written.
- Attachments: images by the button, dragging or Ctrl+V, shown as previews with 12px
  corners. Documents are chips on a faint white wash: a Lucide file-type icon, the name
  shortened in the middle, the size and a remove button; chips wrap rather than overflow.
  A muted "Reading files…" while documents are read.
- The drop cover is a pane with 24px corners and a dashed accent outline, over the main area.
- Errors in the box stay amber on their tint, with 12px corners. While notes update, the box
  says it is waiting.

## Messages
- **Yours:** the panel colour under a soft white gradient, a hairline and 24px corners, the
  bottom right one 8px. Edit sits just left of its bottom corner on hover and focus, only on
  the latest question.
- **The editor** asks for 560px and never takes more than its bubble has; its text area is on
  a darker inset; Enter adds a newline; "Cancel" and "Save & resend" (the accent gradient),
  with a note that saving replaces the latest answer. The old answer stays until the server
  accepts; a refusal shows an inline amber error and keeps the text.
- **Answers:** full width, on no surface of their own.
- **"Beyond your notes" and "From the web":** a 3px left edge in their colour, their tint
  fading right, 16px corners on the right and the label at the top. Web citations are small
  pills with the site's name, opening in a new tab.
- **Callouts:** a 1px outline in their colour at 40% (a hairline for the neutral two), 16px
  corners, their tint, an icon and a label: "Key formula" violet, "Exam tip" aqua, "Common
  mistake" neutral with a warning icon, "Worked example" neutral.
- **Code:** a darker inset (black at 34%) with a hairline and 16px corners; the language at
  top left and Copy at top right. Inline code sits on a faint wash.
- **Tables** have hairlines, a stronger one under the header, muted header text, and scroll
  inside themselves when wide.
- **Status lines** ("Searching your notes…", "Searching the web…" with the globe, "Calculating…",
  "Running Python…") are muted, with a band of the accent passing through the words every 1.6
  seconds.
- **Errors** are amber with an icon and Retry, under my message, never raw technical text.
  **Stopped** is a small marker. Copy and Regenerate appear on hover and focus.
- **Jump to latest** is a glass pill above the message box. **The missing-message notice** is a
  quiet pill in muted text under the header. **Ask about this** is an accent pill kept inside the
  viewport; it focuses the composer with a compact "Regarding" preview (expandable, removable)
  above the input. "Explain this" and "Show an example" fill an empty input only. Whole equations
  render as maths; a partial selection expands to the full expression.
- **Questions** in the header opens a scrollable menu of numbered, shortened questions ("Image
  question" for image-only ones). A message you jump to is focused, briefly highlighted in aqua,
  with its ring following its corners.

## Under an answer
- **The pill** that opens Sources, Found online and Working is 34px high, the panel colour with a
  hairline, in muted text; all three are collapsed by default.
- **Sources:** a glyph of two small slides and "Sources (3)". Opened, a row of slide cards, 176px
  wide at 4 by 3, with 12px corners, a strong hairline and a soft white wash: the module as an
  accent tag at the top, the file name muted and cut after three lines, and "Slide 8" in display
  type. The row scrolls sideways and takes keyboard focus for the arrow keys; a screen reader hears
  a list.
- **Found online** ("Found online (3 cited, 5 searched)", with the globe) and **Working (n)** open
  into a panel of the panel colour with 16px corners and faint small-capitals group headings:
  "Searched for", "Cited in the answer" and "Searched, not cited" (muted); calculations as
  expression and result with rendered maths, Python as highlighted code with its output on the
  darker inset. Long titles and addresses wrap.
- **Python's pictures** show under the answer and open in a glass viewer; other files are chips
  with a download button.
- **Diagrams and charts** sit in boxes of the panel colour with 16px corners and scroll sideways
  inside them. Diagrams are drawn from the theme's tokens and redrawn when it changes. Each theme
  has six chart colours, each at least 3:1 on a pane and never the red, amber or web blue. A
  muted "Drawing…" while streaming; one that fails shows its source with a muted note.

## Cost and context readouts
In the header, left of Questions: a muted cost (`$0.012`) and a 16px ring filling with the share of
the context budget used, aqua, amber from 90%. At the sidebar's foot: "API cost $1.24". Each is
focusable, with an accessible name and a tooltip on hover and focus, one item per line. New
unsaved chats show neither chat readout, and nothing in them animates.

## Motion
- **The backdrop** drifts slowly; only its position changes, never its shape.
- **Charging up:** from the moment a reply starts until it finishes, is stopped or fails, the
  backdrop's lights rise to their charged strength over 1.2 seconds, and a band of the accent
  (accent 2 leading into the accent) travels round the message box's 1.5px edge every 2.2 seconds.
- **The moving message box:** on the first message of a new chat it glides from the centre to the
  bottom in half a second, easing to a stop, through View Transitions. Only the box moves, without
  blur while moving; the rest of the page changes at once.
- **The caret:** an 8px by 17px accent block with a soft glow after the last paragraph, heading or
  list item of a streaming reply, blinking about once a second. A reply ending in a table, code or a
  picture has none.
- **Small motions:** slide cards slide in 18px and fade over 0.45 seconds, one after another, without
  turning; menus, dialogs and their dimmed page fade in over 200ms without moving; prompt cards lift.
- **Calm** stops the drifting, the travelling band (the whole edge shows the accent gradient instead),
  the moving box and the blur. The backdrop still brightens, and the caret, status lines and small
  motions stay.
- **Reduced motion** (the computer's setting) stops all of the above whatever the app's setting; the
  caret shows without blinking; the blur stays.

## Appearance menu
A quiet row with a palette icon at the sidebar's foot, under the API cost, and a palette icon at the
bottom of the rail. Its menu opens above the row (beside the icon on the rail), with "Theme" (Volt,
Aurora, Ice) and "Effects" (Full, Calm) as small-capitals headings, a hairline between them and an
accent tick beside each choice in use. It works by keyboard and stays open after a choice. The browser
remembers the choices and whether the sidebar is open in a wide window, so each browser on each
computer keeps its own.

## Icons
- The mark is two offset slides, the front one cut by a lightning bolt, in the theme's accent gradient.
- The browser tab icon (`frontend/public/favicon.svg`) and the Windows desktop icon
  (`assets/askmynotes.ico`, seven sizes from 16 to 256, each rendered directly) show the mark in Volt
  colours on a rounded tile of Volt's base colour. The bolt and gradient must read at 16 and 32 pixels.

## Accessibility
- Visible keyboard focus in the accent on every control; hover actions also appear on focus.
- Every control has an accessible name; icon-only controls use `aria-label`, not a `title` that
  contains another control's name.
- Respect reduced motion when scrolling, highlighting or animating.

## Checking the design
At the end of each implementation phase only, do the visual inspection and walkthrough in
`docs/PROCESS.md`, at 1280px and a wider size, and in each theme when the look changes. Screenshots
alone don't establish behaviour.
