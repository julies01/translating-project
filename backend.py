import os
import whisperx
from gtts import gTTS
from pydub import AudioSegment
import subprocess
import tempfile
import ffmpeg
import re
import requests
import librosa
import soundfile as sf
import numpy as np
import uuid
from datetime import datetime
import shutil

"""
@brief Extract audio from video file using ffmpeg

@param video_path Path to the input video file
@param audio_path Path where the extracted audio will be saved
@return None
"""
def extract_audio(video_path, audio_path):
    ffmpeg.input(video_path).output(audio_path, acodec='pcm_s16le', ac=1, ar='16k').run(overwrite_output=True)

"""
@brief Transcribe audio using WhisperX and return segments with timing information

@param audio_path Path to the audio file to transcribe
@param device Device to use for processing ("cpu" or "cuda")
@param model_size Size of the Whisper model to use
@return Tuple containing segments list, formatted text, and detected language
"""
def transcribe_audio(audio_path, device="cpu", model_size="turbo"):
    # Load WhisperX model for transcription
    model = whisperx.load_model(model_size, device, compute_type="float32")
    result = model.transcribe(audio_path)

    # Load alignment model for precise timing
    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result_aligned = whisperx.align(result["segments"], align_model, metadata, audio_path, device)
    
    # Process aligned segments into our format
    segments = []
    text = ""
    for idx, seg in enumerate(result_aligned["segments"], 1):
        line = f"[{idx}] {seg['text']}"
        text += line + "\n"
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"]
        })
    
    # Extract detected language
    src_lang = result.get("language", "en")
    return segments, text.strip(), src_lang

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
@brief Stretch or compress audio to match target duration using librosa

@param audio_segment AudioSegment object to be time-stretched
@param target_duration_ms Target duration in milliseconds
@return AudioSegment with adjusted duration
"""
def time_stretch_to_duration(audio_segment, target_duration_ms):
    # Convert audio to numpy array
    samples = np.array(audio_segment.get_array_of_samples())
    
    # Handle stereo/mono conversion
    if audio_segment.channels > 1:
        samples = samples.reshape((-1, audio_segment.channels))
        y = samples.mean(axis=1).astype(np.float32) / 32768.0  # Convert to mono
    else:
        y = samples.astype(np.float32) / 32768.0  # Normalize to [-1, 1]
    
    sr = audio_segment.frame_rate
    current_duration = len(audio_segment) / 1000.0
    target_duration = target_duration_ms / 1000.0
    
    # Skip processing if durations are very close
    if current_duration == 0 or abs(current_duration - target_duration) < 0.01:
        return audio_segment
    
    # Calculate stretch ratio
    rate = current_duration / target_duration

    # Perform time stretching using phase vocoder
    hop_length = 512
    D = librosa.stft(y, hop_length=hop_length)
    D_stretch = librosa.phase_vocoder(D, rate=rate, hop_length=hop_length)
    y_stretch = librosa.istft(D_stretch, hop_length=hop_length)

    # Save to temporary file and reload as AudioSegment
    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp_wav.name, y_stretch, sr)
    stretched = AudioSegment.from_wav(tmp_wav.name)
    tmp_wav.close()
    os.remove(tmp_wav.name)
    return stretched

"""
@brief Generate speech audio for a text segment using gTTS

@param text Text to synthesize into speech
@param lang Language code for speech synthesis
@return AudioSegment containing the synthesized speech
"""
def synthesize_speech_segment(text, lang="fr"):
    # Handle language code mapping for gTTS
    lang_gtts = lang
    if lang == "zh":
        lang_gtts = "zh-CN"
    
    # Generate speech using Google Text-to-Speech
    tts = gTTS(text=text, lang=lang_gtts)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
        tts.save(tmp_mp3.name)
        audio = AudioSegment.from_mp3(tmp_mp3.name)
    return audio

"""
@brief Combine original video with new audio track using ffmpeg

@param original_video_path Path to the original video file
@param new_audio_path Path to the new audio track
@param output_path Path where the combined video will be saved
@return None
"""
def combine_audio_video(original_video_path, new_audio_path, output_path):
    command = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', original_video_path,  # Input video
        '-i', new_audio_path,       # Input audio
        '-c:v', 'copy',             # Copy video stream without re-encoding
        '-map', '0:v:0',            # Map video from first input
        '-map', '1:a:0',            # Map audio from second input
        '-shortest',                # End when shortest stream ends
        output_path
    ]
    subprocess.run(command, check=True)

"""
@brief Convert seconds to SRT timestamp format (HH:MM:SS,mmm)

@param seconds Time in seconds as float
@return String formatted as SRT timestamp
"""
def format_srt_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

"""
@brief Generate SRT subtitle file from segments

@param segments List of segments with timing and text
@param srt_path Path where the SRT file will be saved
@return None
"""
def generate_srt(segments, srt_path):
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_srt_timestamp(seg["start"])
            end = format_srt_timestamp(seg["end"])
            text = seg["text"].replace('\n', ' ')  # Remove newlines from text
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

"""
@brief Burn subtitles directly into video using ffmpeg

@param video_path Path to the input video
@param srt_path Path to the SRT subtitle file
@param output_path Path where the subtitled video will be saved
@return None
"""
def burn_subtitles_on_video(video_path, srt_path, output_path):
    command = [
        "ffmpeg",
        "-y",  # Overwrite output file
        "-i", video_path,
        "-vf", f"subtitles={srt_path}:force_style='FontName=Arial,FontSize=20,PrimaryColour=&HFFFFFF&'",
        "-c:a", "copy",  # Copy audio without re-encoding
        output_path
    ]
    subprocess.run(command, check=True)

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
def extract_and_transcribe(original_video_path, extracted_audio, status_callback, progress_callback):
    # Step 1: Audio extraction
    if status_callback:
        status_callback("Extraction de l'audio de la vidéo ...")
    extract_audio(original_video_path, extracted_audio)
    if progress_callback: progress_callback(0.1)

    # Step 2: Language detection and transcription
    if status_callback:
        status_callback("Détection de la langue et transcription ...")
    segments, formatted_text, src_lang = transcribe_audio(extracted_audio)
    if progress_callback: progress_callback(0.2)
    if status_callback:
        status_callback(f"Langue détectée : {src_lang}")
    
    return segments, formatted_text, src_lang

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
@brief Synthesize speech for each segment and combine into final audio track

@param translated_segments List of segments with translated text and timing
@param tgt_lang Target language for speech synthesis
@param translated_audio Path where final audio will be saved
@param status_callback Function to call with status updates
@param progress_callback Function to call with progress updates
@return None
"""
def synthesize_and_combine_audio(translated_segments, tgt_lang, translated_audio, status_callback, progress_callback):
    nb_segments = len(translated_segments)
    audio_segments = []
    current_time_ms = 0

    if status_callback:
        status_callback("Synthèse audio ...")
    
    # Process each translated segment
    for i, seg in enumerate(translated_segments):
        if status_callback:
            status_callback(f"Synthèse vocale [{i+1}/{nb_segments}] ...")
        if progress_callback: 
            progress_callback(0.2 + 0.3 * (i+1)/nb_segments)
        
        # Generate speech for this segment
        audio = synthesize_speech_segment(seg["text"], lang=tgt_lang)
        
        # Calculate timing for this segment
        seg_start_ms = int(seg["start"] * 1000)
        seg_end_ms = int(seg["end"] * 1000)
        target_duration_ms = seg_end_ms - seg_start_ms

        # Adjust audio duration to match original timing
        if len(audio) > 0 and abs(len(audio) - target_duration_ms) > 30:
            audio = time_stretch_to_duration(audio, target_duration_ms)

        # Pad or trim audio to exact duration
        if len(audio) < target_duration_ms:
            audio += AudioSegment.silent(duration=target_duration_ms - len(audio))
        else:
            audio = audio[:target_duration_ms]

        # Add silence gap if needed between segments
        if seg_start_ms > current_time_ms:
            silence = AudioSegment.silent(duration=seg_start_ms - current_time_ms)
            audio_segments.append(silence)
            current_time_ms = seg_start_ms

        # Add this segment's audio
        audio_segments.append(audio)
        current_time_ms += target_duration_ms

    if progress_callback: progress_callback(0.6)

    # Combine all audio segments and export
    if status_callback:
        status_callback("Génération de l'audio traduit ...")
    final_audio = sum(audio_segments)
    final_audio.export(translated_audio, format="wav")

"""
@brief Combine original video with translated audio track

@param original_video_path Path to the original video
@param translated_audio Path to the translated audio
@param output_video Path where combined video will be saved
@param status_callback Function to call with status updates
@param progress_callback Function to call with progress updates
@return None
"""
def combine_video_audio(original_video_path, translated_audio, output_video, status_callback, progress_callback):
    if status_callback:
        status_callback("Fusion audio/vidéo ...")
    combine_audio_video(original_video_path, translated_audio, output_video)
    if progress_callback: progress_callback(0.7)

"""
@brief Generate subtitle file and burn it into the video

@param translated_segments List of segments with translated text and timing
@param video_for_subs Path to the video to add subtitles to
@param srt_path Path where SRT file will be saved
@param output_video Path where final video will be saved
@param save_dir Working directory
@param status_callback Function to call with status updates
@param progress_callback Function to call with progress updates
@return None
"""
def add_subtitles_to_video(translated_segments, video_for_subs, srt_path, output_video, save_dir, status_callback, progress_callback):
    subtitled_video_path = os.path.join(save_dir, "translated_subtitled.mp4")
    if status_callback:
        status_callback("Génération et incrustation des sous-titres ...")
    
    # Generate SRT file and burn subtitles into video
    generate_srt(translated_segments, srt_path)
    burn_subtitles_on_video(video_for_subs, srt_path, subtitled_video_path)
    if progress_callback: progress_callback(0.9)
    
    # Replace original output with subtitled version
    os.rename(subtitled_video_path, output_video)

"""
@brief Main function to process video translation

@param input_video_path Path to input video file
@param output_video_path Path for output video (unused, kept for compatibility)
@param tgt_lang Target language code for translation
@param progress_callback Function to call with progress updates (0.0 to 1.0)
@param status_callback Function to call with status message updates
@param translate_audio Whether to translate and replace audio
@param add_subtitles Whether to add burned-in subtitles
@param save_dir Directory to save results (auto-generated if None)
@return Dictionary with paths to generated files
"""
def process_video(
    input_video_path,
    output_video_path=None,
    tgt_lang="fr",
    progress_callback=None,
    status_callback=None,
    translate_audio=True,
    add_subtitles=True,
    save_dir=None
):
    # Setup working environment
    save_dir, original_video_path, extracted_audio, translated_audio, output_video, srt_path = setup_directories_and_paths(input_video_path, save_dir)

    # Extract audio and transcribe to get original segments
    original_segments, formatted_text, src_lang = extract_and_transcribe(original_video_path, extracted_audio, status_callback, progress_callback)

    # Translate the transcribed text
    translated_segments = translate_segments(formatted_text, original_segments, src_lang, tgt_lang, status_callback)

    # Generate translated audio if requested
    if translate_audio:
        synthesize_and_combine_audio(translated_segments, tgt_lang, translated_audio, status_callback, progress_callback)
        combine_video_audio(original_video_path, translated_audio, output_video, status_callback, progress_callback)
        video_for_subs = output_video
    else:
        # Use original video if not translating audio
        video_for_subs = original_video_path

    # Add subtitles if requested
    if add_subtitles:
        add_subtitles_to_video(translated_segments, video_for_subs, srt_path, output_video, save_dir, status_callback, progress_callback)
    
    # Final progress update
    if progress_callback: progress_callback(1.0)

    # Return paths to all generated files (kept in history directory)
    return {
        "history_dir": save_dir,
        "original_video": original_video_path,
        "translated_video": output_video,
        "srt": srt_path
    }