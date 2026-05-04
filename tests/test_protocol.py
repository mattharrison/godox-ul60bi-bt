from __future__ import annotations

import pytest

from godox_ul60bi_bt.protocol import (
    validate_brightness,
    validate_cct,
)


@pytest.mark.parametrize("value", [0, 1, 50, 100])
def test_validate_brightness_accepts_percent_range(value: int) -> None:
    assert validate_brightness(value) == value


@pytest.mark.parametrize("value", [-1, 101])
def test_validate_brightness_rejects_out_of_range_values(value: int) -> None:
    with pytest.raises(ValueError, match="brightness must be between 0 and 100"):
        validate_brightness(value)


@pytest.mark.parametrize("value", [2800, 3200, 4300, 5600, 6500])
def test_validate_cct_accepts_ul60bi_kelvin_range(value: int) -> None:
    assert validate_cct(value) == value


@pytest.mark.parametrize("value", [2799, 6501])
def test_validate_cct_rejects_out_of_range_values(value: int) -> None:
    with pytest.raises(ValueError, match="CCT must be between 2800K and 6500K"):
        validate_cct(value)



