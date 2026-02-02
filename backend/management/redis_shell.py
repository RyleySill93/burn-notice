"""
Open up a redis-cli tool
Install redis-cli with apt-get install redis-tools
"""

import os
import sys

# ruff: noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import settings

redisshell_command = f'redis-cli -u {settings.REDIS_URL}'
os.system(redisshell_command)
