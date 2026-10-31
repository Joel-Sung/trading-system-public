from typing import Self

import numpy as np
import pandas as pd
from custom_types.exception import MyValueError
from system.indicator.indicator_types import Indicator
from util.market_data_util import does_df_contain_cols


class IndicatorBuilder:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def _check_contains_required_cols(
        self,
        indicator: Indicator,
        req_cols: list[Indicator],
        df: pd.DataFrame | None = None,
    ):
        if df is None:
            df = self.df

        if not does_df_contain_cols(df, required_cols=req_cols):
            raise MyValueError(
                "Unable to build indicator as dataframe does not have the required columns",
                indicator=indicator,
                req_cols=req_cols,
                df=df,
            )

    def get_df(self) -> pd.DataFrame:
        return self.df

    def add_rolling_high(self, period: int) -> Self:
        self._check_contains_required_cols(Indicator.ROLLING_HIGH, [Indicator.HIGH])

        self.df[Indicator.ROLLING_HIGH] = (
            self.df[Indicator.HIGH].rolling(period).max().shift(1)
        )
        return self

    def add_rolling_low(self, period: int) -> Self:
        self._check_contains_required_cols(Indicator.ROLLING_LOW, [Indicator.LOW])

        self.df[Indicator.ROLLING_LOW] = (
            self.df[Indicator.LOW].rolling(period).min().shift(1)
        )
        return self

    def add_atr(self, period: int) -> Self:
        self._check_contains_required_cols(
            Indicator.ATR, [Indicator.HIGH, Indicator.LOW, Indicator.CLOSE]
        )

        high = self.df[Indicator.HIGH]
        low = self.df[Indicator.LOW]
        close = self.df[Indicator.CLOSE]

        tr = np.maximum(
            high - low,
            np.maximum(
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ),
        )

        self.df[Indicator.ATR] = tr.rolling(period).mean()
        return self

    def _add_relative_strength(
        self,
        df_other: pd.DataFrame,
        lookback: int,
        indicator_name: Indicator = Indicator.RS,
    ) -> Self:
        self._check_contains_required_cols(
            indicator_name, [Indicator.DATETIME, Indicator.CLOSE]
        )
        self._check_contains_required_cols(
            indicator_name, [Indicator.DATETIME, Indicator.CLOSE], df=df_other
        )

        df1 = self.df.sort_values(Indicator.DATETIME).reset_index(drop=True)
        df2 = df_other.sort_values(Indicator.DATETIME).reset_index(drop=True)

        merged = (
            pd.merge(
                df1[[Indicator.DATETIME, Indicator.CLOSE]],
                df2[[Indicator.DATETIME, Indicator.CLOSE]],
                on=Indicator.DATETIME,
                how="outer",
                suffixes=("_1", "_2"),
            )
            .sort_values(Indicator.DATETIME)
            .reset_index(drop=True)
        )

        close_1 = f"{Indicator.CLOSE}_1"
        close_2 = f"{Indicator.CLOSE}_2"

        merged[indicator_name] = 1.0

        merged["norm_1"] = merged[close_1] / merged[close_1].shift(lookback)
        merged["norm_2"] = merged[close_2] / merged[close_2].shift(lookback)

        mask = merged["norm_1"].notna() & merged["norm_2"].notna()

        merged.loc[mask, indicator_name] = (
            merged.loc[mask, "norm_1"] / merged.loc[mask, "norm_2"]
        )

        self.df = self.df.merge(
            merged[[Indicator.DATETIME, indicator_name]],
            on=Indicator.DATETIME,
            how="left",
        )

        return self

    def add_relative_strength_with_sector(
        self, df_other: pd.DataFrame, lookback: int = 50
    ) -> Self:
        return self._add_relative_strength(
            df_other, lookback=lookback, indicator_name=Indicator.RS_WITH_SECTOR
        )

    def add_relative_strength_with_market(
        self, df_other: pd.DataFrame, lookback: int = 50
    ) -> Self:
        return self._add_relative_strength(
            df_other, lookback=lookback, indicator_name=Indicator.RS_WITH_MARKET
        )
