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
    TOKEN_1M = 'token_1m'        # Spark
    TOKEN_10M = 'token_10m'      # Ember
    TOKEN_50M = 'token_50m'      # Blaze
    TOKEN_100M = 'token_100m'    # Inferno
    TOKEN_250M = 'token_250m'    # Firestorm
    TOKEN_500M = 'token_500m'    # Supernova
    TOKEN_1B = 'token_1b'        # Solar Flare
    TOKEN_10B = 'token_10b'      # Big Bang
    # Milestone medals - time
    TIME_10H = 'time_10h'        # Clocked In
    TIME_100H = 'time_100h'      # Grinder
    TIME_500H = 'time_500h'      # Marathoner
    TIME_1000H = 'time_1000h'    # Ironman
    TIME_2500H = 'time_2500h'    # Centurion
    TIME_5000H = 'time_5000h'    # Titan
    TIME_10000H = 'time_10000h'  # Eternal
    TIME_25000H = 'time_25000h'  # Transcendent
    # Action medals
    PURPLE_HEART = 'purple_heart'


class MetricType(BaseEnum):
    TOKENS = 'tokens'
    TIME = 'time'


class PeriodType(BaseEnum):
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
