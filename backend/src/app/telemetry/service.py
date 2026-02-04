"""Telemetry service for processing OTLP metrics from Claude Code."""

from typing import Any

from loguru import logger

from src.app.engineers.service import EngineerService
from src.app.telemetry.constants import DEFAULT_PRICING, MODEL_PRICING
from src.app.telemetry.domains import OTLPResponse
from src.app.usage.domains import TelemetryEventCreate
from src.app.usage.models import TelemetryEvent
from src.app.usage.service import UsageService
from src.core.customer import CustomerRead
from src.core.customer.models import Customer


def calculate_cost(model: str | None, tokens_input: int, tokens_output: int) -> float:
    """Calculate cost in USD based on model and token counts."""
    pricing: dict[str, float] = DEFAULT_PRICING
    if model:
        # Try exact match, then prefix match
        model_lower = model.lower()
        if model_lower in MODEL_PRICING:
            pricing = MODEL_PRICING[model_lower]
        else:
            # Try prefix matching for versioned models
            for model_key, model_pricing in MODEL_PRICING.items():
                if model_lower.startswith(model_key.split('-2')[0]):  # Match base model name
                    pricing = model_pricing
                    break

    # Price is per million tokens
    input_cost = (tokens_input / 1_000_000) * pricing['input']
    output_cost = (tokens_output / 1_000_000) * pricing['output']
    return input_cost + output_cost


def extract_attribute(attributes: list[dict[str, Any]], key: str) -> str | int | float | bool | None:
    """Extract a value from OTLP attributes list."""
    for attr in attributes:
        if attr.get('key') == key:
            value = attr.get('value', {})
            # Handle different value types
            if 'stringValue' in value:
                return str(value['stringValue'])
            if 'intValue' in value:
                return int(value['intValue'])
            if 'doubleValue' in value:
                return float(value['doubleValue'])
            if 'boolValue' in value:
                return bool(value['boolValue'])
    return None


def attributes_to_dict(attributes: list[dict[str, Any]]) -> dict[str, Any]:
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


class TelemetryService:
    """Service for processing OTLP telemetry data."""

    @staticmethod
    def get_customer_from_api_key(
        x_api_key: str | None,
        x_team_api_key: str | None,
        authorization: str | None,
    ) -> tuple[CustomerRead | None, str | None, str | None]:
        """
        Get customer and user info from API key headers.

        Returns:
            Tuple of (customer, user_id, user_name) or (None, None, None) if not found
        """
        # Import here to avoid circular import
        from src.core.membership import MembershipService

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

        return customer, user_from_key, user_name_from_key

    @staticmethod
    def process_metrics(
        body: dict[str, Any],
        customer: CustomerRead,
        user_from_key: str | None,
        user_name_from_key: str | None,
        x_user_id: str | None,
        x_user_name: str | None,
    ) -> OTLPResponse:
        """
        Process OTLP metrics payload and store telemetry events.

        Args:
            body: The parsed OTLP JSON payload
            customer: The customer/team
            user_from_key: User ID from API key (if personal key)
            user_name_from_key: User name from API key (if personal key)
            x_user_id: User ID from header
            x_user_name: User name from header

        Returns:
            OTLPResponse
        """
        # Process resource metrics
        resource_metrics = body.get('resourceMetrics', [])
        events_recorded = 0
        usage_recorded = 0
        total_tokens_input = 0
        total_tokens_output = 0
        metric_names_seen: set[str] = set()

        for rm in resource_metrics:
            # Extract resource attributes (user info, etc.)
            resource = rm.get('resource', {})
            resource_attrs = resource.get('attributes', [])
            resource_attrs_dict = attributes_to_dict(resource_attrs)

            # Try to get user identifier
            external_id = (
                user_from_key
                or x_user_id
                or extract_attribute(resource_attrs, 'user.id')
                or extract_attribute(resource_attrs, 'service.instance.id')
                or extract_attribute(resource_attrs, 'host.name')
                or 'unknown'
            )
            display_name = (
                user_name_from_key
                or x_user_name
                or extract_attribute(resource_attrs, 'user.name')
                or extract_attribute(resource_attrs, 'service.name')
                or external_id
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

                    # Track metric names for summary
                    metric_names_seen.add(metric_name)

                    # Get data points from sum, gauge, or histogram
                    data_points = []
                    if 'sum' in metric:
                        data_points = metric['sum'].get('dataPoints', [])
                    elif 'gauge' in metric:
                        data_points = metric['gauge'].get('dataPoints', [])
                    elif 'histogram' in metric:
                        data_points = metric['histogram'].get('dataPoints', [])

                    for dp in data_points:
                        events_recorded, usage_recorded, total_tokens_input, total_tokens_output = (
                            TelemetryService._process_data_point(
                                dp=dp,
                                metric=metric,
                                metric_name=metric_name,
                                engineer=engineer,
                                resource_attrs_dict=resource_attrs_dict,
                                scope_attrs_dict=scope_attrs_dict,
                                events_recorded=events_recorded,
                                usage_recorded=usage_recorded,
                                total_tokens_input=total_tokens_input,
                                total_tokens_output=total_tokens_output,
                            )
                        )

        # Log summary with metric names for debugging
        logger.info(
            'OTLP metrics processed',
            customer_name=customer.name,
            events_recorded=events_recorded,
            usage_recorded=usage_recorded,
            tokens_input=total_tokens_input,
            tokens_output=total_tokens_output,
            total_tokens=total_tokens_input + total_tokens_output,
            metrics=sorted(metric_names_seen),
        )

        return OTLPResponse(partialSuccess=None)

    @staticmethod
    def _process_data_point(
        dp: dict[str, Any],
        metric: dict[str, Any],
        metric_name: str,
        engineer: Any,
        resource_attrs_dict: dict[str, Any],
        scope_attrs_dict: dict[str, Any],
        events_recorded: int,
        usage_recorded: int,
        total_tokens_input: int,
        total_tokens_output: int,
    ) -> tuple[int, int, int, int]:
        """Process a single data point from OTLP metrics."""
        dp_attrs = dp.get('attributes', [])
        dp_attrs_dict = attributes_to_dict(dp_attrs)
        value = dp.get('asInt') or dp.get('asDouble', 0)

        # Extract common fields
        model = (
            extract_attribute(dp_attrs, 'model')
            or extract_attribute(dp_attrs, 'llm.model')
            or extract_attribute(dp_attrs, 'gen_ai.response.model')
        )
        session_id = (
            extract_attribute(dp_attrs, 'session.id')
            or extract_attribute(dp_attrs, 'session_id')
            or extract_attribute(dp_attrs, 'conversation.id')
        )

        # Extract token counts and cost based on metric name
        tokens_input = 0
        tokens_output = 0
        cache_read_tokens = 0
        cache_creation_tokens = 0
        cost_usd = None

        # Handle Claude Code's standard metrics
        if metric_name == 'claude_code.cost.usage':
            # Cost metric - value is in USD
            cost_usd = float(value)
            logger.debug('OTLP cost metric', cost_usd=cost_usd)
        elif metric_name == 'claude_code.token.usage':
            # Token metric - check 'type' attribute for direction
            token_type = extract_attribute(dp_attrs, 'type')
            logger.debug('OTLP token metric', token_type=token_type, value=value)
            if token_type == 'input':
                tokens_input = int(value)
            elif token_type == 'output':
                tokens_output = int(value)
            elif token_type == 'cacheRead':
                cache_read_tokens = int(value)
            elif token_type == 'cacheCreation':
                cache_creation_tokens = int(value)
            else:
                logger.warning('OTLP unknown token type', token_type=token_type)
        else:
            # Fallback for other metric formats
            tokens_input, tokens_output, cache_read_tokens, cache_creation_tokens = (
                TelemetryService._extract_tokens_fallback(metric_name, value, dp_attrs, dp_attrs_dict)
            )

        # Extract tool usage
        tool_name = extract_attribute(dp_attrs, 'tool.name') or extract_attribute(dp_attrs, 'tool')
        tool_result = extract_attribute(dp_attrs, 'tool.result') or extract_attribute(dp_attrs, 'result')

        # Extract timing
        duration_ms = extract_attribute(dp_attrs, 'duration_ms') or extract_attribute(dp_attrs, 'latency_ms')
        ttft_ms = extract_attribute(dp_attrs, 'time_to_first_token_ms') or extract_attribute(dp_attrs, 'ttft_ms')

        # If no cost from metric and we have tokens, calculate it
        if cost_usd is None:
            cost_from_attr = extract_attribute(dp_attrs, 'cost_usd') or extract_attribute(dp_attrs, 'cost')
            if cost_from_attr is not None:
                cost_usd = float(cost_from_attr)
            elif tokens_input > 0 or tokens_output > 0:
                cost_usd = calculate_cost(str(model) if model else None, tokens_input, tokens_output)

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
            total_tokens_input += tokens_input
            total_tokens_output += tokens_output

        return events_recorded, usage_recorded, total_tokens_input, total_tokens_output

    @staticmethod
    def _extract_tokens_fallback(
        metric_name: str, value: Any, dp_attrs: list[dict[str, Any]], dp_attrs_dict: dict[str, Any]
    ) -> tuple[int, int, int, int]:
        """Fallback token extraction for non-standard metric formats."""
        tokens_input = 0
        tokens_output = 0
        cache_read_tokens = 0
        cache_creation_tokens = 0

        metric_lower = metric_name.lower()
        if 'input' in metric_lower or 'prompt' in metric_lower:
            tokens_input = int(value)
            logger.info('OTLP fallback input metric', metric_name=metric_name, value=value)
        elif 'output' in metric_lower or 'completion' in metric_lower:
            tokens_output = int(value)
            logger.info('OTLP fallback output metric', metric_name=metric_name, value=value)
        elif 'cache_read' in metric_lower:
            cache_read_tokens = int(value)
            logger.info('OTLP fallback cache_read metric', metric_name=metric_name, value=value)
        elif 'cache_creation' in metric_lower:
            cache_creation_tokens = int(value)
            logger.info('OTLP fallback cache_creation metric', metric_name=metric_name, value=value)
        elif 'token' in metric_lower:
            # Generic token metric - check attributes
            direction = extract_attribute(dp_attrs, 'direction') or extract_attribute(dp_attrs, 'type')
            if direction in ('input', 'prompt'):
                tokens_input = int(value)
                logger.info('OTLP generic token input', metric_name=metric_name, value=value)
            elif direction in ('output', 'completion'):
                tokens_output = int(value)
                logger.info('OTLP generic token output', metric_name=metric_name, value=value)
            else:
                logger.warning(
                    'OTLP unhandled token metric',
                    metric_name=metric_name,
                    value=value,
                    attrs=dp_attrs_dict,
                )

        return tokens_input, tokens_output, cache_read_tokens, cache_creation_tokens
