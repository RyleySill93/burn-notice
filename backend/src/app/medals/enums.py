from src.common.enum import BaseEnum


class MedalCategory(BaseEnum):
    RANKING = 'ranking'
    MILESTONE = 'milestone'
    ACTION = 'action'


class MedalType(BaseEnum):
    # Ranking medals
    GOLD = 'gold'
    SILVER = 'silver'
    BRONZE = 'bronze'
    # Milestone medals - tokens
    TOKEN_10M = 'token_10m'
    TOKEN_100M = 'token_100m'
    TOKEN_1B = 'token_1b'
    # Milestone medals - time
    TIME_100H = 'time_100h'
    TIME_1000H = 'time_1000h'
    TIME_10000H = 'time_10000h'
    # Action medals
    PURPLE_HEART = 'purple_heart'


class MetricType(BaseEnum):
    TOKENS = 'tokens'
    TIME = 'time'


class PeriodType(BaseEnum):
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
