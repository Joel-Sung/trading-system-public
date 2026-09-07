from abc import ABC, abstractmethod

import pandas as pd

from system.portfolio.campaign import Campaign


class BaseRiskModel(ABC):
    @abstractmethod
    def get_r_value(self, current_bar: pd.Series, campaign: Campaign) -> float:
        pass

    def __str__(self):
        return ""
