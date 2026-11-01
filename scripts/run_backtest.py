from datetime import datetime
from pathlib import Path

import pandas as pd
from clients.broker.tiger_client import TigerClient
from clients.database.database_client import DatabaseClient
from custom_types.ticker import Ticker
from strategy.example_strategy import ExampleStrategy
from system.engine.backtest_engine import BacktestEngine
from system.models.entry.base_entry_model import BaseEntryModel
from system.portfolio.portfolio import Portfolio


def add_indicators(
    market_data: pd.DataFrame,
    entry_model: BaseEntryModel,
) -> pd.DataFrame:
    return entry_model.prepare_market_data(market_data)


DEFAULT_START_YEAR = 2016
DEFAULT_INITIAL_EQUITY = 100000.0
STRATEGIES = [ExampleStrategy]


def prompt_start_year() -> int:
    while True:
        raw = input(f"Start year [{DEFAULT_START_YEAR}]: ").strip()
        if not raw:
            return DEFAULT_START_YEAR
        try:
            year = int(raw)
            datetime(year, 1, 1)
            return year
        except ValueError:
            print("Please enter a valid year.")


def prompt_strategy():
    print("Select a strategy:")
    for i, strategy_cls in enumerate(STRATEGIES, start=1):
        print(f"  {i}. {strategy_cls.__name__}")
    while True:
        raw = input("Strategy number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(STRATEGIES):
            return STRATEGIES[int(raw) - 1]()
        print(f"Please enter a number between 1 and {len(STRATEGIES)}.")


def prompt_initial_equity() -> float:
    while True:
        raw = input(f"Initial equity [{DEFAULT_INITIAL_EQUITY:,.2f}]: ").strip()
        if not raw:
            return DEFAULT_INITIAL_EQUITY
        try:
            equity = float(raw.replace(",", ""))
            if equity > 0:
                return equity
        except ValueError:
            pass
        print("Please enter a positive number.")


if __name__ == "__main__":
    start_date = datetime(prompt_start_year(), 1, 1)
    strategy = prompt_strategy()
    initial_equity = prompt_initial_equity()

    broker = TigerClient()

    data_dir = Path(__file__).resolve().parents[1] / "data" / "backtest"
    db_client = DatabaseClient(data_dir=data_dir)

    # market_data = db_client.get_csv_data("source", "tiger_data_edited.csv")
    # market_data = add_indicators(market_data, strategy.entry_model)
    # db_client.save_csv_data(market_data, "source", "tiger_data_edited_with_inds.csv")

    market_data = db_client.get_csv_data("source", "tiger_data_edited_with_inds.csv")

    portfolio = Portfolio(initial_equity=initial_equity)

    log_dir = Path(__file__).resolve().parents[1] / "logs"

    tickers: list[Ticker] = []
    # tickers: list[Ticker] = [Ticker.NVDA] # Using this will only backtest NVDA

    debug = False

    BacktestEngine(
        strategy=strategy,
        broker=broker,
        market_data=market_data,
        portfolio=portfolio,
        data_dir=data_dir,
        log_dir=log_dir,
        tickers=tickers,
        start_date=start_date,
        debug=debug,
    ).run()
