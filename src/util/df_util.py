import pandas as pd
from custom_types.exception import MyValueError
from system.indicator.indicator_types import Indicator


def does_df_contain_cols(df: pd.DataFrame, required_cols: list[str]) -> bool:
    for col in required_cols:
        if col not in df.columns:
            return False
    return True


def get_ticker_latest_bar(df: pd.DataFrame, ticker: str) -> pd.Series:
    if not does_df_contain_cols(df, [Indicator.TICKER, Indicator.DATETIME]):
        raise MyValueError(
            f"DataFrame must contain '{Indicator.TICKER}' and '{Indicator.DATETIME}' columns",
            df=df,
            ticker=ticker,
        )

    ticker_data = df.loc[df[Indicator.TICKER] == ticker]
    if ticker_data.empty:
        raise MyValueError(
            "No market data found for ticker",
            df=df,
            ticker=ticker,
        )

    latest_bar = ticker_data.sort_values(Indicator.DATETIME).iloc[-1]
    return latest_bar
