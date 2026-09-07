import pandas as pd
from custom_types.exception import MyValueError
from system.indicator.indicator_types import Indicator
from system.models.risk.base_risk_model import BaseRiskModel
from system.portfolio.campaign import Campaign


class ExampleRiskModel(BaseRiskModel):
    """Risks a fixed percentage of the current price per share."""

    def __init__(self, risk_percentage: float = 0.02):
        self.risk_percentage = risk_percentage

    def get_r_value(self, current_bar: pd.Series, campaign: Campaign | None) -> float:
        current_price = current_bar[Indicator.CLOSE]
        r_value = self.risk_percentage * current_price

        if r_value <= 0:
            raise MyValueError(
                "Calculated R value is less than or equal to 0",
                current_bar=current_bar,
                campaign=campaign,
                r_value=r_value,
                risk_model=self,
            )

        return r_value

    def __str__(self):
        return (
            f"{super().__str__()}"
            f"Example_Risk_Model: risk_percentage [{self.risk_percentage}]"
        )
