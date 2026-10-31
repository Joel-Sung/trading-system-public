from abc import ABC, abstractmethod

import pandas as pd
from custom_types.exception import MyValueError
from custom_types.mode import Mode
from system.indicator.indicator_types import Indicator
from system.portfolio.campaign import Campaign

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
        prepare_market_data after the generic preparation steps, so market_data
        is guaranteed to contain the required columns with a datetime
        Indicator.DATETIME column.
        """

    def prepare_market_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Generic preparation for all entry models: validates the required
        columns, converts Indicator.DATETIME to datetime, then lets the model
        add its own indicators.
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

        market_data = market_data.copy()
        market_data[Indicator.DATETIME] = pd.to_datetime(
            market_data[Indicator.DATETIME]
        )

        return self._add_indicators(market_data)

    @abstractmethod
    def get_long_signal(self, current_bar: pd.DataFrame) -> bool:
        pass

    @abstractmethod
    def get_short_signal(self, current_bar: pd.DataFrame) -> bool:
        pass

    @abstractmethod
    def get_new_mode(self, campaign: Campaign, current_bar: pd.Series) -> Mode:
        """
        Returns the mode the open campaign should be in on this bar, which is
        its current mode if no change is needed. Models that don't use modes
        should return Mode.NONE.
        """

    def __str__(self):
        return ""
