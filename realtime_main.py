
# be kell építeni az interrupting lehetőségét, utánna pedig a tool call-ok mcp serverek, agentstatemanager, stb.
import os
import json
import websocket
import logging
import numpy as np
import sounddevice as sd
import threading
import time
import base64
import queue
from dotenv import load_dotenv
# Állapotot (state) kezelő osztály, amely minden tool kimenetét eltárolja ezt a session update-ben egy f-stringben tudjuk átadni, vagy frissíteni
class RealtimeAgentState:
    def __init__(self):
        self.state = {}

    def set(self, key, value):
        self.state[key] = value

    def get(self, key, default=None):
        return self.state.get(key, default)

    def as_dict(self):
        return dict(self.state)

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17"
headers = [
    "Authorization: Bearer " + OPENAI_API_KEY,
    "OpenAI-Beta: realtime=v1"
]

# Audio settings
SAMPLE_RATE = 24000
CHUNK_DURATION_S = 0.5
CHUNK_SIZE = 2400
CHANNELS = 1

# Push-to-talk state
ptt_active = threading.Event()
ptt_exit = threading.Event()
## EVENTS

# Hungarian transcription config
from events import session_update_event as SESSION_UPDATE

# Speaker output
speaker_stream = None
speaker_queue = queue.Queue()
speaker_thread = None
speaker_running = threading.Event()
session_ready = threading.Event()
session_configured = threading.Event()
session_id = None

# --- DEBUG: Audio chunk számláló és queue log ---
audio_chunk_counter = 0

def clear_speaker_queue():
    while not speaker_queue.empty():
        try:
            speaker_queue.get_nowait()
        except Exception:
            break
    print("[DEBUG] Speaker queue kiürítve.")

def on_open(ws):
    print("Connected to server.")
    # A session config logikát most az on_message callback kezeli
    threading.Thread(target=ptt_listener, daemon=True).start()

def on_message(ws, message):
    global speaker_stream, session_id, speaker_queue, audio_chunk_counter, speaker_thread
    try:
        event = json.loads(message)
    except Exception:
        print("[binary or non-JSON event]")
        return
    print("Received event:", event['type'])
    # Session config: session.created-ből session_id, majd session.update küldése session_id-vel
    if event.get("type") == "conversation.created":
        # Returned when a Session is created. 
        # Emitted automatically when a new connection is established as the first server event. 
        # This event will contain the default Session configuration.
        print("[info] Conversation created.")
    if event.get("type") == "error":
        # Returned when an error occurs, which could be a client problem or a server problem. 
        # Most errors are recoverable and the session will stay open, we recommend to implementors to monitor and log error messages by default.
        print(f"[ERROR] {event.get('message')} teljes event: {event}")

    if event.get("type") == "session.created" and not session_configured.is_set():
        session = event.get("session")
        if session:
            session_id = session.get("id")
            print(f"[info] Session created: {session_id}")
            # session update eküldése
            ws.send(json.dumps(SESSION_UPDATE))
            session_configured.set()
            print(f"[info] Session.update elküldve (magyar beállítva transzkripció beállítva).")
        else:
            print("[ERROR] session_id nem található a session.created eventben!")
        return
    elif event.get("type") == "session.updated" and session_configured.is_set() and not session_ready.is_set():
        print("[info] Session configured, push-to-talk engedélyezve.")
        session_ready.set()
        threading.Thread(target=mic_loop, args=(ws,), daemon=True).start()
        return
    # ...audio, transcription, tool_call, error eventek kezelése...
    if event.get("type") == "input_audio_buffer.cleared":
        # Returned when the input audio buffer is cleared by the client with a input_audio_buffer.clear event.
        pass
    if event.get("type") == "conversation.item.created":
        # Returned when a conversation item is created. There are several scenarios that produce this event:
        # The server is generating a Response, which if successful will produce either one or two Items, which will be of type message (role assistant) or type function_call.
        # The input audio buffer has been committed, either by the client or the server (in server_vad mode). 
        # The server will take the content of the input audio buffer and add it to a new user message Item.
        # The client has sent a conversation.item.create event to add a new Item to the Conversation.
        print(f"[info] Conversation item created:", event)
        pass
    if event.get("type") == "conversation.item.input_audio_transcription.delta":
        pass
    if event.get("type") == "conversation.item.input_audio_transcription.completed":
        print(f"{event.get('transcript')}")
    if event.get("type") == "input_audio_buffer.committed":
        # Returned when an input audio buffer is committed, either by the client or automatically in server VAD mode. 
        # The item_id property is the ID of the user message item that will be created, 
        # thus a conversation.item.created event will also be sent to the client.
        print("[info] Input audio buffer committed, új user message item létrehozva.")
    if event.get("type") == "response.content_part.added":
        pass
    if event.get("type") == "conversation.created":
        # Returned when a conversation is created. Emitted right after session creation.
        print("[info] Conversation created.")
        pass
    if event.get("type") == "response.created":
        # Returned when a new Response is created. 
        # The first event of response creation, where the response is in an initial state of in_progress.
        pass
    if event.get("type") == "response.done":
        # Returned when a Response is done streaming. 
        # Always emitted, no matter the final state. 
        # The Response object included in the response.done event will include all output Items in the Response but will omit the raw audio data.
        # if speaker_stream is not None:
        #     speaker_stream.close()
        #     speaker_stream = None
        print(event)
        pass
    if event.get("type") == "response.output_item.added":
        # Returned when a new Item is created during Response generation.
        pass
    if event.get("type") == "response.output_item.done":
        # Returned when an Item is done streaming. 
        # Also emitted when a Response is interrupted, incomplete, or cancelled.
        pass

    if event.get("type") == "response.audio.delta":
        audio_chunk_counter += 1
        audio_b64 = event["delta"]
        audio_bytes = base64.b64decode(audio_b64)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
        print(f"[DEBUG] response.audio.delta #{audio_chunk_counter}, len={len(audio_np)}, queue size={speaker_queue.qsize()}")
        if audio_np.size > 0:
            speaker_queue.put(audio_np)
            print(f"[DEBUG] Chunk #{audio_chunk_counter} bekerült a queue-ba, új queue size={speaker_queue.qsize()}")
            # Speaker thread indítása, ha nincs élő thread
            if speaker_thread is None or not speaker_thread.is_alive():
                print("[DEBUG] Speaker thread indítása (ha nincs élő thread)")
                start_speaker_thread()
    elif event.get("type") == "response.audio.done":
        print(f"[INFO] Speech audio done. (összesen {audio_chunk_counter} chunk)")
        speaker_queue.put(None)  # Jelzi a threadnek, hogy nincs több chunk, leállhat
        audio_chunk_counter = 0
    elif event.get("type") == "response.audio_transcript.delta":
        print("[AUDIO TRANSCRIPTION DELTA]", event.get("delta"))
    elif event.get("type") == "response.audio_transcript.done":
        print("[AUDIO TRANSCRIPTION COMPLETED]", event.get("transcript"))
    elif event.get("type") == "response.content_part.done":
        pass
    elif event.get("type") == "response.output_item.done":
        pass
    elif event.get("type") == "tool_call":
        print(f"[TOOL CALL] {event.get('tool_name')}({event.get('arguments')})")


def mic_loop(ws):
    """
    Mikrofonból folyamatosan olvasunk, a mintákat egy bufferbe gyűjtjük.
    Ha a buffer eléri az 500ms-nyi mintát (SAMPLE_RATE * 0.5), elküldjük base64-ben egy input_audio_buffer.append eventben.
    Amikor a felvétel leáll, a maradék buffert is elküldjük (ha van), majd küldünk commit és response.create eventet.
    """
    print("[PTT] Nyomj ENTER-t a beszéd indításához/leállításához, 'q' a kilépéshez!")
    session_ready.wait()
    BUFFER_MS = 0.5
    BUFFER_SIZE = int(SAMPLE_RATE * BUFFER_MS)
    READ_SIZE = 1024  # kisebb blokk, hogy minden platformon működjön
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as mic:
        while not ptt_exit.is_set():
            ptt_active.wait()
            if ptt_exit.is_set():
                break
            print("[PTT] Felvétel indult...")
            audio_buffer = np.empty((0,), dtype=np.int16)
            chunk_count = 0
            while ptt_active.is_set() and not ptt_exit.is_set():
                available = mic.read_available
                if available >= READ_SIZE:
                    data, _ = mic.read(READ_SIZE)
                    if data.size > 0:
                        audio_buffer = np.concatenate([audio_buffer, data.flatten()])
                        # Ha elértük az 500ms-nyi mintát, küldjük
                        while len(audio_buffer) >= BUFFER_SIZE:
                            chunk = audio_buffer[:BUFFER_SIZE]
                            audio_buffer = audio_buffer[BUFFER_SIZE:]
                            send_audio_chunk_async(ws, chunk)
                            chunk_count += 1
                    else:
                        print("[DEBUG] Üres audio chunk, nem küldöm!")
                else:
                    time.sleep(0.01)
            # Felvétel leállításakor a maradék buffert is küldjük, ha van
            if len(audio_buffer) > 0:
                send_audio_chunk_async(ws, audio_buffer)
                chunk_count += 1
            print(f"[PTT] Felvétel vége, {chunk_count} audio chunk ment ki. Commit és response.create küldése...")
            if chunk_count > 0:
                # 1. input_audio_buffer.commit event
                input_audio_buffer_commit_event = {
                    "type": "input_audio_buffer.commit"
                }
                ws.send(json.dumps(input_audio_buffer_commit_event))
                # 2. response.create event (testreszabható)
                response_create_event = {
                    "type": "response.create",
                    "response": {
                        "modalities": ["text", "audio"],
                        # "instructions": "Please assist the user.", # ide tehetek be egyedi promtokat?
                        "voice": "sage",
                        "output_audio_format": "pcm16",
                        "tool_choice": "auto",
                        "temperature": 0.8,
                        "max_output_tokens": 1024
                    }
                }
                ws.send(json.dumps(response_create_event))
            else:
                print("[WARN] Nem küldök commit-et, mert nem ment ki legalább 1 audio chunk!")

def send_audio_chunk_async(ws, chunk):
    """
    Egy audio chunkot base64-ben kódolva elküld input_audio_buffer.append eventben.
    """
    import threading
    import base64
    def send():
        audio_b64 = base64.b64encode(chunk.tobytes()).decode("ascii")
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        ws.send(json.dumps(event))
        print(f"[DEBUG] Sent audio chunk, len={len(chunk)}, base64len={len(audio_b64)}")
    threading.Thread(target=send, daemon=True).start()

def ptt_listener():
    while not ptt_exit.is_set():
        key = input()
        if key.strip().lower() == 'q':
            print("[PTT] Kilépés kérve (q)")
            ptt_exit.set()
            break
        if not ptt_active.is_set():
            print("[PTT] PUSH-TO-TALK: ON (Recording from microphone...)") # itt kellene a felvételt elkezdeni küldeni, .append eventekben
            ptt_active.set()
        else:
            print("[PTT] PUSH-TO-TALK: OFF (Stopped recording)") 
            # ekkor kellene a felvételt leállítani és az inpt_audio_buffer.commit és egyben a response.create egészen a response.done eventigindítása
            # lehet hogy darabokban kellene committelni, nem kellene az egész üzenetet egyben, hanem pl két másodpercenként
            # követni kell itemeket, hogy milyen hosszu a cha history, turnkálni kell majd...
            ptt_active.clear()



# --- OUTPUT DEVICE VÁLASZTÓ BLOKK (eltávolítható később) ---
def choose_output_device_interactive():
    import sounddevice as sd
    devices = sd.query_devices()
    print("\n[OUTPUT DEVICE VÁLASZTÓ] Válassz egy audio kimeneti eszközt a listából:")
    for idx, dev in enumerate(devices):
        if dev['max_output_channels'] > 0:
            print(f"  [{idx}] {dev['name']} (max output channels: {dev['max_output_channels']})")
    while True:
        try:
            user_input = input("Add meg a kívánt output device indexét (pl. 10 a 'default'-hoz): ").strip()
            device_idx = int(user_input)
            if 0 <= device_idx < len(devices) and devices[device_idx]['max_output_channels'] > 0:
                print(f"[INFO] Kiválasztott output device: [{device_idx}] {devices[device_idx]['name']}")
                return device_idx
            else:
                print("[WARN] Érvénytelen index vagy nincs output csatorna. Próbáld újra!")
        except Exception as e:
            print(f"[WARN] Hibás input: {e}. Próbáld újra!")

# --- A BLOKK VÉGE ---



def start_speaker_thread():
    global speaker_stream, speaker_queue, speaker_thread, speaker_running, SAMPLE_RATE, global_output_device_idx
    if speaker_thread is not None and speaker_thread.is_alive():
        print("[DEBUG] Speaker thread már fut!")
        return  # Már fut
    output_device = global_output_device_idx if 'global_output_device_idx' in globals() else None
    chosen_samplerate = SAMPLE_RATE
    def speaker_worker():
        global speaker_stream, speaker_queue, speaker_running, speaker_thread
        played_chunks = 0
        try:
            speaker_stream = sd.OutputStream(samplerate=chosen_samplerate, channels=1, dtype=np.int16, device=output_device)
            speaker_stream.start()
            speaker_running.set()
            print(f"[AUDIO] Speaker thread started. Output device: {output_device}, samplerate: {chosen_samplerate}")
            empty_count = 0
            while True:
                try:
                    chunk = speaker_queue.get(timeout=0.5)
                    if chunk is None:
                        print(f"[AUDIO] Speaker thread vége, összesen lejátszott chunk: {played_chunks}")
                        break
                    if not isinstance(chunk, np.ndarray) or chunk.dtype != np.int16:
                        print("[ERROR] Hibás chunk formátum!", type(chunk), getattr(chunk, 'dtype', None))
                        continue
                    if chunk.size == 0:
                        print("[WARN] Üres chunk, nem játszom le!")
                        continue
                    speaker_stream.write(chunk)
                    played_chunks += 1
                    print(f"[AUDIO] Played chunk #{played_chunks}, len={len(chunk)}, queue size={speaker_queue.qsize()}")
                    empty_count = 0  # reset if we got a chunk
                except queue.Empty:
                    empty_count += 1
                    # Ha 3 egymás utáni üres lekérés volt (1.5s), akkor feltételezzük, hogy vége
                    if empty_count >= 3:
                        print(f"[AUDIO] Speaker thread automatikusan leáll (queue üres, nincs több chunk). Lejátszott: {played_chunks}")
                        break
                    continue
        except Exception as e:
            print(f"[ERROR] Speaker thread kivétel: {e}")
        finally:
            if speaker_stream is not None:
                try:
                    speaker_stream.stop()
                    speaker_stream.close()
                except Exception as e:
                    print(f"[WARN] Speaker stream zárás kivétel: {e}")
                speaker_stream = None
            print("[AUDIO] Speaker thread stopped.")
            speaker_thread = None
    speaker_running.set()
    speaker_thread = threading.Thread(target=speaker_worker, daemon=True)
    speaker_thread.start()

def stop_speaker_thread():
    global speaker_queue, speaker_running, speaker_thread
    speaker_running.clear()
    speaker_queue.put(None)
    if speaker_thread is not None:
        speaker_thread.join(timeout=2)
        print("[DEBUG] Speaker thread join-olva.")
        speaker_thread = None
    log_threads()

def log_threads():
    print("[DEBUG] Aktív thread-ek:")
    for t in threading.enumerate():
        print(f"  - {t.name} (daemon={t.daemon})")

def test_speaker_output():
    print("[TEST] Speaker output teszt: 1 másodperc szinusz hang lejátszása...")
    duration = 1.0  # másodperc
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    freq = 440  # Hz (A hang)
    audio = (0.2 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with sd.OutputStream(samplerate=SAMPLE_RATE, channels=1, dtype=np.int16) as stream:
        stream.write(audio)
    print("[TEST] Lejátszás kész.")
    
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_speaker_output()
    # --- OUTPUT DEVICE VÁLASZTÓ BLOKK HASZNÁLATA ---
    output_device_idx = choose_output_device_interactive()
    # Globális változóként elérhetővé tesszük
    global_output_device_idx = output_device_idx
    # --- BLOKK VÉGE ---
    ws = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
    )
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        print("[INFO] Kilépés kérve, szálak leállítása...")
        stop_speaker_thread()
        log_threads()
        print("[INFO] Kilépés kész.")
