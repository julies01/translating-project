"""
<author> : Julie BENED
<date> : 2025-16-05
<description> : This script transcribes a video file, translates the subtitles, and burns them into the video.
"""

import os
import glob
import subprocess
import deepl
from pathlib import Path
import torch
from transformers import pipeline
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline  
import creds
import diarization.diarazation as d


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

    
    audio_path = d.extract_audio(video_path)

    try:
        # Perform speaker diarization
        print("Starting speaker diarization (this may take some time)...")
        speaker_segments = d.diarize_audio(audio_path)
        
        # Merge transcription with speaker information
        enriched_segments = d.merge_transcription_with_diarization(segments, speaker_segments)
        
        # Format as SRT with speaker indicators
        srt_content = []
        for i, segment in enumerate(enriched_segments, 1):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            
            # Format text with speakers
            if len(segment["speakers"]) > 1:
                # Multiple speakers - add dashes and newlines
                speaker_lines = []
                for speaker in segment["speakers"]:
                    speaker_lines.append(f"- {segment['text']}")
                text = "\n".join(speaker_lines)
            else:
                # Single speaker - no need for dash or special formatting
                text = segment["text"].strip()
            
            srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")
    except Exception as e:
        print(f"Error during diarization in transcribe: {e}")
        print("Falling back to standard transcription without speaker detection...")
        srt_content = []
        for i, segment in enumerate(segments, 1):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            text = segment.text.strip()
            srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")

    # Clean up temp audio file
    if os.path.exists(audio_path):
        os.remove(audio_path)

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

"""
def translation_process(selected_lang, srt_content):

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
"""    


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


def main(video_path, selected_lang):
    video_filename = Path(video_path).stem
    srt_path = os.path.join(video_path, f"{video_filename}.srt")
    native_srt_path = os.path.join(video_path, f"{video_filename}_native.srt")

    # Utiliser la nouvelle fonction de transcription avec diarisation
    srt_content = transcribe_video(video_path)
    print(f"Translating subtitles for {video_path}...")

    
    with open(native_srt_path, "w", encoding="utf-8") as f:
        f.writelines(srt_content)

    # Translate only the subtitle text lines, keep timestamps and numbering
    translated_srt = []
    for line in srt_content:
        parts = line.split('\n')
        if len(parts) >= 3:
            # Si le texte contient des tirets (plusieurs locuteurs), traduire chaque ligne séparément
            if "-" in parts[2]:
                speaker_lines = parts[2].split('\n')
                translated_lines = []
                for speaker_line in speaker_lines:
                    translated_line = translate_text(speaker_line, selected_lang)
                    translated_lines.append(translated_line)
                parts[2] = '\n'.join(translated_lines)
            else:
                # Traduire normalement pour un seul locuteur
                parts[2] = translate_text(parts[2], selected_lang)
            translated_srt.append('\n'.join(parts) + '\n')
        else:
            translated_srt.append(line)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(translated_srt)

    put_subtitle_on_video(video_path, srt_path)
    print(f"Output video with subtitles saved as {output_video}")