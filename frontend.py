import streamlit as st
import transcription
import os
from pathlib import Path

# Set page config
st.set_page_config(page_title="Video Subtitle Viewer", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .stVideo {
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .stSelectbox > div > div {
        background-color: #f0f2f6;
        border-radius: 5px;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("🎬 Video Subtitle Viewer")
    st.write("Upload your MP4 video and choose subtitle language")

    # Video upload
    uploaded_file = st.file_uploader("Choose video file", type=["mp4"], accept_multiple_files=False)

    if uploaded_file:
        # Save uploaded file temporarily
        temp_dir = Path("temp_videos")
        temp_dir.mkdir(exist_ok=True)
        
        original_path = temp_dir / "original.mp4"
        with open(original_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Display original video
        st.subheader("Original Video")
        st.video(str(original_path))

        # Language selection
        st.subheader("🌍 Subtitle Options")
        languages = {
            "Arabic":"AR",
            "Bulgarian":"BG",
            "Czech":"CZ",
            "Danish":"DA",
            "German":"DE",
            "Greek":"EL",
            "English (Great Britain)":"EN-GB",
            "English (United States)":"EN-US",
            "Spanish":"ES",
            "Estonian":"ET",
            "Finnish":"FI",
            "French":"FR",
            "Hungarian":"HU",
            "Indonesian":"ID",
            "Italian":"IT",
            "Japanese":"JA",
            "Korean":"KO",
            "Lithuanian":"LT",
            "Latvian":"LV",
            "Norwegian Bohmål":"NO",
            "Dutch":"NL",
            "Polish":"PL",
            "Portuguese (Brazilian)":"PT-BR",
            "Portuguese (European)":"PT-PT",
            "Romanian":"RO",
            "Russian":"RU",
            "Slovak":"SK",
            "Slovenian":"SL",
            "Swedish":"SV",
            "Turkish":"TR",
            "Ukrainian":"UK",
            "Chinese (Simplified)":"ZH-HANS",
            "Chinese (Traditional)":"ZH-HANT",
        }
        
        selected_lang = st.selectbox(
            "Select subtitle language",
            options=list(languages.keys()),
            index=0
        )

        # Display button
        if st.button("Show Subtitled Version"):
            # In your actual app, replace this with loading your pre-made subtitle video
            st.subheader(f"Video with {selected_lang} Subtitles")
            
            # Placeholder - replace with your actual subtitle video path
            subtitle_video_path = temp_dir / languages[selected_lang]
            
            # For demo, we'll just show the original again
            st.video(str(original_path))
            
            # Download button would use your actual subtitle video
            with open(original_path, "rb") as f:
                st.download_button(
                    label=f"Download {selected_lang} Version",
                    data=f,
                    file_name=languages[selected_lang],
                    mime="video/mp4"
                )

        # Clean up
        if st.button("Clear Files"):
            for file in temp_dir.glob("*"):
                file.unlink()
            st.success("Temporary files cleared!")

if __name__ == "__main__":
    main()