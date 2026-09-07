import logging

from clients.broker.broker_client import BrokerClient
from clients.broker.tiger_client import TigerClient
from clients.database.database_client import DatabaseClient
from custom_types.ticker import Ticker
from scripts.main_scripts import (
    align_data,
    get_broker_data,
    place_system_orders,
    run_strategy,
)
from system.engine.trading_engine import TradingEngine
from system.models.entry.base_entry_model import BaseEntryModel
from system.models.entry.breakout_entry_model import BreakoutEntryModel
from system.models.risk.atr_risk_model import AtrRiskModel
from system.models.risk.base_risk_model import BaseRiskModel
from util.datetime_util import format_datetime, get_current_datetime
from util.logger import Logger

from trading_system_private.src.private.system.breakout_strategy import BreakoutStrategy


def main(is_test: bool = True):
    application_name = "main"
    now = get_current_datetime()
    formatted_now = format_datetime(dt=now)
    formatted_now = "2026-07-13T21-24-26"

    log_file_name = f"{application_name}.log.{formatted_now}.txt"
    logger: logging.Logger = Logger(
        system_name=application_name, log_file_name=log_file_name
    ).get_logger()
    broker: BrokerClient = TigerClient()
    db_client: DatabaseClient = DatabaseClient(use_test_dir=is_test)

    entry_model: BaseEntryModel = BreakoutEntryModel()
    risk_model: BaseRiskModel = AtrRiskModel()

    market_assets_file_name: str = f"{formatted_now}_market_assets.csv"
    market_positions_file_name: str = f"{formatted_now}_market_positions.csv"
    market_orders_file_name: str = f"{formatted_now}_market_orders.csv"
    market_data_file_name: str = f"{formatted_now}_market_data.csv"
    only_these_tickers = [Ticker.AAPL, Ticker.GOOGL, Ticker.NVDA]

    get_broker_data.run(
        logger=logger,
        broker=broker,
        entry_model=entry_model,
        db_client=db_client,
        market_assets_file_name=market_assets_file_name,
        market_positions_file_name=market_positions_file_name,
        market_orders_file_name=market_orders_file_name,
        market_data_file_name=market_data_file_name,
        only_these_tickers=only_these_tickers,
    )

    input_portfolio_file_name: str = "test_system_portfolio.csv"
    input_campaign_file_name: str = "test_system_campaigns.csv"
    input_leg_file_name: str = "test_system_legs.csv"
    market_data_prepared_file_name: str = f"{formatted_now}_market_data_prepared.csv"
    output_portfolio_file_name: str = f"{formatted_now}_system_portfolio.csv"
    output_campaign_file_name: str = f"{formatted_now}_system_campaigns.csv"
    output_leg_file_name: str = f"{formatted_now}_system_legs.csv"

    align_data.run(
        logger=logger,
        broker=broker,
        db_client=db_client,
        entry_model=entry_model,
        risk_model=risk_model,
        market_assets_file_name=market_assets_file_name,
        market_positions_file_name=market_positions_file_name,
        market_data_file_name=market_data_file_name,
        market_data_prepared_file_name=market_data_prepared_file_name,
        input_portfolio_file_name=input_portfolio_file_name,
        input_campaign_file_name=input_campaign_file_name,
        input_leg_file_name=input_leg_file_name,
        output_portfolio_file_name=output_portfolio_file_name,
        output_campaign_file_name=output_campaign_file_name,
        output_leg_file_name=output_leg_file_name,
    )

    strategy = BreakoutStrategy()
    engine = TradingEngine(
        strategy=strategy,
        broker=broker,
    )
    system_orders_file_name: str = f"{formatted_now}_system_orders.csv"

    run_strategy.run(
        logger=logger,
        db_client=db_client,
        market_data_file_name=market_data_prepared_file_name,
        portfolio_file_name=output_portfolio_file_name,
        campaign_file_name=output_campaign_file_name,
        leg_file_name=output_leg_file_name,
        engine=engine,
        system_orders_file_name=system_orders_file_name,
    )

    system_orders_file_name: str = "test_system_orders.csv"

    place_system_orders.run(
        logger=logger,
        db_client=db_client,
        system_orders_file_name=system_orders_file_name,
        broker=broker,
    )


if __name__ == "__main__":
    main(is_test=True)
