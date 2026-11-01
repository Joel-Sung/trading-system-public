import logging
import math
from datetime import datetime

import pandas as pd
from clients.broker.broker_service import BrokerService
from custom_types.market import MarketAssets, MarketPosition, TradeType
from strategy.strategy import Strategy
from system.indicator.indicator_types import Indicator
from system.portfolio.campaign import Campaign
from system.portfolio.portfolio import Portfolio
from util.datetime_util import format_date
from util.market_data_util import get_ticker_latest_bar


class AlignDataHandler:
    """Aligns the system's portfolio and campaigns with the broker's assets and positions."""

    def __init__(
        self,
        strategy: Strategy,
        broker_service: BrokerService,
        logger: logging.Logger,
    ):
        self.strategy = strategy
        self.broker_service = broker_service
        self.logger = logger

    def align_portfolio(
        self,
        portfolio: Portfolio | None,
        market_assets: MarketAssets,
    ) -> Portfolio:
        if portfolio is None:
            portfolio = Portfolio(initial_equity=market_assets.net_liquidation)

        portfolio.cash_balance = market_assets.cash_balance
        portfolio.cash_available_for_trading = market_assets.cash_available_for_trading

        return portfolio

    def align_campaigns(
        self,
        portfolio: Portfolio,
        market_positions: list[MarketPosition],
        market_data: pd.DataFrame,
    ) -> Portfolio:
        bar_datetime = market_data[Indicator.DATETIME].max()

        for position in market_positions:
            campaign = portfolio.get_open_campaign(ticker=position.ticker)
            position_qty = abs(position.quantity)

            latest_bar = get_ticker_latest_bar(market_data, position.ticker)
            if latest_bar.empty:
                self.logger.warning(
                    "[%s] No market data found for ticker %s.",
                    format_date(bar_datetime),
                    position.ticker,
                )
                continue

            if campaign is None:
                self._create_campaign(
                    portfolio=portfolio,
                    position=position,
                    latest_bar=latest_bar,
                )
                continue

            if campaign.total_qty == position_qty:
                continue

            if campaign.total_qty < position_qty:
                campaign.main_leg.current_qty += position_qty - campaign.total_qty
                continue

            self._reduce_campaign_qty(
                campaign=campaign,
                qty_to_remove=campaign.total_qty - position_qty,
                exit_price=latest_bar[Indicator.CLOSE],
                exit_datetime=latest_bar[Indicator.DATETIME],
            )
            self._archive_if_closed(portfolio=portfolio, campaign=campaign)

        # The broker no longer reports positions that were fully closed
        held_tickers = {position.ticker for position in market_positions}
        for campaign in list(portfolio.open_trade_campaigns):
            if campaign.ticker in held_tickers:
                continue

            latest_bar = get_ticker_latest_bar(market_data, campaign.ticker)
            self._reduce_campaign_qty(
                campaign=campaign,
                qty_to_remove=campaign.total_qty,
                exit_price=latest_bar[Indicator.CLOSE],
                exit_datetime=latest_bar[Indicator.DATETIME],
            )
            self._archive_if_closed(portfolio=portfolio, campaign=campaign)

        return portfolio

    @staticmethod
    def _archive_if_closed(portfolio: Portfolio, campaign: Campaign) -> None:
        if campaign.is_open:
            return

        portfolio.open_trade_campaigns.remove(campaign)
        portfolio.closed_trade_campaigns.append(campaign)

    def _reduce_campaign_qty(
        self,
        campaign: Campaign,
        qty_to_remove: float,
        exit_price: float,
        exit_datetime: datetime,
    ) -> None:
        """
        Removes qty from the latest leg first, moving on to the previous legs
        until the quantity is removed. Legs left with no quantity are closed.
        """
        while not math.isclose(qty_to_remove, 0) and campaign.open_legs:
            latest_leg = campaign.open_legs[-1]
            leg_qty_to_remove = min(qty_to_remove, latest_leg.current_qty)

            campaign.sell_qty(
                qty=leg_qty_to_remove,
                exit_price=exit_price,
                exit_datetime=exit_datetime,
            )
            qty_to_remove -= leg_qty_to_remove

    def _create_campaign(
        self,
        portfolio: Portfolio,
        position: MarketPosition,
        latest_bar: pd.Series,
    ) -> None:
        entry_datetime = latest_bar[Indicator.DATETIME]
        position_qty = abs(position.quantity)

        new_campaign = portfolio.create_campaign(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_datetime=entry_datetime,
        )

        entry_price = position.average_cost

        r_value = self.strategy.get_r_value(
            current_bar=latest_bar,
            campaign=new_campaign,
        )
        stop_price = (
            entry_price - r_value
            if position.trade_type == TradeType.LONG
            else entry_price + r_value
        )

        fees = self.broker_service.get_trading_fees(
            shares=position_qty,
            price=position.average_cost,
            trade_type=position.trade_type,
        )

        portfolio.create_leg(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_price=entry_price,
            entry_datetime=entry_datetime,
            trading_fees=fees,
            qty=position_qty,
            stop_price=stop_price,
        )
