import logging

import pandas as pd
from clients.broker.broker_client import BrokerClient
from clients.broker.tiger_client import TigerClient
from clients.database.database_client import DatabaseClient
from custom_types.market import (
    MarketAssets,
    MarketBarPeriod,
    MarketOrder,
    MarketPosition,
)
from custom_types.ticker import Ticker
from system.indicator.indicator_types import Indicator
from system.models.entry.base_entry_model import BaseEntryModel
from system.models.entry.breakout_entry_model import BreakoutEntryModel
from util.trading_util import TICKER_TO_SECTOR


def get_broker_market_assets(broker: BrokerClient) -> MarketAssets:
    return broker.get_assets()


def get_broker_market_positions(broker: BrokerClient) -> list[MarketPosition]:
    return broker.get_positions()


def get_broker_market_orders(broker: BrokerClient) -> list[MarketOrder]:
    return broker.get_orders()


def get_broker_market_data(
    broker: BrokerClient,
    number_of_bars: int,
    period: MarketBarPeriod = MarketBarPeriod.DAY,
    only_these_tickers: list[Ticker] | None = None,
) -> pd.DataFrame:
    # Exclude all bonds and currency tickers
    if only_these_tickers is None:
        only_these_tickers = []

    excluded_tickers = [
        Ticker.TLT,
        Ticker.IEF,
        Ticker.SHY,
        Ticker.TIP,
        Ticker.UUP,
        Ticker.FXE,
        Ticker.FXY,
        Ticker.FXA,
        Ticker.FXB,
        Ticker.FXF,
    ]

    all_ticker_dfs: list[pd.DataFrame] = []
    for ticker in Ticker:
        if ticker in excluded_tickers:
            continue

        if len(only_these_tickers) > 0 and ticker not in only_these_tickers:
            continue

        ticker_df = broker.get_market_data(
            ticker=ticker, number_of_bars=number_of_bars, period=period
        )

        sector = TICKER_TO_SECTOR.get(ticker)
        ticker_df[Indicator.SECTOR] = sector

        all_ticker_dfs.append(ticker_df)

    return pd.concat(all_ticker_dfs, ignore_index=True)


def run(
    logger: logging.Logger,
    broker: BrokerClient,
    entry_model: BaseEntryModel,
    db_client: DatabaseClient,
    market_assets_file_name: str,
    market_positions_file_name: str,
    market_orders_file_name: str,
    market_data_file_name: str,
    only_these_tickers: list[Ticker] | None = None,
):
    if only_these_tickers is None:
        only_these_tickers = []

    logger.info("Running retrieve_broker_data.py...")

    logger.info("Listing parameters...")
    logger.info(f"Logger:\n\t\t{logger}")
    logger.info(f"Broker:\n\t\t{broker}")
    logger.info(f"Entry Model:\n\t\t{entry_model}")
    logger.info(f"DB Client:\n\t\t{db_client}")
    logger.info(f"Market Assets File Name: {market_assets_file_name}")
    logger.info(f"Market Positions File Name: {market_positions_file_name}")
    logger.info(f"Market Orders File Name: {market_orders_file_name}")
    logger.info(f"Market Data File Name: {market_data_file_name}")
    logger.info("Only These Tickers:\n\t\t%s", "\n\t\t".join(only_these_tickers))

    logger.info("Retrieving market assets...")
    market_assets = get_broker_market_assets(broker=broker)
    logger.info("Retrieved market assets:\n%s", market_assets)
    db_client.save_market_assets(
        market_assets=market_assets, file_name=market_assets_file_name
    )
    logger.info("Stored market assets")

    logger.info("Retrieving market positions...")
    market_positions = get_broker_market_positions(broker=broker)
    logger.info(
        "Retrieved market positions:\n\t\t%s",
        "\n\t\t".join(str(position) for position in market_positions),
    )
    db_client.save_market_positions(
        market_positions=market_positions, file_name=market_positions_file_name
    )
    logger.info("Stored market positions")

    logger.info("Retrieving market orders...")
    market_orders = get_broker_market_orders(broker=broker)
    logger.info(
        "Retrieved market orders:\n\t\t%s",
        "\n\t\t".join(str(order) for order in market_orders),
    )
    db_client.save_market_orders(
        market_orders=market_orders, file_name=market_orders_file_name
    )
    logger.info("Stored market orders")

    logger.info("Retrieving market data...")
    market_data = get_broker_market_data(
        broker,
        number_of_bars=entry_model.minimum_data_period,
        only_these_tickers=only_these_tickers,
    )
    logger.info("Retrieved market data:\n%s", market_data)
    db_client.save_market_data(market_data=market_data, file_name=market_data_file_name)
    logger.info("Stored market data")

    logger.info("Finished running retrieve_broker_data.py!!!")


if __name__ == "__main__":
    broker: BrokerClient = TigerClient()
    entry_model: BaseEntryModel = BreakoutEntryModel(lookback_period=20, atr_period=14)

    # print("Market Assets:\n", retrieve_market_assets(broker), "\n")
    # print("Market Positions:\n", retrieve_market_positions(broker), "\n")
    # print("Market Orders:\n", retrieve_market_orders(broker), "\n")
    print(
        "Market Data:\n",
        get_broker_market_data(broker, number_of_bars=entry_model.minimum_data_period),
        "\n",
    )
