from fastapi import APIRouter

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("/")
async def list_funds():
    """List all tracked Ålandsbanken funds."""
    return {"funds": []}


@router.get("/{ticker}/performance")
async def get_fund_performance(ticker: str):
    """Get fund performance metrics (returns, volatility, Sharpe, etc.)."""
    return {"ticker": ticker, "metrics": {}}


@router.get("/{ticker}/nav")
async def get_fund_nav(ticker: str, period: str = "1y"):
    """Get NAV history for a fund."""
    return {"ticker": ticker, "period": period, "data": []}
