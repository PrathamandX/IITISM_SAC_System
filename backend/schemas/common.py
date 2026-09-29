from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-09"])]
Money = Annotated[float, Field(ge=0, le=10_000_000)]
Phone = Annotated[str, Field(pattern=r"^\+?[0-9\- ]{7,20}$")]
Name = Annotated[str, Field(min_length=1, max_length=100)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)
