#!/usr/bin/env python3
"""Voice Agent Example - Interactive voice-based agent.

This example demonstrates how to use the AgentFrameworkAPI for voice-based
interactions with an AI assistant in Hungarian.
"""

import asyncio
from agents.voice import VoicePipeline, VoicePipelineConfig, STTModelSettings, TTSModelSettings, AudioInput
from openai_apis.voice.workflow import StreamingVoiceWorkflow
from openai_apis.agents.team import assisstant_agent
from openai_apis.utils.audio_io import record_audio, AudioPlayer
from dotenv import load_dotenv
import numpy as np

load_dotenv()

async def main():
    """Run voice agent in interactive mode."""
    print("Asszisztens indítása (hangalapú mód)")

    # Create workflow
    workflow = StreamingVoiceWorkflow(agent=assisstant_agent)

    # Create voice pipeline
    pipeline = VoicePipeline(
        stt_model="gpt-4o-mini-transcribe",
        tts_model="gpt-4o-mini-tts",
        config=VoicePipelineConfig(
            stt_settings=STTModelSettings(language="hu"),
            tts_settings=TTSModelSettings(voice="ash", speed=4.0)
        ),
        workflow=workflow
    )

    # Main loop
    running = True
    while running:
        print("\n---\nInstrukciók:\n  <Enter> - felvétel indítása/leállítása\n  h - input history kiírása\n  q - kilépés\n  (hangutasítással: 'kilépés' vagy 'exit' is kilép)\n---")

        user_input = input("Válassz műveletet (<Enter>/h/q): ").strip().lower()

        if user_input == "q":
            print("Kilépés...")
            break

        elif user_input == "h":
            print("\n--- Input history ---")
            for i, msg in enumerate(workflow.input_history):
                print(f"{i+1}. [{msg['role']}] {msg['content']}")
            print("---\n")
            continue

        else:
            # Record audio
            print("[INFO] Recording...")
            audio_data = record_audio()
            audio_input = AudioInput(buffer=audio_data)

            # Process through pipeline
            print("[INFO] Processing...")
            result = await pipeline.run(audio_input)

            # Play response
            with AudioPlayer() as player:
                async for event in result.stream():
                    if event.type == "voice_stream_event_audio":
                        player.add_audio(event.data)

                # Add silence padding
                player.add_audio(np.zeros((24000, 1), dtype=np.int16))

            # Check for voice exit command
            if len(workflow.input_history) >= 2:
                last_user = workflow.input_history[-2]["content"]
                if any(x in last_user.lower() for x in ["kilépés", "exit"]):
                    print("[LOG] Hangutasításos kilépés észlelve.")
                    break

    print("---\nA program véget ért.")

if __name__ == "__main__":
    asyncio.run(main())
