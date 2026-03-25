from app.main import _parse_frame_values


def test_parse_frame_values_supports_comma_separated_times() -> None:
    assert _parse_frame_values("12.5, 44.2,91.0", None) == [12.5, 44.2, 91.0]


def test_parse_frame_values_falls_back_to_repeated_frame_flags() -> None:
    assert _parse_frame_values(None, [1.0, 2.0]) == [1.0, 2.0]
