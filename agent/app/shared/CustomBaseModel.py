from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List
from enum import Enum

class CustomBaseModel(BaseModel):
    """
    Base model with datetime fields that are serialized as ISO format strings.
    Also handles enums and other common serialization issues.
    """

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Enum):
                data[key] = value.value
        return data