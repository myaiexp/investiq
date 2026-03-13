from pydantic import BaseModel, ConfigDict, Field


class IndexMetaResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    ticker: str
    region: str
    price: float
    daily_change: float = Field(serialization_alias="dailyChange")
    signal: str
    data_note: str | None = Field(default=None, serialization_alias="dataNote")


class OHLCVBarResponse(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorDataResponse(BaseModel):
    id: str
    series: dict[str, list[dict[str, float]]]
    signal: str


class IndicatorMetaResponse(BaseModel):
    id: str
    category: str
    signal: str


class SignalSummaryResponse(BaseModel):
    aggregate: str
    breakdown: list[IndicatorMetaResponse]
    active_count: dict[str, int] = Field(serialization_alias="activeCount")
