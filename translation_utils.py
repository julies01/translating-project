import os
import re
import requests
import uuid
from datetime import datetime
import shutil
import audio_video_processing as av

"""
@brief Translate text using Ollama API with specific formatting preservation

@param formatted_text Text to translate with numbered format
@param src_lang Source language code
@param tgt_lang Target language code
@return Translated text maintaining the numbered format
"""
def translate_text_ollama(formatted_text, src_lang="en", tgt_lang="fr"):
    # Create prompt for translation with formatting instructions
    prompt = (
        f"Traduis le texte suivant de {src_lang} vers {tgt_lang}. "
        "Pour chaque ligne, commence par le même numéro entre crochets suivi du texte traduit. "
        "Exemple : [1] Bonjour.\n\n"
        f"{formatted_text} /no_think"
    )
    
    # Send request to Ollama API
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen3:8b",
            "prompt": prompt,
            "stream": False
        }
    )
    response.raise_for_status()
    
    # Extract and clean response
    translated = response.json()["response"].strip()
    # Remove any thinking tags that might appear
    translated = re.sub(r"<think>.*?</think>", "", translated, flags=re.DOTALL).strip()
    return translated

"""
@brief Parse translated text back into segments with original timing

@param translated_text The translated text with numbered format
@param original_segments Original segments with timing information
@return List of segments with translated text and original timing
"""
def parse_translated_segments(translated_text, original_segments):
    lines = translated_text.strip().splitlines()
    segments = []
    line_re = re.compile(r"\[(\d+)\]\s*(.*)")
    
    for line in lines:
        m = line_re.match(line)
        if not m:
            continue
        
        # Extract index and text from numbered format
        idx, text = m.groups()
        idx = int(idx) - 1  # Convert to 0-based index
        
        # Map translated text to original timing
        if 0 <= idx < len(original_segments):
            seg = original_segments[idx]
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": text.strip()
            })
    return segments

"""
@brief Translate text segments while preserving timing information

@param formatted_text Text with numbered format to translate
@param original_segments Original segments with timing
@param src_lang Source language code
@param tgt_lang Target language code
@param status_callback Function to call with status updates
@return List of translated segments with original timing
"""
def translate_segments(formatted_text, original_segments, src_lang, tgt_lang, status_callback):
    # Step 3: Translation via Ollama
    if status_callback:
        status_callback("Traduction du texte ...")
    translated_text = translate_text_ollama(formatted_text, src_lang=src_lang, tgt_lang=tgt_lang)
    translated_segments = parse_translated_segments(translated_text, original_segments)
    return translated_segments


"""
@brief Setup working directories and file paths for processing

@param input_video_path Path to the input video file
@param save_dir Directory to save results (auto-generated if None)
@return Tuple containing all necessary file paths
"""
def setup_directories_and_paths(input_video_path, save_dir):
    # Create unique directory if not provided
    if save_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        save_dir = os.path.join("history", f"{timestamp}_{unique_id}")
    os.makedirs(save_dir, exist_ok=True)

    # Copy original video to working directory (for history preservation)
    original_video_path = os.path.join(save_dir, "original.mp4")
    shutil.copy(input_video_path, original_video_path) 

    # Define paths for temporary and output files
    extracted_audio = os.path.join(save_dir, "audio.wav")
    translated_audio = os.path.join(save_dir, "translated_audio.wav")
    output_video = os.path.join(save_dir, "translated.mp4")
    srt_path = os.path.join(save_dir, "translated.srt")
    
    return save_dir, original_video_path, extracted_audio, translated_audio, output_video, srt_path


"""
@brief Extract audio from video and transcribe it to text with timing

@param original_video_path Path to the video file
@param extracted_audio Path where extracted audio will be saved
@param status_callback Function to call with status updates
@param progress_callback Function to call with progress updates
@return Tuple containing segments, formatted text, and detected language
"""
def extract_and_transcribe(original_video_path, extracted_audio, status_callback, progress_callback,device):
    # Step 1: Audio extraction
    if status_callback:
        status_callback("Extraction de l'audio de la vidéo ...")
    av.extract_audio(original_video_path, extracted_audio)
    if progress_callback: progress_callback(0.1)

    # Step 2: Language detection and transcription
    if status_callback:
        status_callback("Détection de la langue et transcription ...")
    segments, formatted_text, src_lang = av.transcribe_audio(extracted_audio,device)
    if progress_callback: progress_callback(0.2)
    if status_callback:
        status_callback(f"Langue détectée : {src_lang}")
    
    return segments, formatted_text, src_lang