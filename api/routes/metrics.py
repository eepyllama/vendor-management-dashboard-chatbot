"""
api/routes/metrics.py
─────────────────────
API router for token usage metrics.
"""

from fastapi import APIRouter
from services.metrics_service import get_metrics_service

router = APIRouter()

@router.get("/metrics/tokens", tags=["metrics"])
async def get_token_metrics():
    """
    Get aggregated token usage statistics and estimated cost.
    """
    metrics_service = get_metrics_service()
    return metrics_service.get_aggregated_metrics()
