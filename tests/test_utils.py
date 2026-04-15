from pathlib import Path

from core.utils import _find_tool_in_common_locations


def test_find_tool_in_common_locations_finds_existing_binary() -> None:
    path = _find_tool_in_common_locations("sh")

    assert path is not None
    assert Path(path).name == "sh"


def test_find_tool_in_common_locations_returns_none_for_missing_binary() -> None:
    assert _find_tool_in_common_locations("definitely-not-a-real-binary-name") is None
