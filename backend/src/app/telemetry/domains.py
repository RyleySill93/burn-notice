from src.common.domain import BaseDomain


class OTLPResponse(BaseDomain):
    """Standard OTLP response."""

    partialSuccess: dict | None = None
