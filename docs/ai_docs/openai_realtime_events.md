# OpenAI Realtime API Events Reference

**Documentation Version:** Based on gpt-4o-mini-realtime-preview-2024-12-17
**API Version:** realtime=v1

## Overview

The OpenAI Realtime API uses a bidirectional WebSocket protocol with event-based communication. Events flow in both directions:
- **Client Events:** Sent from your application to the OpenAI server
- **Server Events:** Sent from the OpenAI server to your application

## WebSocket Connection

**Endpoint:**
```
wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17
```

**Headers:**
```
Authorization: Bearer YOUR_OPENAI_API_KEY
OpenAI-Beta: realtime=v1
```

## Event Structure

All events are JSON objects with a `type` field:
```json
{
  "type": "event.name",
  ...additional_fields
}
```

---

## Server Events (Server → Client)

### Session Management

#### `session.created`
**When:** Automatically emitted when a new WebSocket connection is established (first server event)
**Purpose:** Contains the session ID and default session configuration
**Fields:**
- `session.id` - Unique session identifier
- `session` object - Default session configuration

**Example:**
```json
{
  "type": "session.created",
  "session": {
    "id": "sess_abc123",
    ...configuration
  }
}
```

**Implementation Note:** Extract `session.id` from this event for tracking purposes.

---

#### `session.updated`
**When:** Emitted after the client sends a `session.update` event
**Purpose:** Confirms that session configuration has been updated
**Fields:**
- `session` object - Updated session configuration

**Example:**
```json
{
  "type": "session.updated",
  "session": {
    "modalities": ["text", "audio"],
    "instructions": "...",
    ...
  }
}
```

---

### Conversation Management

#### `conversation.created`
**When:** Emitted automatically right after session creation
**Purpose:** Indicates that a conversation object has been created

**Example:**
```json
{
  "type": "conversation.created"
}
```

---

#### `conversation.item.created`
**When:** Multiple scenarios:
1. Server is generating a Response (creates message or function_call items)
2. Input audio buffer has been committed (creates user message item)
3. Client sent a `conversation.item.create` event

**Purpose:** Notifies that a new conversation item has been added
**Fields:**
- `item` object - The created conversation item
- `item.id` - Unique item identifier
- `item.type` - Type: "message" or "function_call"
- `item.role` - For messages: "user", "assistant", or "system"

**Example:**
```json
{
  "type": "conversation.item.created",
  "item": {
    "id": "msg_abc123",
    "type": "message",
    "role": "user",
    ...
  }
}
```

---

### Input Audio Buffer Events

#### `input_audio_buffer.committed`
**When:** Input audio buffer is committed (by client or automatically in server VAD mode)
**Purpose:** Indicates that audio buffer content will be used to create a user message item
**Fields:**
- `item_id` - ID of the user message item that will be created

**Example:**
```json
{
  "type": "input_audio_buffer.committed",
  "item_id": "msg_abc123"
}
```

**Note:** A `conversation.item.created` event will also be sent after this.

---

#### `input_audio_buffer.cleared`
**When:** Client sends an `input_audio_buffer.clear` event
**Purpose:** Confirms that the input audio buffer has been cleared

**Example:**
```json
{
  "type": "input_audio_buffer.cleared"
}
```

---

#### `input_audio_buffer.speech_started`
**When:** Server VAD detects speech in the audio buffer
**Purpose:** Indicates that the user has started speaking (only in server VAD mode)

---

#### `input_audio_buffer.speech_stopped`
**When:** Server VAD detects end of speech
**Purpose:** Indicates that the user has stopped speaking (only in server VAD mode)

---

### Transcription Events

#### `conversation.item.input_audio_transcription.delta`
**When:** During transcription of user audio input
**Purpose:** Streams partial transcription results
**Fields:**
- `delta` - Partial transcription text

---

#### `conversation.item.input_audio_transcription.completed`
**When:** User audio transcription is complete
**Purpose:** Provides the final transcription of user audio
**Fields:**
- `transcript` - Complete transcription text
- `item_id` - Associated conversation item ID

**Example:**
```json
{
  "type": "conversation.item.input_audio_transcription.completed",
  "item_id": "msg_abc123",
  "transcript": "Hello, how are you?"
}
```

**Implementation:** Display this transcript to show what the user said.

---

#### `conversation.item.input_audio_transcription.failed`
**When:** Transcription fails
**Purpose:** Indicates transcription error

---

### Response Lifecycle Events

#### `response.created`
**When:** New Response generation starts
**Purpose:** First event of response creation, response is in "in_progress" state
**Fields:**
- `response` object - Response configuration
- `response.id` - Unique response identifier

**Example:**
```json
{
  "type": "response.created",
  "response": {
    "id": "resp_abc123",
    "status": "in_progress",
    ...
  }
}
```

---

#### `response.done`
**When:** Response streaming is complete
**Purpose:** Always emitted regardless of final state (completed, cancelled, failed)
**Fields:**
- `response` object - Complete response object (without raw audio data)
- `response.status` - Final status: "completed", "cancelled", "failed", or "incomplete"

**Example:**
```json
{
  "type": "response.done",
  "response": {
    "id": "resp_abc123",
    "status": "completed",
    "output": [...]
  }
}
```

**Note:** The response object includes all output items but omits raw audio data.

---

### Response Output Events

#### `response.output_item.added`
**When:** New item is created during Response generation
**Purpose:** Indicates a new output item (message or function call) is being added

---

#### `response.output_item.done`
**When:** Output item streaming is complete
**Purpose:** Emitted when an item is done, even if Response is interrupted/incomplete/cancelled

---

#### `response.content_part.added`
**When:** New content part is added to an output item
**Purpose:** Indicates new content segment (text, audio, etc.)

---

#### `response.content_part.done`
**When:** Content part streaming is complete
**Purpose:** Indicates that a content part is fully transmitted

---

### Audio Response Events

#### `response.audio.delta`
**When:** During audio response streaming
**Purpose:** Streams audio chunks in real-time
**Fields:**
- `delta` - Base64-encoded PCM16 audio data chunk
- `response_id` - Associated response ID
- `item_id` - Associated output item ID
- `output_index` - Index in the response output array
- `content_index` - Index in the item's content array

**Example:**
```json
{
  "type": "response.audio.delta",
  "response_id": "resp_abc123",
  "item_id": "msg_abc456",
  "output_index": 0,
  "content_index": 0,
  "delta": "base64_encoded_audio_data..."
}
```

**Implementation:**
```python
audio_b64 = event["delta"]
audio_bytes = base64.b64decode(audio_b64)
audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
# Play audio_np through speaker
```

---

#### `response.audio.done`
**When:** Audio streaming is complete
**Purpose:** Indicates all audio chunks have been sent
**Fields:**
- `response_id` - Associated response ID
- `item_id` - Associated output item ID
- `output_index` - Index in the response output array
- `content_index` - Index in the item's content array

**Example:**
```json
{
  "type": "response.audio.done",
  "response_id": "resp_abc123",
  "item_id": "msg_abc456",
  "output_index": 0,
  "content_index": 0
}
```

**Implementation Note:** Use this to signal end of audio playback (e.g., put `None` in speaker queue).

---

### Audio Transcript Events

#### `response.audio_transcript.delta`
**When:** During transcription of assistant audio output
**Purpose:** Streams partial transcription of what the assistant is saying
**Fields:**
- `delta` - Partial transcription text

**Example:**
```json
{
  "type": "response.audio_transcript.delta",
  "delta": "I can help you with"
}
```

---

#### `response.audio_transcript.done`
**When:** Audio transcription is complete
**Purpose:** Provides complete transcription of assistant audio
**Fields:**
- `transcript` - Complete transcription text

**Example:**
```json
{
  "type": "response.audio_transcript.done",
  "transcript": "I can help you with that question."
}
```

**Implementation:** Display this as the assistant's spoken message.

---

### Text Response Events

#### `response.text.delta`
**When:** During text response streaming (text modality)
**Purpose:** Streams partial text responses
**Fields:**
- `delta` - Partial text content

---

#### `response.text.done`
**When:** Text response is complete
**Purpose:** Indicates all text has been sent
**Fields:**
- `text` - Complete text content

---

### Function Call Events

#### `response.function_call_arguments.delta`
**When:** During function call argument streaming
**Purpose:** Streams partial function call arguments

---

#### `response.function_call_arguments.done`
**When:** Function call arguments are complete
**Purpose:** Provides complete function call arguments

---

### System Events

#### `error`
**When:** An error occurs (client or server problem)
**Purpose:** Communicates error information
**Fields:**
- `error.type` - Error type
- `error.code` - Error code
- `error.message` - Human-readable error message
- `error.param` - Related parameter (if applicable)

**Example:**
```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "code": "invalid_value",
    "message": "Invalid audio format",
    "param": "audio"
  }
}
```

**Note:** Most errors are recoverable; session stays open. Implement error monitoring and logging.

---

#### `rate_limits.updated`
**When:** Rate limit information changes
**Purpose:** Provides current rate limit status
**Fields:**
- Rate limit information for the session

---

## Client Events (Client → Server)

### Session Management

#### `session.update`
**Purpose:** Update session configuration
**When to send:** After receiving `session.created`
**Fields:**
- `session` object with configuration parameters

**Example:**
```python
session_update_event = {
    "type": "session.update",
    "session": {
        "modalities": ["text", "audio"],
        "instructions": "You are a helpful Hungarian assistant.",
        "voice": "sage",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": {
            "model": "whisper-1",
            "language": "hu"  # Hungarian
        },
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500
        },
        "temperature": 0.8,
        "max_response_output_tokens": 4096
    }
}
```

**Configuration Options:**
- `modalities`: Array of "text" and/or "audio"
- `instructions`: System instructions for the assistant
- `voice`: TTS voice ("alloy", "echo", "shimmer", "sage", "ash")
- `input_audio_format`: "pcm16" or "g711_ulaw" or "g711_alaw"
- `output_audio_format`: "pcm16" or "g711_ulaw" or "g711_alaw"
- `input_audio_transcription`: Transcription settings
  - `model`: "whisper-1"
  - `language`: ISO 639-1 code (e.g., "hu", "en")
- `turn_detection`: VAD configuration or `null` for manual control
  - `type`: "server_vad"
  - `threshold`: 0.0 to 1.0
  - `prefix_padding_ms`: milliseconds
  - `silence_duration_ms`: milliseconds
- `temperature`: 0.0 to 2.0
- `max_response_output_tokens`: integer or "inf"

---

### Audio Input Events

#### `input_audio_buffer.append`
**Purpose:** Add audio data to the input buffer
**When to send:** Continuously during recording (recommended: 500ms chunks)
**Fields:**
- `audio` - Base64-encoded PCM16 audio data

**Example:**
```python
audio_chunk = np.array([...], dtype=np.int16)  # 500ms of audio
audio_b64 = base64.b64encode(audio_chunk.tobytes()).decode("ascii")

event = {
    "type": "input_audio_buffer.append",
    "audio": audio_b64
}
ws.send(json.dumps(event))
```

**Best Practice:** Send chunks of ~500ms (12000 samples at 24kHz) for smooth streaming.

---

#### `input_audio_buffer.commit`
**Purpose:** Commit the audio buffer and create a user message
**When to send:** After recording stops (manual VAD mode)

**Example:**
```json
{
  "type": "input_audio_buffer.commit"
}
```

**Note:** Server will create a user message item with the buffered audio and emit `input_audio_buffer.committed` event.

---

#### `input_audio_buffer.clear`
**Purpose:** Clear the audio buffer without creating a message
**When to send:** To discard current audio (e.g., user cancelled)

**Example:**
```json
{
  "type": "input_audio_buffer.clear"
}
```

---

### Response Control Events

#### `response.create`
**Purpose:** Request a new response from the assistant
**When to send:** After committing audio buffer or adding conversation items
**Fields:**
- `response` object (optional) - Response configuration

**Example:**
```json
{
  "type": "response.create",
  "response": {
    "modalities": ["text", "audio"],
    "instructions": "Please respond in Hungarian.",
    "voice": "sage",
    "output_audio_format": "pcm16",
    "temperature": 0.8,
    "max_output_tokens": 1024,
    "tool_choice": "auto"
  }
}
```

**Response Configuration:**
- `modalities`: Override session modalities
- `instructions`: Additional instructions for this response
- `voice`: Override session voice
- `output_audio_format`: Override session format
- `temperature`: Override session temperature
- `max_output_tokens`: Token limit for this response
- `tool_choice`: "auto", "none", "required", or specific tool

---

#### `response.cancel`
**Purpose:** Cancel an in-progress response
**When to send:** To interrupt the assistant (e.g., user starts speaking)
**Fields:**
- `response_id` (optional) - Specific response to cancel

**Example:**
```json
{
  "type": "response.cancel"
}
```

**Note:** Causes `response.done` with status "cancelled".

---

### Conversation Item Events

#### `conversation.item.create`
**Purpose:** Add a new item to the conversation
**When to send:** To manually add messages or function results
**Fields:**
- `item` object - The conversation item to add

**Example (adding user message):**
```json
{
  "type": "conversation.item.create",
  "item": {
    "type": "message",
    "role": "user",
    "content": [
      {
        "type": "input_text",
        "text": "What is the weather?"
      }
    ]
  }
}
```

---

#### `conversation.item.truncate`
**Purpose:** Truncate a conversation item
**When to send:** To shorten conversation history

---

#### `conversation.item.delete`
**Purpose:** Remove an item from the conversation
**When to send:** To manage conversation history
**Fields:**
- `item_id` - ID of item to delete

---

## Event Flow Examples

### Push-to-Talk Workflow (Manual VAD)

1. **Connection:**
   - Client connects to WebSocket
   - Server sends `session.created`

2. **Configuration:**
   - Client sends `session.update` (with `turn_detection: null`)
   - Server sends `session.updated`

3. **User Speaks:**
   - Client sends multiple `input_audio_buffer.append` events
   - Client sends `input_audio_buffer.commit`
   - Server sends `input_audio_buffer.committed`
   - Server sends `conversation.item.created` (user message)
   - Server sends `conversation.item.input_audio_transcription.completed`

4. **Request Response:**
   - Client sends `response.create`
   - Server sends `response.created`

5. **Assistant Responds:**
   - Server sends multiple `response.audio.delta` events
   - Server sends multiple `response.audio_transcript.delta` events
   - Server sends `response.audio.done`
   - Server sends `response.audio_transcript.done`
   - Server sends `response.done`

---

### Server VAD Workflow

1-2. Same as Push-to-Talk

3. **User Speaks:**
   - Client continuously sends `input_audio_buffer.append` events
   - Server automatically detects speech and sends `input_audio_buffer.speech_started`
   - Server detects silence and sends `input_audio_buffer.speech_stopped`
   - Server auto-commits and creates user message
   - Server automatically triggers response generation

4-5. Same as Push-to-Talk (but automated)

---

## Audio Format Specifications

### PCM16 Format
- **Sample Rate:** 24000 Hz
- **Channels:** 1 (mono)
- **Bit Depth:** 16-bit signed integers
- **Byte Order:** Little-endian
- **Encoding:** Linear PCM
- **Chunk Size Recommendation:** 12000 samples (500ms at 24kHz) = 24000 bytes

### Base64 Encoding
```python
# Encoding (client → server)
audio_np = np.array([...], dtype=np.int16)
audio_b64 = base64.b64encode(audio_np.tobytes()).decode("ascii")

# Decoding (server → client)
audio_bytes = base64.b64decode(audio_b64)
audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
```

---

## Best Practices

### Error Handling
- Monitor all `error` events
- Log error details for debugging
- Most errors are recoverable; don't close connection
- Implement retry logic for transient errors

### Audio Streaming
- Send audio in consistent chunks (~500ms)
- Use threading/async for non-blocking audio I/O
- Maintain separate queues for input and output audio
- Handle buffer underruns gracefully

### State Management
- Track session state (created, configured, ready)
- Maintain conversation history if needed
- Implement conversation truncation for long sessions
- Store session ID for debugging

### Performance
- Use binary WebSocket frames for efficiency
- Minimize latency in audio pipeline
- Implement audio buffering and jitter handling
- Monitor queue sizes to detect bottlenecks

### Interruption Handling
- Detect user speech during assistant response
- Send `response.cancel` to stop current response
- Clear speaker queue to prevent audio overlap
- Commit new user audio and request new response

---

## References

- **Official Documentation:** [OpenAI Realtime API Guide](https://platform.openai.com/docs/guides/realtime)
- **Server Events Reference:** [Server Events API Reference](https://platform.openai.com/docs/api-reference/realtime-server-events)
- **Client Events Reference:** [Client Events API Reference](https://platform.openai.com/docs/api-reference/realtime-client-events)
- **WebSocket Guide:** [Realtime WebSocket Guide](https://platform.openai.com/docs/guides/realtime-websocket)
- **Main API Reference:** [Realtime API Reference](https://platform.openai.com/docs/api-reference/realtime)

---

**Document Version:** 1.0
**Last Updated:** 2025-12-25
**Model:** gpt-4o-mini-realtime-preview-2024-12-17
