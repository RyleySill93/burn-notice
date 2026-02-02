import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ruff: noqa: E402
from src.app.ai.v0.assistant.management import OpenAIAssistantManager

OpenAIAssistantManager().sync()
