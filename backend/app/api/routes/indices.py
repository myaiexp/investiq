from fastapi import APIRouter

router = APIRouter(prefix="/indices", tags=["indices"])


@router.get("/")
async def list_indices():
    """List all tracked indices."""
    return {"indices": []}


@router.get("/{ticker}/ohlcv")
async def get_ohlcv(ticker: str, period: str = "1y"):
    """Get OHLCV data for an index."""
    return {"ticker": ticker, "period": period, "data": []}


@router.get("/{ticker}/indicators")
async def get_indicators(ticker: str, indicators: str = "all"):
    """Get technical indicator values for an index."""
    return {"ticker": ticker, "indicators": []}


@router.get("/{ticker}/signal")
async def get_signal(ticker: str):
    """Get aggregated buy/sell/hold signal for an index."""
    return {"ticker": ticker, "signal": "hold", "details": []}
