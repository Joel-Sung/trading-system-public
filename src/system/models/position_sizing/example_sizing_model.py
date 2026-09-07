import pandas as pd
from custom_types.exception import MyValueError
from system.indicator.indicator_types import Indicator
from system.models.position_sizing.base_sizing_model import BaseSizingModel
from system.portfolio.portfolio import Portfolio


class ExampleSizingModel(BaseSizingModel):
    """Sizes every leg using the same fixed percentage of available capital."""

    def __init__(self, capital_percentage: float = 0.01):
        self.capital_percentage = capital_percentage

    def calculate_qty(
        self, portfolio: Portfolio, bar_data: pd.Series, leg_num: int
    ) -> float:
        current_price = bar_data[Indicator.CLOSE]

        capital_risked = self.capital_percentage * portfolio.cash_available_for_trading
        qty = capital_risked / current_price

        if qty <= 0:
            raise MyValueError(
                "Sizing model returned qty <= 0",
                sizing_model=self,
                leg_number=leg_num,
                qty=qty,
                bar_data=bar_data,
                portfolio=portfolio,
            )

        return qty

    def __str__(self):
        return (
            f"{super().__str__()}"
            f"Example_Sizing_Model: capital_percentage [{self.capital_percentage}]"
        )
