from abc import ABC, abstractmethod

import pandas as pd


class BaseEntryModel(ABC):
    def __init__(self, disable_long: bool = False, disable_short: bool = False):
        self.disable_long = disable_long
        self.disable_short = disable_short

    @property
    @abstractmethod
    def minimum_data_period(self) -> int:
        pass

    @abstractmethod
    def prepare_market_data(self, market_data: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_long_signal(self, current_bar: pd.DataFrame) -> bool:
        pass

    @abstractmethod
    def get_short_signal(self, current_bar: pd.DataFrame) -> bool:
        pass

    def __str__(self):
        return ""
