import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from clients.broker.broker_client import BrokerClient
from clients.broker.broker_service import BrokerService
from clients.broker.stub_broker_client import StubBrokerClient
from clients.database.database_client import DatabaseClient, FileType
from clients.database.stub_database_service import StubDatabaseService
from custom_types.exception import MyValueError
from custom_types.ticker import Ticker
from strategy.strategy import Strategy
from system.engine.trading_engine import TradingEngine
from system.evaluator.evaluator import SystemEvaluator
from system.indicator.indicator_types import Indicator
from system.portfolio.portfolio import Portfolio
from system.portfolio.snapshot.snapshot_collector import SnapshotCollector
from util.datetime_util import format_date, format_dt, get_current_dt
from util.logger import Logger, LogLevel
from util.market_data_util import format_market_data


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
    ) -> None:
        self.strategy = strategy
        self.broker = broker
        self.market_data = market_data
        self.portfolio = portfolio

        self.db_client = DatabaseClient(data_dir=data_dir)

        now = get_current_dt()
        log_file_path = Path(log_dir) / f"backtest.log.{format_dt(dt=now)}.txt"
        self.logger: Logger = Logger(
            system_name="backtest",
            log_file_path=log_file_path,
        )

        self.start_date = start_date

        self.included_tickers = tickers
        self.excluded_tickers = []
        # DOW has no data from 2017-08-31 to 2019-04-02
        if start_date is None or start_date < datetime(2019, 5, 1):
            self.excluded_tickers.append(Ticker.DOW)

        self.duration_mins: float | None = None
        self.engine_start_time = now
        self._has_run = False

        # Everything the backtest needs is prepared here so that run() only replays
        init_start = time.perf_counter()

        step_start = time.perf_counter()
        data = self._preprocess_data(market_data=self.market_data)
        print(
            f"[init] Preprocessed market data: {len(data)} rows in "
            f"{time.perf_counter() - step_start:.2f}s"
        )

        step_start = time.perf_counter()
        self.run_datetimes: list[pd.Timestamp] = self._get_run_datetimes(
            data, start_date=self.start_date
        )
        if not self.run_datetimes:
            raise MyValueError(
                "Market data has no bars to backtest",
                start_date=self.start_date,
                min_bars_req=self.strategy.min_bars_req_for_inds,
                data=data,
            )
        print(
            f"[init] Found {len(self.run_datetimes)} bars to backtest "
            f"({format_date(self.run_datetimes[0])} to "
            f"{format_date(self.run_datetimes[-1])}) in "
            f"{time.perf_counter() - step_start:.2f}s"
        )

        step_start = time.perf_counter()
        self.stub_broker_client: StubBrokerClient = StubBrokerClient(
            market_data=data,
            initial_cash=self.portfolio.cash_balance,
            fee_broker=self.broker,
            start_datetime=self.run_datetimes[0],
        )
        print(
            f"[init] Created stub broker client in "
            f"{time.perf_counter() - step_start:.2f}s"
        )

        step_start = time.perf_counter()
        self.stub_database_service = StubDatabaseService()
        self.stub_database_service.save_portfolio(self.portfolio)
        database_service = self.stub_database_service

        self.trading_engine: TradingEngine = TradingEngine(
            broker_service=BrokerService(self.stub_broker_client),
            strategy=self.strategy,
            database_service=database_service,
            logger=self.logger,
        )
        print(
            f"[init] Created trading engine in {time.perf_counter() - step_start:.2f}s"
        )
        print(f"[init] Backtest ready in {time.perf_counter() - init_start:.2f}s")

    def run(self) -> SnapshotCollector:
        print("Starting backtest...")
        now = get_current_dt()

        self.engine_start_time = now
        self.logger.log(
            source="BacktestEngine",
            log_datetime=now,
            log_level=LogLevel.INFO,
            message="Starting backtest engine",
        )

        start_time = get_current_dt()
        snapshot_collector = self._run_backtest()
        end_time = get_current_dt()

        self.duration_mins = (end_time - start_time).total_seconds() / 60
        self.logger.log(
            source="BacktestEngine",
            log_datetime=end_time,
            log_level=LogLevel.INFO,
            message="Backtest finished",
            additional_info={"duration_mins": f"{self.duration_mins:.2f}"},
        )
        print(f"Finished backtest in {self.duration_mins:.2f} mins...")

        print("Storing snapshots...")
        step_start = time.perf_counter()
        self._save_states(snap_collector=snapshot_collector, timestamp=now)
        print(f"Stored snapshots in {time.perf_counter() - step_start:.2f}s")

        print("Running evaluation...")
        step_start = time.perf_counter()
        self._evaluate_and_save_evaluation(
            snap_collector=snapshot_collector, timestamp=now
        )
        print(
            f"Evaluated and stored results in {time.perf_counter() - step_start:.2f}s"
        )

        print("Backtest completed...")
        return snapshot_collector

    def _run_backtest(self) -> SnapshotCollector:
        if self._has_run:
            raise MyValueError(
                "Backtest engine has already run, create a new engine to run again"
            )
        self._has_run = True

        bar_datetimes = self.run_datetimes
        trading_engine = self.trading_engine
        snapshot_collector = SnapshotCollector()
        first_bar_datetime = bar_datetimes[0]
        final_bar_datetime = bar_datetimes[-1]

        portfolio = self.portfolio
        snapshot_collector.collect_state(
            portfolio=portfolio,
            timestamp=first_bar_datetime - timedelta(days=1),
            is_start=True,
        )
        self.logger.log(
            source="BacktestEngine",
            log_datetime=first_bar_datetime,
            log_level=LogLevel.INFO,
            message="Collected initial state",
            additional_info={"snapshot_collector": snapshot_collector},
        )

        self.logger.log(
            source="BacktestEngine",
            log_datetime=first_bar_datetime,
            log_level=LogLevel.INFO,
            message="Starting strategy",
        )
        current_year: int | None = None
        current_month: int | None = None

        # Time spent in each part of the daily loop
        engine_secs = 0.0
        broker_secs = 0.0
        snapshot_secs = 0.0
        month_start = time.perf_counter()
        month_days = 0
        loop_start = time.perf_counter()

        for bar_datetime in bar_datetimes:
            if bar_datetime.year != current_year:
                current_year = bar_datetime.year
                print(
                    f"[{format_dt(dt=get_current_dt())}] Reached year {current_year}... "
                    f"trading engine took {engine_secs:.2f}s, "
                    f"broker advance took {broker_secs:.2f}s, "
                    f"snapshot collection took {snapshot_secs:.2f}s"
                )

            if bar_datetime.month != current_month:
                prev_month_str = ""
                if month_days > 0:
                    prev_month_str = f"Prev month took {time.perf_counter() - month_start:.2f}s for {month_days} days"
                current_month = bar_datetime.month
                month_start = time.perf_counter()
                month_days = 0
                print(
                    f"[{format_dt(dt=get_current_dt())}] Reached month {current_month}... {prev_month_str}"
                )

            step_start = time.perf_counter()
            portfolio = trading_engine.run(end_time=bar_datetime)
            engine_secs += time.perf_counter() - step_start

            step_start = time.perf_counter()
            self.stub_broker_client.advance()
            broker_secs += time.perf_counter() - step_start

            step_start = time.perf_counter()
            snapshot_collector.collect_state(
                portfolio=portfolio, timestamp=bar_datetime
            )
            snapshot_secs += time.perf_counter() - step_start
            month_days += 1

            if portfolio.total_equity <= 0.01 * portfolio.initial_equity:
                self.logger.log(
                    source="BacktestEngine",
                    log_datetime=bar_datetime,
                    log_level=LogLevel.INFO,
                    message="I am broke",
                    additional_info={"portfolio": portfolio},
                )
                break

        loop_secs = time.perf_counter() - loop_start
        print(
            f"Total duration: {loop_secs:.2f}s, "
            f"trading engine took {engine_secs:.2f}s, "
            f"broker advance took {broker_secs:.2f}s, "
            f"snapshot collection took {snapshot_secs:.2f}s"
        )

        step_start = time.perf_counter()
        snapshot_collector.collect_state(
            portfolio=portfolio,
            timestamp=final_bar_datetime,
            is_end=True,
        )
        print(
            f"Collected final leg and campaign states in "
            f"{time.perf_counter() - step_start:.2f}s"
        )
        self.logger.log(
            source="BacktestEngine",
            log_datetime=final_bar_datetime,
            log_level=LogLevel.INFO,
            message="Collected final state",
            additional_info={"snapshot_collector": snapshot_collector},
        )

        return snapshot_collector

    def _get_run_datetimes(
        self, data: pd.DataFrame, start_date: datetime | None
    ) -> list[pd.Timestamp]:
        """
        Bar datetimes the trading engine runs on. The engine needs
        min_bars_req_for_inds bars of history, so the first runs are skipped until
        that many bars exist. Bars before start_date still count as history.
        """
        # data is already formatted: sorted by datetime
        all_datetimes = pd.Series(data[Indicator.DATETIME].unique())
        first_index = max(self.strategy.min_bars_req_for_inds - 1, 0)
        run_datetimes = all_datetimes.iloc[first_index:]

        if start_date is not None:
            run_datetimes = run_datetimes[run_datetimes >= start_date]

        return [pd.Timestamp(d) for d in run_datetimes]

    def _preprocess_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        data = market_data

        if self.included_tickers is not None and len(self.included_tickers) > 0:
            data = data[data[Indicator.TICKER].isin(self.included_tickers)]

        if self.excluded_tickers is not None and len(self.excluded_tickers) > 0:
            data = data[~data[Indicator.TICKER].isin(self.excluded_tickers)]

        return format_market_data(data)

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
            key=lambda x: (x.ticker, x.fill_datetime),
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
            f"{INDENT}Initial Equity: {self.portfolio.initial_equity}\n"
            f"{INDENT}Market Data Start Date: {format_date(self.start_date)}\n"
            f"{INDENT}Tickers: {self.included_tickers}\n"
            f"{INDENT}Strategy:\n{self.strategy}\n"
            f")"
        )
