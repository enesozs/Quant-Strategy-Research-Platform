"""FastAPI app: routes only. Contract: api/CONTRACT.md.

Run from the repository root:
    fastapi dev api/main.py --port 8020
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import api  # noqa: F401  (puts the repository root on sys.path)
from api import schemas, services
from api.cache import MarketDataError

logger = logging.getLogger("api")

app = FastAPI(
    title="Strategy Backtester API",
    version="1.0.0",
    description="Research endpoints for the strategy backtester. See api/CONTRACT.md.",
)


def _field_name(location: tuple[Any, ...]) -> str:
    parts = [str(part) for part in location if part != "body"]
    return ".".join(parts)


@app.exception_handler(RequestValidationError)
def _validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    messages = []
    for item in error.errors():
        message = str(item.get("msg", "Invalid value")).removeprefix("Value error, ")
        field = _field_name(tuple(item.get("loc", ())))
        messages.append(f"{field}: {message}" if field else message)
    return JSONResponse(
        status_code=422, content={"detail": "; ".join(messages) or "Invalid request."}
    )


@app.exception_handler(ValueError)
def _value_error(_: Request, error: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


@app.exception_handler(MarketDataError)
def _market_data_error(_: Request, error: MarketDataError) -> JSONResponse:
    logger.warning("Market data download failed: %s", error)
    return JSONResponse(status_code=502, content={"detail": str(error)})


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta")
def meta() -> dict[str, Any]:
    return services.get_meta()


@router.post("/backtest")
def backtest(request: schemas.BacktestRequest) -> dict[str, Any]:
    return services.run_backtest_request(request)


@router.post("/compare")
def compare(request: schemas.CompareRequest) -> dict[str, Any]:
    return services.run_compare_request(request)


@router.post("/optimize")
def optimize(request: schemas.OptimizeRequest) -> dict[str, Any]:
    return services.run_optimize_request(request)


@router.post("/validate/split")
def validate_split(request: schemas.ValidateSplitRequest) -> dict[str, Any]:
    return services.run_validate_split_request(request)


@router.post("/validate/walk-forward")
def validate_walk_forward(request: schemas.WalkForwardRequest) -> dict[str, Any]:
    return services.run_walk_forward_request(request)


@router.post("/pairs/research")
def pairs_research(request: schemas.PairsResearchRequest) -> dict[str, Any]:
    return services.run_pairs_research_request(request)


@router.post("/pairs/sensitivity")
def pairs_sensitivity(request: schemas.PairsResearchRequest) -> dict[str, Any]:
    return services.run_pairs_sensitivity_request(request)


@router.post("/pairs/discover")
def pairs_discover(request: schemas.PairsUniverseRequest) -> dict[str, Any]:
    return services.run_pairs_discover_request(request)


@router.post("/pairs/portfolio")
def pairs_portfolio(request: schemas.PairsUniverseRequest) -> dict[str, Any]:
    return services.run_pairs_portfolio_request(request)


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def api_not_found(path: str) -> JSONResponse:
    # Keeps unknown /api paths from falling through to the SPA's index.html.
    return JSONResponse(
        status_code=404, content={"detail": f"Unknown API endpoint '/api/{path}'."}
    )


app.include_router(router)

# Production: serve the built React app (API routes are matched first; unknown
# paths fall back to index.html for client-side routing).
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if (WEB_DIST / "index.html").is_file():
    app.frontend("/", directory=WEB_DIST, fallback="index.html")
