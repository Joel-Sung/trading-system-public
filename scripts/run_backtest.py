from datetime import datetime
from pathlib import Path

from clients.broker.tiger_client import TigerClient
from clients.database.database_client import DatabaseClient
from custom_types.ticker import Ticker
from strategy.example_strategy import ExampleStrategy
from system.engine.backtest_engine import BacktestEngine
from system.portfolio.portfolio import Portfolio

DEFAULT_START_YEAR = 2016
DEFAULT_INITIAL_EQUITY = 100_000.0
STRATEGIES = [ExampleStrategy]
DIVIDER = "=" * 75


def prompt_start_year() -> int:
    print(DIVIDER)
    while True:
        raw = input(
            f"Enter start year (from 2005 to 2026) [default: {DEFAULT_START_YEAR}]: "
        ).strip()
        if not raw:
            return DEFAULT_START_YEAR
        try:
            year = int(raw)
            if 2005 <= year <= 2026:
                datetime(year, 1, 1)
                return year
            print("Year must be between 2005 and 2026.")
        except ValueError:
            print("Please enter a valid year.")


def prompt_strategy():
    print(DIVIDER)
    print("Enter strategy option:")
    for i, strategy_cls in enumerate(STRATEGIES, start=1):
        print(f"  [{i}] {strategy_cls.__name__}")
    while True:
        raw = input("Strategy number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(STRATEGIES):
            return STRATEGIES[int(raw) - 1]()
        print(f"Please enter a number between 1 and {len(STRATEGIES)}.")


def prompt_initial_equity() -> float:
    print(DIVIDER)
    while True:
        raw = input(
            f"Initial equity [default: {DEFAULT_INITIAL_EQUITY:,.2f}]: "
        ).strip()
        if not raw:
            return DEFAULT_INITIAL_EQUITY
        try:
            equity = float(raw.replace(",", ""))
            if equity > 0:
                return equity
        except ValueError:
            pass
        print("Please enter a positive number.")


def prompt_confirmation(start_year: int, strategy, initial_equity: float) -> bool:
    print(DIVIDER)
    print("Backtest settings:")
    print(f"  Start year     : {start_year}")
    print(f"  Strategy       : {type(strategy).__name__}")
    print(f"  Initial equity : {initial_equity:,.2f}")
    while True:
        raw = input("Start backtest? (Y/N): ").strip().lower()
        if raw == "y":
            return True
        if raw == "n":
            return False
        print("Please enter Y or N.")


if __name__ == "__main__":
    start_year = prompt_start_year()
    strategy = prompt_strategy()
    initial_equity = prompt_initial_equity()

    if not prompt_confirmation(start_year, strategy, initial_equity):
        print("Backtest cancelled.")
        raise SystemExit(0)

    print(DIVIDER)
    print("Initializing backtest engine...")

    start_date = datetime(start_year, 1, 1)

    broker = TigerClient()

    data_dir = Path(__file__).resolve().parents[1] / "data" / "backtest"
    db_client = DatabaseClient(data_dir=data_dir)
    market_data = db_client.get_csv_data("source", "tiger_data_edited_with_inds.csv")

    portfolio = Portfolio(initial_equity=initial_equity)

    log_dir = Path(__file__).resolve().parents[1] / "logs"

    tickers: list[Ticker] = []
    # tickers: list[Ticker] = [Ticker.NVDA] # Using this will only backtest NVDA

    BacktestEngine(
        strategy=strategy,
        broker=broker,
        market_data=market_data,
        portfolio=portfolio,
        data_dir=data_dir,
        log_dir=log_dir,
        tickers=tickers,
        start_date=start_date,
    ).run()
