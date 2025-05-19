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

INPUT_VIDEO = "input.mp4"
EXTRACTED_AUDIO = "audio.wav"
TRANSLATED_AUDIO = "translated_audio.wav"
OUTPUT_VIDEO = "translated_video.mp4"

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
        '-i', original_video_path,
        '-i', new_audio_path,
        '-c:v', 'copy',
        '-map', '0:v:0',
        '-map', '1:a:0',
        '-shortest',
        output_path
    ]
    subprocess.run(command, check=True)

def process_video(input_video_path, output_video_path, tgt_lang="fr", progress_callback=None, status_callback=None):
    total_steps = 4
    progress = 0

    def update_progress(val):
        if progress_callback:
            progress_callback(val)

    # 1. Extraction
    if status_callback:
        status_callback("Extraction de l'audio de la vidéo ...")
    extract_audio(input_video_path, EXTRACTED_AUDIO)
    progress += 1
    update_progress(progress / total_steps)

    # 2. Détection de la langue et transcription
    if status_callback:
        status_callback("Détection de la langue et transcription ...")
    segments, formatted_text, src_lang = transcribe_audio(EXTRACTED_AUDIO)
    progress += 1
    update_progress(progress / total_steps)
    if status_callback:
        status_callback(f"Langue détectée : {src_lang}")
    original_segments = segments

    # 3. Traduction via Ollama
    if status_callback:
        status_callback("Traduction du texte ...")
    translated_text = translate_text_ollama(formatted_text, src_lang=src_lang, tgt_lang=tgt_lang)
    translated_segments = parse_translated_segments(translated_text, original_segments)

    nb_segments = len(translated_segments)
    audio_segments = []
    current_time_ms = 0

    # 4. Synthèse audio segmentée
    if status_callback:
        status_callback("Synthèse audio ...")
    for i, seg in enumerate(translated_segments):
        if status_callback:
            status_callback(f"Synthèse vocale [{i+1}/{nb_segments}] ...")
        update_progress((progress + (i + 1) / nb_segments) / total_steps)
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

    progress += 1
    update_progress(progress / total_steps)

    # 5. Génération de l'audio final et fusion
    if status_callback:
        status_callback("Génération de l'audio traduit ...")
    final_audio = sum(audio_segments)
    final_audio.export(TRANSLATED_AUDIO, format="wav")

    if status_callback:
        status_callback("Fusion audio/vidéo ...")
    combine_audio_video(input_video_path, TRANSLATED_AUDIO, output_video_path)
    progress += 1
    update_progress(progress / total_steps)

    # Nettoyage
    if os.path.exists(EXTRACTED_AUDIO):
        os.remove(EXTRACTED_AUDIO)
    if os.path.exists(TRANSLATED_AUDIO):
        os.remove(TRANSLATED_AUDIO)