"""The settings the browser needs, sent by `GET /api/config`."""

from askmynotes.chats.models import ApiModel
from askmynotes.settings import AppSettings


class ClientConfig(ApiModel):
    """Settings from `settings.toml` that the browser needs to know about."""

    user_name: str
    example_prompts: list[str]
    max_images_per_message: int
    max_image_size_mb: int
    max_documents_per_message: int
    max_document_size_mb: int


def client_config_from(settings: AppSettings) -> ClientConfig:
    """Pick out the settings the browser needs."""
    return ClientConfig(
        user_name=settings.user_name,
        example_prompts=settings.example_prompts,
        max_images_per_message=settings.max_images_per_message,
        max_image_size_mb=settings.max_image_size_mb,
        max_documents_per_message=settings.max_documents_per_message,
        max_document_size_mb=settings.max_document_size_mb,
    )
