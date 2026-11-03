from datetime import datetime

import pandas as pd
from clients.broker.broker_service import BrokerService
from clients.database.database_service import DatabaseService
from custom_types.market import (
    MarketAssets,
    MarketBarPeriod,
    MarketOrder,
    MarketPosition,
)
from custom_types.system import SystemOrder
from strategy.strategy import Strategy
from system.engine.align_data_handler import AlignDataHandler
from system.engine.position_manager import PositionManager
from system.portfolio.portfolio import Portfolio
from util.logger import Logger, LogLevel


class TradingEngine:
    def __init__(
        self,
        broker_service: BrokerService,
        strategy: Strategy,
        database_service: DatabaseService,
        logger: Logger,
        period: MarketBarPeriod = MarketBarPeriod.DAY,
    ):
        self.broker_service = broker_service
        self.strategy = strategy
        self.period = period
        self.database_service = database_service
        self.logger = logger
        self.align_data_handler = AlignDataHandler(
            strategy=strategy,
            broker_service=broker_service,
            logger=logger,
        )
        self.position_manager = PositionManager(
            strategy=strategy,
            broker=broker_service.broker,
            logger=logger,
        )

    def _get_broker_data(self, end_time: datetime):
        assets: MarketAssets = self.broker_service.get_assets()
        positions: list[MarketPosition] = self.broker_service.get_positions()
        orders: list[MarketOrder] = self.broker_service.get_orders()
        market_data: pd.DataFrame = self.broker_service.get_market_data(
            number_of_bars=self.strategy.min_bars_req_for_inds,
            period=self.period,
            end_time=end_time,
        )
        return assets, positions, orders, market_data

    def _get_portfolio_data(self) -> Portfolio | None:
        return self.database_service.get_portfolio()

    def _align_portfolio_data(
        self,
        portfolio: Portfolio | None,
        assets: MarketAssets,
        positions: list[MarketPosition],
        market_data: pd.DataFrame,
    ) -> Portfolio:
        if portfolio is None:
            portfolio = Portfolio(initial_equity=assets.net_liquidation)

        portfolio = self.align_data_handler.align_campaigns(
            portfolio=portfolio,
            market_positions=positions,
            market_data=market_data,
        )
        # Last, so the broker's assets overwrite the cash the portfolio tracked while aligning campaigns
        portfolio = self.align_data_handler.align_portfolio(
            portfolio=portfolio, market_assets=assets
        )
        return portfolio

    def _create_orders(
        self, portfolio: Portfolio, market_data: pd.DataFrame
    ) -> list[SystemOrder]:
        return self.position_manager.create_system_orders(
            portfolio=portfolio, market_data=market_data
        )

    def _place_orders(self, system_orders: list[SystemOrder]) -> list:
        return self.broker_service.place_orders(system_orders)

    def _save_portfolio(self, portfolio: Portfolio) -> None:
        self.database_service.save_portfolio(portfolio)

    def run(self, end_time: datetime | None = None) -> Portfolio:
        if end_time is None:
            end_time = datetime.now()
        assets, positions, _, bars = self._get_broker_data(end_time=end_time)

        market_data = self.strategy.prepare_data(bars)
        portfolio = self._get_portfolio_data()
        portfolio = self._align_portfolio_data(
            portfolio,
            assets,
            positions,
            market_data,
        )

        system_orders = self._create_orders(portfolio, market_data)

        self._place_orders(system_orders)
        self.logger.log(
            source="TradingEngine",
            log_datetime=end_time,
            log_level=LogLevel.INFO,
            message="Placed system orders",
            additional_info={"system orders count": len(system_orders)},
        )

        self._save_portfolio(portfolio)
        self.logger.log(
            source="TradingEngine",
            log_datetime=end_time,
            log_level=LogLevel.INFO,
            message="Saved portfolio",
            additional_info={"portfolio": portfolio},
        )

        return portfolio
