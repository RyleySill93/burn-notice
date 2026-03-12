from src.common.enum import BaseEnum


class RecordType(BaseEnum):
    TOKENS = 'tokens'
    TIME = 'time'


class RecordPeriod(BaseEnum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'


class RecordScope(BaseEnum):
    PERSONAL = 'personal'
    COMPANY = 'company'
