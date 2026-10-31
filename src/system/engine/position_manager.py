import logging
from datetime import datetime

import pandas as pd
from clients.broker.broker_client import BrokerClient
from custom_types.exception import MyValueError
from custom_types.market import Action, OrderType, TradeType
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker
from strategy.strategy import Strategy
from system.indicator.indicator_types import Indicator
from system.portfolio.campaign import Campaign
from system.portfolio.leg import Leg
from system.portfolio.portfolio import Portfolio
from util.datetime_util import format_date


class PositionManager:
    def __init__(
        self,
        strategy: Strategy,
        broker: BrokerClient,
        debug: bool = False,
    ) -> None:
        self.strategy = strategy
        self.broker = broker
        self.debug = debug

    def create_system_orders(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        market_data = market_data.copy()

        system_orders = []
        for ticker, ticker_data in market_data.groupby(Indicator.TICKER):
            ticker_system_orders = self._create_system_orders_for_ticker(
                ticker=ticker,
                portfolio=portfolio,
                ticker_data=ticker_data,
                logger=logger,
            )

            system_orders.extend(ticker_system_orders)

        return system_orders

    def _create_system_orders_for_ticker(
        self,
        ticker: Ticker,
        portfolio: Portfolio,
        ticker_data: pd.Series,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        if len(ticker_data) < self.strategy.min_bars_req_for_entry:
            raise MyValueError(
                "Not enough bars required for entry model",
                ticker=ticker,
                ticker_data=ticker_data,
                strategy=self.strategy,
            )

        campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None:
            entry_orders = self._check_for_entry(
                portfolio=portfolio,
                ticker=ticker,
                bar_data=ticker_data,
                logger=logger,
            )

            return entry_orders

        update_orders = self._manage_existing_campaign(
            portfolio=portfolio,
            ticker=ticker,
            bar_data=ticker_data.iloc[-1],
            logger=logger,
        )

        return update_orders

    def _check_for_entry(
        self,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.DataFrame,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        long_signal = self.strategy.get_long_signal(current_bar=bar_data)
        short_signal = self.strategy.get_short_signal(current_bar=bar_data)

        if not long_signal and not short_signal:
            return []

        if long_signal and short_signal:
            raise MyValueError(
                "Entry model generated both a long and short signal.",
                entry_model=self.strategy.entry_model,
                ticker=ticker,
                bar_datetime=bar_data[Indicator.DATETIME].iloc[-1],
                long_signal=long_signal,
                short_signal=short_signal,
                bar_data=bar_data,
            )

        leg_order = self._create_leg_order(
            portfolio=portfolio,
            ticker=ticker,
            trade_type=TradeType.LONG if long_signal else TradeType.SHORT,
            bar_data=bar_data.iloc[-1],
            logger=logger,
        )

        return leg_order

    def _manage_existing_campaign(
        self,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.Series,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        self._check_for_mode_change(
            portfolio=portfolio,
            ticker=ticker,
            bar_data=bar_data,
            logger=logger,
        )

        portfolio.update_with_current_bar(
            ticker=ticker,
            current_bar=bar_data,
            broker=self.broker,
        )

        stop_orders = self._update_trailing_stops(
            portfolio=portfolio,
            ticker=ticker,
            bar_data=bar_data,
            logger=logger,
        )

        pyramid_orders = self._check_for_pyramid_add(
            portfolio=portfolio,
            ticker=ticker,
            bar_data=bar_data,
            logger=logger,
        )

        system_orders: list[SystemOrder] = []
        system_orders.extend(stop_orders)
        system_orders.extend(pyramid_orders)

        return system_orders

    def _check_for_mode_change(
        self,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.Series,
        logger: logging.Logger,
    ) -> None:
        campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None:
            return

        new_mode = self.strategy.get_new_mode(campaign=campaign, current_bar=bar_data)

        if new_mode == campaign.mode:
            return

        if self.debug:
            logger.info(
                "[%s] Changed campaign mode from %s to %s: %s",
                format_date(bar_data[Indicator.DATETIME]),
                campaign.mode,
                new_mode,
                campaign,
            )

        campaign.change_mode(new_mode=new_mode)

    def _update_trailing_stops(
        self,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.Series,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        bar_datetime: datetime = bar_data[Indicator.DATETIME]
        current_price = bar_data[Indicator.CLOSE]
        campaign: Campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None:
            return []

        new_stops: list[float] = self.strategy.get_new_stops(
            current_price=current_price, campaign=campaign
        )
        legs: list[Leg] = campaign.open_legs.copy()

        stop_orders: list[SystemOrder] = []

        for index, leg in enumerate(legs):
            prev_stop_price = leg.current_stop_price
            new_stop_price = new_stops[index]

            if prev_stop_price != new_stop_price:
                leg.move_stop(new_stop_price=new_stops[index])

            stop_order = SystemOrder(
                ticker=ticker,
                action=Action.SELL if leg.trade_type == TradeType.LONG else Action.BUY,
                order_type=OrderType.STP,
                quantity=leg.current_qty,
                submitted_dt=bar_datetime,
                stop_price=new_stop_price,
            )

            if self.debug:
                logger.info(
                    "[%s] Created stop order: %s, leg: %s",
                    format_date(bar_datetime),
                    stop_order,
                    leg,
                )

            stop_orders.append(stop_order)

        # Submit stop orders for later legs first
        return list(reversed(stop_orders))

    def _check_for_pyramid_add(
        self,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.Series,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        campaign: Campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None:
            return []

        should_add_leg = self.strategy.should_pyramid(campaign=campaign)

        if not should_add_leg:
            return []

        leg_orders = self._create_leg_order(
            portfolio=portfolio,
            ticker=ticker,
            trade_type=campaign.trade_type,
            bar_data=bar_data,
            logger=logger,
        )

        return leg_orders

    def _create_leg_order(
        self,
        portfolio: Portfolio,
        ticker: Ticker,
        trade_type: TradeType,
        bar_data: pd.Series,
        logger: logging.Logger,
    ) -> list[SystemOrder]:
        bar_datetime: datetime = bar_data[Indicator.DATETIME]

        campaign = portfolio.get_open_campaign(ticker=ticker)
        leg_num = campaign.next_leg_num if campaign is not None else 0

        limit_price = bar_data[Indicator.CLOSE]

        qty = self.strategy.calculate_qty(
            portfolio=portfolio,
            bar_data=bar_data,
            leg_num=leg_num,
        )

        # The leg's stop is created once the position exists, see AlignDataHandler
        leg_lmt_order = SystemOrder(
            ticker=ticker,
            action=Action.BUY if trade_type == TradeType.LONG else Action.SELL,
            order_type=OrderType.LMT,
            quantity=qty,
            submitted_dt=bar_datetime,
            limit_price=limit_price,
        )

        if self.debug:
            logger.info(
                "[%s] Created leg limit order: %s",
                format_date(bar_datetime),
                leg_lmt_order,
            )

        return [leg_lmt_order]

    def __str__(self):
        INDENT = "  "
        return (
            f"Position Manager (\n"
            f"{INDENT}Broker Client : {self.broker}\n"
            f"{INDENT}In Debug Mode : {self.debug}\n"
            f"{INDENT}Strategy      :\n{self.strategy}"
            f")"
        )
