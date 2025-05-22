import pytest
import sys
import os 
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from unittest.mock import patch, MagicMock, mock_open
from diarization.transcription_pyannote import format_timestamp, translate_text, translation_process, put_subtitle_on_video, transcribe_video, main

def test_format_timestamp_basic():
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(1.234) == "00:00:01,234"
    assert format_timestamp(3661.789) == "01:01:01,789"

@patch("transcription.translator")
def test_translate_text_empty(mock_translator):
    assert translate_text("", "fr") == ""
    assert translate_text("   ", "fr") == ""
    mock_translator.translate_text.assert_not_called()

@patch("transcription.translator")
def test_translate_text_nonempty(mock_translator):
    mock_translator.translate_text.return_value.text = "Bonjour"
    assert translate_text("Hello", "fr") == "Bonjour"
    mock_translator.translate_text.assert_called_once_with("Hello", target_lang="fr")

@patch("transcription.translate_text")
def test_translation_process_translates_only_text(mock_translate_text):
    mock_translate_text.side_effect = lambda text, lang: f"XX-{text}-XX"
    srt_content = [
        "1\n00:00:01,000 --> 00:00:05,000\nHello, how are you?\n",
        "2\n00:00:06,000 --> 00:00:10,000\nI am fine, thank you!\n"
    ]
    result = translation_process("fr", srt_content)
    assert "XX-Hello, how are you?-XX" in result[0]
    assert "XX-I am fine, thank you!-XX" in result[1]

@patch("transcription.subprocess.run")
def test_put_subtitle_on_video_calls_ffmpeg(mock_run):
    put_subtitle_on_video("video.mp4", "subs.srt")
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "ffmpeg" in args[0]
    assert "-i" in args
    assert "video.mp4" in args
    assert "subs.srt" in "".join(args)

@patch("transcription.WhisperModel")
def test_transcribe_video_formats_srt(mock_model_cls):
    mock_model = MagicMock()
    mock_model_cls.return_value = mock_model
    mock_info = MagicMock()
    mock_info.language = "en"
    mock_model.transcribe.side_effect = [
        (None, mock_info),
        ([MagicMock(start=1.0, end=2.0, text="Hello")], None)
    ]
    srt = transcribe_video("video.mp4")
    assert srt[0].startswith("1\n")
    assert "Hello" in srt[0]

@patch("transcription.put_subtitle_on_video")
@patch("transcription.translation_process")
@patch("transcription.transcribe_video")
@patch("builtins.open", new_callable=mock_open)
def test_main_runs_all_steps(mock_open_fn, mock_transcribe, mock_translate, mock_put_subs):
    mock_transcribe.return_value = ["1\n00:00:01,000 --> 00:00:05,000\nHello\n"]
    mock_translate.return_value = ["1\n00:00:01,000 --> 00:00:05,000\nBonjour\n"]
    main("video.mp4", "fr")
    assert mock_transcribe.called
    assert mock_translate.called
    assert mock_put_subs.called
    assert mock_open_fn.call_count == 2