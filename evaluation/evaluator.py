"""
Evaluation dashboard for the University Assistant (agentic RAG).

Run from the project root:
    python -m evaluation.evaluator

Retrieval tab: scores the search engine itself (Chroma + reranker) on each test question.
Answers tab:   runs every test through the agent, has the judge grade the answer, and
               shows how often the agent chose to search the notes.
"""
import html
from collections import defaultdict

import gradio as gr
import pandas as pd
from dotenv import load_dotenv

from evaluation.eval import evaluate_all_retrieval, evaluate_all_answers

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
MODULES = {
    "Business Law": {"code": "BUSB5025", "short": "Business Law", "color": "#60a5fa"},
    "Financial Reporting": {"code": "BUSB5020", "short": "Fin. Reporting", "color": "#fbbf24"},
    "Intermediate Management Accounting": {"code": "BUSB5023", "short": "Mgmt Accounting", "color": "#34d399"},
}
ALL_MODULES = "All modules"

TEST_SETS = {
    "Small (50 tests)": "tests_small.jsonl",
    "Large (135 tests)": "tests.jsonl",
}

CATEGORIES = ["direct_fact", "definition", "calculation", "spanning", "paraphrased", "not_covered"]

# (green at or above, amber at or above) - anything lower is red
THRESHOLDS = {
    "mrr": (0.9, 0.75),
    "ndcg": (0.9, 0.75),
    "coverage": (90.0, 75.0),
    "answer": (4.5, 4.0),     # 1-5 scale
    "search_rate": (95.0, 85.0),  # % of uni questions where the agent searched the notes
}
STATUS = {
    "good": {"color": "#22c55e", "icon": "✓", "label": "Good"},
    "ok": {"color": "#f59e0b", "icon": "▲", "label": "OK"},
    "bad": {"color": "#ef4444", "icon": "✕", "label": "Needs work"},
}

# Palette (matches the chat app)
ACCENT = "#a78bfa"
ACCENT_DEEP = "#7c3aed"
GLOW = "139, 92, 246"
BG = "#08070f"
PANEL = "#110f1c"
BORDER = "#26213d"
TEXT = "#e6e3f2"
MUTED = "#8b86a6"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def status_of(value: float, metric: str) -> dict:
    green, amber = THRESHOLDS[metric]
    if value >= green:
        return STATUS["good"]
    if value >= amber:
        return STATUS["ok"]
    return STATUS["bad"]


def module_of(test) -> str:
    return getattr(test, "module", None) or "Unknown"


def mean(values) -> float:
    return sum(values) / len(values) if values else 0.0


def pretty(category: str) -> str:
    return category.replace("_", " ").capitalize()


def short_name(module: str) -> str:
    """Shorter module names so the results table stays readable."""
    return MODULES.get(module, {}).get("short", module)


def filter_rows(rows: list[dict], module: str) -> list[dict]:
    if not rows or module == ALL_MODULES:
        return rows or []
    return [r for r in rows if r["Module"] == module]


# ---------------------------------------------------------------------------
# Theme and styling - dark midnight violet, same look as the chat app
# ---------------------------------------------------------------------------
violet = gr.themes.Color(
    c50="#f5f3ff", c100="#ede9fe", c200="#ddd6fe", c300="#c4b5fd",
    c400="#a78bfa", c500="#8b5cf6", c600="#7c3aed", c700="#6d28d9",
    c800="#5b21b6", c900="#4c1d95", c950="#2e1065", name="midnight_violet",
)
_base = gr.themes.Base(
    primary_hue=violet,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
    radius_size=gr.themes.sizes.radius_lg,
)


def _dual(theme, **colours):
    """Use the same colour in light and dark mode, so the dashboard always looks the same."""
    out = {}
    for name, value in colours.items():
        if hasattr(theme, name):
            out[name] = value
        if hasattr(theme, name + "_dark"):
            out[name + "_dark"] = value
    return out


THEME = _base.set(**_dual(
    _base,
    body_background_fill=BG, background_fill_primary=PANEL, background_fill_secondary=BG,
    block_background_fill=PANEL, block_border_color=BORDER, border_color_primary=BORDER,
    body_text_color=TEXT, body_text_color_subdued=MUTED,
    block_label_text_color=MUTED, block_title_text_color=TEXT, block_info_text_color=MUTED,
    color_accent=ACCENT, color_accent_soft=f"rgba({GLOW}, 0.14)",
    input_background_fill="#161327", input_border_color=BORDER,
    button_primary_background_fill=ACCENT_DEEP, button_primary_background_fill_hover="#8b5cf6", button_primary_text_color="#ffffff",
    button_primary_border_color=ACCENT_DEEP,
    checkbox_background_color_selected=ACCENT_DEEP, checkbox_border_color_selected=ACCENT_DEEP,
    checkbox_label_background_fill="#161327", checkbox_label_background_fill_hover="#1d1935",
    checkbox_label_background_fill_selected=f"rgba({GLOW}, 0.22)", checkbox_label_border_color=BORDER,
    checkbox_label_border_color_selected=ACCENT, checkbox_label_text_color=TEXT,
    checkbox_label_text_color_selected="#ffffff", checkbox_background_color="#0d0b18",
    table_even_background_fill=PANEL, table_odd_background_fill="#0d0b18",
    table_border_color=BORDER,
))

CSS = f"""
.gradio-container {{
    max-width: 1200px !important; width: 100% !important; margin: 0 auto !important;
    background: radial-gradient(900px 420px at 50% -10%, rgba({GLOW}, 0.18), transparent 70%), {BG} !important;
}}
.gradio-container main, .gradio-container .main {{ width: 100% !important; }}

/* Header */
.dash-header {{ display: flex; align-items: center; gap: 14px; margin: 6px 0 4px; }}
.dash-mark {{
    width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0; display: grid; place-items: center;
    background: linear-gradient(135deg, {ACCENT_DEEP}, #4c1d95);
    box-shadow: 0 0 0 1px rgba(255,255,255,0.12) inset, 0 0 24px rgba({GLOW}, 0.45);
    color: #fff; font-size: 19px;
}}
.dash-title {{ font-size: 22px; font-weight: 700; letter-spacing: -0.01em; color: #f5f3ff; line-height: 1.2; }}
.dash-sub {{ font-size: 13.5px; color: {MUTED}; margin-top: 2px; }}

/* Controls card */
.controls {{ border: 1px solid {BORDER} !important; border-radius: 14px !important; padding: 6px !important;
             background: rgba(17, 15, 28, 0.7) !important; }}

.panel {{ min-height: 260px; }}
.empty {{ min-height: 220px; display: flex; flex-direction: column; align-items: center; justify-content: center;
          gap: 6px; text-align: center; color: {MUTED};
          border: 1px dashed {BORDER}; border-radius: 14px; background: rgba(17, 15, 28, 0.5); }}
.empty b {{ color: {TEXT}; font-size: 15px; }}

.section-title {{ font-size: 12px; font-weight: 650; text-transform: uppercase; letter-spacing: .06em;
                  color: {MUTED}; margin: 28px 0 10px; }}

/* Score tiles */
.tiles {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
.tiles.four {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
@media (max-width: 960px) {{ .tiles.four {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 760px) {{ .tiles, .tiles.four {{ grid-template-columns: 1fr; }} }}
.tile {{ background: linear-gradient(180deg, #15122a, {PANEL}); border: 1px solid {BORDER};
         border-radius: 14px; padding: 16px 18px; }}
.tile .top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
.tile .name {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
.tile .value {{ font-size: 34px; font-weight: 700; color: #fbfaff; margin: 8px 0 4px;
                font-variant-numeric: tabular-nums; line-height: 1.1; letter-spacing: -0.02em; }}
.tile .hint {{ font-size: 12.5px; color: {MUTED}; line-height: 1.45; }}
.badge {{ font-size: 11.5px; font-weight: 600; padding: 3px 9px; border-radius: 999px; white-space: nowrap;
          color: {TEXT}; background: color-mix(in srgb, var(--status) 18%, transparent);
          border: 1px solid color-mix(in srgb, var(--status) 45%, transparent); }}

/* Agent routing strip */
.routing {{ margin-top: 12px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 22px;
            padding: 12px 16px; border-radius: 12px; border: 1px solid {BORDER};
            background: color-mix(in srgb, var(--status) 8%, {PANEL}); }}
.routing .label {{ font-size: 12px; font-weight: 650; text-transform: uppercase; letter-spacing: .06em; color: {MUTED}; }}
.routing .stat {{ font-size: 14px; color: {TEXT}; }}
.routing .stat b {{ font-variant-numeric: tabular-nums; color: #fbfaff; }}
.routing .warn {{ color: #fca5a5; }}

.summary {{ margin-top: 12px; font-size: 14px; color: {TEXT}; line-height: 1.6; }}
.summary .muted {{ color: {MUTED}; }}

/* Module x category grid */
.grid-wrap {{ overflow-x: auto; }}
table.grid {{ width: 100%; border-collapse: separate !important; border-spacing: 4px !important; border: none !important;
              font-size: 13px; margin: 0 !important; background: transparent !important; }}
table.grid tr, table.grid th, table.grid td {{ border: none !important; background: transparent; }}
table.grid th {{ font-weight: 600; color: {MUTED}; text-align: center; padding: 4px; white-space: nowrap; }}
table.grid th.mod {{ text-align: left; color: {TEXT}; font-size: 13.5px; padding-right: 12px; }}
table.grid td {{ text-align: center; padding: 10px 6px; border-radius: 9px; color: #fbfaff;
                 font-variant-numeric: tabular-nums; font-weight: 600;
                 background: color-mix(in srgb, var(--status) 18%, transparent) !important; }}
table.grid td.all {{ box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--status) 55%, transparent); }}
table.grid td.na {{ background: transparent !important; color: {MUTED}; font-weight: 400; }}
table.grid td small {{ display: block; font-weight: 400; font-size: 11px; color: {MUTED}; }}
.dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 8px; vertical-align: middle; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: {MUTED}; margin-top: 10px; }}
.legend i {{ display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }}

/* Results table: same font as the rest of the page */
.results-table * {{ font-family: Inter, ui-sans-serif, system-ui, sans-serif !important; }}
.results-table th {{ white-space: nowrap; }}

/* Tabs */
.tabs button[role="tab"][aria-selected="true"] {{ color: {ACCENT} !important; border-color: {ACCENT} !important; }}
"""

HEADER = """
<div class="dash-header">
  <div class="dash-mark">✦</div>
  <div>
    <div class="dash-title">University Assistant · Evaluation</div>
    <div class="dash-sub">How well the agent finds, uses and answers from my Year 2 notes.</div>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# HTML pieces
# ---------------------------------------------------------------------------
def empty_panel(title: str, hint: str) -> str:
    return f"<div class='empty'><b>{html.escape(title)}</b><span>{html.escape(hint)}</span></div>"


def tile(name: str, value: float, metric: str, fmt: str, hint: str) -> str:
    s = status_of(value, metric)
    return f"""
    <div class="tile">
      <div class="top"><span class="name">{name}</span>
        <span class="badge" style="--status:{s['color']}">{s['icon']} {s['label']}</span></div>
      <div class="value">{fmt.format(value)}</div>
      <div class="hint">{hint}</div>
    </div>"""


def routing_html(rows: list[dict]) -> str:
    """How often the agent chose to search the notes. Every test is a uni question, so it should be ~100%."""
    counts = [r["Searches"] for r in rows if r["Searches"] is not None]
    if not counts:
        return ""  # eval.py isn't passing the search count yet
    searched = sum(1 for c in counts if c > 0)
    rate = searched / len(counts) * 100
    skipped = len(counts) - searched
    s = status_of(rate, "search_rate")
    skipped_text = (f"<span class='stat warn'><b>{skipped}</b> answered from memory without searching</span>"
                    if skipped else "<span class='stat'>Searched for every question</span>")
    return f"""
    <div class="routing" style="--status:{s['color']}">
      <span class="label">Agent searching</span>
      <span class="badge" style="--status:{s['color']}">{s['icon']} {s['label']}</span>
      <span class="stat">Searched the notes on <b>{searched}/{len(counts)}</b> questions ({rate:.0f}%)</span>
      <span class="stat"><b>{mean(counts):.1f}</b> searches per question on average</span>
      {skipped_text}
    </div>"""


def module_name_html(name: str) -> str:
    color = MODULES.get(name, {}).get("color", "#8a8a85")
    return f"<span class='dot' style='background:{color}'></span>{html.escape(name)}"


def summary_html(rows: list[dict], key: str, fmt: str, n_text: str) -> str:
    """One plain-English line naming the strongest and weakest module/category combos."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["Module"], r["Category"])].append(r[key])
    ranked = sorted(((mean(v), m, c) for (m, c), v in groups.items() if len(v) >= 3))
    if len(ranked) < 2:
        return f"<div class='summary muted'>{n_text}</div>"
    low, high = ranked[0], ranked[-1]
    return f"""
    <div class="summary">
      Weakest area: <b>{html.escape(low[1])} · {pretty(low[2])}</b> ({fmt.format(low[0])}).
      Strongest: <b>{html.escape(high[1])} · {pretty(high[2])}</b> ({fmt.format(high[0])}).
      <span class="muted">{n_text}</span>
    </div>"""


def grid_html(rows: list[dict], key: str, metric: str, fmt: str) -> str:
    """Module x category table; each cell is the average score, tinted by status."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["Module"], r["Category"])].append(r[key])
        groups[(r["Module"], "all")].append(r[key])

    modules = [m for m in list(MODULES) + ["Unknown"] if any(r["Module"] == m for r in rows)]
    present = {r["Category"] for r in rows}
    categories = [c for c in CATEGORIES if c in present] + sorted(present - set(CATEGORIES))

    head = "".join(f"<th>{pretty(c)}</th>" for c in categories) + "<th>Overall</th>"
    body = ""
    for m in modules:
        cells = ""
        for c in categories + ["all"]:
            scores = groups.get((m, c), [])
            if not scores:
                cells += "<td class='na'>–</td>"
                continue
            avg = mean(scores)
            s = status_of(avg, metric)
            cls = "all" if c == "all" else ""
            tip = html.escape(f"{m} · {pretty(c)}: {fmt.format(avg)} across {len(scores)} tests")
            cells += (f"<td class='{cls}' style='--status:{s['color']}' title='{tip}'>"
                      f"{fmt.format(avg)}<small>{len(scores)} tests</small></td>")
        body += f"<tr><th class='mod'>{module_name_html(m)}</th>{cells}</tr>"

    green, amber = THRESHOLDS[metric]
    legend = f"""
    <div class="legend">
      <span><i style="background:{STATUS['good']['color']}"></i>✓ Good (≥ {fmt.format(green)})</span>
      <span><i style="background:{STATUS['ok']['color']}"></i>▲ OK (≥ {fmt.format(amber)})</span>
      <span><i style="background:{STATUS['bad']['color']}"></i>✕ Needs work</span>
    </div>"""
    return f"<div class='grid-wrap'><table class='grid'><tr><th></th>{head}</tr>{body}</table></div>{legend}"


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
RETRIEVAL_EMPTY = empty_panel("No retrieval results yet",
                              "Press 'Run retrieval evaluation' to score how well the search engine finds the right chunks.")


def run_retrieval_evaluation(test_set: str, module: str, progress=gr.Progress()):
    rows = []
    for test, result, prog_value in evaluate_all_retrieval(TEST_SETS[test_set]):
        rows.append({
            "Module": module_of(test),
            "Category": test.category,
            "Question": test.question,
            "MRR": round(result.mrr, 3),
            "nDCG": round(result.ndcg, 3),
            "Coverage %": round(result.keyword_coverage, 1),
            "_scored": bool(test.keywords),  # not_covered tests have no keywords to find
        })
        progress(prog_value, desc=f"Retrieval: test {len(rows)} ({module_of(test)})")
    return (rows, *render_retrieval(rows, module))


def render_retrieval(rows: list[dict], module: str):
    rows = filter_rows(rows, module)
    if not rows:
        return RETRIEVAL_EMPTY, gr.update(value=None, visible=False)

    scored = [r for r in rows if r["_scored"]]
    skipped = len(rows) - len(scored)
    n_text = f"{len(scored)} tests scored; {skipped} not_covered tests skipped (no keywords to find)."

    panel = f"""
    <div class="tiles">
      {tile("MRR", mean([r["MRR"] for r in scored]), "mrr", "{:.2f}",
            "How near the top the first relevant chunk appears. 1.00 = always first.")}
      {tile("nDCG", mean([r["nDCG"] for r in scored]), "ndcg", "{:.2f}",
            "How well all the relevant chunks are ranked, not just the first.")}
      {tile("Keyword coverage", mean([r["Coverage %"] for r in scored]), "coverage", "{:.0f}%",
            "Share of expected keywords found anywhere in the retrieved chunks.")}
    </div>
    {summary_html(scored, "MRR", "{:.2f}", n_text)}
    <div class="section-title">MRR by module and question type</div>
    {grid_html(scored, "MRR", "mrr", "{:.2f}")}"""

    table = (pd.DataFrame(scored).drop(columns="_scored")
             .assign(Module=lambda d: d["Module"].map(short_name),
                     Category=lambda d: d["Category"].map(pretty))
             .sort_values(["MRR", "Coverage %"]).reset_index(drop=True))
    return panel, gr.update(value=table, visible=True)


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------
ANSWER_EMPTY = empty_panel("No answer results yet",
                           "Press 'Run answer evaluation' to run every test through the agent and have the judge grade it.")


def run_answer_evaluation(test_set: str, module: str, progress=gr.Progress()):
    rows = []
    for item in evaluate_all_answers(TEST_SETS[test_set]):
        # eval.py yields (test, result, searches, progress); older versions yield (test, result, progress)
        if len(item) == 4:
            test, result, searches, prog_value = item
        else:
            (test, result, prog_value), searches = item, None
        rows.append({
            "Module": module_of(test),
            "Category": test.category,
            "Question": test.question,
            "Searches": searches,
            "Accuracy": result.accuracy,
            "Completeness": result.completeness,
            "Relevance": result.relevance,
            "Grounding": result.grounding,
            "Feedback": getattr(result, "feedback", ""),
        })
        progress(prog_value, desc=f"Answers: test {len(rows)} ({module_of(test)})")
    return (rows, *render_answers(rows, module))


def render_answers(rows: list[dict], module: str):
    rows = filter_rows(rows, module)
    if not rows:
        return ANSWER_EMPTY, gr.update(value=None, visible=False)

    n_text = f"{len(rows)} answers judged on a 1–5 scale."
    panel = f"""
    <div class="tiles four">
      {tile("Accuracy", mean([r["Accuracy"] for r in rows]), "answer", "{:.2f}",
            "Are the answer's claims correct against the reference and notes?")}
      {tile("Completeness", mean([r["Completeness"] for r in rows]), "answer", "{:.2f}",
            "Does it cover all the key points in the reference answer?")}
      {tile("Relevance", mean([r["Relevance"] for r in rows]), "answer", "{:.2f}",
            "Does it answer the question asked, without padding?")}
      {tile("Grounding", mean([r["Grounding"] for r in rows]), "answer", "{:.2f}",
            "Does it stick to your notes and label anything from outside them?")}
    </div>
    {routing_html(rows)}
    {summary_html(rows, "Accuracy", "{:.2f}", n_text)}
    <div class="section-title">Accuracy by module and question type</div>
    {grid_html(rows, "Accuracy", "answer", "{:.2f}")}"""

    df = pd.DataFrame(rows)
    if df["Searches"].isna().all():
        df = df.drop(columns="Searches")  # eval.py isn't passing the search count yet
    table = (df.assign(Module=lambda d: d["Module"].map(short_name),
                       Category=lambda d: d["Category"].map(pretty))
             .sort_values(["Accuracy", "Completeness"]).reset_index(drop=True))
    return panel, gr.update(value=table, visible=True)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def main():
    with gr.Blocks(title="University Assistant · Evaluation") as app:
        retrieval_state = gr.State([])
        answer_state = gr.State([])

        gr.HTML(HEADER, padding=False)

        with gr.Group(elem_classes="controls"):
            test_set = gr.Radio(
                choices=list(TEST_SETS),
                value="Small (50 tests)",
                label="Test set",
                info="Which test file the next run uses. Small is cheaper for answer runs.",
            )
            module_filter = gr.Radio(
                choices=[ALL_MODULES] + list(MODULES),
                value=ALL_MODULES,
                label="Module",
                info="Filters the latest results. It doesn't re-run anything.",
            )

        with gr.Tabs(elem_classes="tabs"):
            with gr.Tab("Retrieval"):
                retrieval_button = gr.Button("Run retrieval evaluation", variant="primary")
                retrieval_panel = gr.HTML(RETRIEVAL_EMPTY, elem_classes="panel")
                retrieval_table = gr.Dataframe(label="Every test, weakest first", interactive=False,
                                               wrap=True, visible=False, max_height=420, elem_classes="results-table",
                                               column_widths=["15%", "11%", "50%", "8%", "8%", "8%"])

            with gr.Tab("Answers"):
                answer_button = gr.Button("Run answer evaluation", variant="primary")
                answer_panel = gr.HTML(ANSWER_EMPTY, elem_classes="panel")
                answer_table = gr.Dataframe(label="Every test, weakest first", interactive=False,
                                            wrap=True, visible=False, max_height=420, elem_classes="results-table",
                                            column_widths=["10%", "9%", "23%", "8%", "8%", "11%", "8%", "8%", "15%"])

        # Progress shows once, on the results panel, instead of over every component
        retrieval_button.click(
            run_retrieval_evaluation,
            inputs=[test_set, module_filter],
            outputs=[retrieval_state, retrieval_panel, retrieval_table],
            show_progress_on=retrieval_panel,
        )
        answer_button.click(
            run_answer_evaluation,
            inputs=[test_set, module_filter],
            outputs=[answer_state, answer_panel, answer_table],
            show_progress_on=answer_panel,
        )
        module_filter.change(render_retrieval, inputs=[retrieval_state, module_filter],
                             outputs=[retrieval_panel, retrieval_table], show_progress="hidden")
        module_filter.change(render_answers, inputs=[answer_state, module_filter],
                             outputs=[answer_panel, answer_table], show_progress="hidden")

    app.launch(inbrowser=True, theme=THEME, css=CSS, footer_links=[])


if __name__ == "__main__":
    main()