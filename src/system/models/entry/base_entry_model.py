from abc import ABC, abstractmethod

import pandas as pd
from custom_types.exception import MyValueError
from custom_types.mode import Mode
from system.indicator.indicator_types import Indicator
from system.portfolio.campaign import Campaign
from util.trading_util import TICKER_TO_SECTOR

REQUIRED_MARKET_DATA_COLS = [
    Indicator.TICKER,
    Indicator.DATETIME,
    Indicator.OPEN,
    Indicator.HIGH,
    Indicator.LOW,
    Indicator.CLOSE,
]


class BaseEntryModel(ABC):
    def __init__(self, disable_long: bool = False, disable_short: bool = False):
        self.disable_long = disable_long
        self.disable_short = disable_short

    @property
    @abstractmethod
    def min_bars_req_for_inds(self) -> int:
        pass

    @property
    @abstractmethod
    def min_bars_req_for_signals(self) -> int:
        pass

    @abstractmethod
    def _add_indicators(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Adds the indicators the model needs to market_data. Called by
        prepare_data after the generic preparation steps, so market_data
        is guaranteed to contain the required columns with a datetime
        Indicator.DATETIME column.
        """

    def prepare_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Generic preparation for all entry models: validates the required
        columns and adds the sector if missing, then lets the model add its own
        indicators. market_data must already be formatted (datetime column
        converted and sorted).
        """
        missing_cols = [
            col for col in REQUIRED_MARKET_DATA_COLS if col not in market_data.columns
        ]
        if missing_cols:
            raise MyValueError(
                "Market data is missing required columns",
                missing_cols=[str(col) for col in missing_cols],
                required_cols=[str(col) for col in REQUIRED_MARKET_DATA_COLS],
                columns=list(market_data.columns),
            )

        if Indicator.SECTOR not in market_data.columns:
            market_data = market_data.assign(
                **{
                    Indicator.SECTOR: market_data[Indicator.TICKER].map(
                        TICKER_TO_SECTOR
                    )
                }
            )

        return self._add_indicators(market_data)

    @abstractmethod
    def get_long_signal(self, ticker_data: pd.DataFrame) -> bool:
        """
        ticker_data holds all of the ticker's bars up to the current one, with
        the latest bar last. The model decides which bars to use.
        """

    @abstractmethod
    def get_short_signal(self, ticker_data: pd.DataFrame) -> bool:
        """See get_long_signal for ticker_data."""

    @abstractmethod
    def get_new_mode(self, campaign: Campaign, ticker_data: pd.DataFrame) -> Mode:
        """
        Returns the mode the open campaign should be in on this bar, which is
        its current mode if no change is needed. Models that don't use modes
        should return Mode.NONE.
        """

    def __str__(self):
        return ""
