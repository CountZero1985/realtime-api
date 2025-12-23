import numpy as np
import sounddevice as sd
from agents import function_tool



# --- Utility for audio recording ---
def record_audio():
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
        # Felvétel leáll, stream automatikusan bezár
    if audio_buffer:
        audio_data = np.concatenate(audio_buffer, axis=0)
    else:
        audio_data = np.empty((0, 1), dtype=np.int16)
    print(f"[LOG] Felvétel kész, minták száma: {audio_data.shape}")
    return audio_data

# --- Utility for audio playback ---
class AudioPlayer:
    def __enter__(self):
        self.stream = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
        self.stream.start()
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.stop()
        self.stream.close()
    def add_audio(self, audio_data):
        # Győződjünk meg róla, hogy a shape (N,) legyen, ne (N,1)
        if audio_data.ndim == 2 and audio_data.shape[1] == 1:
            audio_data = audio_data.flatten()
        self.stream.write(audio_data)