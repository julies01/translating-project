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
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if torch.cuda.is_available() else "int8"

    # Load the Whisper model
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # First, detect language by running with language=None
    _, info = model.transcribe(
        video_path, language=None, task="transcribe", vad_filter=True
    )
    print(f"Detected language: {info.language}")

    # Now, transcribe with the detected language code
    segments, _ = model.transcribe(
        video_path, language=info.language, task="transcribe", vad_filter=True
    )

    return formatting_as_SRT(segments)


def formatting_as_SRT(segments):
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


def translation_process(srt_content,selected_lang):
    # Translate only the subtitle text lines, keep timestamps and numbering
    translated_srt = []
    for line in srt_content:
        parts = line.split('\n')
        if len(parts) >= 3:
            # parts[2] is the subtitle text
            translated_text = translate_text(parts[2], selected_lang)
            parts[2] = translated_text
            translated_srt.append('\n'.join(parts) + '\n')
        else:
            translated_srt.append(line)

    return translated_srt


def main(video_path, selected_lang,progress_callback=None):
    video_filename = Path(video_path).stem
    srt_path = os.path.join(video_dir, f"{video_filename}.srt")
    native_srt_path = os.path.join(video_dir, f"{video_filename}_native.srt")

    if progress_callback:
        progress_callback(0.1, "Transcription en cours...")
    srt_content = transcribe_video(video_path)
    print(f"Translating subtitles for {video_path}...")

    if progress_callback:
        progress_callback(0.3, "Génération du fichier SRT natif...")
    with open(native_srt_path, "w", encoding="utf-8") as f:
        f.writelines(srt_content)

    if progress_callback:
        progress_callback(0.5, "Traduction des sous-titres...")
    translated_srt = translation_process(srt_content,selected_lang)
    
    if progress_callback:
        progress_callback(0.7, "Génération du fichier SRT traduit...")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(translated_srt)

    if progress_callback:
        progress_callback(0.9, "Ajout des sous-titres à la vidéo...")
    put_subtitle_on_video(video_path, srt_path)

    if progress_callback:
        progress_callback(1.0, "Vidéo prête !")