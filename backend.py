import torch
import audio_video_processing as av
import translation_utils as tu

"""
@brief Determine the best available device (CUDA, MPS, or CPU)

@return torch.device object for the best available device
"""
def get_device():
    if torch.cuda.is_available():
        return 'cuda'
    else:
        return 'cpu'

device = get_device()

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
    save_dir, original_video_path, extracted_audio, translated_audio, output_video, srt_path = tu.setup_directories_and_paths(input_video_path, save_dir)

    # Extract audio and transcribe to get original segments
    original_segments, formatted_text, src_lang = tu.extract_and_transcribe(original_video_path, extracted_audio, status_callback, progress_callback,device)

    # Translate the transcribed text
    translated_segments = tu.translate_segments(formatted_text, original_segments, src_lang, tgt_lang, status_callback)

    # Generate translated audio if requested
    if translate_audio:
        av.synthesize_and_combine_audio(translated_segments, tgt_lang, translated_audio, status_callback, progress_callback)
        av.combine_video_audio(original_video_path, translated_audio, output_video, status_callback, progress_callback)
        video_for_subs = output_video
    else:
        # Use original video if not translating audio
        video_for_subs = original_video_path

    # Add subtitles if requested
    if add_subtitles:
        av.add_subtitles_to_video(translated_segments, video_for_subs, srt_path, output_video, save_dir, status_callback, progress_callback)
    
    # Final progress update
    if progress_callback: progress_callback(1.0)

    # Return paths to all generated files (kept in history directory)
    return {
        "history_dir": save_dir,
        "original_video": original_video_path,
        "translated_video": output_video,
        "srt": srt_path
    }