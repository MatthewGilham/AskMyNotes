"""Converting every module's slides and PDFs to Markdown files.

The folders listed in `settings.toml` are only ever read. Everything written
goes under `data/`:

    data/notes_markdown/<module>/<file name>.md   the converted Markdown
    data/pptx_copies/<module>/<file name>.pptx    .pptx copies of .ppt files
    data/libreoffice_profile/                     LibreOffice's own settings

A file that can't be read is skipped and reported, and the rest carry on.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from askmynotes.notes.convert import (
    ConvertedFile,
    UnreadableFile,
    convert_pdf,
    convert_pptx,
    require_text,
)
from askmynotes.notes.libreoffice import convert_with_libreoffice
from askmynotes.settings import Module

logger = logging.getLogger(__name__)

NOTE_SUFFIXES = {".pdf", ".pptx", ".ppt"}


@dataclass(frozen=True)
class ConvertedNote:
    """A file that was converted, and where its Markdown was saved."""

    module: str
    source: Path
    markdown_file: Path
    kind: str
    page_count: int


@dataclass(frozen=True)
class SkippedNote:
    """A file that couldn't be read, and why."""

    module: str
    source: Path
    reason: str


@dataclass
class ConversionReport:
    """What a conversion run did."""

    converted: list[ConvertedNote] = field(default_factory=list)
    skipped: list[SkippedNote] = field(default_factory=list)


def find_note_files(folder: Path) -> list[Path]:
    """The PDFs and PowerPoint files in a folder, including any subfolders.

    Other files, and the temporary lock files Office leaves beside an open
    document (`~$name.pptx`), are ignored.
    """
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in NOTE_SUFFIXES
        and not path.name.startswith(("~$", "."))
    )


def render_markdown(module: Module, source_name: str, converted: ConvertedFile) -> str:
    """The Markdown file's text: a marker line in front of every slide or page.

    The markers are what keep the numbers, so every answer can cite them.
    """
    parts = [f"<!-- module: {module.short_name} | file: {source_name} -->"]
    for page in converted.pages:
        parts.append(f"<!-- {converted.kind} {page.number} -->\n{page.text}".rstrip())
    return "\n\n".join(parts) + "\n"


def convert_note(
    source: Path, module: Module, libreoffice_path: Path, data_dir: Path
) -> ConvertedFile:
    """Convert one file to pages. Raises `UnreadableFile` if it can't be read."""
    relative = source.relative_to(module.folder)
    suffix = source.suffix.lower()
    if suffix == ".ppt":
        copies = data_dir / "pptx_copies" / module.short_name
        pptx = convert_with_libreoffice(
            libreoffice_path,
            source,
            "pptx",
            output_dir=copies / relative.parent,
            work_dir=data_dir / "libreoffice_work",
            profile_dir=data_dir / "libreoffice_profile",
        )
        return require_text(convert_pptx(pptx))
    if suffix == ".pptx":
        return require_text(convert_pptx(source))
    return require_text(convert_pdf(source))


def check_folder_exists(module: Module) -> None:
    """Stop with a clear message if a module's folder is missing."""
    if not module.folder.is_dir():
        raise FileNotFoundError(
            f"The folder for {module.short_name} doesn't exist: {module.folder}"
        )


def describe_failure(error: Exception) -> str:
    """Why a file couldn't be read, in a form that can be shown to you."""
    if isinstance(error, UnreadableFile):
        return str(error)
    return f"{type(error).__name__}: {error}"


def markdown_file_for(data_dir: Path, module_short_name: str, relative: Path) -> Path:
    """Where a file's converted Markdown is saved."""
    return data_dir / "notes_markdown" / module_short_name / (str(relative) + ".md")


def save_markdown(
    data_dir: Path, module: Module, source: Path, converted: ConvertedFile
) -> Path:
    """Save a converted file as Markdown, and return where it was saved."""
    relative = source.relative_to(module.folder)
    markdown_file = markdown_file_for(data_dir, module.short_name, relative)
    markdown_file.parent.mkdir(parents=True, exist_ok=True)
    markdown_file.write_text(
        render_markdown(module, source.name, converted), encoding="utf-8"
    )
    return markdown_file


def remove_converted(data_dir: Path, module_short_name: str, relative: Path) -> None:
    """Delete what was made from a file: its Markdown, and any .pptx copy."""
    markdown_file_for(data_dir, module_short_name, relative).unlink(missing_ok=True)
    if relative.suffix.lower() == ".ppt":
        copy = data_dir / "pptx_copies" / module_short_name / relative.parent
        (copy / (relative.stem + ".pptx")).unlink(missing_ok=True)


def convert_modules(
    modules: list[Module], libreoffice_path: Path, data_dir: Path
) -> ConversionReport:
    """Convert every file in every module's folder."""
    report = ConversionReport()
    for module in modules:
        check_folder_exists(module)
        for source in find_note_files(module.folder):
            try:
                converted = convert_note(source, module, libreoffice_path, data_dir)
            except Exception as error:  # one bad file mustn't stop the rest
                logger.exception("Couldn't read %s", source)
                report.skipped.append(
                    SkippedNote(module.short_name, source, describe_failure(error))
                )
                continue

            markdown_file = save_markdown(data_dir, module, source, converted)
            report.converted.append(
                ConvertedNote(
                    module=module.short_name,
                    source=source,
                    markdown_file=markdown_file,
                    kind=converted.kind,
                    page_count=len(converted.pages),
                )
            )
    return report
