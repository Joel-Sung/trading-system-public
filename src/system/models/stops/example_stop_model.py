from custom_types.market import TradeType
from system.models.stops.base_stop_model import BaseStopModel
from system.portfolio.campaign import Campaign
from system.portfolio.leg import Leg


class ExampleStopModel(BaseStopModel):
    """Trails a fixed percentage below (long) or above (short) the current price."""

    def __init__(self, trail_percentage: float = 0.05):
        self.trail_percentage = trail_percentage

    def get_new_stop_price(self, current_price: float, leg: Leg) -> float:
        if leg.trade_type == TradeType.LONG:
            new_stop_price = current_price * (1 - self.trail_percentage)
            return max(new_stop_price, leg.current_stop_price)

        new_stop_price = current_price * (1 + self.trail_percentage)
        return min(new_stop_price, leg.current_stop_price)

    def get_new_stops(self, current_price: float, campaign: Campaign) -> list[float]:
        main_leg_new_stop = self.get_new_stop_price(
            current_price=current_price, leg=campaign.main_leg
        )

        self._validate_new_stop_price(
            new_stop_price=main_leg_new_stop,
            current_price=current_price,
            leg=campaign.main_leg,
        )

        # Apply the same stop price to all legs
        return [main_leg_new_stop for _ in campaign.open_legs]

    def __str__(self):
        return (
            f"{super().__str__()}"
            f"Example_Stop_Model: trail_percentage [{self.trail_percentage}]"
        )
