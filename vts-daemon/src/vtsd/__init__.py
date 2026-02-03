"""
Virtual Toaster Source (VTS)
Video source daemon for Video Toaster emulation
"""

__version__ = "0.1.0"
__author__ = "VTS Contributors"

from .formats import VideoFormat, ColorSpace
from .video_source import VideoSource, PlayState
from .protocol import FrameHeader

__all__ = [
    "VideoFormat",
    "ColorSpace", 
    "VideoSource",
    "PlayState",
    "FrameHeader",
    "__version__",
]
