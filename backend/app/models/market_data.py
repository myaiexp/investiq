from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Index(Base):
    __tablename__ = "indices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    ticker: Mapped[str] = mapped_column(String(20), unique=True)
    region: Mapped[str] = mapped_column(String(20))  # nordic, global
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal: Mapped[str | None] = mapped_column(String(10), nullable=True)


class OHLCVData(Base):
    __tablename__ = "ohlcv_data"
    __table_args__ = (UniqueConstraint("ticker", "date", "interval"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    interval: Mapped[str] = mapped_column(String(5), default="1D")
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Fund(Base):
    __tablename__ = "funds"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    ticker: Mapped[str] = mapped_column(String(30), unique=True)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fund_type: Mapped[str] = mapped_column(String(30))  # equity, bond, mixed
    benchmark_ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    benchmark_name: Mapped[str] = mapped_column(String(100), default="")
    nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    daily_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_1y: Mapped[float | None] = mapped_column(Float, nullable=True)


class FundNAV(Base):
    __tablename__ = "fund_nav"
    __table_args__ = (UniqueConstraint("ticker", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(30), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    nav: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class IndicatorData(Base):
    __tablename__ = "indicator_data"
    __table_args__ = (
        UniqueConstraint("ticker", "indicator_id", "interval", "date", "series_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    indicator_id: Mapped[str] = mapped_column(String(20))
    interval: Mapped[str] = mapped_column(String(5))
    date: Mapped[date] = mapped_column(Date, index=True)
    series_key: Mapped[str] = mapped_column(String(20))
    value: Mapped[float] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class SignalData(Base):
    __tablename__ = "signal_data"
    __table_args__ = (UniqueConstraint("ticker", "indicator_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    indicator_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    signal: Mapped[str] = mapped_column(String(10))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class FundPerformance(Base):
    __tablename__ = "fund_performance"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(30), unique=True)
    returns_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    returns_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    returns_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_returns_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_returns_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    benchmark_returns_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    ter: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
