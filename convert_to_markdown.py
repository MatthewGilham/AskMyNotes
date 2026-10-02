"""
Convert university files (Word, PowerPoint, PDF) into Markdown for RAG.

Reads from each folder in SOURCES (never modifies them) and writes .md files into
knowledge_base/<destination>/, so the year, module and type can be read from the path later.

Run from the project root:
    python convert_to_markdown.py
"""
import re
from pathlib import Path

from markitdown import MarkItDown

UNI = Path("/Users/matthewgilham/Desktop/All desktop folders/University")

# source folder -> where its files go inside knowledge_base/ (year / module / type)
SOURCES = {
    UNI / "University Third Year/Advanced Financial Accounting/Lecture Slides":
        "University Final Year/Advanced Financial Accounting/Lecture Slides",

    UNI / "University Third Year/Investment and Portfolio Analysis/Lecture Slides":
        "University Final Year/Investment and Portfolio Analysis/Lecture Slides",

    UNI / "University Second Year/Financial Reporting (FR)/Lecture Slides":
        "University Second Year/Financial Reporting (FR)/Lecture Slides",

    UNI / "University Second Year/Principles Of Finance (POF)/Lecture Slides":
        "University Second Year/Principles Of Finance (POF)/Lecture Slides",

    UNI / "University Second Year/Intermediate Management Accounting (IMA)/Lecture Slides":
        "University Second Year/Intermediate Management Accounting (IMA)/Lecture Slides",

    UNI / "University Second Year/Strategic Management (SM)/Lecture Slides":
        "University Second Year/Strategic Management (SM)/Lecture Slides",

    UNI / "University Second Year/Corporate FInance (CF)/Lecture Slides":
        "University Second Year/Corporate FInance (CF)/Lecture Slides",

    UNI / "University Second Year/Business Law (BL)/Lecture Slides":
        "University Second Year/Business Law (BL)/Lecture Slides"
}
OUTPUT_DIR = Path(__file__).parent / "knowledge_base"

FILE_TYPES = {".docx", ".pptx", ".pdf", ".doc"}
MIN_CHARACTERS = 200   # anything shorter is probably a scanned PDF or empty file

converter = MarkItDown()


def clean(text):
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)   # remove image placeholders
    text = re.sub(r"\n{3,}", "\n\n", text)             # collapse leftover blank lines
    return text.strip()


def convert_file(source_file, source_dir, destination):
    """Convert one file and save it as Markdown. Returns a status word."""
    relative_path = Path(destination) / source_file.relative_to(source_dir)
    output_file = (OUTPUT_DIR / relative_path).with_suffix(".md")

    if output_file.exists():
        return "skipped"          # already converted on an earlier run

    result = converter.convert(str(source_file))
    text = clean(result.markdown)

    if len(text) < MIN_CHARACTERS:
        return "empty"            # probably scanned, so there is no text layer

    output_file.parent.mkdir(parents=True, exist_ok=True)
    header = f"# {source_file.stem}\n\nSource: {relative_path}\n\n"
    output_file.write_text(header + text, encoding="utf-8")
    return "converted"


def main():
    counts = {"converted": 0, "skipped": 0, "empty": 0, "failed": 0}

    for source_dir, destination in SOURCES.items():
        if not source_dir.exists():
            print(f"FOLDER NOT FOUND: {source_dir}\n")
            continue

        files = [f for f in source_dir.rglob("*")
                 if f.suffix.lower() in FILE_TYPES and not f.name.startswith("~$")]
        print(f"{destination}: {len(files)} files")

        for source_file in files:
            try:
                status = convert_file(source_file, source_dir, destination)
            except Exception as error:
                status = "failed"
                print(f"  FAILED: {source_file.name} ({error})")
            counts[status] += 1
            if status in ("converted", "empty"):
                print(f"  {status}: {source_file.name}")
        print()

    print(f"Done: {counts}")


if __name__ == "__main__":
    main()