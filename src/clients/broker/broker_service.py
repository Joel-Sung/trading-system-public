from datetime import datetime, timedelta

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import (
    Action,
    MarketAssets,
    MarketBarPeriod,
    MarketOrder,
    MarketPosition,
    OrderType,
    TradeType,
)
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker
from system.indicator.indicator_types import Indicator
from util.broker_util import retry_on_rate_limit
from util.trading_util import TICKER_TO_SECTOR

_ORDER_TYPES = {
    OrderType.LMT,
    OrderType.STP,
    OrderType.LMT_STP,
}


class BrokerService:
    """
    Interface layer between the trading engine and a BrokerClient.
    Owns the multi-call strategies (looping, pagination, rate limit retries)
    so that BrokerClient only exposes basic broker API calls.
    """

    def __init__(
        self,
        broker: BrokerClient,
    ):
        self.broker = broker

    def get_name(self) -> str:
        return self.broker.get_name()

    def get_assets(self) -> MarketAssets:
        return self.broker.get_assets()

    def get_positions(self) -> list[MarketPosition]:
        return self.broker.get_positions()

    def get_orders(self) -> list[MarketOrder]:
        return self.broker.get_orders()

    def get_trading_fees(
        self, shares: float, price: float, trade_type: TradeType
    ) -> float:
        return self.broker.get_trading_fees(
            shares=shares, price=price, trade_type=trade_type
        )

    def place_limit_order(
        self, ticker: Ticker, quantity: int, action: Action, limit_price: float
    ):
        return self.broker.place_limit_order(
            ticker=ticker,
            quantity=quantity,
            action=action,
            limit_price=limit_price,
        )

    def place_stop_order(
        self, ticker: Ticker, quantity: int, action: Action, stop_price: float
    ):
        return self.broker.place_stop_order(
            ticker=ticker,
            quantity=quantity,
            action=action,
            stop_price=stop_price,
        )

    def place_limit_stop_order(
        self,
        ticker: Ticker,
        quantity: int,
        action: Action,
        limit_price: float,
        stop_price: float,
    ):
        return self.broker.place_limit_stop_order(
            ticker=ticker,
            quantity=quantity,
            action=action,
            limit_price=limit_price,
            stop_price=stop_price,
        )

    def _place_order(self, order: SystemOrder) -> None:
        if order.order_type == OrderType.LMT:
            return self.place_limit_order(
                ticker=order.ticker,
                quantity=order.quantity,
                action=order.action,
                limit_price=order.limit_price,
            )

        if order.order_type == OrderType.STP:
            return self.place_stop_order(
                ticker=order.ticker,
                quantity=order.quantity,
                action=order.action,
                stop_price=order.stop_price,
            )

        if order.order_type == OrderType.LMT_STP:
            return self.place_limit_stop_order(
                ticker=order.ticker,
                quantity=order.quantity,
                action=order.action,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
            )

        raise MyValueError(
            "Unsupported order type",
            order=order,
        )

    def place_orders(self, system_orders: list[SystemOrder]) -> None:
        for order in system_orders:
            self._place_order(order)

    def _get_market_data_for_ticker(
        self,
        ticker: Ticker,
        lookback_period: int,
        end_time: datetime,
        period: MarketBarPeriod = MarketBarPeriod.DAY,
    ) -> pd.DataFrame:
        """
        Retrieves the latest number_of_bars bars of a ticker, walking backwards
        in time one window at a time until enough bars are collected.
        Set number_of_bars = None to retrieve the full history.
        """

        all_data: list[pd.DataFrame] = []
        total_bars = 0
        api_retries = 5

        while True:
            begin_time = end_time - timedelta(days=lookback_period)

            data = retry_on_rate_limit(
                lambda begin_time=begin_time, end_time=end_time: (
                    self.broker.get_market_data(
                        ticker=ticker,
                        begin_time=begin_time,
                        end_time=end_time,
                        period=period,
                    )
                ),
                retries=api_retries,
            )

            if data.empty:
                break

            all_data.append(data)

            total_bars += len(data)
            if lookback_period is not None and total_bars >= lookback_period:
                break

            end_time = begin_time

        if not all_data:
            return pd.DataFrame()

        ticker_df = (
            pd.concat(all_data, ignore_index=True)
            .drop_duplicates(subset=["ticker", "datetime"])
            .sort_values("datetime")
            .reset_index(drop=True)
        )

        if lookback_period is None:
            return ticker_df

        return ticker_df.tail(lookback_period)

    def get_market_data(
        self,
        number_of_bars: int,
        end_time: datetime,
        period: MarketBarPeriod = MarketBarPeriod.DAY,
    ) -> pd.DataFrame:
        """
        Retrieves market data of all tickers as a single DataFrame,
        tagged with each ticker's sector.
        """
        ticker_dfs: list[pd.DataFrame] = []
        for ticker in Ticker:
            ticker_df = self._get_market_data_for_ticker(
                ticker=ticker,
                lookback_period=number_of_bars,
                period=period,
                end_time=end_time,
            )
            ticker_df[Indicator.SECTOR] = TICKER_TO_SECTOR.get(ticker)
            ticker_dfs.append(ticker_df)

        if not ticker_dfs:
            return pd.DataFrame()

        return pd.concat(ticker_dfs, ignore_index=True)

    def __str__(self) -> str:
        return f"Broker Service ({self.broker})"
