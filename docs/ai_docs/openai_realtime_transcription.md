# OpenAI Realtime API - Transcription Session & Events

**Documentation Version:** Based on gpt-4o-mini-realtime-preview-2024-12-17
**API Version:** realtime=v1

## Overview

The OpenAI Realtime API provides automatic speech transcription in both directions:
1. **Input Audio Transcription:** User speech → Text (via Whisper)
2. **Output Audio Transcription:** Assistant speech → Text (automatic)

This document focuses on transcription configuration, session management, and related events.

---

## Input Audio Transcription Configuration

### Session Update for Transcription

Input audio transcription is configured via the `session.update` event:

```python
session_update_event = {
    "type": "session.update",
    "session": {
        "input_audio_transcription": {
            "model": "whisper-1",
            "language": "hu"  # ISO 639-1 language code
        },
        # ... other session settings
    }
}
```

### Configuration Parameters

#### `model`
- **Type:** String
- **Options:** `"whisper-1"` (currently the only option)
- **Purpose:** Specifies the Whisper model for transcription

#### `language`
- **Type:** String (ISO 639-1 code)
- **Options:** Any language supported by Whisper
  - `"hu"` - Hungarian (Magyar)
  - `"en"` - English
  - `"es"` - Spanish
  - `"fr"` - French
  - `"de"` - German
  - `"it"` - Italian
  - `"pt"` - Portuguese
  - `"ru"` - Russian
  - `"ja"` - Japanese
  - `"zh"` - Chinese
  - And 90+ more languages
- **Purpose:** Improves transcription accuracy by specifying expected language
- **Note:** Optional but highly recommended for non-English languages

### Example: Hungarian Configuration

```json
{
  "type": "session.update",
  "session": {
    "modalities": ["text", "audio"],
    "instructions": "Te egy magyar nyelvű asszisztens vagy.",
    "voice": "sage",
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "input_audio_transcription": {
      "model": "whisper-1",
      "language": "hu"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 500
    }
  }
}
```

---

## Input Audio Transcription Events

### `conversation.item.input_audio_transcription.delta`

**When:** During transcription of user's audio input
**Purpose:** Streams partial transcription results as they become available
**Direction:** Server → Client

**Event Structure:**
```json
{
  "type": "conversation.item.input_audio_transcription.delta",
  "item_id": "msg_abc123",
  "content_index": 0,
  "delta": "Hel"
}
```

**Fields:**
- `item_id` - ID of the conversation item being transcribed
- `content_index` - Index of the content part
- `delta` - Partial transcription text chunk

**Implementation Example:**
```python
if event.get("type") == "conversation.item.input_audio_transcription.delta":
    delta_text = event.get("delta", "")
    # Append to running transcription buffer for display
    current_transcription += delta_text
    print(f"[Transcribing...] {current_transcription}", end='\r')
```

**Use Case:** Display live transcription to user as they speak

---

### `conversation.item.input_audio_transcription.completed`

**When:** User's audio transcription is complete
**Purpose:** Provides final, complete transcription of user's speech
**Direction:** Server → Client

**Event Structure:**
```json
{
  "type": "conversation.item.input_audio_transcription.completed",
  "item_id": "msg_abc123",
  "content_index": 0,
  "transcript": "Helló, hogy vagy?"
}
```

**Fields:**
- `item_id` - ID of the conversation item
- `content_index` - Index of the content part
- `transcript` - Complete final transcription

**Implementation Example:**
```python
if event.get("type") == "conversation.item.input_audio_transcription.completed":
    transcript = event.get("transcript", "")
    print(f"\n[User said]: {transcript}")
    # Log to conversation history
    conversation_history.append({
        "role": "user",
        "content": transcript,
        "timestamp": time.time()
    })
```

**Use Case:**
- Display final transcription to user
- Log user input for conversation history
- Trigger follow-up actions based on transcribed text

---

### `conversation.item.input_audio_transcription.failed`

**When:** Transcription fails for any reason
**Purpose:** Indicates that transcription could not be completed
**Direction:** Server → Client

**Event Structure:**
```json
{
  "type": "conversation.item.input_audio_transcription.failed",
  "item_id": "msg_abc123",
  "content_index": 0,
  "error": {
    "type": "transcription_error",
    "code": "...",
    "message": "..."
  }
}
```

**Implementation Example:**
```python
if event.get("type") == "conversation.item.input_audio_transcription.failed":
    error = event.get("error", {})
    print(f"[Transcription Error]: {error.get('message')}")
    # Fallback: proceed without transcript or retry
```

---

## Output Audio Transcription Events

Output audio transcription happens automatically when the assistant responds with audio. No configuration needed beyond setting `modalities: ["audio"]` or `["text", "audio"]`.

### `response.audio_transcript.delta`

**When:** During assistant's audio response generation
**Purpose:** Streams partial transcription of what the assistant is saying
**Direction:** Server → Client

**Event Structure:**
```json
{
  "type": "response.audio_transcript.delta",
  "response_id": "resp_abc123",
  "item_id": "msg_def456",
  "output_index": 0,
  "content_index": 0,
  "delta": "Rendben, "
}
```

**Fields:**
- `response_id` - ID of the response
- `item_id` - ID of the output item
- `output_index` - Index in response outputs array
- `content_index` - Index in item's content array
- `delta` - Partial transcription text

**Implementation Example:**
```python
if event.get("type") == "response.audio_transcript.delta":
    delta = event.get("delta", "")
    assistant_transcript_buffer += delta
    print(f"[Assistant]: {assistant_transcript_buffer}", end='\r')
```

**Use Case:**
- Display live captions of assistant speech
- Accessibility feature for hearing-impaired users
- Real-time UI feedback

---

### `response.audio_transcript.done`

**When:** Assistant's audio transcription is complete
**Purpose:** Provides complete transcription of assistant's spoken response
**Direction:** Server → Client

**Event Structure:**
```json
{
  "type": "response.audio_transcript.done",
  "response_id": "resp_abc123",
  "item_id": "msg_def456",
  "output_index": 0,
  "content_index": 0,
  "transcript": "Rendben, segítek neked ebben a kérdésben."
}
```

**Fields:**
- `response_id` - ID of the response
- `item_id` - ID of the output item
- `output_index` - Index in response outputs array
- `content_index` - Index in item's content array
- `transcript` - Complete final transcription

**Implementation Example:**
```python
if event.get("type") == "response.audio_transcript.done":
    transcript = event.get("transcript", "")
    print(f"\n[Assistant said]: {transcript}")
    conversation_history.append({
        "role": "assistant",
        "content": transcript,
        "timestamp": time.time()
    })
```

**Use Case:**
- Log assistant responses to conversation history
- Display final assistant message
- Save conversation transcript to file/database

---

## Transcription Session Workflow

### Complete Push-to-Talk Transcription Flow

```
1. [Client] Connect to WebSocket
   ↓
2. [Server] session.created
   ↓
3. [Client] session.update (with input_audio_transcription config)
   ↓
4. [Server] session.updated
   ↓
5. [Client] Multiple input_audio_buffer.append events (user speaking)
   ↓
6. [Client] input_audio_buffer.commit
   ↓
7. [Server] input_audio_buffer.committed
   ↓
8. [Server] conversation.item.created (user message with audio)
   ↓
9. [Server] conversation.item.input_audio_transcription.delta (streaming)
   ↓
10. [Server] conversation.item.input_audio_transcription.completed
    ↓
11. [Client] response.create
    ↓
12. [Server] response.created
    ↓
13. [Server] response.audio.delta (streaming audio)
    [Server] response.audio_transcript.delta (streaming transcript)
    ↓
14. [Server] response.audio.done
    ↓
15. [Server] response.audio_transcript.done
    ↓
16. [Server] response.done
```

### Server VAD Transcription Flow

With server-side Voice Activity Detection (`turn_detection: { type: "server_vad" }`):

```
1-4. Same as Push-to-Talk
   ↓
5. [Client] Continuously send input_audio_buffer.append
   ↓
6. [Server] input_audio_buffer.speech_started (auto-detected)
   ↓
7. [Server] input_audio_buffer.speech_stopped (auto-detected)
   ↓
8. [Server] Auto-commit, conversation.item.created
   ↓
9-10. Transcription events (same as Push-to-Talk)
   ↓
11. [Server] Auto-trigger response generation
   ↓
12-16. Same as Push-to-Talk
```

---

## Transcription Accuracy Best Practices

### Language Configuration
**Always specify the language** for best results:
```python
"input_audio_transcription": {
    "model": "whisper-1",
    "language": "hu"  # Specify expected language
}
```

### Audio Quality
- **Sample Rate:** Use 24000 Hz (API requirement)
- **Format:** PCM16 mono (single channel)
- **Noise:** Minimize background noise
- **Distance:** Keep microphone at consistent distance
- **Clipping:** Avoid audio clipping (too loud)

### Chunk Size
- **Recommendation:** 500ms chunks (12000 samples at 24kHz)
- **Too Small:** Increased overhead, potential processing delays
- **Too Large:** Increased latency, larger memory buffers

### VAD Configuration (Server VAD Mode)
```python
"turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,          # Lower = more sensitive
    "prefix_padding_ms": 300,   # Include 300ms before speech
    "silence_duration_ms": 500  # 500ms silence = end of turn
}
```

**Tuning Parameters:**
- `threshold`: 0.3-0.7 depending on environment noise
- `prefix_padding_ms`: 200-500ms to capture beginning of utterance
- `silence_duration_ms`: 300-1000ms depending on speaking style

---

## Implementation Patterns

### Transcription State Manager

```python
class TranscriptionManager:
    def __init__(self):
        self.user_transcript_buffer = ""
        self.assistant_transcript_buffer = ""
        self.conversation_history = []

    def handle_user_transcript_delta(self, event):
        delta = event.get("delta", "")
        self.user_transcript_buffer += delta
        # Display live update
        print(f"[User]: {self.user_transcript_buffer}", end='\r')

    def handle_user_transcript_completed(self, event):
        transcript = event.get("transcript", "")
        print(f"\n[User]: {transcript}")
        self.conversation_history.append({
            "role": "user",
            "content": transcript,
            "item_id": event.get("item_id")
        })
        self.user_transcript_buffer = ""

    def handle_assistant_transcript_delta(self, event):
        delta = event.get("delta", "")
        self.assistant_transcript_buffer += delta
        print(f"[Assistant]: {self.assistant_transcript_buffer}", end='\r')

    def handle_assistant_transcript_completed(self, event):
        transcript = event.get("transcript", "")
        print(f"\n[Assistant]: {transcript}")
        self.conversation_history.append({
            "role": "assistant",
            "content": transcript,
            "item_id": event.get("item_id")
        })
        self.assistant_transcript_buffer = ""

    def save_conversation(self, filepath):
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f,
                     ensure_ascii=False, indent=2)
```

### Event Handler Integration

```python
def on_message(ws, message):
    event = json.loads(message)
    event_type = event.get("type")

    transcription_mgr = TranscriptionManager()

    # User transcription
    if event_type == "conversation.item.input_audio_transcription.delta":
        transcription_mgr.handle_user_transcript_delta(event)

    elif event_type == "conversation.item.input_audio_transcription.completed":
        transcription_mgr.handle_user_transcript_completed(event)

    elif event_type == "conversation.item.input_audio_transcription.failed":
        print(f"[Error] Transcription failed: {event.get('error')}")

    # Assistant transcription
    elif event_type == "response.audio_transcript.delta":
        transcription_mgr.handle_assistant_transcript_delta(event)

    elif event_type == "response.audio_transcript.done":
        transcription_mgr.handle_assistant_transcript_completed(event)
```

---

## Stateless Transcription-Only Mode

For applications that only need transcription (no response generation):

### Configuration
```python
session_config = {
    "type": "session.update",
    "session": {
        "modalities": ["text"],  # Text only, no audio response
        "input_audio_transcription": {
            "model": "whisper-1",
            "language": "hu"
        },
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500
        }
    }
}
```

### Workflow
```
1. Connect → session.created
2. Configure → session.update
3. Stream audio → input_audio_buffer.append (continuous)
4. Auto-detect speech → speech_started
5. Auto-detect end → speech_stopped, auto-commit
6. Receive transcript → conversation.item.input_audio_transcription.completed
7. No response generation (text-only mode)
8. Repeat steps 3-6 for continuous transcription
```

### Use Cases
- Voice-to-text dictation
- Meeting transcription
- Live captioning
- Speech analytics

---

## Transcription Limitations & Considerations

### Latency
- **Streaming Latency:** ~100-500ms for delta events
- **Completion Latency:** ~200-1000ms after audio ends
- **Factors:** Audio quality, network, server load

### Language Detection
- Whisper can auto-detect language if not specified
- **Recommendation:** Always specify language for better accuracy and lower latency

### Multi-Language Support
- One language per session
- To change language: send new `session.update`
- For multi-language conversations: consider separate sessions

### Accuracy
- **Best:** Clear speech, low noise, specified language
- **Challenges:** Accents, technical terms, background noise
- **Tip:** Include domain-specific context in assistant instructions

### Conversation History Management
Transcripts accumulate in conversation context:
- Monitor context length (token limits)
- Implement conversation truncation
- Use `conversation.item.delete` to remove old items
- Consider summarization for long conversations

---

## Error Handling

### Transcription Failure Recovery

```python
def handle_transcription_error(event):
    error = event.get("error", {})
    error_type = error.get("type")
    error_code = error.get("code")

    if error_code == "audio_too_short":
        print("[Info] Audio too short for transcription")
        # Continue without transcript

    elif error_code == "audio_unintelligible":
        print("[Info] Audio could not be transcribed")
        # Ask user to repeat

    else:
        print(f"[Error] Transcription failed: {error.get('message')}")
        # Log error, may need to restart session
```

---

## Testing Transcription

### Test Script Example

```python
import websocket
import json
import base64
import numpy as np

def test_transcription():
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17"
    headers = [
        f"Authorization: Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta: realtime=v1"
    ]

    def on_message(ws, message):
        event = json.loads(message)
        event_type = event.get("type")

        if event_type == "session.created":
            # Configure for Hungarian transcription
            ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "input_audio_transcription": {
                        "model": "whisper-1",
                        "language": "hu"
                    }
                }
            }))

        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript")
            print(f"✓ Transcription: {transcript}")

    ws = websocket.WebSocketApp(url, header=headers, on_message=on_message)
    ws.run_forever()

if __name__ == "__main__":
    test_transcription()
```

---

## References

- **Main Realtime API Guide:** [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- **Server Events:** [Server Events Reference](https://platform.openai.com/docs/api-reference/realtime-server-events)
- **Client Events:** [Client Events Reference](https://platform.openai.com/docs/api-reference/realtime-client-events)
- **Whisper Documentation:** [Whisper Model](https://platform.openai.com/docs/guides/speech-to-text)
- **Language Codes:** [ISO 639-1 Codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-25
**Model:** gpt-4o-mini-realtime-preview-2024-12-17
