from system.models.pyramiding.base_pyramid_model import BasePyramidModel
from system.portfolio.campaign import Campaign


class ExamplePyramidModel(BasePyramidModel):
    """Adds a single extra leg once the campaign's main leg is up 1R, then stops pyramiding."""

    def __init__(self, profit_r_threshold: float = 1.0):
        self.profit_r_threshold = profit_r_threshold

    def should_pyramid(self, campaign: Campaign) -> bool:
        if campaign.next_leg_num != 1:
            return False

        return campaign.main_leg.current_profit_in_r >= self.profit_r_threshold

    def __str__(self):
        return (
            f"{super().__str__()}"
            f"Example_Pyramid_Model: profit_r_threshold [{self.profit_r_threshold}]"
        )
