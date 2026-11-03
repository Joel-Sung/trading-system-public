import math

import pandas as pd
from clients.broker.broker_service import BrokerService
from custom_types.market import MarketAssets, MarketPosition, TradeType
from strategy.strategy import Strategy
from system.indicator.indicator_types import Indicator
from system.portfolio.leg import Leg
from system.portfolio.portfolio import Portfolio
from util.logger import Logger, LogLevel
from util.market_data_util import get_ticker_latest_bar


class AlignDataHandler:
    """Aligns the system's portfolio and campaigns with the broker's assets and positions."""

    def __init__(
        self,
        strategy: Strategy,
        broker_service: BrokerService,
        logger: Logger,
    ):
        self.strategy = strategy
        self.broker_service = broker_service
        self.logger = logger

    def align_campaigns(
        self,
        portfolio: Portfolio,
        market_positions: list[MarketPosition],
        market_data: pd.DataFrame,
    ) -> Portfolio:
        bar_datetime = market_data[Indicator.DATETIME].max()

        # Check for missing campaigns and out-of-sync quantities
        for position in market_positions:
            campaign = portfolio.get_open_campaign(ticker=position.ticker)

            latest_bar = get_ticker_latest_bar(market_data, position.ticker)
            if latest_bar.empty:
                self.logger.log(
                    source="AlignDataHandler",
                    log_datetime=bar_datetime,
                    log_level=LogLevel.WARNING,
                    message="No market data found",
                    additional_info={"ticker": position.ticker},
                )
                continue

            if campaign is None:
                leg = self._create_campaign(
                    portfolio=portfolio,
                    position=position,
                    latest_bar=latest_bar,
                )
                self.logger.log(
                    source="AlignDataHandler",
                    log_datetime=bar_datetime,
                    log_level=LogLevel.INFO,
                    message="Created new campaign",
                    additional_info={"ticker": position.ticker, "leg 0": leg},
                )
                continue

            qty_diff = abs(campaign.total_qty - position.quantity)
            if math.isclose(qty_diff, 0, abs_tol=1e-9):
                continue

            if campaign.total_qty < position.quantity:
                campaign.main_leg.current_qty += qty_diff
                self.logger.log(
                    source="AlignDataHandler",
                    log_datetime=bar_datetime,
                    log_level=LogLevel.WARNING,
                    message="Increased main leg quantity",
                    additional_info={
                        "ticker": position.ticker,
                        "qty added": qty_diff,
                        "main leg": campaign.main_leg,
                    },
                )
                continue

            portfolio.sell_campaign_qty(
                campaign=campaign,
                qty=qty_diff,
                exit_price=latest_bar[Indicator.CLOSE],
                exit_datetime=latest_bar[Indicator.DATETIME],
            )
            self.logger.log(
                source="AlignDataHandler",
                log_datetime=bar_datetime,
                log_level=LogLevel.WARNING,
                message="Reduced campaign quantity",
                additional_info={
                    "ticker": position.ticker,
                    "qty removed": qty_diff,
                    "main leg": campaign.main_leg,
                },
            )

        # Check for extra campaigns
        position_tickers = {position.ticker for position in market_positions}
        for campaign in list(portfolio.open_trade_campaigns):
            if campaign.ticker in position_tickers:
                continue

            latest_bar = get_ticker_latest_bar(market_data, campaign.ticker)
            portfolio.sell_campaign_qty(
                campaign=campaign,
                qty=campaign.total_qty,
                exit_price=latest_bar[Indicator.CLOSE],
                exit_datetime=latest_bar[Indicator.DATETIME],
            )
            self.logger.log(
                source="AlignDataHandler",
                log_datetime=bar_datetime,
                log_level=LogLevel.INFO,
                message="Closed campaign",
                additional_info={
                    "ticker": campaign.ticker,
                    "main leg": campaign.main_leg,
                },
            )

        return portfolio

    def _create_campaign(
        self,
        portfolio: Portfolio,
        position: MarketPosition,
        latest_bar: pd.Series,
    ) -> Leg:
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

        new_leg = portfolio.create_leg(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_price=entry_price,
            entry_datetime=entry_datetime,
            trading_fees=fees,
            qty=position_qty,
            stop_price=stop_price,
        )

        return new_leg

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
