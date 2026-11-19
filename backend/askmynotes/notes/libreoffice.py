"""Converting old Office files (.ppt, .doc, .xls) to the newer formats with
LibreOffice.

MarkItDown only reads the newer formats (.pptx, .docx, .xlsx). LibreOffice is
installed on the computer separately; the app runs it in the background, without
a window.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from askmynotes.notes.convert import UnreadableFile


def default_soffice_path(platform: str = sys.platform) -> Path:
    """Where LibreOffice's installer puts it on Windows or macOS.

    Only the tests and the end-to-end setup use this; the real app reads the
    path from settings.toml, so it works wherever LibreOffice really is.
    """
    if platform == "win32":
        return Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    if platform == "darwin":
        return Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    raise NotImplementedError(f"No LibreOffice location is known for {platform!r}")


# a stuck conversion shouldn't hang the app for ever.
TIMEOUT_SECONDS = 300


def convert_with_libreoffice(
    soffice: Path,
    source: Path,
    new_extension: str,
    output_dir: Path,
    work_dir: Path,
    profile_dir: Path,
) -> Path:
    """Convert an old Office file to `new_extension` (such as "pptx"); return the
    new file, written into `output_dir`.

    The original is never opened by LibreOffice. LibreOffice drops a lock file
    next to any document it opens, and nothing may be written in the notes
    folders, so it works on a copy kept in `work_dir`. `profile_dir` is where
    LibreOffice keeps its own settings, so it writes nothing to the user
    folder.
    """
    if not soffice.exists():
        raise UnreadableFile(f"LibreOffice was not found at {soffice}")
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    copy = work_dir / source.name
    shutil.copy2(source, copy)
    try:
        completed = subprocess.run(
            [
                str(soffice),
                f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                "--headless",
                "--convert-to",
                new_extension,
                "--outdir",
                str(output_dir),
                str(copy),
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise UnreadableFile(
            f"LibreOffice took longer than {TIMEOUT_SECONDS} seconds to convert it"
        ) from None
    finally:
        copy.unlink(missing_ok=True)

    converted = output_dir / f"{source.stem}.{new_extension}"
    if completed.returncode != 0 or not converted.exists():
        detail = (completed.stderr or completed.stdout).strip()
        raise UnreadableFile(f"LibreOffice could not convert it: {detail}")
    return converted
