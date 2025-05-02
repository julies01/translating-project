import os
import glob
import subprocess
import creds
import deepl
from pathlib import Path
import torch
from transformers import pipeline
from faster_whisper import WhisperModel

translator = deepl.Translator(creds.auth_key)

os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid warnings
os.environ["USE_TORCH"] = "1"  # Force use of PyTorch
os.environ["USE_TF"] = "0"  # Disable TensorFlow

video_dir = os.getcwd()  # Get current working directory
output_video = os.path.join(video_dir, "output.mp4")


def transcribe_video(video_path):
    print(f"Transcribing {video_path}...")

    # Using faster-whisper for better performance
    model_size = "medium"
    # Run on GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if torch.cuda.is_available() else "int8"

    # Load the Whisper model
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # Transcribe the audio
    segments, _ = model.transcribe(
        video_path, language="en", task="transcribe", vad_filter=True
    )

    # Format as SRT
    srt_content = []
    for i, segment in enumerate(segments, 1):
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        text = segment.text.strip()

        srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")

    return srt_content

def format_timestamp(seconds):
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"


def translate_text(text,target_lang):
    if not text.strip():
        return ""

    translated = translator.translate_text(text, target_lang=target_lang)
    return translated.text

def put_subtitle_on_video(video_path, srt_path):
    cmd = [
    "ffmpeg",
    "-i", video_path,
    "-vf", f"subtitles={srt_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF&'",
    "-c:a", "copy",  # Keep original audio
    output_video
    ]
    subprocess.run(cmd, check=True)
    print("Subtitles burned successfully!")

def essai(video_path,selected_lang):
    
    video_filename = Path(video_path).stem
    srt_path = f"{video_filename}.srt"

    transcribe_video(video_path)
    srt_content = transcribe_video(video_path)

    print(f"Translating subtitles for {video_path}...")
    translated_srt = []
    for line in srt_content:
        parts = line.strip().split("\n")
        if len(parts) >= 3:  # Valid subtitle entry
            subtitle_index = parts[0]
            timestamp = parts[1]
            text = parts[2]

            # Translate to the target language
            translation = translate_text(text,selected_lang)

            combined_text = (
                f"{translation}"
                if translation
                else text
            )

            translated_srt.append(
                f"{subtitle_index}\n{timestamp}\n{combined_text}\n\n"
            )

    # Write to SRT file
    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(translated_srt)

    print(f"Subtitles with translation saved to {srt_path}")
    put_subtitle_on_video(video_path, srt_path)
