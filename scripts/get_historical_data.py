import pandas as pd
from clients.broker.broker_client import BrokerClient
from clients.broker.broker_service import BrokerService
from clients.broker.tiger_client import TigerClient
from clients.database.database_client import DatabaseClient
from custom_types.market import MarketBarPeriod
from custom_types.ticker import Ticker


def retrieve_ticker_historical_data(
    broker: BrokerClient, ticker: Ticker
) -> pd.DataFrame:
    data: pd.DataFrame = BrokerService(broker).get_market_data(
        ticker=ticker, lookback_period=None, period=MarketBarPeriod.DAY
    )

    return data


def retrieve_historical_data(
    broker: BrokerClient, db_client: DatabaseClient, overwrite: bool = False
) -> int:
    # start_date = datetime(2005, 1, 1, tzinfo=ZoneInfo("Asia/Singapore"))

    for ticker in list(Ticker):
        # if ticker != Ticker.MRVL and ticker != Ticker.FXF:
        #     continue
        if ticker not in (Ticker.EQIX, Ticker.KLAC, Ticker.MRVL, Ticker.FXF):
            continue

        ticker_df_exists = db_client.does_raw_data_exist(
            ticker=ticker, client=broker.get_name()
        )

        if ticker_df_exists and not overwrite:
            print(f"Ticker {ticker} data exists, skipping...")
            continue

        if ticker_df_exists and overwrite:
            print(f"Ticker {ticker} data exists, overwriting...")

        ticker_data_df = retrieve_ticker_historical_data(broker=broker, ticker=ticker)

        db_client.save_raw_data(
            df=ticker_data_df, ticker=ticker, client=broker.get_name()
        )

    return 0


if __name__ == "__main__":
    db_client = DatabaseClient()
    broker = TigerClient()

    overwrite = False
    # overwrite = True
    retrieve_historical_data(broker=broker, db_client=db_client, overwrite=overwrite)
