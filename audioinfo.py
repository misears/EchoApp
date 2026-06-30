#C:\EchoPro\EchoApp\audio_info.py

from pydub import AudioSegment

def get_audio_length_ms(path: str) -> int:
    """
    Return the length of an audio file in milliseconds.
    """
    audio = AudioSegment.from_file(path)
    return len(audio)