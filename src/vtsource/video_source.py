"""
Video source management

Handles loading, decoding, and serving video frames.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional
from collections import OrderedDict

import av
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from .formats import VideoFormat, ColorSpace
from .colorspace import rgb24_to_yuv422_uyvy, rgb24_to_yuv420p


logger = logging.getLogger(__name__)


class PlayState(Enum):
    """Playback state"""
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


@dataclass
class VideoInfo:
    """Information about loaded video"""
    filepath: Path
    width: int
    height: int
    frame_count: int
    frame_rate: float
    duration_seconds: float
    codec: str
    pixel_format: str


class FrameCache:
    """
    LRU cache for decoded frames
    
    Caches recently accessed frames to avoid redundant decoding.
    """
    
    def __init__(self, max_size: int = 30):
        self.max_size = max_size
        self._cache: OrderedDict[int, NDArray] = OrderedDict()
    
    def get(self, frame_number: int) -> Optional[NDArray]:
        """Get frame from cache, updating LRU order"""
        if frame_number in self._cache:
            self._cache.move_to_end(frame_number)
            return self._cache[frame_number]
        return None
    
    def put(self, frame_number: int, frame: NDArray):
        """Add frame to cache, evicting oldest if necessary"""
        if frame_number in self._cache:
            self._cache.move_to_end(frame_number)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            self._cache[frame_number] = frame
    
    def clear(self):
        """Clear all cached frames"""
        self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)


class VideoSource:
    """
    Manages a video file as a frame source
    
    Handles loading, seeking, and frame extraction with format conversion.
    """
    
    def __init__(self, output_format: VideoFormat, cache_size: int = 30):
        """
        Initialize video source
        
        Args:
            output_format: Target output format (NTSC/PAL, colorspace)
            cache_size: Number of frames to cache
        """
        self.output_format = output_format
        self.cache = FrameCache(max_size=cache_size)
        
        self._container: Optional[av.container.InputContainer] = None
        self._stream: Optional[av.video.stream.VideoStream] = None
        self._info: Optional[VideoInfo] = None
        
        self._state = PlayState.STOPPED
        self._current_frame: int = 0
        self._loop: bool = False
        
        # Reusable resampler for scaling
        self._resampler: Optional[av.video.reformatter.VideoReformatter] = None
    
    @property
    def state(self) -> PlayState:
        return self._state
    
    @state.setter
    def state(self, value: PlayState):
        self._state = value
    
    @property
    def current_frame(self) -> int:
        return self._current_frame
    
    @property
    def total_frames(self) -> int:
        return self._info.frame_count if self._info else 0
    
    @property
    def loop(self) -> bool:
        return self._loop
    
    @loop.setter
    def loop(self, value: bool):
        self._loop = value
    
    @property
    def info(self) -> Optional[VideoInfo]:
        return self._info
    
    @property
    def is_loaded(self) -> bool:
        return self._container is not None
    
    def load(self, filepath: Path) -> bool:
        """
        Load a video file
        
        Args:
            filepath: Path to video file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.close()
            
            self._container = av.open(str(filepath))
            self._stream = self._container.streams.video[0]
            
            # Calculate frame count
            if self._stream.frames and self._stream.frames > 0:
                frame_count = self._stream.frames
            elif self._stream.duration:
                duration = float(self._stream.duration * self._stream.time_base)
                fps = float(self._stream.average_rate or self._stream.base_rate or 30)
                frame_count = int(duration * fps)
            else:
                # Last resort: scan the file
                frame_count = self._count_frames()
            
            # Build video info
            self._info = VideoInfo(
                filepath=filepath,
                width=self._stream.width,
                height=self._stream.height,
                frame_count=frame_count,
                frame_rate=float(self._stream.average_rate or 30),
                duration_seconds=frame_count / float(self._stream.average_rate or 30),
                codec=self._stream.codec_context.name,
                pixel_format=self._stream.pix_fmt or "unknown",
            )
            
            self._current_frame = 0
            self._state = PlayState.STOPPED
            self.cache.clear()
            
            logger.info(f"Loaded: {filepath} ({frame_count} frames, "
                       f"{self._info.width}x{self._info.height})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            self.close()
            return False
    
    def _count_frames(self) -> int:
        """Count frames by decoding (slow, last resort)"""
        count = 0
        for _ in self._container.decode(video=0):
            count += 1
        # Reset container
        self._container.seek(0)
        return count
    
    def close(self):
        """Close current video file and release resources"""
        if self._container:
            self._container.close()
        self._container = None
        self._stream = None
        self._info = None
        self._resampler = None
        self._state = PlayState.STOPPED
        self._current_frame = 0
        self.cache.clear()
    
    def seek(self, frame_number: int) -> bool:
        """
        Seek to specific frame
        
        Args:
            frame_number: Target frame number
            
        Returns:
            True if successful
        """
        if not self._container or not self._info:
            return False
        
        frame_number = max(0, min(frame_number, self._info.frame_count - 1))
        
        try:
            # Convert frame number to timestamp
            time_base = self._stream.time_base
            fps = self._info.frame_rate
            target_pts = int(frame_number / fps / float(time_base))
            
            self._container.seek(target_pts, stream=self._stream)
            self._current_frame = frame_number
            return True
            
        except Exception as e:
            logger.error(f"Seek to frame {frame_number} failed: {e}")
            return False
    
    def get_frame(self, frame_number: Optional[int] = None) -> Optional[NDArray]:
        """
        Get a frame, scaled and converted to output format
        
        Args:
            frame_number: Specific frame to get, or None for current frame
            
        Returns:
            Frame data in output format, or None if unavailable
        """
        if not self._container:
            return None
        
        if frame_number is None:
            frame_number = self._current_frame
        
        # Check cache first
        cached = self.cache.get(frame_number)
        if cached is not None:
            return cached
        
        # Seek if necessary
        if frame_number != self._current_frame:
            if not self.seek(frame_number):
                return None
        
        try:
            # Decode frames until we get the one we want
            for frame in self._container.decode(video=0):
                # Convert to RGB24
                frame_rgb = frame.to_ndarray(format='rgb24')
                
                # Scale to output format
                scaled = self._scale_frame(frame_rgb)
                
                # Convert colorspace
                output = self._convert_colorspace(scaled)
                
                # Cache and return
                self.cache.put(frame_number, output)
                self._current_frame = frame_number
                return output
                
        except Exception as e:
            logger.error(f"Frame decode failed: {e}")
            return None
        
        return None
    
    def _scale_frame(self, frame: NDArray) -> NDArray:
        """Scale frame to output dimensions"""
        h, w = frame.shape[:2]
        target_w = self.output_format.width
        target_h = self.output_format.height
        
        if w == target_w and h == target_h:
            return frame
        
        # Use PIL for high-quality scaling
        img = Image.fromarray(frame)
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        return np.array(img)
    
    def _convert_colorspace(self, frame: NDArray) -> NDArray:
        """Convert RGB24 frame to output colorspace"""
        cs = self.output_format.colorspace
        
        if cs == ColorSpace.RGB24:
            return frame
        elif cs == ColorSpace.YUV422:
            return rgb24_to_yuv422_uyvy(frame)
        elif cs == ColorSpace.YUV420P:
            return rgb24_to_yuv420p(frame)
        else:
            logger.warning(f"Unknown colorspace {cs}, returning RGB24")
            return frame
    
    def advance(self) -> bool:
        """
        Advance to next frame
        
        Returns:
            True if advanced, False if at end (and not looping)
        """
        if not self._info:
            return False
        
        if self._current_frame < self._info.frame_count - 1:
            self._current_frame += 1
            return True
        elif self._loop:
            self._current_frame = 0
            self.seek(0)
            return True
        return False
    
    def retreat(self) -> bool:
        """
        Go back one frame
        
        Returns:
            True if moved back, False if at start
        """
        if self._current_frame > 0:
            self._current_frame -= 1
            return True
        return False
