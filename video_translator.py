import os
import whisper
from gtts import gTTS
from pydub import AudioSegment
from transformers import MarianMTModel, MarianTokenizer
import subprocess
import tempfile
import streamlit as st
import ffmpeg

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
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"]
        })
    return segments

# === 3. Traduire le texte ===
def translate_text(text, src_lang="en", tgt_lang="fr"):
    model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}"
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    outputs = model.generate(**inputs)
    translated = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    return translated[0]

# === 4. Synthétiser l’audio traduit ===
def synthesize_speech_segment(text, lang="fr"):
    tts = gTTS(text=text, lang=lang)
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

def process_video(input_video_path, output_video_path, st=None, status_placeholder=None):
    if st and status_placeholder:
        status_placeholder.info("Extraction de l'audio de la vidéo...")
    extract_audio(input_video_path, EXTRACTED_AUDIO)

    if st and status_placeholder:
        status_placeholder.info("Transcription de l'audio...")
    segments = transcribe_audio(EXTRACTED_AUDIO)
    i = 0
    nb_segments = len(segments)
    if st and status_placeholder:
        status_placeholder.info("Traduction du texte [{}/{}]...".format(i, nb_segments))
    translated_segments = []
    audio_segments = []
    current_time_ms = 0
    for seg in segments:
        status_placeholder.info("Traduction du texte [{}/{}]...".format(i, nb_segments))
        i+=1
        translated = translate_text(seg["text"])
        translated_segments.append(translated)
        audio = synthesize_speech_segment(translated)
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

    if st and status_placeholder:
        status_placeholder.info("Génération de l'audio traduit...")
    final_audio = sum(audio_segments)
    final_audio.export(TRANSLATED_AUDIO, format="wav")

    if st and status_placeholder:
        status_placeholder.info("Fusion audio/vidéo…")
    combine_audio_video(input_video_path, TRANSLATED_AUDIO, output_video_path)

    # Nettoyage
    if os.path.exists(EXTRACTED_AUDIO):
        os.remove(EXTRACTED_AUDIO)
    if os.path.exists(TRANSLATED_AUDIO):
        os.remove(TRANSLATED_AUDIO)

# === Interface Streamlit ===
st.title("🎬 Traducteur de Vidéo Automatique")

uploaded_file = st.file_uploader("Télécharge ta vidéo à traduire (format mp4)", type=["mp4"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    st.video(tmp_input_path)
    if st.button("Traduire la vidéo"):
        status_placeholder = st.empty()
        output_path = tmp_input_path.replace(".mp4", "_translated.mp4")
        process_video(tmp_input_path, output_path, st=st, status_placeholder=status_placeholder)
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