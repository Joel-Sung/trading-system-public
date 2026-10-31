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


if __name__ == "__main__":
    strategy = ExampleStrategy()
    broker = TigerClient()
    # start_date = datetime(2005, 1, 1)
    start_date = datetime(2016, 1, 1)
    # start_date = datetime(2023, 1, 1)

    data_dir = Path(__file__).resolve().parents[1] / "data" / "backtest"
    db_client = DatabaseClient(data_dir=data_dir)

    # market_data = db_client.get_csv_data("source", "tiger_data_edited.csv")
    # market_data = add_indicators(market_data, strategy.entry_model)
    # db_client.save_csv_data(market_data, "source", "tiger_data_edited_with_inds.csv")

    market_data = db_client.get_csv_data("source", "tiger_data_edited_with_inds.csv")

    portfolio = Portfolio(initial_equity=100000.0)

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
