"""
Audio compression utility for speech-to-text processing.
Compresses audio files to reduce size while maintaining speech quality.
"""
import subprocess
import tempfile
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum file size before compression (45MB to stay under Supabase 50MB limit)
MAX_AUDIO_SIZE_BYTES = 45 * 1024 * 1024  # 45 MB

# Compression settings optimized for speech-to-text
# Mono channel, 16kHz sample rate, low bitrate for speech
AUDIO_COMPRESSION_SETTINGS = [
    "-ac", "1",           # Convert to mono (single channel)
    "-ar", "16000",       # Sample rate: 16kHz (sufficient for speech)
    "-b:a", "32k",        # Audio bitrate: 32kbps (low bitrate for speech)
    "-acodec", "libmp3lame",  # Use MP3 codec
]


def compress_audio(file_bytes: bytes, input_format: str = "m4a") -> Optional[bytes]:
    """
    Compress audio file for speech-to-text processing.
    
    Optimizes audio for speech recognition:
    - Converts to mono (single channel)
    - Reduces sample rate to 16kHz
    - Low bitrate (32kbps) suitable for speech
    
    Args:
        file_bytes: Original audio file content as bytes
        input_format: Input audio format (e.g., "m4a", "mp3", "wav")
    
    Returns:
        Compressed audio bytes, or None if compression fails
    """
    if not file_bytes:
        return None
    
    # Initialize paths to None to ensure they're defined in finally block
    input_path = None
    output_path = None
    
    # Create temporary files for input and output
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{input_format}") as input_file:
            input_path = input_file.name
            input_file.write(file_bytes)
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as output_file:
            output_path = output_file.name
        
        # Build ffmpeg command
        # -i: input file
        # -y: overwrite output file without asking
        # Compression settings from AUDIO_COMPRESSION_SETTINGS
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-y",  # Overwrite output file
        ] + AUDIO_COMPRESSION_SETTINGS + [
            output_path
        ]
        
        # Run ffmpeg compression
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Audio compression failed: {result.stderr}")
            return None
        
        
        # Read compressed file
        with open(output_path, "rb") as f:
            compressed_bytes = f.read()
        
        logger.info(
            f"Audio compressed: {len(file_bytes)} bytes -> {len(compressed_bytes)} bytes "
            f"({len(compressed_bytes) / len(file_bytes) * 100:.1f}% of original)"
        )
        
        return compressed_bytes
        
    except subprocess.TimeoutExpired:
        logger.error("Audio compression timed out after 60 seconds")
        return None
    except Exception as e:
        logger.error(f"Audio compression error: {str(e)}")
        return None
    finally:
        # Clean up temporary files
        # Check if paths are defined before attempting cleanup
        try:
            if input_path and os.path.exists(input_path):
                os.unlink(input_path)
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
        except Exception as e:
            logger.warning(f"Failed to clean up temp files: {str(e)}")


def validate_audio_size(file_bytes: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate audio file size before upload.
    
    Args:
        file_bytes: Audio file content as bytes
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    file_size = len(file_bytes)
    
    if file_size > MAX_AUDIO_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        max_mb = MAX_AUDIO_SIZE_BYTES / (1024 * 1024)
        return False, f"Audio file too large: {size_mb:.1f}MB. Maximum allowed: {max_mb}MB"
    
    return True, None
