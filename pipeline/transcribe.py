"""transcribe.py — extract audio from a video file and transcribe it with local Whisper."""
import os
import subprocess
import tempfile
from pathlib import Path


def transcribe(video_path: str, model_name: str = "base") -> str:
    """Return a transcript string for the given video file.

    Requires ffmpeg on PATH and the openai-whisper package.
    Downloads the Whisper model on first call (~150 MB for 'base').
    """
    import whisper

    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(video),
                "-ar", "16000", "-ac", "1",
                "-c:a", "pcm_s16le",
                audio_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (is ffmpeg installed?):\n{result.stderr[-500:]}"
            )

        model = whisper.load_model(model_name)
        output = model.transcribe(audio_path)
        return output["text"].strip()
    finally:
        if os.path.exists(audio_path):
            os.unlink(audio_path)
