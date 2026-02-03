"""
OTLP (OpenTelemetry Protocol) receiver for Claude Code metrics.

Receives metrics at /v1/metrics and stores token usage data.
"""
from fastapi import APIRouter, Header, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from src.app.engineers.service import EngineerService
from src.app.usage.service import UsageService
from src.core.customer.models import Customer
from src.core.membership import MembershipService

router = APIRouter()


class OTLPResponse(BaseModel):
    """Standard OTLP response."""
    partialSuccess: dict | None = None


def extract_attribute(attributes: list[dict], key: str) -> str | int | None:
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
    return None


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
    Receive OTLP metrics from Claude Code.

    Expects one of:
    - X-API-Key header with personal API key (preferred, identifies both user and team)
    - X-Team-API-Key header with customer ID (legacy, requires X-User-Id/X-User-Name)
    - Authorization: Bearer <customer_id> header (legacy)
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

    # Debug: log headers and payload
    import json
    logger.info(f'OTLP headers - X-User-Id: {x_user_id}, X-User-Name: {x_user_name}')
    logger.info(f'OTLP payload: {json.dumps(body, indent=2)}')

    # Process resource metrics
    resource_metrics = body.get('resourceMetrics', [])
    metrics_recorded = 0

    for rm in resource_metrics:
        # Extract resource attributes (user info, etc.)
        resource = rm.get('resource', {})
        resource_attrs = resource.get('attributes', [])

        # Try to get user identifier - prefer API key lookup, then headers, then resource attributes
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

        # Process scope metrics
        for sm in rm.get('scopeMetrics', []):
            scope = sm.get('scope', {})
            scope_name = scope.get('name', '')

            # Process individual metrics
            for metric in sm.get('metrics', []):
                metric_name = metric.get('name', '')

                # Look for token usage metrics
                # Claude Code might use names like:
                # - claude.tokens.input, claude.tokens.output
                # - llm.token.count with attributes
                # - api.tokens.used

                tokens_input = 0
                tokens_output = 0
                model = None
                session_id = None

                # Handle sum metrics (counters)
                if 'sum' in metric:
                    data_points = metric['sum'].get('dataPoints', [])
                    for dp in data_points:
                        dp_attrs = dp.get('attributes', [])
                        value = dp.get('asInt') or dp.get('asDouble', 0)

                        # Check metric name patterns
                        if 'input' in metric_name.lower() or 'prompt' in metric_name.lower():
                            tokens_input = int(value)
                        elif 'output' in metric_name.lower() or 'completion' in metric_name.lower():
                            tokens_output = int(value)
                        elif 'token' in metric_name.lower():
                            # Generic token metric - check attributes for direction
                            direction = extract_attribute(dp_attrs, 'direction') or extract_attribute(dp_attrs, 'type')
                            if direction in ('input', 'prompt'):
                                tokens_input = int(value)
                            elif direction in ('output', 'completion'):
                                tokens_output = int(value)

                        # Extract model and session from attributes
                        model = model or extract_attribute(dp_attrs, 'model') or extract_attribute(dp_attrs, 'llm.model')
                        session_id = session_id or extract_attribute(dp_attrs, 'session.id') or extract_attribute(dp_attrs, 'session_id')

                # Handle gauge metrics
                elif 'gauge' in metric:
                    data_points = metric['gauge'].get('dataPoints', [])
                    for dp in data_points:
                        dp_attrs = dp.get('attributes', [])
                        value = dp.get('asInt') or dp.get('asDouble', 0)

                        if 'input' in metric_name.lower():
                            tokens_input = int(value)
                        elif 'output' in metric_name.lower():
                            tokens_output = int(value)

                        model = model or extract_attribute(dp_attrs, 'model')
                        session_id = session_id or extract_attribute(dp_attrs, 'session.id')

                # Record usage if we have token data
                if tokens_input > 0 or tokens_output > 0:
                    engineer = EngineerService.get_or_create(
                        customer_id=customer.id,
                        external_id=str(external_id),
                        display_name=str(display_name),
                    )

                    UsageService.record_usage(
                        engineer_id=engineer.id,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        model=model,
                        session_id=session_id,
                    )
                    metrics_recorded += 1
                    logger.debug(f'Recorded usage: {external_id} - {tokens_input}/{tokens_output} tokens')

    logger.info(f'Processed OTLP metrics: {metrics_recorded} usage records for team {customer.name}')

    return OTLPResponse(partialSuccess=None)


@router.post('/v1/traces', response_model=OTLPResponse)
async def receive_traces(request: Request) -> OTLPResponse:
    """Accept traces but don't process them (for compatibility)."""
    return OTLPResponse(partialSuccess=None)


@router.post('/v1/logs', response_model=OTLPResponse)
async def receive_logs(request: Request) -> OTLPResponse:
    """Accept logs but don't process them (for compatibility)."""
    return OTLPResponse(partialSuccess=None)
