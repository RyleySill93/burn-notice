# Claude API pricing per million tokens (as of 2024)
# https://www.anthropic.com/pricing
MODEL_PRICING = {
    # Claude 3.5 Sonnet
    'claude-3-5-sonnet-20241022': {'input': 3.00, 'output': 15.00},
    'claude-3-5-sonnet-20240620': {'input': 3.00, 'output': 15.00},
    'claude-3-5-sonnet': {'input': 3.00, 'output': 15.00},
    # Claude 3.5 Haiku
    'claude-3-5-haiku-20241022': {'input': 0.80, 'output': 4.00},
    'claude-3-5-haiku': {'input': 0.80, 'output': 4.00},
    # Claude 3 Opus
    'claude-3-opus-20240229': {'input': 15.00, 'output': 75.00},
    'claude-3-opus': {'input': 15.00, 'output': 75.00},
    # Claude 3 Sonnet
    'claude-3-sonnet-20240229': {'input': 3.00, 'output': 15.00},
    'claude-3-sonnet': {'input': 3.00, 'output': 15.00},
    # Claude 3 Haiku
    'claude-3-haiku-20240307': {'input': 0.25, 'output': 1.25},
    'claude-3-haiku': {'input': 0.25, 'output': 1.25},
}

# Default pricing for unknown models (use Sonnet pricing as reasonable default)
DEFAULT_PRICING = {'input': 3.00, 'output': 15.00}
