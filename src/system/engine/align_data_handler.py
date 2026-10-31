import math
from collections.abc import Callable
from datetime import datetime

import pandas as pd
from clients.broker.broker_service import BrokerService
from custom_types.market import MarketAssets, MarketPosition, TradeType
from strategy.strategy import Strategy
from system.indicator.indicator_types import Indicator
from system.portfolio.campaign import Campaign
from system.portfolio.portfolio import Portfolio
from util.datetime_util import get_current_dt
from util.df_util import get_ticker_latest_bar


class AlignDataHandler:
    """Aligns the system's portfolio and campaigns with the broker's assets and positions."""

    def __init__(
        self,
        strategy: Strategy,
        broker_service: BrokerService,
        get_now: Callable[[], datetime] | None = None,
    ):
        self.strategy = strategy
        self.broker_service = broker_service
        # Injectable so a backtest can run on its own simulated clock
        self.get_now = get_now or get_current_dt

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
        for position in market_positions:
            campaign = portfolio.get_open_campaign(ticker=position.ticker)
            position_qty = abs(position.quantity)
            latest_bar = get_ticker_latest_bar(market_data, position.ticker)

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
        self, campaign: Campaign, qty_to_remove: float, exit_price: float
    ) -> None:
        """
        Removes qty from the latest leg first, moving on to the previous legs
        until the quantity is removed. Legs left with no quantity are closed.
        """
        now = self.get_now()

        while not math.isclose(qty_to_remove, 0) and campaign.open_legs:
            latest_leg = campaign.open_legs[-1]
            leg_qty_to_remove = min(qty_to_remove, latest_leg.current_qty)

            campaign.sell_qty(
                qty=leg_qty_to_remove,
                exit_price=exit_price,
                exit_datetime=now,
            )
            qty_to_remove -= leg_qty_to_remove

    def _create_campaign(
        self,
        portfolio: Portfolio,
        position: MarketPosition,
        latest_bar: pd.Series,
    ) -> None:
        now = self.get_now()
        position_qty = abs(position.quantity)

        new_campaign = portfolio.create_campaign(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_datetime=now,
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

        fees = self.broker_service.calculate_fees(
            shares=position_qty,
            price=position.average_cost,
            trade_type=position.trade_type,
        )

        cash_balance = portfolio.cash_balance
        cash_available_for_trading = portfolio.cash_available_for_trading

        portfolio.create_leg(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_price=entry_price,
            entry_datetime=now,
            trading_fees=fees,
            qty=position_qty,
            stop_price=stop_price,
        )

        # The broker's cash already accounts for the position, so creating its leg
        # must not take the cost out of the aligned cash a second time
        portfolio.cash_balance = cash_balance
        portfolio.cash_available_for_trading = cash_available_for_trading
