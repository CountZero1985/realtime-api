#!/usr/bin/env python3
# válasz megszakítása # ha szükséges
# agent_state = VoiceAgentState()  # állapot kezelése
# session id vagy valami saját memória kell. session üzeneteket követni hogy a context hogy áll illetve a betelt sessionoket trunkálni kell
#a handoffok helyett a response.create kell használni egyedi prompttal es toolokkal

import asyncio
from agents import AgentOutputSchema, Runner
from agents.voice import AudioInput, SingleAgentVoiceWorkflow, SingleAgentWorkflowCallbacks, VoicePipeline, VoicePipelineConfig, STTModelSettings, TTSModelSettings
from agents.voice.workflow import VoiceWorkflowHelper
from datetime import datetime
import os
from streaming_voice_workflow import StreamingVoiceWorkflow
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from utility_methods import record_audio, AudioPlayer
import numpy as np
import subprocess
import time
import requests
from agents import WebSearchTool
from agents import Agent
from agentic_tools import websearch_tool, gmail_mcp_server, file_container
from agent_team import assisstant_agent, tools_agent
from tts_prompt import tts_instruct_prompt
from dotenv import load_dotenv

load_dotenv()

class PrintTranscriptionCallback(SingleAgentWorkflowCallbacks):
    def on_run(self, workflow, transcription):
        print(f"[TRANSZKRIPCIÓ] {transcription}")

# Állapotot (state) kezelő osztály, amely minden tool kimenetét eltárolja
class VoiceAgentState:
    def __init__(self):
        self.state = {}

    def set(self, key, value):
        self.state[key] = value

    def get(self, key, default=None):
        return self.state.get(key, default)

    def as_dict(self):
        return dict(self.state)

# Az agent state példánya
voice_agent_state = VoiceAgentState()

async def main():
    print("Asszisztens indítása")
    try:
        workflow = StreamingVoiceWorkflow(agent=assisstant_agent, callbacks=PrintTranscriptionCallback())
        pipeline = VoicePipeline(
            stt_model="gpt-4o-mini-transcribe",
            tts_model="gpt-4o-mini-tts",
            config=VoicePipelineConfig(stt_settings=STTModelSettings(language="hu"),
                                       tts_settings=TTSModelSettings(voice="ash", speed=4.0)), # instructions=tts_instruct_prompt, buffer_size=2400
            workflow=workflow
        )

        while True:
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
                # Felvétel indítása/leállítása
                audio_data = record_audio()
                audio_input = AudioInput(buffer=audio_data)
                print("[LOG] pipeline.run_streamed indítása...")
                # Átadjuk a state-et is a pipeline/agent futtatásához
                result = await pipeline.run(audio_input)
                print("[LOG] pipeline.run_streamed elindult, szöveges válasz streamelése:")
                full_transcript = None
                with AudioPlayer() as player:
                    async for event in result.stream():
                        if event.type == "voice_stream_event_audio":
                            player.add_audio(event.data)
                        elif event.type == "voice_stream_event_lifecycle":
                            print(f"[LOG] Lifecycle event: {event.event}")
                        elif event.type == "voice_stream_event_transcript":
                            # Ha van ilyen event, elmentjük a transcriptet
                            full_transcript = event.data
                    # 1 mp szünet a végére
                    player.add_audio(np.zeros((24000, 1), dtype=np.int16))
                # Hangutasításos kilépés
                last_user = workflow.input_history[-2]["content"] if len(workflow.input_history) >= 2 else ""
                if any(x in last_user.lower() for x in ["kilépés", "exit"]):
                    print("[LOG] Hangutasításos kilépés észlelve.")
                    break
        print("---\nA program véget ért.")
    finally:
        # MCP kapcsolatok lezárása
        await file_container.cleanup()
        await gmail_mcp_server.cleanup()
        
async def cli_main():
    """Szöveges CLI interfész az ügynökkel való kommunikációhoz"""
    print("Asszisztens indítása szöveges módban")

    try:
        input_history = []
        while True:
            print("\n---\nParancsok:\n  <üzenet> - szöveges üzenet küldése\n  h - előzmények\n  q - kilépés\n---")
            user_input = input("Felhasználó: ").strip()
            
            if user_input.lower() == "q":
                print("Kilépés...")
                break
                
            if user_input.lower() == "h":
                print("\n--- Előzmények ---")
                for i, msg in enumerate(input_history):
                    print(f"{i+1}. [{msg['role']}] {msg['content']}")
                print("------------------")
                continue

            # Üzenet hozzáadása a historyhoz
            input_history.append({"role": "user", "content": user_input})

            # Ügynök futtatása

            result = Runner.run_streamed(assisstant_agent, input_history, context=voice_agent_state.as_dict())
            full_response = ""
            
            print("Ügynök: ", end="", flush=True)
            async for chunk in VoiceWorkflowHelper.stream_text_from(result):
                print(chunk, end="", flush=True)
                full_response += chunk
            print()

            # Válasz hozzáadása a historyhoz
            input_history.append({"role": "assistant", "content": full_response})

            # Kilépés szöveges paranccsal
            if user_input.lower() in ["exit", "kilépés"]:
                break

    finally:
        print("A program véget ért.")

if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "agent_zero":
        # CLI mód indítása
        # mcp_proc = subprocess.Popen(["python3", "mcp_server_tools.py"])
        # gmail_proc = subprocess.Popen(["python3", "gmail_mcp_server_tool.py"])
        # file_container_proc = subprocess.Popen(["python3", "file_container_mcp_server.py"])
        print("CLI mód indítása")
        time.sleep(5)
        try:
            asyncio.run(cli_main())
        finally:
            print("CLI mód vége")
            # mcp_proc.terminate()
            # gmail_proc.terminate()
            # file_container_proc.terminate()
    else:
        # Eredeti voice mód
        # mcp_proc = subprocess.Popen(["python3", "mcp_server_tools.py"])
        # gmail_proc = subprocess.Popen(["python3", "gmail_mcp_server_tool.py"])
        # file_container_proc = subprocess.Popen(["python3", "file_container_mcp_server.py"])       
        time.sleep(5)
        try:
            asyncio.run(main())
        finally:
            print("CLI mód vége")
            # mcp_proc.terminate()
            # gmail_proc.terminate()
            # file_container_proc.terminate()