from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd
from custom_types.market import (
    Action,
    MarketAssets,
    MarketBarPeriod,
    MarketOrder,
    MarketPosition,
    TradeType,
)
from custom_types.ticker import Ticker


class BrokerClient(ABC):
    """ "
    1. All functions that call broker API should raise an
        APIRateLimitExceededError if the broker API rate limit is exceeded.
    2. All stops time_in_force should be 'Day'.
        Stop orders are to be resubmitted each bar.
    """

    @staticmethod
    @abstractmethod
    def get_name() -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_trading_fees(shares: float, price: float, trade_type: TradeType) -> float:
        pass

    @staticmethod
    @abstractmethod
    def get_margin_interest(margin_amount: float, duration_days: int) -> float:
        pass

    @abstractmethod
    def get_assets(self) -> MarketAssets:
        pass

    @abstractmethod
    def get_positions(self) -> list[MarketPosition]:
        pass

    @abstractmethod
    def get_orders(self) -> list[MarketOrder]:
        pass

    @abstractmethod
    def place_limit_order(
        self, ticker: Ticker, quantity: int, action: Action, limit_price: float
    ):
        pass

    @abstractmethod
    def place_stop_order(
        self, ticker: Ticker, quantity: int, action: Action, stop_price: float
    ):
        pass

    @abstractmethod
    def get_market_data(
        self,
        ticker: Ticker,
        begin_time: datetime,
        end_time: datetime,
        period: MarketBarPeriod,
    ) -> pd.DataFrame:
        """
        Single API call returning the bars of a ticker between begin_time and end_time.
        Looping/pagination and rate limit retries are handled by BrokerService.
        Returns an empty DataFrame if there are no bars.
        """

    def __str__(self):
        return ""
