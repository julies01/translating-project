# 🎬 Automatic Video Translator

A Streamlit app for automatic video translation and subtitling using WhisperX, Ollama, and gTTS.

---

## Features

- Upload `.mp4` videos and translate their audio to another language.
- Supported target languages: French, English, Chinese, Spanish, German, Italian, Dutch, Portuguese, Russian.
- Choose to translate audio, add subtitles, or both.
- Download translated videos and `.srt` subtitle files.
- Persistent translation history in the sidebar.
- Multilingual interface (French, English, Chinese).
- All processing is local (except for gTTS, which requires an internet connection).

---

## Requirements

- **Python** 3.9 or newer  
  [Download Python](https://www.python.org/downloads/)  
  Make sure to check **"Add Python to PATH"** during installation.

- **ffmpeg**  
  - **macOS**:  
    ```bash
    brew install ffmpeg
    ```
  - **Windows**:  
    Download from [FFmpeg Official Site](https://ffmpeg.org/download.html) and add to `PATH`.

- **Ollama** (for local LLM translation)  
  [Ollama install instructions](https://ollama.com/download)  
  Start the model before running the app:
  ```bash
  ollama serve
  ```

- **Python packages**  
  Install all dependencies with:
  ```bash
  pip install streamlit whisperx gtts pydub ffmpeg-python requests librosa soundfile numpy
  ```

---

## Usage

1. **Start Ollama** with the desired model:
   ```bash
   ollama run serve
   ```
2. **Run the Streamlit app**:
   ```bash
   streamlit run app.py
   ```
3. Open the web interface (usually at [http://localhost:8501](http://localhost:8501)).
4. Upload your `.mp4` video, select the target language, and choose your options.
5. Click **Translate video**.
6. Download the translated video and/or subtitles.
7. Access your translation history in the sidebar.

---

## Project Structure

```
.
├── app.py                # Streamlit user interface
├── backend.py            # Video/audio processing and translation logic
├── history/              # Stores all translation results and originals
├── README.md
```

---

## Technical Details

- **Transcription & alignment**: [WhisperX](https://github.com/m-bain/whisperx)
- **Translation**: Local Ollama LLM (default: `qwen3:8b`)
- **Speech synthesis**: [gTTS](https://pypi.org/project/gTTS/)
- **Subtitles**: Generated in `.srt` format and can be burned into the video
- **History**: Each translation is saved in a unique folder under `history/` with original, translated, and subtitle files

---

## Limitations

- Ollama server must be running before using the app.
- gTTS requires an internet connection for speech synthesis.
- Long videos may take several minutes to process.
- Only `.mp4` video files are supported for upload.
- If you are in China, you must use a VPN to access gTTS. If you encounter issues while using the app with a VPN, try disabling the HTTP Proxy in your system settings.