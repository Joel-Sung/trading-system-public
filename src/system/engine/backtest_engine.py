import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from clients.broker.broker_client import BrokerClient
from clients.broker.broker_service import BrokerService
from clients.broker.stub_broker_client import StubBrokerClient
from clients.database.database_client import DatabaseClient, FileType
from clients.database.database_service import DatabaseService
from clients.database.stub_database_client import StubDatabaseClient
from custom_types.exception import MyValueError
from custom_types.ticker import Ticker
from strategy.strategy import Strategy
from system.engine.trading_engine import TradingEngine
from system.evaluator.evaluator import SystemEvaluator
from system.indicator.indicator_types import Indicator
from system.portfolio.portfolio import Portfolio
from system.portfolio.snapshot.snapshot_collector import SnapshotCollector
from util.datetime_util import format_date, format_dt, get_current_dt
from util.logger import Logger
from util.market_data_util import does_df_contain_cols


class BacktestEngine:
    """
    Replays the live application: for every day in the market data, the
    TradingEngine runs once against a StubBrokerClient and a StubDatabaseClient,
    which are created for every run. The stubs keep the broker account, the
    orders and the stored portfolio in memory, so nothing is written to disk
    while the backtest runs.

    broker is only used for its fee calculations. data_dir/log_dir are only
    used to store the results of the backtest once it has finished.
    """

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

        now = get_current_dt()
        log_file_path = Path(log_dir) / f"backtest.log.{format_dt(dt=now)}.txt"
        self.logger: logging.Logger = Logger(
            system_name="backtest",
            log_file_path=log_file_path,
        ).get_logger()

        self.tickers = tickers
        self.start_date = start_date
        self.debug = debug

        self.duration_mins: float | None = None
        self._now: datetime | None = None

        self.stub_broker_client: StubBrokerClient | None = None
        self.stub_database_client: StubDatabaseClient | None = None
        self.trading_engine: TradingEngine | None = None

    def run(self) -> SnapshotCollector:
        now = get_current_dt()
        logger = self.logger

        self.engine_start_time = now
        logger.info("Starting backtest engine on %s...\n", format_dt(dt=now))
        print("Starting backtest...")

        start_time = get_current_dt()
        snapshot_collector = self._run_backtest()
        end_time = get_current_dt()

        self.duration_mins = (end_time - start_time).total_seconds() / 60
        logger.info("Backtest took %.2f minutes...", self.duration_mins)
        print(f"Finished backtest in {self.duration_mins:.2f} mins...")

        print("Storing snapshots and running evaluation...")
        self._save_states(snap_collector=snapshot_collector, timestamp=now)
        self._evaluate_and_save_evaluation(
            snap_collector=snapshot_collector, timestamp=now
        )

        return snapshot_collector

    def _run_backtest(self) -> SnapshotCollector:
        logger = self.logger
        start_date = self.start_date

        data = self._prepare_data(market_data=self.market_data)

        bar_datetimes = self._get_bar_datetimes(data, start_date=start_date)
        if bar_datetimes.empty:
            raise MyValueError(
                "Market data has no bars to backtest",
                start_date=start_date,
                data=data,
            )

        trading_engine = self._create_trading_engine(
            data, start_datetime=bar_datetimes.iloc[0]
        )

        snapshot_collector = SnapshotCollector()
        first_bar_datetime = bar_datetimes.iloc[0]
        final_bar_datetime = bar_datetimes.iloc[-1]

        portfolio = self.portfolio
        snapshot_collector.collect_state(
            portfolio=portfolio,
            timestamp=first_bar_datetime - timedelta(days=1),
            is_start=True,
        )
        logger.info("Collected initial state...\n%s", snapshot_collector)

        logger.info("Starting strategy...")
        current_year: int | None = None

        for bar_datetime in bar_datetimes:
            if bar_datetime.year != current_year:
                current_year = bar_datetime.year
                print(
                    f"[{format_dt(dt=get_current_dt())}] Reached year {current_year}..."
                )

            # A new day: the engine runs, then the broker moves on and matches its orders
            self._now = bar_datetime
            portfolio = trading_engine.run()
            self.stub_broker_client.advance()

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

        return snapshot_collector

    def _create_trading_engine(
        self, history: pd.DataFrame, start_datetime: datetime
    ) -> TradingEngine:
        """
        Builds the trading engine on fresh stubs. The stubs start with the given
        portfolio's cash and the portfolio itself, as an engine that has
        already been set up in the live application.
        """
        stub_broker_client = StubBrokerClient(
            market_data=history,
            initial_cash=self.portfolio.cash_balance,
            fee_broker=self.broker,
            start_datetime=start_datetime,
        )
        stub_database_client = StubDatabaseClient()
        database_service = DatabaseService(stub_database_client)
        database_service.save_portfolio(self.portfolio)

        # Everything that asks for the time uses the simulated day of the backtest
        self._now = start_datetime
        broker_service = BrokerService(stub_broker_client, get_now=lambda: self._now)
        trading_engine = TradingEngine(
            broker_service=broker_service,
            strategy=self.strategy,
            database_service=database_service,
            logger=self.logger,
        )
        trading_engine.position_manager.debug = self.debug

        self.stub_broker_client = stub_broker_client
        self.stub_database_client = stub_database_client
        self.trading_engine = trading_engine

        return trading_engine

    @staticmethod
    def _get_bar_datetimes(
        data: pd.DataFrame, start_date: datetime | None
    ) -> pd.Series:
        bar_datetimes = data[Indicator.DATETIME]
        if start_date is not None:
            bar_datetimes = bar_datetimes[bar_datetimes >= start_date]

        return bar_datetimes.drop_duplicates().sort_values().reset_index(drop=True)

    def _prepare_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
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

        if self.tickers is not None and len(self.tickers) > 0:
            data = data[data[Indicator.TICKER].isin(self.tickers)]

        return data

    def _save_states(
        self,
        snap_collector: SnapshotCollector,
        timestamp: datetime,
    ):
        port_snapshot_file_name = "snaps_portfolio.csv"
        cam_snapshot_file_name = "snaps_campaigns.csv"
        legs_snapshot_file_name = "snaps_legs.csv"

        # Save portfolio snapshots
        self.db_client.save(
            data=snap_collector.portfolio_snapshots,
            file_name=port_snapshot_file_name,
        )
        self.db_client.backup(file_name=port_snapshot_file_name, timestamp=timestamp)

        # Save campaign snapshots
        self.db_client.save(
            data=snap_collector.campaign_snapshots,
            file_name=cam_snapshot_file_name,
        )
        self.db_client.backup(file_name=cam_snapshot_file_name, timestamp=timestamp)

        # Save leg snapshots
        ordered_leg_snapshots = sorted(
            snap_collector.leg_snapshots,
            key=lambda x: (x.ticker, x.entry_datetime),
        )
        self.db_client.save(
            data=ordered_leg_snapshots,
            file_name=legs_snapshot_file_name,
        )
        self.db_client.backup(file_name=legs_snapshot_file_name, timestamp=timestamp)

    def _evaluate_and_save_evaluation(
        self,
        snap_collector: SnapshotCollector,
        timestamp: datetime,
    ):
        evaluation_file_name = "snaps_evaluation.txt"

        evaluator = SystemEvaluator(
            leg_snapshots=snap_collector.leg_snapshots,
            portfolio_snapshots=snap_collector.portfolio_snapshots,
            backtest_engine=self,
        )
        evaluation_content = evaluator.evaluate()

        self.db_client.save(
            data=evaluation_content,
            file_name=evaluation_file_name,
            file_type=FileType.TXT,
        )
        self.db_client.backup(file_name=evaluation_file_name, timestamp=timestamp)

    def __str__(self):
        INDENT = "  "
        return (
            f"Backtest Engine (\n"
            f"{INDENT}Engine Start Time: {format_dt(self.engine_start_time)}\n"
            f"{INDENT}Backtest Duration: {f'{self.duration_mins:.2f} mins' if self.duration_mins else 'Not run yet'}\n"
            f"{INDENT}Broker: {self.broker}\n"
            f"{INDENT}Debug: {self.debug}\n"
            f"{INDENT}Initial Equity: {self.portfolio.initial_equity}\n"
            f"{INDENT}Market Data Start Date: {format_date(self.start_date)}\n"
            f"{INDENT}Tickers: {self.tickers}\n"
            f"{INDENT}Strategy:\n{self.strategy}\n"
            f")"
        )
