# Requirements

## Python
Download & Install
    
   [Python Official Website](https://www.python.org/downloads/)
        
   Ensure you check  **"Add Python to PATH"**  during installation.

## torch (PyTorch)
Installation :

**macOS (CPU-only)** :
	
    pip install torch
  **Windows (CPU-only)** :
  

    pip install torch


**GPU Support (CUDA)** :  
    Visit  [PyTorch Official Install Guide](https://pytorch.org/get-started/locally/)  for CUDA-compatible versions.

## transformers (Hugging Face)

Installation (macOS & Windows) :

    pip install transformers
**Website**:  [Hugging Face Transformers](https://huggingface.co/transformers/)

## faster_whisper ( Faster Whisper Transcription)
Installation:

**macOS** :

    pip install faster-whisper

 **Windows**

    pip install faster-whisper

 Additional Dependencies (if errors occur) :
    
   -> Install  **FFmpeg**:
        
 **macOS**:  `brew install ffmpeg`
            
   **Windows**: Download from  [FFmpeg Official Site](https://ffmpeg.org/download.html)  and add to  `PATH`.
## Git LFS

Github supports files to a certain extent in terms of size. For the long videos, I used git LFS (Large File Sharing). Here's how to install it : 
On Mac, open your terminal, and type : 

    brew install git_lfs
    git lfs install

**FYI**

    git lfs track "*.mp4"
This line allows LFS to convert the big files into adresses on it's servers.



