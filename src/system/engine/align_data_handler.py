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

            position_qty = abs(position.quantity)
            qty_diff = abs(campaign.total_qty - position_qty)
            if math.isclose(qty_diff, 0, abs_tol=1e-9):
                continue

            if campaign.total_qty < position_qty:
                fill_price = self._get_fill_price(
                    campaign_cost=sum(
                        leg.fill_price * leg.current_qty for leg in campaign.open_legs
                    ),
                    position=position,
                    qty_diff=qty_diff,
                    latest_bar=latest_bar,
                )
                fees = self.broker_service.get_trading_fees(
                    shares=qty_diff,
                    price=fill_price,
                    trade_type=position.trade_type,
                )
                excess_qty = portfolio.fill_legs(
                    ticker=position.ticker,
                    qty=qty_diff,
                    fill_price=fill_price,
                    fill_datetime=latest_bar[Indicator.DATETIME],
                    trading_fees=fees,
                )
                self.logger.log(
                    source="AlignDataHandler",
                    log_datetime=bar_datetime,
                    log_level=LogLevel.INFO
                    if math.isclose(excess_qty, 0, abs_tol=1e-9)
                    else LogLevel.WARNING,
                    message="Filled pending legs"
                    if math.isclose(excess_qty, 0, abs_tol=1e-9)
                    else "Filled pending legs and increased main leg quantity",
                    additional_info={
                        "ticker": position.ticker,
                        "qty filled": qty_diff,
                        "excess qty": excess_qty,
                        "campaign": campaign,
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

            # The entry order never filled, so there is nothing to close
            if math.isclose(campaign.total_qty, 0, abs_tol=1e-9):
                portfolio.cancel_unfilled_campaign(campaign=campaign)
                self.logger.log(
                    source="AlignDataHandler",
                    log_datetime=bar_datetime,
                    log_level=LogLevel.INFO,
                    message="Cancelled campaign with unfilled legs",
                    additional_info={"ticker": campaign.ticker},
                )
                continue

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

        new_leg = portfolio.create_pending_leg(
            ticker=position.ticker,
            trade_type=position.trade_type,
            order_price=entry_price,
            order_qty=position_qty,
            order_datetime=entry_datetime,
            stop_price=stop_price,
        )
        portfolio.fill_legs(
            ticker=position.ticker,
            qty=position_qty,
            fill_price=entry_price,
            fill_datetime=entry_datetime,
            trading_fees=fees,
        )

        return new_leg

    def _get_fill_price(
        self,
        campaign_cost: float,
        position: MarketPosition,
        qty_diff: float,
        latest_bar: pd.Series,
    ) -> float:
        # The broker only reports the position's average cost, so derive the new fill's price from it
        fill_price = (
            abs(position.quantity) * position.average_cost - campaign_cost
        ) / qty_diff
        return fill_price if fill_price > 0 else latest_bar[Indicator.CLOSE]

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
