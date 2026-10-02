"""
University Assistant: the Gradio chat app for the personal knowledge worker.

Run from the project root:
    python app.py

How it works:
1. You type a question (or click an example). add_user_message() shows it in the chat straight away.
2. respond() streams the answer from stream_answer() in rag/retrieval.py into the chat.
3. While an answer is streaming, the send button becomes a stop button.
"""
import html
import time
import asyncio
import gradio as gr
from dotenv import load_dotenv

from rag.agent import stream_agent_answer
from theme import THEME, CSS, LOGO_SVG

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Shown as the pill in the header - update it if you change the answer model in rag/retrieval.py
ANSWER_MODEL = "gpt-6-luna"

# Seconds to pause between streamed pieces (0 = as fast as the model sends them)
STREAM_DELAY = 0.02

# Colour for each module's label on the example cards
MODULE_COLOURS = {
    "Business Law": "#60a5fa",
    "Financial Reporting": "#fbbf24",
    "Management Accounting": "#34d399",
}

# (module, question) - shown as cards on the welcome screen
EXAMPLES = [
    ("Business Law", "Explain the Caparo test for a duty of care"),
    ("Financial Reporting", "How does the IAS 16 revaluation model work?"),
    ("Management Accounting", "How do you calculate a sales-mix variance?"),
    ("Business Law", "What's the difference between wrongful and unfair dismissal?"),
]

# Must match the heading the system prompt tells the model to use
OUTSIDE_HEADING = "⚠️ Outside your notes (general knowledge):"
CALLOUT_OPEN = '<div class="outside"><div class="outside-label">⚠️ Outside your notes · general knowledge</div>'

WELCOME = """<div class="hero-eyebrow">✦ Grounded in your lecture and seminar notes</div>

# What do you want to revise?

Ask anything from your lecture slides, seminar slides or seminar solutions. Answers come from your notes, and anything else is clearly labelled."""

HEADER = f"""
<div class="brand">
  <div class="brand-mark">{LOGO_SVG}</div>
  <div class="brand-title">AskMyNotes</div>
  <div class="brand-divider"></div>
  <span class="model-pill">{ANSWER_MODEL}</span>
</div>
"""

FOOTER = """
<div class="dock-footer">
  <span class="note">Answers come from your notes · <b>⚠️ Outside your notes</b> marks anything else</span>
  <span class="keys"><kbd>Enter</kbd> to send · <kbd>Shift</kbd> + <kbd>Enter</kbd> for a new line</span>
</div>
"""


def example_css():
    """Give each example card its module label and colour (CSS can't read them from Python otherwise)."""
    rules = []
    for i, (module, _question) in enumerate(EXAMPLES, start=1):
        colour = MODULE_COLOURS.get(module, "#a78bfa")
        rules.append(
            f'button.example:nth-child({i}) {{ --module-colour: {colour}; }}\n'
            f'button.example:nth-child({i})::before {{ content: "{module}"; }}'
        )
    return "\n".join(rules)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def text_of(content):
    """
    Get plain text from a chat message's content.
    Gradio can store content as a plain string, or as a list of parts like
    [{"type": "text", "text": "..."}]. This handles both.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def format_answer(answer):
    """
    Show the "Outside your notes" section as a highlighted callout box.
    Everything before the heading is left exactly as the model wrote it.
    """
    if OUTSIDE_HEADING not in answer:
        return answer
    
    notes_part, outside_part = answer.split(OUTSIDE_HEADING, 1)
    return (
        f"{notes_part.rstrip()}\n\n"
        f"{CALLOUT_OPEN}\n\n"
        f"{outside_part.strip()}\n\n</div>"
    )

def plain_text(answer):
    answer = answer.replace(CALLOUT_OPEN, OUTSIDE_HEADING)
    answer = answer.replace("</div>", "")
    return answer
    



# ---------------------------------------------------------------------------
# Chat functions (these are what the textbox, examples and buttons call)
# ---------------------------------------------------------------------------

def add_user_message(message, history):
    """Show the user's message in the chat immediately and clear the textbox."""
    if not message.strip():
        return "", history
    return "", history + [{"role": "user", "content": message}]


def add_example(example: gr.SelectData, history):
    """Clicking an example question puts it in the chat as if it had been typed."""
    return history + [{"role": "user", "content": example.value["text"]}]


async def respond(history):
    """Stream the answer to the latest user message into the chat."""
    if not history or history[-1]["role"] != "user":
        yield history
        return

    messages = [
    {"role": m["role"],
    "content": plain_text(text_of(m["content"])) if m["role"] == "assistant" else text_of(m["content"])}
    for m in history]
    print(messages)

    answer = ""
    try:
        async for piece in stream_agent_answer(messages):
            await asyncio.sleep(STREAM_DELAY)
            if not answer:
                # First words have arrived: add the reply bubble now, so the
                # typing dots stay on screen while the notes are being searched
                history = history + [{"role": "assistant", "content": ""}]
            answer += piece
            history[-1]["content"] = format_answer(answer)
            yield history
            await asyncio.sleep(STREAM_DELAY)
    except Exception as error:
        message = f"Sorry, something went wrong: {html.escape(str(error))}"
        if answer:
            history[-1]["content"] = format_answer(answer) + f"\n\n*{message}*"
        else:
            history = history + [{"role": "assistant", "content": message}]
        yield history


def clear_chat():
    """Start a new, empty conversation."""
    return []


def show_stop_button():
    """While an answer streams, swap the send button for a stop button."""
    return gr.Textbox(submit_btn=False, stop_btn=True)


def show_send_button():
    """Once the answer finishes (or is stopped), bring the send button back."""
    return gr.Textbox(submit_btn=True, stop_btn=False)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

def build_ui():
    with gr.Blocks(fill_height=True, title="AskMyNotes") as ui:
        with gr.Column(elem_classes="shell", scale=1):
            # Header: full-width bar with the brand and model on the left, New chat on the right
            with gr.Row(elem_classes="topbar", equal_height=True):
                gr.HTML(HEADER, padding=False, container=False)
                new_chat = gr.Button("＋  New chat", variant="secondary", size="sm",
                                     scale=0, min_width=0, elem_classes="new-chat")

            chatbot = gr.Chatbot(
                height="100%",  # theme.py makes the chat fill the space between header and input
                show_label=False,
                container=False,
                buttons=["copy"],
                placeholder=WELCOME,
                examples=[{"text": question} for _module, question in EXAMPLES],
                sanitize_html=False,  # lets the "Outside your notes" callout keep its styling
                elem_classes="chat",
            
            )

            # Input dock: the message box and a line of hints underneath
            with gr.Column(elem_classes="dock"):
                message = gr.Textbox(
                    placeholder="Ask about your notes…",
                    show_label=False,
                    container=False,
                    autofocus=True,
                    lines=1,
                    max_lines=6,
                    submit_btn=True,
                    stop_btn=False,
                    elem_classes="ask",
                )
                gr.HTML(FOOTER, padding=False, container=False)

        # Typing + Enter (or the send button) and clicking an example both:
        # 1) show the question, 2) swap in the stop button, 3) stream the answer, 4) swap back
        typed = message.submit(add_user_message, inputs=[message, chatbot], outputs=[message, chatbot], queue=False)
        clicked = chatbot.example_select(add_example, inputs=chatbot, outputs=chatbot, queue=False)

        answering = []
        for trigger in (typed, clicked):
            trigger.then(show_stop_button, outputs=message, queue=False)
            answer = trigger.then(respond, inputs=chatbot, outputs=chatbot)
            answer.then(show_send_button, outputs=message, queue=False)
            answering.append(answer)

        # The stop button cancels whichever answer is streaming; the text so far stays in the chat
        message.stop(None, None, None, cancels=answering)

        new_chat.click(clear_chat, outputs=chatbot, cancels=answering).then(
            show_send_button, outputs=message, queue=False
        )

    return ui


if __name__ == "__main__":
    build_ui().launch(inbrowser=True, theme=THEME, css=CSS + example_css(), footer_links=[])