import pandas as pd
import pytest
from custom_types.exception import MyValueError
from system.indicator.indicator_types import Indicator
from system.models.entry.example_entry_model import ExampleEntryModel
from util.trading_util import TICKER_TO_SECTOR


@pytest.fixture
def model() -> ExampleEntryModel:
    return ExampleEntryModel(lookback_period=2)


@pytest.fixture
def market_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAPL"] * 4,
            "datetime": ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"],
            "open": [1.0, 2.0, 3.0, 4.0],
            "high": [2.0, 3.0, 4.0, 5.0],
            "low": [0.5, 1.5, 2.5, 3.5],
            "close": [1.5, 2.5, 3.5, 4.5],
        }
    )


def test_prepare_market_data_adds_sector_per_ticker(model):
    data = pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL", "NVDA", "NVDA"],
            "datetime": pd.to_datetime(["2026-01-05", "2026-01-06"] * 2),
            "open": [1.0] * 4,
            "high": [2.0] * 4,
            "low": [0.5] * 4,
            "close": [1.5] * 4,
        }
    )

    prepared = model.prepare_data(data)

    assert prepared[Indicator.SECTOR].tolist() == [
        TICKER_TO_SECTOR.get("AAPL"),
        TICKER_TO_SECTOR.get("AAPL"),
        TICKER_TO_SECTOR.get("NVDA"),
        TICKER_TO_SECTOR.get("NVDA"),
    ]


def test_prepare_market_data_does_not_mutate_input(model, market_data):
    original = market_data.copy()

    model.prepare_data(market_data)

    pd.testing.assert_frame_equal(market_data, original)


def test_prepare_market_data_adds_model_indicators(model, market_data):
    prepared = model.prepare_data(market_data)

    assert Indicator.ROLLING_HIGH in prepared.columns
    assert Indicator.ROLLING_LOW in prepared.columns


@pytest.mark.parametrize(
    "missing_col", ["ticker", "datetime", "open", "high", "low", "close"]
)
def test_prepare_market_data_raises_when_required_column_missing(
    model, market_data, missing_col
):
    with pytest.raises(MyValueError, match=missing_col):
        model.prepare_data(market_data.drop(columns=[missing_col]))
