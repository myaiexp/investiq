import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import (
    Fund,
    FundNAV,
    FundPerformance,
    Index,
    IndicatorData,
    OHLCVData,
    SignalData,
)

logger = logging.getLogger(__name__)

SEED_INDICES: list[dict] = [
    {"name": "OMXH25", "ticker": "^OMXH25", "region": "nordic", "currency": "EUR"},
    {"name": "OMXS30", "ticker": "^OMX", "region": "nordic", "currency": "SEK"},
    {"name": "OMXC25", "ticker": "^OMXC25", "region": "nordic", "currency": "DKK"},
    {"name": "OBX (TR)", "ticker": "OBX.OL", "region": "nordic", "currency": "NOK"},
    {"name": "S&P 500", "ticker": "^GSPC", "region": "global", "currency": "USD"},
    {"name": "NASDAQ-100", "ticker": "^NDX", "region": "global", "currency": "USD"},
    {"name": "DAX 40", "ticker": "^GDAXI", "region": "global", "currency": "EUR"},
    {"name": "FTSE 100", "ticker": "^FTSE", "region": "global", "currency": "GBP"},
    {"name": "Nikkei 225", "ticker": "^N225", "region": "global", "currency": "JPY"},
    {"name": "MSCI World (URTH)", "ticker": "URTH", "region": "global", "currency": "USD"},
]

SEED_FUNDS: list[dict] = [
    {
        "name": "ÅAB Europa Aktie B",
        "ticker": "0P00000N9Y.F",
        "isin": "FI0008805031",
        "fund_type": "equity",
        "benchmark_ticker": "IEUR",
        "benchmark_name": "MSCI Europe",
    },
    {
        "name": "ÅAB Norden Aktie EUR",
        "ticker": "0P00015D0H.F",
        "isin": "FI4000123179",
        "fund_type": "equity",
        "benchmark_ticker": "^OMXH25",
        "benchmark_name": "OMXH25",
    },
    {
        "name": "ÅAB Global Aktie B",
        "ticker": "0P0000CNVH.F",
        "isin": "FI0008812607",
        "fund_type": "equity",
        "benchmark_ticker": "URTH",
        "benchmark_name": "MSCI World",
    },
    {
        "name": "ÅAB Euro Bond B",
        "ticker": "0P00000N9Q.F",
        "isin": "FI0008805007",
        "fund_type": "bond",
        "benchmark_ticker": "SYBA.DE",
        "benchmark_name": "Bloomberg Euro Aggregate Bond",
    },
    {
        "name": "ÅAB Green Bond ESG C",
        "ticker": "0P0001HOZS.F",
        "isin": None,
        "fund_type": "bond",
        "benchmark_ticker": "GRON.DE",
        "benchmark_name": "Bloomberg Euro Green Bond",
    },
    {
        "name": "ÅAB Nordiska Småbolag B",
        "ticker": "0P0001JWUW.F",
        "isin": None,
        "fund_type": "equity",
        "benchmark_ticker": "^OMX",
        "benchmark_name": "OMXS30",
    },
    {
        "name": "ÅAB Varainhoito B",
        "ticker": "0P00001CPE.F",
        "isin": "FI0008809934",
        "fund_type": "balanced",
        "benchmark_ticker": None,
        "benchmark_name": "",
    },
]

INDICATOR_CATEGORIES: dict[str, str] = {
    "rsi": "oscillator",
    "macd": "oscillator",
    "bollinger": "overlay",
    "ma": "overlay",
    "stochastic": "oscillator",
    "obv": "oscillator",
    "fibonacci": "overlay",
    "atr": "oscillator",
    "ichimoku": "overlay",
    "cci": "oscillator",
}


async def seed_database(session: AsyncSession) -> None:
    """Insert missing indices and funds. Skip existing by ticker."""
    # --- Rename existing records (idempotent) ---
    # OMXS30 ticker: ^OMXS30 → ^OMX
    await session.execute(
        update(Index).where(Index.ticker == "^OMXS30").values(ticker="^OMX")
    )
    # MSCI World name clarification
    await session.execute(
        update(Index).where(Index.name == "MSCI World").values(name="MSCI World (URTH)")
    )
    # OBX name clarification (Total Return index)
    await session.execute(
        update(Index).where(Index.name == "OBX").values(name="OBX (TR)")
    )
    # Fund benchmark ticker: ^OMXS30 → ^OMX
    await session.execute(
        update(Fund)
        .where(Fund.benchmark_ticker == "^OMXS30")
        .values(benchmark_ticker="^OMX")
    )

    # --- Phase 3 ticker migrations (idempotent) ---

    # Euro Bond: swap ticker A → B across all tables
    old_eb, new_eb = "0P00000N9R.F", "0P00000N9Q.F"
    await session.execute(
        update(Fund).where(Fund.ticker == old_eb).values(
            ticker=new_eb,
            name="ÅAB Euro Bond B",
            benchmark_ticker="SYBA.DE",
            benchmark_name="Bloomberg Euro Aggregate Bond",
        )
    )
    await session.execute(update(OHLCVData).where(OHLCVData.ticker == old_eb).values(ticker=new_eb))
    await session.execute(update(IndicatorData).where(IndicatorData.ticker == old_eb).values(ticker=new_eb))
    await session.execute(update(SignalData).where(SignalData.ticker == old_eb).values(ticker=new_eb))
    await session.execute(update(FundNAV).where(FundNAV.ticker == old_eb).values(ticker=new_eb))
    await session.execute(update(FundPerformance).where(FundPerformance.ticker == old_eb).values(ticker=new_eb))

    # Europa Aktie B: update benchmark to MSCI Europe
    await session.execute(
        update(Fund).where(Fund.ticker == "0P00000N9Y.F").values(
            benchmark_ticker="IEUR",
            benchmark_name="MSCI Europe",
        )
    )

    # Green Bond ESG C: add benchmark
    await session.execute(
        update(Fund).where(Fund.ticker == "0P0001HOZS.F").values(
            benchmark_ticker="GRON.DE",
            benchmark_name="Bloomberg Euro Green Bond",
        )
    )

    # Index currency: update all
    for idx in SEED_INDICES:
        await session.execute(
            update(Index).where(Index.ticker == idx["ticker"]).values(currency=idx["currency"])
        )

    existing_indices = set(
        (await session.execute(select(Index.ticker))).scalars().all()
    )
    for data in SEED_INDICES:
        if data["ticker"] not in existing_indices:
            session.add(Index(**data))

    existing_funds = set(
        (await session.execute(select(Fund.ticker))).scalars().all()
    )
    for data in SEED_FUNDS:
        if data["ticker"] not in existing_funds:
            session.add(Fund(**data))

    await session.commit()
    logger.info("Seed complete: %d indices, %d funds", len(SEED_INDICES), len(SEED_FUNDS))
