Base64EncodedAudioData = ""
input_text = ""
session_update_event = {
    # "event_id": "event_123", # id of the server event
    "type": "session.update",
    "session": {
        "modalities": ["text", "audio"],
        "instructions": "segíts a kizárólag magyarul beszéló felhasználónak",
        "voice": "sage",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": {
            "model": "gpt-4o-mini-transcribe",
            "language": "hu"
        },
        "turn_detection": None,
        # "tools": [
        #     {
        #         "type": "function",
        #         "name": "get_weather",
        #         "description": "Get the current weather...",
        #         "parameters": {
        #             "type": "object",
        #             "properties": {
        #                 "location": { "type": "string" }
        #             },
        #             "required": ["location"]
        #         }
        #     }
        # ],
        # "tool_choice": "auto",
        "temperature": 0.8,
        "max_response_output_tokens": "inf",
        "speed": 1.1,
        "tracing": "auto"
    }
}

inpu_audio_buffer_append_event = {
    # "event_id": "event_456",
    "type": "input_audio_buffer.append",
    "audio": Base64EncodedAudioData # max 15 MiB, Base64-encoded audio bytes. This must be in the format specified by the input_audio_format field in the session configuration.
}

input_audio_buffer_append_event = {
    "event_id": "event_456",
    "type": "input_audio_buffer.append",
    "audio": "Base64EncodedAudioData"
}


input_audio_buffer_commit_event = {
    # "event_id": "event_012",
    "type": "input_audio_buffer.clear"
}


conversation_item_create_event = {
    # "event_id": "event_345",
    "type": "conversation.item.create",
    "previous_item_id": None,
    "item": {
        # "id": "msg_001",
        "type": "message",
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": input_text
            }
        ]
    }
}



## server events

conversation_item_created_event = {
    "event_id": "event_1920", # id of the server event
    "type": "conversation.item.created",
    "previous_item_id": "msg_002",
    "item": {
        "id": "msg_003",
        "object": "realtime.item",
        "type": "message",
        "status": "completed",
        "role": "user",
        "content": []
    }
}

conversation_created_event = {
    "event_id": "event_9101", # id of the server event
    "type": "conversation.created",
    "conversation": {
        # "id": "conv_001",
        "object": "realtime.conversation"
    }
}

conversation_item_input_audio_transcription_delta_event = {
    "type": "conversation.item.input_audio_transcription.delta",
    "event_id": "event_001",
    "item_id": "item_001",
    "content_index": 0,
    "delta": "Hello"
}



