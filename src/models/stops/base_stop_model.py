from abc import ABC, abstractmethod

from custom_types.exception import MyValueError
from system.portfolio.campaign import Campaign
from system.portfolio.leg import Leg


class BaseStopModel(ABC):
    @abstractmethod
    def get_new_stop_price(self, current_price: float, leg: Leg) -> float:
        pass

    @abstractmethod
    def get_new_stops(self, current_price: float, campaign: Campaign) -> list[float]:
        pass

    def _validate_new_stop_price(
        self, new_stop_price: float, current_price: float, leg: Leg
    ) -> None:
        """Validate the newly calculated stop price."""
        if new_stop_price < 0:
            raise MyValueError(
                "Generated negative stop price.",
                stop_model=self,
                new_stop_price=new_stop_price,
                current_price=current_price,
                trade_leg=leg,
            )

    def __str__(self):
        return ""
