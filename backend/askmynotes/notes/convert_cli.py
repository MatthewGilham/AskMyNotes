"""`uv run askmynotes-convert-notes`: convert every module's slides to Markdown.

It costs nothing (no model is called). Open the files it writes under
`data/notes_markdown/` to see exactly what the app has read from each slide.
"""

import sys

from askmynotes.main import load_settings
from askmynotes.notes.pipeline import convert_modules
from askmynotes.settings import DATA_DIR


def main() -> None:
    """Convert all the notes and print what happened to each file."""
    settings = load_settings()
    try:
        report = convert_modules(settings.modules, settings.libreoffice_path, DATA_DIR)
    except FileNotFoundError as error:
        sys.exit(str(error))

    for note in report.converted:
        unit = "slides" if note.kind == "slide" else "pages"
        print(f"{note.module:4} {note.source.name}: {note.page_count} {unit}")
    print(
        f"\nConverted {len(report.converted)} files into {DATA_DIR / 'notes_markdown'}"
    )

    if report.skipped:
        print(f"\n{len(report.skipped)} file(s) couldn't be read and were skipped:")
        for note in report.skipped:
            print(f"  {note.module:4} {note.source.name}: {note.reason}")


if __name__ == "__main__":
    main()
