from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NaturalGasImportRecord(BaseModel):
    """One row from the EIA `natural-gas/move/impc` (imports by country) route."""

    model_config = ConfigDict(populate_by_name=True)

    period: str
    duoarea: str
    area_name: str = Field(alias="area-name")
    product: str
    product_name: str = Field(alias="product-name")
    process: str
    process_name: str = Field(alias="process-name")
    series: str
    series_description: str = Field(alias="series-description")
    value: float | None
    units: str

    @field_validator("value", mode="before")
    @classmethod
    def _parse_value(cls, raw: object) -> float | None:
        if raw in (None, ""):
            return None
        return float(raw)
