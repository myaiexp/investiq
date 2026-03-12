import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import Fund, Index

logger = logging.getLogger(__name__)

SEED_INDICES: list[dict] = [
    {"name": "OMXH25", "ticker": "^OMXH25", "region": "nordic"},
    {"name": "OMXS30", "ticker": "^OMXS30", "region": "nordic"},
    {"name": "OMXC25", "ticker": "^OMXC25", "region": "nordic"},
    {"name": "OBX", "ticker": "OBX.OL", "region": "nordic"},
    {"name": "S&P 500", "ticker": "^GSPC", "region": "global"},
    {"name": "NASDAQ-100", "ticker": "^NDX", "region": "global"},
    {"name": "DAX 40", "ticker": "^GDAXI", "region": "global"},
    {"name": "FTSE 100", "ticker": "^FTSE", "region": "global"},
    {"name": "Nikkei 225", "ticker": "^N225", "region": "global"},
    {"name": "MSCI World", "ticker": "URTH", "region": "global"},
]

SEED_FUNDS: list[dict] = [
    {
        "name": "ÅAB Europa Aktie B",
        "ticker": "0P00000N9Y.F",
        "isin": "FI0008805031",
        "fund_type": "equity",
        "benchmark_ticker": "^STOXX50E",
        "benchmark_name": "EURO STOXX 50",
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
        "name": "ÅAB Euro Bond A",
        "ticker": "0P00000N9R.F",
        "isin": "FI0008805007",
        "fund_type": "bond",
        "benchmark_ticker": None,
        "benchmark_name": "Bloomberg Euro Aggregate",
    },
    {
        "name": "ÅAB Green Bond ESG C",
        "ticker": "0P0001HOZS.F",
        "isin": None,
        "fund_type": "bond",
        "benchmark_ticker": None,
        "benchmark_name": "Bloomberg Euro Green Bond",
    },
    {
        "name": "ÅAB Nordiska Småbolag B",
        "ticker": "0P0001JWUW.F",
        "isin": None,
        "fund_type": "equity",
        "benchmark_ticker": "^OMXS30",
        "benchmark_name": "OMXS30",
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
