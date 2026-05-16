"""Agent system prompts and instructions."""

from examples.agents.prompts.voice_assistant import shodan_prompt
from examples.agents.prompts.generic_assistant import generic_assistant_prompt
from examples.agents.prompts.tts import tts_instruct_prompt, tts_robot_prompt, tts_natural_prompt, tts_news_prompt

# Backward compatibility
assisstant_prompt = shodan_prompt

__all__ = [
    "shodan_prompt",
    "generic_assistant_prompt",
    "assisstant_prompt",
    "tts_instruct_prompt",
    "tts_robot_prompt",
    "tts_natural_prompt",
    "tts_news_prompt",
]
