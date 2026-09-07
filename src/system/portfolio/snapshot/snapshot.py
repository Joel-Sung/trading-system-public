from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum


class Snapshot:
    def to_dict(self) -> dict:
        return {
            field.name: self._serialize(getattr(self, field.name))
            for field in fields(self)
        }

    @classmethod
    def _serialize(cls, value):
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, Enum):
            return value.value

        if is_dataclass(value):
            return {
                field.name: cls._serialize(getattr(value, field.name))
                for field in fields(value)
            }

        if isinstance(value, list):
            return [cls._serialize(item) for item in value]

        if isinstance(value, tuple):
            return tuple(cls._serialize(item) for item in value)

        if isinstance(value, dict):
            return {cls._serialize(k): cls._serialize(v) for k, v in value.items()}

        return value
