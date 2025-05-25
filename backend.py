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

def extract_audio(video_path, audio_path):
    ffmpeg.input(video_path).output(audio_path, acodec='pcm_s16le', ac=1, ar='16k').run(overwrite_output=True)

def transcribe_audio(audio_path, device="cpu", model_size="turbo"):
    model = whisperx.load_model(model_size, device, compute_type="float32")
    result = model.transcribe(audio_path)

    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result_aligned = whisperx.align(result["segments"], align_model, metadata, audio_path, device)
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
    src_lang = result.get("language", "en")
    return segments, text.strip(), src_lang

def translate_text_ollama(formatted_text, src_lang="en", tgt_lang="fr"):
    prompt = (
        f"Traduis le texte suivant de {src_lang} vers {tgt_lang}. "
        "Pour chaque ligne, commence par le même numéro entre crochets suivi du texte traduit. "
        "Exemple : [1] Bonjour.\n\n"
        f"{formatted_text} /no_think"
    )
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen3:8b",
            "prompt": prompt,
            "stream": False
        }
    )
    response.raise_for_status()
    translated = response.json()["response"].strip()
    translated = re.sub(r"<think>.*?</think>", "", translated, flags=re.DOTALL).strip()
    return translated

def parse_translated_segments(translated_text, original_segments):
    lines = translated_text.strip().splitlines()
    segments = []
    line_re = re.compile(r"\[(\d+)\]\s*(.*)")
    for line in lines:
        m = line_re.match(line)
        if not m:
            continue
        idx, text = m.groups()
        idx = int(idx) - 1
        if 0 <= idx < len(original_segments):
            seg = original_segments[idx]
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": text.strip()
            })
    return segments

def time_stretch_to_duration(audio_segment, target_duration_ms):
    samples = np.array(audio_segment.get_array_of_samples())
    if audio_segment.channels > 1:
        samples = samples.reshape((-1, audio_segment.channels))
        y = samples.mean(axis=1).astype(np.float32) / 32768.0
    else:
        y = samples.astype(np.float32) / 32768.0
    sr = audio_segment.frame_rate
    current_duration = len(audio_segment) / 1000.0
    target_duration = target_duration_ms / 1000.0
    if current_duration == 0 or abs(current_duration - target_duration) < 0.01:
        return audio_segment
    rate = current_duration / target_duration

    hop_length = 512
    D = librosa.stft(y, hop_length=hop_length)
    D_stretch = librosa.phase_vocoder(D, rate=rate, hop_length=hop_length)
    y_stretch = librosa.istft(D_stretch, hop_length=hop_length)

    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp_wav.name, y_stretch, sr)
    stretched = AudioSegment.from_wav(tmp_wav.name)
    tmp_wav.close()
    os.remove(tmp_wav.name)
    return stretched

def synthesize_speech_segment(text, lang="fr"):
    lang_gtts = lang
    if lang == "zh":
        lang_gtts = "zh-CN"
    tts = gTTS(text=text, lang=lang_gtts)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
        tts.save(tmp_mp3.name)
        audio = AudioSegment.from_mp3(tmp_mp3.name)
    return audio

def combine_audio_video(original_video_path, new_audio_path, output_path):
    command = [
        'ffmpeg',
        '-y',
        '-i', original_video_path,
        '-i', new_audio_path,
        '-c:v', 'copy',
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-shortest',
        output_path
    ]
    subprocess.run(command, check=True)

def format_srt_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def generate_srt(segments, srt_path):
    """Génère un fichier SRT à partir des segments."""
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_srt_timestamp(seg["start"])
            end = format_srt_timestamp(seg["end"])
            text = seg["text"].replace('\n', ' ')
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def burn_subtitles_on_video(video_path, srt_path, output_path):
    """Incruste les sous-titres sur la vidéo avec ffmpeg."""
    command = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"subtitles={srt_path}:force_style='FontName=Arial,FontSize=20,PrimaryColour=&HFFFFFF&'",
        "-c:a", "copy",
        output_path
    ]
    subprocess.run(command, check=True)

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
    # Création d'un dossier unique pour cette requête
    if save_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        save_dir = os.path.join("history", f"{timestamp}_{unique_id}")
    os.makedirs(save_dir, exist_ok=True)

    # Copie la vidéo originale dans le dossier
    original_video_path = os.path.join(save_dir, "original.mp4")
    shutil.copy(input_video_path, original_video_path)

    # Chemins pour les fichiers temporaires dans le dossier
    extracted_audio = os.path.join(save_dir, "audio.wav")
    translated_audio = os.path.join(save_dir, "translated_audio.wav")
    output_video = os.path.join(save_dir, "translated.mp4")
    srt_path = os.path.join(save_dir, "translated.srt")

    # 1. Extraction
    if status_callback:
        status_callback("Extraction de l'audio de la vidéo ...")
    extract_audio(original_video_path, extracted_audio)
    if progress_callback: progress_callback(0.1)

    # 2. Détection de la langue et transcription
    if status_callback:
        status_callback("Détection de la langue et transcription ...")
    segments, formatted_text, src_lang = transcribe_audio(extracted_audio)
    if progress_callback: progress_callback(0.2)
    if status_callback:
        status_callback(f"Langue détectée : {src_lang}")
    original_segments = segments

    # 3. Traduction via Ollama
    if status_callback:
        status_callback("Traduction du texte ...")
    translated_text = translate_text_ollama(formatted_text, src_lang=src_lang, tgt_lang=tgt_lang)
    translated_segments = parse_translated_segments(translated_text, original_segments)

    # 4. Synthèse audio segmentée
    if translate_audio:
        nb_segments = len(translated_segments)
        audio_segments = []
        current_time_ms = 0

        if status_callback:
            status_callback("Synthèse audio ...")
        for i, seg in enumerate(translated_segments):
            if status_callback:
                status_callback(f"Synthèse vocale [{i+1}/{nb_segments}] ...")
            if progress_callback: progress_callback(0.2 + 0.3 * (i+1)/nb_segments)
            audio = synthesize_speech_segment(seg["text"], lang=tgt_lang)
            seg_start_ms = int(seg["start"] * 1000)
            seg_end_ms = int(seg["end"] * 1000)
            target_duration_ms = seg_end_ms - seg_start_ms

            if len(audio) > 0 and abs(len(audio) - target_duration_ms) > 30:
                audio = time_stretch_to_duration(audio, target_duration_ms)

            if len(audio) < target_duration_ms:
                audio += AudioSegment.silent(duration=target_duration_ms - len(audio))
            else:
                audio = audio[:target_duration_ms]

            if seg_start_ms > current_time_ms:
                silence = AudioSegment.silent(duration=seg_start_ms - current_time_ms)
                audio_segments.append(silence)
                current_time_ms = seg_start_ms

            audio_segments.append(audio)
            current_time_ms += target_duration_ms

        if progress_callback: progress_callback(0.6)

        # Génération de l'audio final et fusion
        if status_callback:
            status_callback("Génération de l'audio traduit ...")
        final_audio = sum(audio_segments)
        final_audio.export(translated_audio, format="wav")

        if status_callback:
            status_callback("Fusion audio/vidéo ...")
        combine_audio_video(original_video_path, translated_audio, output_video)
        if progress_callback: progress_callback(0.7)
        video_for_subs = output_video
    else:
        video_for_subs = original_video_path

    # 5. Génération et incrustation des sous-titres (si demandé)
    if add_subtitles:
        subtitled_video_path = os.path.join(save_dir, "translated_subtitled.mp4")
        if status_callback:
            status_callback("Génération et incrustation des sous-titres ...")
        generate_srt(translated_segments, srt_path)
        burn_subtitles_on_video(video_for_subs, srt_path, subtitled_video_path)
        if progress_callback: progress_callback(0.9)
        os.rename(subtitled_video_path, output_video)
    if progress_callback: progress_callback(1.0)

    # Nettoyage : on garde tout dans le dossier pour l'historique
    return {
        "history_dir": save_dir,
        "original_video": original_video_path,
        "translated_video": output_video,
        "srt": srt_path
    }