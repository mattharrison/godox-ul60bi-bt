import pytest


def test_analysis_not_importable_from_package():
    with pytest.raises(ImportError):
        from godox_ul60bi_bt import analysis  # noqa: F401


def test_captures_not_importable_from_package():
    with pytest.raises(ImportError):
        from godox_ul60bi_bt import captures  # noqa: F401


def test_replay_not_importable_from_package():
    with pytest.raises(ImportError):
        from godox_ul60bi_bt import replay  # noqa: F401
