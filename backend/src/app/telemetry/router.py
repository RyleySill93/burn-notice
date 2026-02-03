"""
OTLP (OpenTelemetry Protocol) receiver for Claude Code metrics.

Receives metrics at /v1/metrics and stores full telemetry data.
"""
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from src.app.engineers.service import EngineerService
from src.app.usage.domains import TelemetryEventCreate
from src.app.usage.models import TelemetryEvent
from src.app.usage.service import UsageService
from src.core.customer.models import Customer
from src.core.membership import MembershipService

router = APIRouter()


class OTLPResponse(BaseModel):
    """Standard OTLP response."""
    partialSuccess: dict | None = None


def extract_attribute(attributes: list[dict], key: str) -> str | int | float | None:
    """Extract a value from OTLP attributes list."""
    for attr in attributes:
        if attr.get('key') == key:
            value = attr.get('value', {})
            # Handle different value types
            if 'stringValue' in value:
                return value['stringValue']
            if 'intValue' in value:
                return int(value['intValue'])
            if 'doubleValue' in value:
                return value['doubleValue']
            if 'boolValue' in value:
                return value['boolValue']
    return None


def attributes_to_dict(attributes: list[dict]) -> dict[str, Any]:
    """Convert OTLP attributes list to a dictionary."""
    result = {}
    for attr in attributes:
        key = attr.get('key')
        if key:
            value = attr.get('value', {})
            if 'stringValue' in value:
                result[key] = value['stringValue']
            elif 'intValue' in value:
                result[key] = int(value['intValue'])
            elif 'doubleValue' in value:
                result[key] = value['doubleValue']
            elif 'boolValue' in value:
                result[key] = value['boolValue']
            elif 'arrayValue' in value:
                result[key] = value['arrayValue']
            elif 'kvlistValue' in value:
                result[key] = value['kvlistValue']
    return result


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
    customer = None
    user_from_key = None
    user_name_from_key = None

    # First, try X-API-Key (personal per-user key)
    if x_api_key:
        membership_service = MembershipService.factory()
        membership = membership_service.get_membership_with_user_by_api_key(x_api_key)
        if membership:
            customer = Customer.get_or_none(id=membership.customer_id)
            if membership.user:
                user_from_key = membership.user.email or membership.user_id
                user_name_from_key = membership.user.full_name or membership.user.email

    # Fall back to X-Team-API-Key (legacy)
    if not customer:
        team_key = x_team_api_key
        if not team_key and authorization:
            if authorization.startswith('Bearer '):
                team_key = authorization[7:]

        if team_key:
            customer = Customer.get_or_none(id=team_key)

    if not customer:
        raise HTTPException(
            status_code=401,
            detail='Missing or invalid API key. Use X-API-Key header with your personal API key.'
        )

    # Parse the OTLP payload
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f'Failed to parse OTLP payload: {e}')
        raise HTTPException(status_code=400, detail='Invalid JSON payload')

    # Process resource metrics
    resource_metrics = body.get('resourceMetrics', [])
    events_recorded = 0
    usage_recorded = 0

    for rm in resource_metrics:
        # Extract resource attributes (user info, etc.)
        resource = rm.get('resource', {})
        resource_attrs = resource.get('attributes', [])
        resource_attrs_dict = attributes_to_dict(resource_attrs)

        # Try to get user identifier
        external_id = (
            user_from_key or
            x_user_id or
            extract_attribute(resource_attrs, 'user.id') or
            extract_attribute(resource_attrs, 'service.instance.id') or
            extract_attribute(resource_attrs, 'host.name') or
            'unknown'
        )
        display_name = (
            user_name_from_key or
            x_user_name or
            extract_attribute(resource_attrs, 'user.name') or
            extract_attribute(resource_attrs, 'service.name') or
            external_id
        )

        # Get or create engineer
        engineer = EngineerService.get_or_create(
            customer_id=customer.id,
            external_id=str(external_id),
            display_name=str(display_name),
        )

        # Process scope metrics
        for sm in rm.get('scopeMetrics', []):
            scope = sm.get('scope', {})
            scope_name = scope.get('name', '')
            scope_attrs_dict = {'scope_name': scope_name, 'scope_version': scope.get('version')}

            # Process individual metrics
            for metric in sm.get('metrics', []):
                metric_name = metric.get('name', '')
                metric_description = metric.get('description', '')
                metric_unit = metric.get('unit', '')

                # Get data points from sum, gauge, or histogram
                data_points = []
                if 'sum' in metric:
                    data_points = metric['sum'].get('dataPoints', [])
                elif 'gauge' in metric:
                    data_points = metric['gauge'].get('dataPoints', [])
                elif 'histogram' in metric:
                    data_points = metric['histogram'].get('dataPoints', [])

                for dp in data_points:
                    dp_attrs = dp.get('attributes', [])
                    dp_attrs_dict = attributes_to_dict(dp_attrs)
                    value = dp.get('asInt') or dp.get('asDouble', 0)

                    # Extract common fields
                    model = (
                        extract_attribute(dp_attrs, 'model') or
                        extract_attribute(dp_attrs, 'llm.model') or
                        extract_attribute(dp_attrs, 'gen_ai.response.model')
                    )
                    session_id = (
                        extract_attribute(dp_attrs, 'session.id') or
                        extract_attribute(dp_attrs, 'session_id') or
                        extract_attribute(dp_attrs, 'conversation.id')
                    )

                    # Extract token counts based on metric name
                    tokens_input = 0
                    tokens_output = 0
                    cache_read_tokens = 0
                    cache_creation_tokens = 0

                    metric_lower = metric_name.lower()
                    if 'input' in metric_lower or 'prompt' in metric_lower:
                        tokens_input = int(value)
                    elif 'output' in metric_lower or 'completion' in metric_lower:
                        tokens_output = int(value)
                    elif 'cache_read' in metric_lower:
                        cache_read_tokens = int(value)
                    elif 'cache_creation' in metric_lower:
                        cache_creation_tokens = int(value)
                    elif 'token' in metric_lower:
                        # Generic token metric - check attributes
                        direction = extract_attribute(dp_attrs, 'direction') or extract_attribute(dp_attrs, 'type')
                        if direction in ('input', 'prompt'):
                            tokens_input = int(value)
                        elif direction in ('output', 'completion'):
                            tokens_output = int(value)

                    # Extract tool usage
                    tool_name = extract_attribute(dp_attrs, 'tool.name') or extract_attribute(dp_attrs, 'tool')
                    tool_result = extract_attribute(dp_attrs, 'tool.result') or extract_attribute(dp_attrs, 'result')

                    # Extract timing
                    duration_ms = extract_attribute(dp_attrs, 'duration_ms') or extract_attribute(dp_attrs, 'latency_ms')
                    ttft_ms = extract_attribute(dp_attrs, 'time_to_first_token_ms') or extract_attribute(dp_attrs, 'ttft_ms')

                    # Extract cost if present
                    cost_usd = extract_attribute(dp_attrs, 'cost_usd') or extract_attribute(dp_attrs, 'cost')

                    # Store full telemetry event
                    telemetry_event = TelemetryEventCreate(
                        engineer_id=engineer.id,
                        session_id=str(session_id) if session_id else None,
                        event_type='metrics',
                        metric_name=metric_name,
                        model=str(model) if model else None,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        cache_read_tokens=cache_read_tokens,
                        cache_creation_tokens=cache_creation_tokens,
                        cost_usd=float(cost_usd) if cost_usd else None,
                        tool_name=str(tool_name) if tool_name else None,
                        tool_result=str(tool_result) if tool_result else None,
                        duration_ms=int(duration_ms) if duration_ms else None,
                        time_to_first_token_ms=int(ttft_ms) if ttft_ms else None,
                        raw_payload={'metric': metric, 'dataPoint': dp},
                        resource_attributes=resource_attrs_dict,
                        scope_attributes=scope_attrs_dict,
                        data_point_attributes=dp_attrs_dict,
                    )
                    TelemetryEvent.create(telemetry_event)
                    events_recorded += 1

                    # Also record to legacy usage table for backward compatibility
                    if tokens_input > 0 or tokens_output > 0:
                        UsageService.record_usage(
                            engineer_id=engineer.id,
                            tokens_input=tokens_input,
                            tokens_output=tokens_output,
                            model=str(model) if model else None,
                            session_id=str(session_id) if session_id else None,
                        )
                        usage_recorded += 1

    logger.info(f'OTLP: {events_recorded} telemetry events, {usage_recorded} usage records for {customer.name}')

    return OTLPResponse(partialSuccess=None)


@router.post('/v1/traces', response_model=OTLPResponse)
async def receive_traces(request: Request) -> OTLPResponse:
    """Accept traces but don't process them (for compatibility)."""
    return OTLPResponse(partialSuccess=None)


@router.post('/v1/logs', response_model=OTLPResponse)
async def receive_logs(request: Request) -> OTLPResponse:
    """Accept logs but don't process them (for compatibility)."""
    return OTLPResponse(partialSuccess=None)
