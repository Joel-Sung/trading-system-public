import pandas as pd
from system.indicator.indicator_builder import IndicatorBuilder
from system.indicator.indicator_types import Indicator
from system.models.entry.base_entry_model import BaseEntryModel
from util.df_util import does_df_contain_cols


class ExampleEntryModel(BaseEntryModel):
    """Enters long/short on a simple rolling high/low breakout, with no confirmation margin."""

    def __init__(
        self,
        lookback_period: int = 20,
        disable_long: bool = False,
        disable_short: bool = False,
    ):
        super().__init__(disable_long=disable_long, disable_short=disable_short)
        self.lookback_period = lookback_period

    @property
    def minimum_data_period(self) -> int:
        return self.lookback_period + 1

    def prepare_market_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        required_cols = [Indicator.ROLLING_HIGH, Indicator.ROLLING_LOW]

        if does_df_contain_cols(df=market_data, required_cols=required_cols):
            return market_data

        ticker_dfs: list[pd.DataFrame] = []

        for _, ticker_df in market_data.groupby(Indicator.TICKER):
            ticker_df = ticker_df.sort_values(Indicator.DATETIME).copy()

            ticker_df = (
                IndicatorBuilder(ticker_df)
                .add_rolling_high(self.lookback_period)
                .add_rolling_low(self.lookback_period)
                .get_df()
            )

            ticker_dfs.append(ticker_df)

        return pd.concat(ticker_dfs).reset_index(drop=True)

    def get_long_signal(self, current_bar: pd.DataFrame) -> bool:
        if self.disable_long:
            return False

        return current_bar[Indicator.CLOSE] > current_bar[Indicator.ROLLING_HIGH]

    def get_short_signal(self, current_bar: pd.DataFrame) -> bool:
        if self.disable_short:
            return False

        return current_bar[Indicator.CLOSE] < current_bar[Indicator.ROLLING_LOW]

    def __str__(self):
        return (
            f"{super().__str__()}"
            f"Example_Entry_Model: "
            f"lookback_period [{self.lookback_period}], "
            f"disable_long [{self.disable_long}], "
            f"disable_short [{self.disable_short}]"
        )
