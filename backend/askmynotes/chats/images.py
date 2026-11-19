"""Images attached to a message: checking them, saving them, and reading them
back for the model.

An image belongs only to the chat it was sent in. It is saved under
`data/uploads/<chat id>/`, and nothing here touches the notes database.
"""

import base64
import binascii
import uuid
from pathlib import Path
from typing import Any

from askmynotes.chats.models import ImageUpload

# The image types OpenAI accepts, and the file extension used for each.
EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}
MEDIA_TYPES = {extension: media for media, extension in EXTENSIONS.items()}

# Saved images are served by the app at this address.
URL_PREFIX = "/api/uploads/"

BYTES_PER_MEGABYTE = 1024 * 1024


class InvalidImage(ValueError):
    """Raised when an attached image can't be accepted. The message says why."""


def decode_images(
    uploads: list[ImageUpload], max_count: int, max_megabytes: int
) -> list[bytes]:
    """Check the attached images against the limits and decode them."""
    if len(uploads) > max_count:
        raise InvalidImage(f"You can attach up to {max_count} images to a message.")
    decoded = []
    for upload in uploads:
        try:
            data = base64.b64decode(upload.data, validate=True)
        except binascii.Error:
            raise InvalidImage(f"{upload.name} isn't a valid image.") from None
        if len(data) > max_megabytes * BYTES_PER_MEGABYTE:
            raise InvalidImage(f"{upload.name} is larger than {max_megabytes} MB.")
        decoded.append(data)
    return decoded


def save_images(
    uploads_dir: Path, chat_id: str, uploads: list[ImageUpload], decoded: list[bytes]
) -> list[str]:
    """Write the images to disk and return where each one is, relative to
    the uploads folder (for example `<chat id>/<random name>.png`)."""
    saved = []
    for upload, data in zip(uploads, decoded, strict=True):
        # A random name, so two images called "image.png" never collide.
        relative = f"{chat_id}/{uuid.uuid4().hex}.{EXTENSIONS[upload.media_type]}"
        path = uploads_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        saved.append(relative)
    return saved


def to_url(relative_path: str) -> str:
    """The address the browser uses to show a saved image."""
    return URL_PREFIX + relative_path


def message_content(uploads_dir: Path, text: str, image_urls: list[str]) -> Any:
    """What the model is sent for a student's message.

    Plain text if there are no images; otherwise a list of parts, one for the
    text and one for each image, with the image data included inline.
    """
    if not image_urls:
        return text
    parts: list[dict[str, Any]] = []
    if text:
        parts.append({"type": "text", "text": text})
    for url in image_urls:
        relative = url.removeprefix(URL_PREFIX)
        media_type = MEDIA_TYPES[relative.rsplit(".", 1)[1]]
        data = base64.b64encode((uploads_dir / relative).read_bytes()).decode()
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{data}"},
            }
        )
    return parts
