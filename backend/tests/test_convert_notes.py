"""Tests for converting slides and PDFs to Markdown.

The files are generated here from made-up text, so no lecture content is
needed. One test uses the real LibreOffice installed on this PC.
"""

import base64
import io
import subprocess
from pathlib import Path

import pymupdf
import pytest
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from askmynotes.notes.convert import (
    ConvertedFile,
    Page,
    convert_pdf,
    convert_pptx,
    tidy_pdf_text,
)
from askmynotes.notes.libreoffice import default_soffice_path
from askmynotes.notes.pipeline import convert_modules, render_markdown
from askmynotes.settings import Module

LIBREOFFICE = default_soffice_path()

# A real 1x1 pixel PNG, to put a picture on a slide.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def make_deck(path: Path) -> None:
    """Three slides: text with speaker notes, a blank one, and a chart + picture."""
    deck = Presentation()
    first = deck.slides.add_slide(deck.slide_layouts[1])
    first.shapes.title.text = "Basic EPS"
    first.placeholders[1].text = "Profit divided by shares"
    first.notes_slide.notes_text_frame.text = "Mention preference dividends"
    deck.slides.add_slide(deck.slide_layouts[6])
    third = deck.slides.add_slide(deck.slide_layouts[5])
    third.shapes.title.text = "Revenue growth"
    third.shapes.add_picture(
        io.BytesIO(PNG), Inches(1), Inches(3), Inches(1), Inches(1)
    )
    data = CategoryChartData()
    data.categories = ["2024", "2025"]
    data.add_series("Revenue", (10, 20))
    third.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(3), Inches(3), Inches(4), Inches(3), data
    )
    deck.save(path)


def make_pdf(path: Path, page_texts: list[str]) -> None:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def module_for(folder: Path) -> Module:
    return Module(name="Advanced Financial Accounting", short_name="AFA", folder=folder)


def snapshot(folder: Path) -> list[tuple[str, int, int]]:
    """Every file's relative path, size and modified time."""
    return sorted(
        (str(p.relative_to(folder)), p.stat().st_size, p.stat().st_mtime_ns)
        for p in folder.rglob("*")
        if p.is_file()
    ) + sorted(
        (str(p.relative_to(folder)), 0, 0) for p in folder.rglob("*") if p.is_dir()
    )


@pytest.fixture
def notes(tmp_path: Path) -> Path:
    folder = tmp_path / "notes"
    folder.mkdir()
    return folder


def test_pptx_slide_numbers_are_kept(tmp_path: Path) -> None:
    make_deck(tmp_path / "deck.pptx")

    converted = convert_pptx(tmp_path / "deck.pptx")

    assert converted.kind == "slide"
    assert [page.number for page in converted.pages] == [1, 2, 3]
    assert "Basic EPS" in converted.pages[0].text
    assert "Profit divided by shares" in converted.pages[0].text
    assert converted.pages[1].text == ""  # a slide with no text keeps its number
    assert "Revenue growth" in converted.pages[2].text


def test_pptx_speaker_notes_and_chart_data_are_kept(tmp_path: Path) -> None:
    make_deck(tmp_path / "deck.pptx")

    converted = convert_pptx(tmp_path / "deck.pptx")

    assert "Mention preference dividends" in converted.pages[0].text
    assert "| 2025 | 20.0 |" in converted.pages[2].text


def test_pptx_picture_placeholders_are_removed(tmp_path: Path) -> None:
    make_deck(tmp_path / "deck.pptx")

    converted = convert_pptx(tmp_path / "deck.pptx")

    assert all("![" not in page.text for page in converted.pages)


def test_pdf_page_numbers_are_kept(tmp_path: Path) -> None:
    make_pdf(tmp_path / "doc.pdf", ["First page text", "", "Third page text"])

    converted = convert_pdf(tmp_path / "doc.pdf")

    assert converted.kind == "page"
    assert [page.number for page in converted.pages] == [1, 2, 3]
    assert "First page text" in converted.pages[0].text
    assert converted.pages[1].text == ""
    assert "Third page text" in converted.pages[2].text


def test_markdown_has_one_marker_for_every_slide_and_page(
    tmp_path: Path, notes: Path
) -> None:
    make_deck(notes / "Lecture 1.pptx")
    make_pdf(notes / "Handout.pdf", ["Alpha", "Beta"])
    data = tmp_path / "data"

    report = convert_modules([module_for(notes)], LIBREOFFICE, data)

    assert report.skipped == []
    deck = (data / "notes_markdown" / "AFA" / "Lecture 1.pptx.md").read_text("utf-8")
    pdf = (data / "notes_markdown" / "AFA" / "Handout.pdf.md").read_text("utf-8")
    assert deck.startswith("<!-- module: AFA | file: Lecture 1.pptx -->")
    assert [f"<!-- slide {n} -->" in deck for n in (1, 2, 3)] == [True] * 3
    assert "<!-- slide 4 -->" not in deck
    assert "<!-- page 1 -->\nAlpha" in pdf
    assert "<!-- page 2 -->\nBeta" in pdf


def test_pdf_picture_text_is_kept_without_its_wrapping() -> None:
    raw = (
        "<!-- Start of picture text -->\nKBS: Future Ready<br>Careers<br>"
        "<!-- End of picture text -->\n\n\n\nPlain text"
    )

    assert tidy_pdf_text(raw) == "KBS: Future Ready\nCareers\n\nPlain text"


def test_render_markdown_puts_the_text_after_its_marker() -> None:
    module = module_for(Path("unused"))
    converted = ConvertedFile(kind="page", pages=[Page(1, "One"), Page(2, "")])

    text = render_markdown(module, "x.pdf", converted)

    assert text == (
        "<!-- module: AFA | file: x.pdf -->\n\n"
        "<!-- page 1 -->\nOne\n\n"
        "<!-- page 2 -->\n"
    )


def test_unreadable_file_is_skipped_and_reported(tmp_path: Path, notes: Path) -> None:
    make_deck(notes / "good.pptx")
    (notes / "broken.pptx").write_bytes(b"this is not a PowerPoint file")
    (notes / "broken.pdf").write_bytes(b"this is not a PDF")
    make_pdf(notes / "blank.pdf", ["", ""])

    report = convert_modules([module_for(notes)], LIBREOFFICE, tmp_path / "data")

    assert [n.source.name for n in report.converted] == ["good.pptx"]
    skipped = {n.source.name: n.reason for n in report.skipped}
    assert set(skipped) == {"broken.pptx", "broken.pdf", "blank.pdf"}
    assert "no text" in skipped["blank.pdf"]
    assert all(reason for reason in skipped.values())
    # The good file still converted, and no Markdown was written for the bad ones.
    markdown = tmp_path / "data" / "notes_markdown" / "AFA"
    assert sorted(p.name for p in markdown.iterdir()) == ["good.pptx.md"]


def test_lock_files_and_other_file_types_are_ignored(
    tmp_path: Path, notes: Path
) -> None:
    make_deck(notes / "good.pptx")
    (notes / "~$good.pptx").write_bytes(b"office lock file")
    (notes / "readme.txt").write_text("not a slide")

    report = convert_modules([module_for(notes)], LIBREOFFICE, tmp_path / "data")

    assert [n.source.name for n in report.converted] == ["good.pptx"]
    assert report.skipped == []


def test_files_in_subfolders_are_converted_and_keep_their_place(
    tmp_path: Path, notes: Path
) -> None:
    (notes / "Week 1").mkdir()
    make_pdf(notes / "Week 1" / "Intro.pdf", ["Hello"])

    report = convert_modules([module_for(notes)], LIBREOFFICE, tmp_path / "data")

    assert report.converted[0].markdown_file == (
        tmp_path / "data" / "notes_markdown" / "AFA" / "Week 1" / "Intro.pdf.md"
    )
    assert report.converted[0].markdown_file.exists()


def test_the_notes_folder_is_not_modified(tmp_path: Path, notes: Path) -> None:
    make_deck(notes / "Lecture 1.pptx")
    make_pdf(notes / "Handout.pdf", ["Alpha"])
    (notes / "broken.pdf").write_bytes(b"not a pdf")
    before = snapshot(notes)

    convert_modules([module_for(notes)], LIBREOFFICE, tmp_path / "data")

    assert snapshot(notes) == before


def test_a_missing_module_folder_is_reported_clearly(tmp_path: Path) -> None:
    missing = module_for(tmp_path / "does not exist")

    with pytest.raises(FileNotFoundError, match="folder for AFA doesn't exist"):
        convert_modules([missing], LIBREOFFICE, tmp_path / "data")


@pytest.mark.skipif(
    not LIBREOFFICE.exists(), reason="LibreOffice is not installed on this computer"
)
def test_ppt_is_converted_through_libreoffice(tmp_path: Path, notes: Path) -> None:
    # Make a real old-format .ppt: LibreOffice saves one from a generated deck.
    deck_dir = tmp_path / "decks"
    deck_dir.mkdir()
    make_deck(deck_dir / "Lecture 2.pptx")
    subprocess.run(
        [
            str(LIBREOFFICE),
            f"-env:UserInstallation={(tmp_path / 'test_profile').as_uri()}",
            "--headless",
            "--convert-to",
            "ppt",
            "--outdir",
            str(notes),
            str(deck_dir / "Lecture 2.pptx"),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
    assert (notes / "Lecture 2.ppt").exists()
    before = snapshot(notes)
    data = tmp_path / "data"

    report = convert_modules([module_for(notes)], LIBREOFFICE, data)

    assert report.skipped == []
    [note] = report.converted
    assert note.source.name == "Lecture 2.ppt"
    assert note.page_count == 3
    text = note.markdown_file.read_text("utf-8")
    # Sources cite the original .ppt, not the converted copy.
    assert text.startswith("<!-- module: AFA | file: Lecture 2.ppt -->")
    assert "Basic EPS" in text
    assert "<!-- slide 3 -->" in text
    assert (data / "pptx_copies" / "AFA" / "Lecture 2.pptx").exists()
    # LibreOffice left nothing behind in the notes folder, such as a lock file,
    # and its settings went inside data/, not the user folder.
    assert snapshot(notes) == before
    assert (data / "libreoffice_profile").exists()


def test_default_soffice_path_depends_on_the_platform() -> None:
    windows = default_soffice_path("win32")
    mac = default_soffice_path("darwin")

    assert windows.name == "soffice.exe"
    assert windows.parts[-3:] == ("LibreOffice", "program", "soffice.exe")
    assert mac.as_posix() == "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    with pytest.raises(NotImplementedError, match="linux"):
        default_soffice_path("linux")
