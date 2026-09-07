from abc import ABC, abstractmethod

from system.portfolio.campaign import Campaign


class BasePyramidModel(ABC):
    @abstractmethod
    def should_pyramid(self, campaign: Campaign) -> bool:
        pass

    def __str__(self):
        return ""
