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
from util.logger import Logger, LogLevel


class PositionManager:
    def __init__(
        self, strategy: Strategy, broker: BrokerClient, logger: Logger
    ) -> None:
        self.strategy = strategy
        self.broker = broker
        self.logger = logger

    def create_system_orders(
        self,
        portfolio: Portfolio,
        market_data: pd.DataFrame,
    ) -> list[SystemOrder]:
        system_orders = []
        for ticker, ticker_data in market_data.groupby(Indicator.TICKER, sort=False):
            bar_data = ticker_data.iloc[-1]
            ticker_system_orders = self._create_system_orders_for_ticker(
                bar_datetime=bar_data[Indicator.DATETIME],
                ticker=ticker,
                portfolio=portfolio,
                ticker_data=ticker_data,
                bar_data=bar_data,
            )

            system_orders.extend(ticker_system_orders)

        return system_orders

    def _create_system_orders_for_ticker(
        self,
        bar_datetime: datetime,
        ticker: Ticker,
        portfolio: Portfolio,
        ticker_data: pd.DataFrame,
        bar_data: pd.Series,
    ) -> list[SystemOrder]:
        if len(ticker_data) < self.strategy.min_bars_req_for_entry:
            self.logger.log(
                source="PositionManager",
                log_datetime=bar_datetime,
                log_level=LogLevel.WARNING,
                message="Not enough bars required for entry model",
                additional_info={
                    "required": self.strategy.min_bars_req_for_entry,
                    "available": len(ticker_data),
                },
            )
            return []

        campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None:
            entry_orders = self._check_for_entry(
                bar_datetime=bar_datetime,
                portfolio=portfolio,
                ticker=ticker,
                ticker_data=ticker_data,
                bar_data=bar_data,
            )

            return entry_orders

        update_orders = self._manage_existing_campaign(
            bar_datetime=bar_datetime,
            portfolio=portfolio,
            ticker=ticker,
            ticker_data=ticker_data,
            bar_data=bar_data,
        )

        return update_orders

    def _check_for_entry(
        self,
        bar_datetime: datetime,
        portfolio: Portfolio,
        ticker: Ticker,
        ticker_data: pd.DataFrame,
        bar_data: pd.Series,
    ) -> list[SystemOrder]:
        long_signal = self.strategy.get_long_signal(ticker_data=ticker_data)
        short_signal = self.strategy.get_short_signal(ticker_data=ticker_data)

        if not long_signal and not short_signal:
            return []

        if long_signal and short_signal:
            raise MyValueError(
                "Entry model generated both a long and short signal.",
                entry_model=self.strategy.entry_model,
                ticker=ticker,
                bar_datetime=bar_datetime,
                long_signal=long_signal,
                short_signal=short_signal,
                bar_data=bar_data,
            )

        leg_order = self._create_leg_order(
            bar_datetime=bar_datetime,
            portfolio=portfolio,
            ticker=ticker,
            trade_type=TradeType.LONG if long_signal else TradeType.SHORT,
            bar_data=bar_data,
        )

        return leg_order

    def _manage_existing_campaign(
        self,
        bar_datetime: datetime,
        portfolio: Portfolio,
        ticker: Ticker,
        ticker_data: pd.DataFrame,
        bar_data: pd.Series,
    ) -> list[SystemOrder]:
        self._check_for_mode_change(
            bar_datetime=bar_datetime,
            portfolio=portfolio,
            ticker=ticker,
            ticker_data=ticker_data,
        )

        portfolio.update_with_current_bar(
            ticker=ticker,
            current_bar=bar_data,
            broker=self.broker,
        )

        stop_orders = self._update_trailing_stops(
            bar_datetime=bar_datetime,
            portfolio=portfolio,
            ticker=ticker,
            bar_data=bar_data,
        )

        pyramid_orders = self._check_for_pyramid_add(
            bar_datetime=bar_datetime,
            portfolio=portfolio,
            ticker=ticker,
            bar_data=bar_data,
        )

        system_orders: list[SystemOrder] = []
        system_orders.extend(stop_orders)
        system_orders.extend(pyramid_orders)

        return system_orders

    def _check_for_mode_change(
        self,
        bar_datetime: datetime,
        portfolio: Portfolio,
        ticker: Ticker,
        ticker_data: pd.DataFrame,
    ) -> None:
        campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None:
            return

        new_mode = self.strategy.get_new_mode(
            campaign=campaign, ticker_data=ticker_data
        )

        if new_mode == campaign.mode:
            return

        self.logger.log(
            source="PositionManager",
            log_datetime=bar_datetime,
            log_level=LogLevel.INFO,
            message="Changed campaign mode",
            additional_info={
                "from": campaign.mode,
                "to": new_mode,
                "campaign": campaign,
            },
        )

        campaign.change_mode(new_mode=new_mode)

    def _update_trailing_stops(
        self,
        bar_datetime: datetime,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.Series,
    ) -> list[SystemOrder]:
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

            # Pending legs have no position to protect yet
            if leg.is_pending:
                continue

            stop_order = SystemOrder(
                ticker=ticker,
                action=Action.SELL if leg.trade_type == TradeType.LONG else Action.BUY,
                order_type=OrderType.STP,
                quantity=leg.current_qty,
                submitted_dt=bar_datetime,
                stop_price=new_stop_price,
            )

            # self.logger.log(
            #     source="PositionManager",
            #     log_datetime=bar_datetime,
            #     log_level=LogLevel.DEBUG,
            #     message="Created stop order",
            #     additional_info={"stop_order": stop_order, "leg": leg},
            # )

            stop_orders.append(stop_order)

        # Submit stop orders for later legs first
        return list(reversed(stop_orders))

    def _check_for_pyramid_add(
        self,
        bar_datetime: datetime,
        portfolio: Portfolio,
        ticker: Ticker,
        bar_data: pd.Series,
    ) -> list[SystemOrder]:
        campaign: Campaign = portfolio.get_open_campaign(ticker=ticker)

        if campaign is None or any(leg.is_pending for leg in campaign.open_legs):
            return []

        should_add_leg = self.strategy.should_pyramid(campaign=campaign)

        if not should_add_leg:
            return []

        leg_orders = self._create_leg_order(
            bar_datetime=bar_datetime,
            portfolio=portfolio,
            ticker=ticker,
            trade_type=campaign.trade_type,
            bar_data=bar_data,
        )

        return leg_orders

    def _create_leg_order(
        self,
        bar_datetime: datetime,
        portfolio: Portfolio,
        ticker: Ticker,
        trade_type: TradeType,
        bar_data: pd.Series,
    ) -> list[SystemOrder]:

        campaign = portfolio.get_open_campaign(ticker=ticker)
        leg_num = campaign.next_leg_num if campaign is not None else 0

        limit_price = bar_data[Indicator.CLOSE]

        qty = self.strategy.calculate_qty(
            portfolio=portfolio,
            bar_data=bar_data,
            leg_num=leg_num,
        )
        qty = round(qty, 3)

        if qty == 0:
            return []

        r_value = self.strategy.get_r_value(current_bar=bar_data, campaign=campaign)
        stop_price = (
            limit_price - r_value
            if trade_type == TradeType.LONG
            else limit_price + r_value
        )

        limit_stop_order = SystemOrder(
            ticker=ticker,
            action=Action.BUY if trade_type == TradeType.LONG else Action.SELL,
            order_type=OrderType.LMT_STP,
            quantity=qty,
            submitted_dt=bar_datetime,
            limit_price=limit_price,
            stop_price=stop_price,
        )

        portfolio.create_pending_leg(
            ticker=ticker,
            trade_type=trade_type,
            order_price=limit_price,
            order_qty=qty,
            order_datetime=bar_datetime,
            stop_price=stop_price,
        )

        # self.logger.log(
        #     source="PositionManager",
        #     log_datetime=bar_datetime,
        #     log_level=LogLevel.DEBUG,
        #     message="Created leg limit stop order",
        #     additional_info={"limit_stop_order": limit_stop_order},
        # )

        return [limit_stop_order]

    def __str__(self):
        INDENT = "  "
        return (
            f"Position Manager (\n"
            f"{INDENT}Broker Client : {self.broker}\n"
            f"{INDENT}Strategy      :\n{self.strategy}"
            f")"
        )
