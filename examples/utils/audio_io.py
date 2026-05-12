"""Audio I/O utilities for voice examples.

This module provides simple utilities for recording and playing audio:
- record_audio(): Push-to-talk recording at 24kHz mono int16
- AudioPlayer: Context manager for streaming audio playback

Both utilities are configured for the OpenAI APIs' standard 24kHz mono format.
"""

import numpy as np
import sounddevice as sd


def record_audio():
    """Push-to-talk audio recording. Returns numpy array (N,1) int16 at 24kHz."""
    print("Nyomj <Enter>-t a felvétel indításához, majd újra <Enter>-t a leállításhoz!")
    input("Felvétel indítása: nyomj <Enter>-t...")
    samplerate = 24000
    audio_buffer = []
    recording = True
    def callback(indata, frames, time_info, status):
        if recording:
            audio_buffer.append(indata.copy())
    with sd.InputStream(samplerate=samplerate, channels=1, dtype=np.int16, callback=callback):
        input("Felvétel leállítása: nyomj <Enter>-t...")
    if audio_buffer:
        audio_data = np.concatenate(audio_buffer, axis=0)
    else:
        audio_data = np.empty((0, 1), dtype=np.int16)
    print(f"[LOG] Felvétel kész, minták száma: {audio_data.shape}")
    return audio_data


class AudioPlayer:
    """Context manager for audio playback at 24kHz mono int16."""
    def __enter__(self):
        self.stream = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
        self.stream.start()
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.stop()
        self.stream.close()
    def add_audio(self, audio_data):
        if audio_data.ndim == 2 and audio_data.shape[1] == 1:
            audio_data = audio_data.flatten()
        self.stream.write(audio_data)
