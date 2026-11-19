"""Tests for loading settings.toml."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from askmynotes.settings import PROJECT_ROOT, load_app_settings

VALID = r"""
user_name = "Matt"
port = 8000
max_images_per_message = 5
max_image_size_mb = 10
max_documents_per_message = 5
max_document_size_mb = 25
max_document_tokens = 100000
max_generated_files_per_reply = 10
max_generated_file_mb = 25
context_budget_tokens = 200000
max_chunk_characters = 3000
notes_search_results = 8
libreoffice_path = 'C:\soffice.exe'
example_prompts = ["Hello"]

[prices]
chat_input = 0.10
chat_cached_input = 0.01
chat_output = 0.50
embedding_input = 0.13
web_search_call = 0.01
python_session = 0.03

[web_search]
country = "GB"
timezone = "Europe/London"

[[modules]]
name = "Business Law"
short_name = "BL"
folder = 'C:\slides'
"""


def test_a_valid_settings_file_loads(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(VALID)

    settings = load_app_settings(path)

    assert settings.modules[0].short_name == "BL"


def test_a_missing_setting_is_named_in_the_error(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(VALID.replace("port = 8000\n", ""))

    with pytest.raises(ValidationError, match="port"):
        load_app_settings(path)


def test_the_example_settings_file_matches_the_settings_model() -> None:
    load_app_settings(PROJECT_ROOT / "settings.example.toml")


def test_document_text_larger_than_half_the_context_budget_is_refused(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(
        VALID.replace("max_document_tokens = 100000", "max_document_tokens = 100001")
    )

    with pytest.raises(ValidationError, match="max_document_tokens"):
        load_app_settings(path)


def test_a_missing_price_stops_start_up_naming_it(tmp_path: Path) -> None:
    path = tmp_path / "settings.toml"
    path.write_text(VALID.replace("chat_cached_input = 0.01\n", ""))

    with pytest.raises(ValidationError, match="chat_cached_input"):
        load_app_settings(path)
