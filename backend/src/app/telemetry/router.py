"""
OTLP (OpenTelemetry Protocol) receiver for Claude Code metrics.

Receives metrics at /v1/metrics and stores full telemetry data.
"""

from fastapi import APIRouter, Header, HTTPException, Request
from loguru import logger

from src.app.telemetry.domains import OTLPResponse
from src.app.telemetry.service import TelemetryService

router = APIRouter()


@router.post('/v1/metrics', response_model=OTLPResponse)
async def receive_metrics(
    request: Request,
    x_api_key: str = Header(None, alias='X-API-Key'),
    x_team_api_key: str = Header(None, alias='X-Team-API-Key'),
    x_user_id: str = Header(None, alias='X-User-Id'),
    x_user_name: str = Header(None, alias='X-User-Name'),
    authorization: str = Header(None),
) -> OTLPResponse:
    """
    Receive OTLP metrics from Claude Code with full granularity capture.

    Stores every metric with full payload for complete telemetry.
    """
    # Get customer from API key
    customer, user_from_key, user_name_from_key = TelemetryService.get_customer_from_api_key(
        x_api_key=x_api_key,
        x_team_api_key=x_team_api_key,
        authorization=authorization,
    )

    if not customer:
        raise HTTPException(
            status_code=401,
            detail='Missing or invalid API key. Use X-API-Key header with your personal API key.',
        )

    # Parse the OTLP payload
    try:
        body = await request.json()
    except Exception as e:
        logger.error('Failed to parse OTLP payload', error=str(e))
        raise HTTPException(status_code=400, detail='Invalid JSON payload')

    # Process metrics via service
    return TelemetryService.process_metrics(
        body=body,
        customer=customer,
        user_from_key=user_from_key,
        user_name_from_key=user_name_from_key,
        x_user_id=x_user_id,
        x_user_name=x_user_name,
    )


@router.post('/v1/traces', response_model=OTLPResponse)
async def receive_traces(request: Request) -> OTLPResponse:
    """Accept traces but don't process them (for compatibility)."""
    return OTLPResponse(partialSuccess=None)


@router.post('/v1/logs', response_model=OTLPResponse)
async def receive_logs(request: Request) -> OTLPResponse:
    """Accept logs but don't process them (for compatibility)."""
    return OTLPResponse(partialSuccess=None)
