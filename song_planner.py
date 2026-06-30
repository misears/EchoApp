
from pathlib import Path
from typing import List, Dict
from math import floor

from app_paths import ECHO_ROOT
from music_generator import generate_music_clip

def split_lyrics_into_sections(lyrics: str, structure: List[str]) -> Dict[str, str]:
    lines = [l.strip() for l in lyrics.split("\n") if l.strip()]
    if not lines:
        return {section: "" for section in structure}

    per_section = floor(len(lines) / len(structure)) or 1
    sections = {}
    idx = 0
    for section in structure:
        chunk = lines[idx:idx+per_section]
        sections[section] = "\n".join(chunk)
        idx += per_section

    if idx < len(lines):
        sections[structure[-1]] += "\n" + "\n".join(lines[idx:])

    return sections

def plan_song_clips(total_length_sec: int, structure: List[str]) -> Dict[str, int]:
    per_section_ms = floor((total_length_sec * 1000) / len(structure))
    return {section: per_section_ms for section in structure}

def generate_song_sections(
    lyrics: str,
    structure: List[str],
    total_length_sec: int,
    key: str,
    chords: str,
    time_signature: str,
    tempo: int,
    style: str,
    genre: str,
    mood: str,
    project_id: str,
    use_cloud: bool = False
) -> List[Path]:
    song_dir = ECHO_ROOT / "generated" / project_id
    song_dir.mkdir(parents=True, exist_ok=True)

    lyric_sections = split_lyrics_into_sections(lyrics, structure)
    durations = plan_song_clips(total_length_sec, structure)

    generated_paths: List[Path] = []

    for section in structure:
        duration_ms = durations[section]
        duration_sec = max(10, duration_ms // 1000)
        result = generate_music_clip(
            style=style,
            genre=genre,
            mood=mood,
            lyrics=lyric_sections.get(section, ""),
            duration_seconds=duration_sec,
            key=key,
            chords=chords,
            time_signature=time_signature,
            tempo_bpm=tempo,
            section_name=section,
            seed=None,
            project_id=project_id,
            use_cloud=use_cloud,
        )
        generated_paths.append(result.audio_path)

    return generated_paths