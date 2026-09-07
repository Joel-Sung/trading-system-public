import logging

import pandas as pd
from clients.database.database_client import DatabaseClient
from custom_types.system import SystemOrder
from system.engine.trading_engine import TradingEngine


def get_latest_bar(
    market_data_file_name: str, db_client: DatabaseClient
) -> pd.DataFrame:
    market_data = db_client.get_market_data(market_data_file_name)
    latest_bars = (
        market_data.sort_values(["ticker", "datetime"])
        .groupby("ticker", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )

    return latest_bars


def run(
    logger: logging.Logger,
    db_client: DatabaseClient,
    market_data_file_name: str,
    portfolio_file_name: str,
    campaign_file_name: str,
    leg_file_name: str,
    engine: TradingEngine,
    system_orders_file_name: str,
):
    logger.info("Running run_strategy.py...")

    logger.info("Listing parameters...")
    logger.info("DB Client:%s", db_client)
    logger.info("Market Data file_name:%s", market_data_file_name)
    logger.info("Portfolio file_name:%s", portfolio_file_name)
    logger.info("Campaign file_name:%s", campaign_file_name)
    logger.info("Leg file_name:%s", leg_file_name)
    logger.info("Trading Engine:\n%s", engine)
    logger.info("System Orders file_name:%s", system_orders_file_name)

    logger.info("Retrieving market data latest bars...")
    latest_bars = get_latest_bar(
        market_data_file_name=market_data_file_name, db_client=db_client
    )
    logger.info("Retrieved market data latest bars:\n%s", latest_bars)

    logger.info("Retrieving portfolio...")
    portfolio = db_client.get_system_state(
        portfolio_file_name=portfolio_file_name,
        campaign_file_name=campaign_file_name,
        leg_file_name=leg_file_name,
    )
    logger.info("Retrieved portfolio:\n%s", portfolio)

    logger.info("Running strategy...")
    system_orders: list[SystemOrder] = engine.process_latest_bars(
        portfolio=portfolio, bar_data=latest_bars, logger=logger
    )
    logger.info("Strategy completed, system orders generated:\n%s", system_orders)

    logger.info("Storing system orders...")
    db_client.save_system_orders(
        system_orders=system_orders, file_name=system_orders_file_name
    )

    logger.info("Finished running run_strategy.py!!!")
