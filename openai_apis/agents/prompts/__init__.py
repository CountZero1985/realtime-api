"""Agent system prompts and instructions."""

from openai_apis.agents.prompts.voice_assistant import assisstant_prompt
from openai_apis.agents.prompts.tts import tts_instruct_prompt

__all__ = ["assisstant_prompt", "tts_instruct_prompt"]
