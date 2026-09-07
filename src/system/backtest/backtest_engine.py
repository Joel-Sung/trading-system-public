import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from clients.broker.broker_client import BrokerClient
from clients.database.database_client import DatabaseClient
from custom_types.exception import MyValueError
from custom_types.system import SystemOrder
from custom_types.ticker import Ticker
from strategy.strategy import Strategy
from system.backtest.order_handler import OrderHandler
from system.engine.trading_engine import TradingEngine
from system.evaluator.evaluator import SystemEvaluator
from system.indicator.indicator_types import Indicator
from system.portfolio.portfolio import Portfolio
from system.portfolio.snapshot.snapshot_collector import SnapshotCollector
from util.datetime_util import format_date, format_datetime, get_current_datetime
from util.df_util import does_df_contain_cols
from util.logger import Logger


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        broker: BrokerClient,
        market_data: pd.DataFrame,
        portfolio: Portfolio,
        data_dir: str,
        log_dir: str,
        tickers: list[Ticker] | None = None,
        start_date: datetime | None = None,
        debug: bool = False,
    ) -> None:
        self.strategy = strategy
        self.broker = broker
        self.market_data = market_data
        self.portfolio = portfolio

        self.db_client = DatabaseClient(data_dir=data_dir)

        now = get_current_datetime()
        log_file_path = Path(log_dir) / f"backtest.log.{format_datetime(dt=now)}.txt"
        self.logger: logging.Logger = Logger(
            system_name="backtest",
            log_file_path=log_file_path,
        ).get_logger()

        self.tickers = tickers
        self.start_date = start_date
        self.debug = debug

        self.trading_engine = TradingEngine(
            strategy=strategy,
            broker=broker,
            debug=debug,
        )

    def run(self) -> SnapshotCollector:
        now = get_current_datetime()
        logger = self.logger
        portfolio = self.portfolio
        start_date = self.start_date
        market_data = self.market_data
        logger.info(
            "Starting backtest engine on %s...\n%s",
            format_datetime(dt=now),
            self,
        )

        data = self._prepare_data(market_data=market_data, start_date=start_date)
        logger.info("Prepared data...\n%s", data)

        snapshot_collector = SnapshotCollector()
        first_bar_datetime = data[Indicator.DATETIME].iloc[0]
        final_bar_datetime = data[Indicator.DATETIME].iloc[-1]

        snapshot_collector.collect_state(
            portfolio=portfolio,
            timestamp=first_bar_datetime - timedelta(days=1),
            is_start=True,
        )
        logger.info("Collected initial state...\n%s", snapshot_collector)

        logger.info("Starting strategy...")
        order_handler = OrderHandler(debug=self.debug)
        for bar_datetime, bar_data in data.groupby(Indicator.DATETIME):
            system_orders: list[SystemOrder] = self.trading_engine.process_latest_bars(
                portfolio=portfolio,
                bar_data=bar_data,
                logger=logger,
            )

            portfolio = order_handler.process_orders(
                portfolio=portfolio,
                system_orders=system_orders,
                bar_data=bar_data,
                broker=self.trading_engine.broker,
                logger=logger,
            )

            snapshot_collector.collect_state(
                portfolio=portfolio, timestamp=bar_datetime
            )

            if portfolio.total_equity <= 0.01 * portfolio.initial_equity:
                logger.info("I am broke...\n%s", portfolio)
                break

        snapshot_collector.collect_state(
            portfolio=portfolio,
            timestamp=final_bar_datetime,
            is_end=True,
        )
        logger.info("Collected final state...\n%s", snapshot_collector)

        self.store_states(
            snap_collector=snapshot_collector,
            timestamp=now,
        )
        return snapshot_collector

    def _prepare_data(
        self,
        market_data: pd.DataFrame,
        start_date: datetime | None,
    ) -> pd.DataFrame:
        data = market_data.copy()

        if not does_df_contain_cols(
            data,
            [
                Indicator.TICKER,
                Indicator.DATETIME,
                Indicator.OPEN,
                Indicator.HIGH,
                Indicator.LOW,
                Indicator.CLOSE,
            ],
        ):
            raise MyValueError(
                "Market data does not have the required columns",
                data=data,
            )

        if self.strategy.sector_filter is not None:
            data = data[~data[Indicator.SECTOR].isin(self.strategy.sector_filter)]

        data[Indicator.DATETIME] = pd.to_datetime(data[Indicator.DATETIME])
        data = data.sort_values(Indicator.DATETIME)

        if start_date is not None:
            data = data[data[Indicator.DATETIME] >= start_date]

        if self.tickers is not None and len(self.tickers) > 0:
            data = data[data[Indicator.TICKER].isin(self.tickers)]

        return data

    def store_states(
        self,
        snap_collector: SnapshotCollector,
        timestamp: datetime,
    ):
        port_snapshot_file_name = "snaps_portfolio.csv"
        cam_snapshot_file_name = "snaps_campaigns.csv"
        legs_snapshot_file_name = "snaps_legs.csv"
        evaluation_file_name = "snaps_evaluation.csv"

        # Save portfolio snapshots
        self.db_client.save_system_snapshots(
            snapshots=snap_collector.portfolio_snapshots,
            file_name=port_snapshot_file_name,
        )
        self.db_client.save_backup(
            file_name=port_snapshot_file_name, timestamp=timestamp
        )

        # Save campaign snapshots
        self.db_client.save_system_snapshots(
            snapshots=snap_collector.campaign_snapshots,
            file_name=cam_snapshot_file_name,
        )
        self.db_client.save_backup(
            file_name=cam_snapshot_file_name, timestamp=timestamp
        )

        # Save leg snapshots
        ordered_leg_snapshots = sorted(
            snap_collector.leg_snapshots,
            key=lambda x: (x.ticker, x.entry_datetime),
        )
        self.db_client.save_system_snapshots(
            snapshots=ordered_leg_snapshots, file_name=legs_snapshot_file_name
        )
        self.db_client.save_backup(
            file_name=legs_snapshot_file_name, timestamp=timestamp
        )

        evaluator = SystemEvaluator(
            leg_snapshots=snap_collector.leg_snapshots,
            portfolio_snapshots=snap_collector.portfolio_snapshots,
        )
        evaluation_content = evaluator.evaluate()

        self.db_client.save_evaluation_data(
            content=evaluation_content,
            file_name=evaluation_file_name,
        )
        self.db_client.save_backup(file_name=evaluation_file_name, timestamp=timestamp)

    def __str__(self):
        INDENT = "    "
        return (
            f"Backtest Engine (\n"
            f"{INDENT}Broker: {self.broker}\n"
            f"{INDENT}Debug: {self.debug}\n"
            f"{INDENT}Initial Equity: {self.portfolio.initial_equity}\n"
            f"{INDENT}Start Date: {format_date(self.start_date)}\n"
            f"{INDENT}Tickers: {self.tickers}\n"
            f"{INDENT}Strategy: {self.strategy}\n"
            f")"
        )
