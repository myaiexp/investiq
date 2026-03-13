from pydantic import BaseModel, ConfigDict, Field


class FundMetaResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    ticker: str
    isin: str | None
    fund_type: str = Field(serialization_alias="fundType")
    benchmark_ticker: str | None = Field(serialization_alias="benchmarkTicker")
    benchmark_name: str = Field(serialization_alias="benchmarkName")
    nav: float
    daily_change: float = Field(serialization_alias="dailyChange")
    return_1y: float = Field(serialization_alias="return1Y")
    data_note: str | None = Field(default=None, serialization_alias="dataNote")


class FundNAVPointResponse(BaseModel):
    time: int
    value: float


class FundPerformanceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    returns: dict[str, float]
    benchmark_returns: dict[str, float] = Field(serialization_alias="benchmarkReturns")
    volatility: float
    sharpe: float
    max_drawdown: float = Field(serialization_alias="maxDrawdown")
    ter: float
    data_notes: dict[str, str] | None = Field(default=None, serialization_alias="dataNotes")
