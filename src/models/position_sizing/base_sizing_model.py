from abc import ABC, abstractmethod

import pandas as pd

from system.portfolio.portfolio import Portfolio


class BaseSizingModel(ABC):
    @abstractmethod
    def calculate_qty(
        self, portfolio: Portfolio, bar_data: pd.Series, leg_number: int
    ) -> float:
        pass

    def __str__(self):
        return ""
