import os
import whisper
import ffmpeg
from gtts import gTTS
from pydub import AudioSegment
from transformers import MarianMTModel, MarianTokenizer
import subprocess
from pydub import AudioSegment
import tempfile

INPUT_VIDEO = "input.mp4"
EXTRACTED_AUDIO = "audio.wav"
TRANSLATED_AUDIO = "translated_audio.wav"
OUTPUT_VIDEO = "translated_video.mp4"

# === 1. Extraire l’audio de la vidéo ===
def extract_audio(video_path, audio_path):
    ffmpeg.input(video_path).output(audio_path, acodec='pcm_s16le', ac=1, ar='16k').run(overwrite_output=True)

# === 2. Transcrire l’audio (avec timestamps) ===
def transcribe_audio(audio_path):
    model = whisper.load_model("small")
    result = model.transcribe(audio_path)
    # Retourne la liste des segments avec texte et timecodes
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

def main():
    print("[1] Extraction audio...")
    extract_audio(INPUT_VIDEO, EXTRACTED_AUDIO)

    print("[2] Transcription audio...")
    segments = transcribe_audio(EXTRACTED_AUDIO)
    for seg in segments:
        print(f"[{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")

    print("[3] Traduction et synthèse vocal")
    translated_segments = []
    audio_segments = []
    current_time_ms = 0

    for seg in segments:
        print("Transcription :", seg["text"])
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

    final_audio = sum(audio_segments)
    final_audio.export(TRANSLATED_AUDIO, format="wav")

    print("[4] Recréation vidéo...")
    combine_audio_video(INPUT_VIDEO, TRANSLATED_AUDIO, OUTPUT_VIDEO)

    print("✅ Vidéo traduite générée :", OUTPUT_VIDEO)

    if os.path.exists(EXTRACTED_AUDIO):
        os.remove(EXTRACTED_AUDIO)
    if os.path.exists(TRANSLATED_AUDIO):
        os.remove(TRANSLATED_AUDIO)

if __name__ == "__main__":
    main()