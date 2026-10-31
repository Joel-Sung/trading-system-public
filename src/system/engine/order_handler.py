import logging

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import Action, OrderType, TradeType
from custom_types.system import SystemOrder
from system.indicator.indicator_types import Indicator
from system.portfolio.campaign import Campaign
from system.portfolio.portfolio import Portfolio
from util.datetime_util import format_date


class OrderHandler:
    def __init__(self, debug: bool = False):
        self.debug = debug

    def _handle_lmt_order(
        self,
        portfolio: Portfolio,
        system_order: SystemOrder,
        ticker_data: pd.Series,
        broker: BrokerClient,
        logger: logging.Logger,
    ) -> Portfolio:
        datetime = ticker_data[Indicator.DATETIME]
        open = ticker_data[Indicator.OPEN]
        high = ticker_data[Indicator.HIGH]
        low = ticker_data[Indicator.LOW]
        close = ticker_data[Indicator.CLOSE]

        if system_order.action == Action.BUY and low > system_order.limit_price:
            return portfolio

        if system_order.action == Action.SELL and high < system_order.limit_price:
            return portfolio

        trade_type = (
            TradeType.LONG if system_order.action == Action.BUY else TradeType.SHORT
        )

        fees = broker.get_trading_fees(
            shares=system_order.quantity,
            price=system_order.limit_price,
            trade_type=trade_type,
        )

        leg = portfolio.create_leg(
            ticker=system_order.ticker,
            trade_type=trade_type,
            entry_price=system_order.limit_price,
            entry_datetime=system_order.submitted_dt,
            trading_fees=fees,
            qty=system_order.quantity,
            stop_price=system_order.stop_price,
        )

        logger.info(
            "[%s] Executed LMT order [%s]: %s, leg: %s",
            format_date(datetime),
            f"O ${open:.2f}, H ${high:.2f}, L ${low:.2f}, C ${close:.2f}",
            system_order,
            leg,
        )

        return portfolio

    def _handle_stp_order(
        self,
        portfolio: Portfolio,
        system_order: SystemOrder,
        ticker_data: pd.Series,
        broker: BrokerClient,
        logger: logging.Logger,
    ) -> Portfolio:
        datetime = ticker_data[Indicator.DATETIME]
        open = ticker_data[Indicator.OPEN]
        high = ticker_data[Indicator.HIGH]
        low = ticker_data[Indicator.LOW]
        close = ticker_data[Indicator.CLOSE]

        ticker = system_order.ticker

        if system_order.action == Action.BUY and high < system_order.stop_price:
            return portfolio

        if system_order.action == Action.SELL and low > system_order.stop_price:
            return portfolio

        campaign: Campaign = portfolio.sell_ticker_qty(
            ticker=ticker,
            qty=system_order.quantity,
            exit_price=system_order.stop_price,
            exit_datetime=system_order.submitted_dt,
            broker=broker,
        )

        logger.info(
            "[%s] Executed STP order [%s]: %s, cam: %s",
            format_date(datetime),
            f"O ${open:.2f}, H ${high:.2f}, L ${low:.2f}, C ${close:.2f}",
            system_order,
            campaign,
        )

        return portfolio

    def _handle_lmt_order_with_stp(
        self,
        portfolio: Portfolio,
        system_order: SystemOrder,
        ticker_data: pd.Series,
        broker: BrokerClient,
        logger: logging.Logger,
    ) -> Portfolio:
        if (
            system_order.action == Action.BUY
            and system_order.limit_price < system_order.stop_price
        ):
            raise MyValueError(
                "Stop price higher than limit price for buy order.",
                system_order=system_order,
            )

        if (
            system_order.action == Action.SELL
            and system_order.limit_price > system_order.stop_price
        ):
            raise MyValueError(
                "Stop price lower than limit price for sell order.",
                system_order=system_order,
            )

        portfolio = self._handle_lmt_order(
            portfolio=portfolio,
            system_order=system_order,
            ticker_data=ticker_data,
            broker=broker,
            logger=logger,
        )

        # Inverse action for stop order
        system_order.action = (
            Action.BUY if system_order.action == Action.SELL else Action.SELL
        )

        portfolio = self._handle_stp_order(
            portfolio=portfolio,
            system_order=system_order,
            ticker_data=ticker_data,
            broker=broker,
            logger=logger,
        )

        return portfolio

    def _process_order(
        self,
        portfolio: Portfolio,
        system_order: SystemOrder,
        bar_data: pd.DataFrame,
        broker: BrokerClient,
        logger: logging.Logger,
    ) -> Portfolio:
        ticker = system_order.ticker

        ticker_data_df = bar_data.loc[bar_data["ticker"] == ticker]
        if len(ticker_data_df) != 1:
            raise MyValueError(
                "Expected exactly one row for ticker in bar_data.",
                system_order=system_order,
                num_rows=len(ticker_data_df),
                ticker_data_df=ticker_data_df,
            )

        ticker_data: pd.Series = ticker_data_df.iloc[0]

        datetime = ticker_data[Indicator.DATETIME]
        open = ticker_data[Indicator.OPEN]
        high = ticker_data[Indicator.HIGH]
        low = ticker_data[Indicator.LOW]
        close = ticker_data[Indicator.CLOSE]

        if self.debug:
            logger.info(
                "[%s] Listing Bar Data for System Order, Ticker: %s, O: %s, H: %s, L: %s, C: %s, Stop: %s, Action: %s",
                format_date(datetime),
                ticker,
                open,
                high,
                low,
                close,
                system_order.stop_price,
                system_order.action,
            )

        if system_order.order_type == OrderType.LMT_STP:
            portfolio = self._handle_lmt_order_with_stp(
                portfolio=portfolio,
                system_order=system_order,
                ticker_data=ticker_data,
                broker=broker,
                logger=logger,
            )

        elif system_order.order_type == OrderType.STP:
            portfolio = self._handle_stp_order(
                portfolio=portfolio,
                system_order=system_order,
                ticker_data=ticker_data,
                broker=broker,
                logger=logger,
            )

        else:
            raise MyValueError(
                "OrderHandler cannot handle system order of this type.",
                system_order=system_order,
            )

        return portfolio

    def process_orders(
        self,
        portfolio: Portfolio,
        system_orders: list[SystemOrder],
        bar_data: pd.DataFrame,
        broker: BrokerClient,
        logger: logging.Logger,
    ) -> Portfolio:
        for order in system_orders:
            portfolio = self._process_order(
                portfolio=portfolio,
                system_order=order,
                bar_data=bar_data,
                broker=broker,
                logger=logger,
            )

        return portfolio
