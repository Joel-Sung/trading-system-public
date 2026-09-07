import logging

import pandas as pd
from clients.broker.broker_client import BrokerClient
from clients.database.database_client import DatabaseClient
from custom_types.market import MarketAssets, MarketPosition
from system.models.entry.base_entry_model import BaseEntryModel
from system.models.risk.base_risk_model import BaseRiskModel
from system.portfolio.campaign import Campaign
from system.portfolio.portfolio import Portfolio
from util.datetime_util import get_current_datetime


def align_portfolio(
    portfolio: Portfolio | None,
    market_assets: MarketAssets,
) -> Portfolio:
    if portfolio is None:
        portfolio = Portfolio(initial_equity=market_assets.net_liquidation)

    portfolio.cash_balance = market_assets.cash_balance
    portfolio.cash_available_for_trading = market_assets.cash_available_for_trading

    return portfolio


def align_campaigns(
    portfolio: Portfolio,
    market_positions: list[MarketPosition],
    risk_model: BaseRiskModel,
    market_data: pd.DataFrame,
    broker: BrokerClient,
) -> Portfolio:
    for position in market_positions:
        campaign: Campaign = portfolio.get_open_campaign(ticker=position.ticker)

        if campaign is not None and campaign.total_qty != position.quantity:
            campaign.main_leg.current_qty += position.quantity - campaign.total_qty
            continue

        # Create new campaign as it doesn't exist
        now = get_current_datetime()

        new_campaign = portfolio.create_campaign(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_datetime=now,
        )

        ticker_data = market_data.loc[
            market_data["ticker"] == new_campaign.ticker
        ].sort_values("datetime")

        if ticker_data.empty:
            raise ValueError(f"No market data found for ticker {new_campaign.ticker}")

        latest_bar = ticker_data.iloc[-1]

        entry_price = position.average_cost

        r_value = risk_model.get_r_value(current_bar=latest_bar, campaign=new_campaign)
        stop_price = (
            entry_price - r_value
            if position.trade_type == "LONG"
            else entry_price + r_value
        )

        fees = broker.calculate_fees(
            shares=position.quantity,
            price=position.average_cost,
            trade_type=position.trade_type,
        )

        portfolio.create_leg(
            ticker=position.ticker,
            trade_type=position.trade_type,
            entry_price=entry_price,
            entry_datetime=now,
            trading_fees=fees,
            qty=position.quantity,
            stop_price=stop_price,
        )

    return portfolio


def run(
    logger: logging.Logger,
    broker: BrokerClient,
    db_client: DatabaseClient,
    entry_model: BaseEntryModel,
    risk_model: BaseRiskModel,
    market_assets_file_name: str,
    market_positions_file_name: str,
    market_data_file_name: str,
    market_data_prepared_file_name: str,
    input_portfolio_file_name: str,
    input_campaign_file_name: str,
    input_leg_file_name: str,
    output_portfolio_file_name: str,
    output_campaign_file_name: str,
    output_leg_file_name: str,
):
    logger.info("Running align_data.py...")

    logger.info("Listing parameters...")
    logger.info("Broker Client:%s", broker)
    logger.info("DB Client:%s", db_client)
    logger.info("Entry Model:%s", entry_model)
    logger.info("Risk Model:%s", risk_model)
    logger.info(f"Market Assets File Name: {market_assets_file_name}")
    logger.info(f"Market Positions File Name: {market_positions_file_name}")
    logger.info(f"Market Data file name: {market_data_file_name}")
    logger.info(f"Input Portfolio File Name: {input_portfolio_file_name}")
    logger.info(f"Input Campaign File Name: {input_campaign_file_name}")
    logger.info(f"Input Leg File Name: {input_leg_file_name}")
    logger.info(f"Output Portfolio File Name: {output_portfolio_file_name}")
    logger.info(f"Output Campaign File Name: {output_campaign_file_name}")
    logger.info(f"Output Leg File Name: {output_leg_file_name}")

    logger.info("Retrieving market assets...")
    market_assets = db_client.get_market_assets(file_name=market_assets_file_name)
    logger.info("Retrieved market assets:\n%s", market_assets)

    logger.info("Retrieving market positions...")
    market_positions = db_client.get_market_positions(
        file_name=market_positions_file_name
    )
    logger.info(
        "Retrieved market positions:\n\t\t%s",
        "\n\t\t".join(str(position) for position in market_positions),
    )

    logger.info("Retrieving market data...")
    market_data = db_client.get_market_data(file_name=market_data_file_name)
    logger.info("Retrieved market data:\n%s", market_data)

    logger.info("Preparing market data using entry model...")
    market_data = entry_model.prepare_market_data(market_data=market_data)
    logger.info("Prepared market data:\n%s", market_data)

    logger.info("Storing prepared market data...")
    db_client.save_market_data(
        market_data=market_data, file_name=market_data_prepared_file_name
    )
    logger.info("Stored prepared market data")

    logger.info("Retrieving portfolio...")
    portfolio = db_client.get_system_state(
        portfolio_file_name=input_portfolio_file_name,
        campaign_file_name=input_campaign_file_name,
        leg_file_name=input_leg_file_name,
    )
    logger.info("Retrieved portfolio:\n%s", portfolio)

    logger.info("Aligning portfolio...")
    portfolio = align_portfolio(
        portfolio=portfolio,
        market_assets=market_assets,
    )
    logger.info("Aligned portfolio:\n%s", portfolio)

    logger.info("Aligning campaigns...")
    portfolio = align_campaigns(
        portfolio=portfolio,
        market_positions=market_positions,
        risk_model=risk_model,
        market_data=market_data,
        broker=broker,
    )
    logger.info("Aligned portfolio:\n%s", portfolio)

    logger.info("Storing aligned system state...")
    db_client.save_system_state(
        portfolio=portfolio,
        portfolio_file_name=output_portfolio_file_name,
        campaign_file_name=output_campaign_file_name,
        leg_file_name=output_leg_file_name,
    )

    logger.info("Finished running align_data.py!!!")
