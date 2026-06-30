
import sounddevice as sd
import soundfile as sf
from pathlib import Path

def record_voice_to_wav(output_path: Path, duration_sec: int = 10, samplerate: int = 44100):
    """
    Record audio from the default microphone for duration_sec seconds
    and save to output_path as a WAV file.
    """
    channels = 1
    print(f"Recording for {duration_sec} seconds...")
    audio = sd.rec(int(duration_sec * samplerate), samplerate=samplerate, channels=channels)
    sd.wait()
    sf.write(str(output_path), audio, samplerate)
    print(f"Saved recording to {output_path}")