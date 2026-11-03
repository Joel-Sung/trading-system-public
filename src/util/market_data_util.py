import pandas as pd
from custom_types.exception import MyValueError
from system.indicator.indicator_types import Indicator


def does_df_contain_cols(df: pd.DataFrame, required_cols: list[str]) -> bool:
    for col in required_cols:
        if col not in df.columns:
            return False
    return True


def format_market_data(market_data: pd.DataFrame) -> pd.DataFrame:
    """
    The single place where raw market data is validated, converted and sorted.
    Returns a new frame sorted by datetime, the input is left untouched.
    """
    required_cols = [
        Indicator.TICKER,
        Indicator.DATETIME,
        Indicator.OPEN,
        Indicator.HIGH,
        Indicator.LOW,
        Indicator.CLOSE,
        Indicator.VOLUME,
    ]
    if not does_df_contain_cols(market_data, required_cols):
        raise MyValueError(
            "Market data is missing essential columns",
            required_cols=required_cols,
            df=market_data,
        )

    return market_data.assign(
        **{Indicator.DATETIME: pd.to_datetime(market_data[Indicator.DATETIME])}
    ).sort_values(Indicator.DATETIME, kind="stable")


def get_ticker_latest_bar(df: pd.DataFrame, ticker: str) -> pd.Series:
    if not does_df_contain_cols(df, [Indicator.TICKER, Indicator.DATETIME]):
        raise MyValueError(
            f"DataFrame must contain '{Indicator.TICKER}' and '{Indicator.DATETIME}' columns",
            df=df,
            ticker=ticker,
        )

    ticker_data = df.loc[df[Indicator.TICKER] == ticker]
    if ticker_data.empty:
        return pd.Series()

    # market data is already sorted by datetime
    return ticker_data.iloc[-1]
