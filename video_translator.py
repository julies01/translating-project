import os
import whisper
from gtts import gTTS
from pydub import AudioSegment
from transformers import MarianMTModel, MarianTokenizer
import subprocess
import tempfile
import streamlit as st
import ffmpeg
import re
import requests

INPUT_VIDEO = "input.mp4"
EXTRACTED_AUDIO = "audio.wav"
TRANSLATED_AUDIO = "translated_audio.wav"
OUTPUT_VIDEO = "translated_video.mp4"

# === 1. Extraire l’audio de la vidéo ===
def extract_audio(video_path, audio_path):
    print(f"Extraction de l'audio de {video_path} vers {audio_path}")
    ffmpeg.input(video_path).output(audio_path, acodec='pcm_s16le', ac=1, ar='16k').run(overwrite_output=True)

# === 2. Transcrire l’audio (avec timestamps) ===
def transcribe_audio(audio_path):
    model = whisper.load_model("small")
    result = model.transcribe(audio_path)
    segments = []
    text = ""
    for idx, seg in enumerate(result["segments"], 1):
        line = f"[{idx}] {seg['text']}"
        text += line + "\n"
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"]
        })
    return segments, text.strip()

# === 3. Traduire le texte via Ollama Qwen3:8b ===
def translate_text_ollama(formatted_text, src_lang="en", tgt_lang="fr"):
    prompt = (
        f"Traduis le texte suivant de {src_lang} vers {tgt_lang}. "
        "Pour chaque ligne, commence par le même numéro entre crochets suivi du texte traduit. "
        "Exemple : [1] Bonjour.\n\n"
        f"{formatted_text}"
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
    # Supprimer le bloc <think>...</think> s'il existe
    translated = re.sub(r"<think>.*?</think>", "", translated, flags=re.DOTALL).strip()
    return translated

# === 3b. Recréer les segments à partir du texte traduit ===
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

# === 4. Synthétiser l’audio traduit ===
def synthesize_speech_segment(text, lang="fr"):
    lang_gtts = lang
    if lang == "zh":
        lang_gtts = "zh-CN" 
    tts = gTTS(text=text, lang=lang_gtts)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
        tts.save(tmp_mp3.name)
        audio = AudioSegment.from_mp3(tmp_mp3.name)
    return audio

# === 5. Recréer la vidéo avec le nouvel audio ===
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

def process_video(input_video_path, output_video_path, st=None, status_placeholder=None, tgt_lang="fr"):
    total_steps = 4
    progress = 0

    def update_progress(val):
        if st and progress_bar:
            progress_bar.progress(val)

    progress_bar = st.progress(0) if st else None

    # 1. Extraction
    if st and status_placeholder:
        status_placeholder.text("Extraction de l'audio de la vidéo ...")
    extract_audio(input_video_path, EXTRACTED_AUDIO)
    progress += 1
    update_progress(progress / total_steps)

    # 2. Transcription
    if st and status_placeholder:
        status_placeholder.text("Transcription de l'audio ...")
    original_segments, formatted_text = transcribe_audio(EXTRACTED_AUDIO)
    progress += 1
    update_progress(progress / total_steps)

    # 3. Traduction via Ollama
    if st and status_placeholder:
        status_placeholder.text("Traduction du texte ...")
    translated_text = translate_text_ollama(formatted_text, src_lang="en", tgt_lang=tgt_lang)
    translated_segments = parse_translated_segments(translated_text, original_segments)

    nb_segments = len(translated_segments)
    audio_segments = []
    current_time_ms = 0

    # 4. Synthèse audio segmentée
    if st and status_placeholder:
        status_placeholder.text("Synthèse audio ...")
    for i, seg in enumerate(translated_segments):
        if st and status_placeholder:
            status_placeholder.text(f"Synthèse vocale [{i+1}/{nb_segments}] ...")
        update_progress((progress + (i + 1) / nb_segments) / total_steps)
        audio = synthesize_speech_segment(seg["text"], lang=tgt_lang)
        seg_start_ms = int(seg["start"] * 1000)
        seg_end_ms = int(seg["end"] * 1000)
        target_duration_ms = seg_end_ms - seg_start_ms

        if seg_start_ms > current_time_ms:
            silence = AudioSegment.silent(duration=seg_start_ms - current_time_ms)
            audio_segments.append(silence)
            current_time_ms = seg_start_ms

        if len(audio) < target_duration_ms:
            audio += AudioSegment.silent(duration=target_duration_ms - len(audio))
        else:
            audio = audio[:target_duration_ms]

        audio_segments.append(audio)
        current_time_ms += target_duration_ms

    progress += 1
    update_progress(progress / total_steps)

    # 5. Génération de l'audio final et fusion
    if st and status_placeholder:
        status_placeholder.text("Génération de l'audio traduit ...")
    final_audio = sum(audio_segments)
    final_audio.export(TRANSLATED_AUDIO, format="wav")

    if st and status_placeholder:
        status_placeholder.text("Fusion audio/vidéo ...")
    combine_audio_video(input_video_path, TRANSLATED_AUDIO, output_video_path)
    progress += 1
    update_progress(progress / total_steps)

    # Nettoyage
    if os.path.exists(EXTRACTED_AUDIO):
        os.remove(EXTRACTED_AUDIO)
    if os.path.exists(TRANSLATED_AUDIO):
        os.remove(TRANSLATED_AUDIO)
    progress_bar.empty()

# === Interface Streamlit ===
st.title("🎬 Traducteur de Vidéo Automatique")

uploaded_file = st.file_uploader("Télécharge ta vidéo à traduire (format mp4)", type=["mp4"])

LANGUAGES = {
    "Français": "fr",
    "Anglais": "en",
    "Chinois (simplifié)": "zh",
    "Espagnol": "es",
    "Allemand": "de",
    "Italien": "it",
    "Néerlandais": "nl",
    "Portugais": "pt",
    "Russe": "ru"
}
tgt_lang_label = st.selectbox("Choisis la langue de traduction :", list(LANGUAGES.keys()), index=0)
tgt_lang = LANGUAGES[tgt_lang_label]

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    st.video(tmp_input_path)
    if st.button("Traduire la vidéo"):
        status_placeholder = st.empty()
        output_path = tmp_input_path.replace(".mp4", "_translated.mp4")
        process_video(
            tmp_input_path,
            output_path,
            st=st,
            status_placeholder=status_placeholder,
            tgt_lang=tgt_lang
        )
        status_placeholder.success("✅ Traduction terminée !")
        with open(output_path, "rb") as f:
            st.download_button(
                label="Télécharger la vidéo traduite",
                data=f,
                file_name="video_traduite.mp4",
                mime="video/mp4"
            )
        st.video(output_path)
        os.remove(output_path)
    os.remove(tmp_input_path)