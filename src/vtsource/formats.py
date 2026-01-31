"""
Video format specifications for NTSC and PAL
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Tuple


class ColorSpace(Enum):
    """Output colorspace options"""
    RGB24 = 0    # 24-bit RGB, 3 bytes per pixel
    YUV422 = 1   # 4:2:2 packed (UYVY), 2 bytes per pixel
    YUV420P = 2  # 4:2:0 planar, 1.5 bytes per pixel
    
    @property
    def bytes_per_pixel(self) -> float:
        """Average bytes per pixel for this colorspace"""
        return {
            ColorSpace.RGB24: 3.0,
            ColorSpace.YUV422: 2.0,
            ColorSpace.YUV420P: 1.5,
        }[self]


class VideoStandard(Enum):
    """Video standard (NTSC or PAL)"""
    NTSC = auto()
    PAL = auto()


@dataclass(frozen=True)
class VideoFormat:
    """
    Video format specification
    
    Defines resolution, frame rate, and colorspace for video output.
    """
    width: int
    height: int
    frame_rate_num: int
    frame_rate_den: int
    colorspace: ColorSpace
    standard: VideoStandard
    pixel_aspect_num: int = 1
    pixel_aspect_den: int = 1
    
    @classmethod
    def ntsc(cls, colorspace: ColorSpace = ColorSpace.RGB24) -> 'VideoFormat':
        """
        Create NTSC format specification
        
        NTSC: 720x486, 29.97fps, 10:11 pixel aspect ratio
        """
        return cls(
            width=720,
            height=486,
            frame_rate_num=30000,
            frame_rate_den=1001,
            colorspace=colorspace,
            standard=VideoStandard.NTSC,
            pixel_aspect_num=10,
            pixel_aspect_den=11,
        )
    
    @classmethod
    def pal(cls, colorspace: ColorSpace = ColorSpace.RGB24) -> 'VideoFormat':
        """
        Create PAL format specification
        
        PAL: 720x576, 25fps, 59:54 pixel aspect ratio
        """
        return cls(
            width=720,
            height=576,
            frame_rate_num=25,
            frame_rate_den=1,
            colorspace=colorspace,
            standard=VideoStandard.PAL,
            pixel_aspect_num=59,
            pixel_aspect_den=54,
        )
    
    @property
    def frame_rate(self) -> float:
        """Frame rate as floating point"""
        return self.frame_rate_num / self.frame_rate_den
    
    @property
    def frame_duration_ms(self) -> float:
        """Duration of one frame in milliseconds"""
        return (self.frame_rate_den / self.frame_rate_num) * 1000
    
    @property
    def frame_duration_us(self) -> int:
        """Duration of one frame in microseconds"""
        return int((self.frame_rate_den / self.frame_rate_num) * 1_000_000)
    
    @property
    def pixel_aspect_ratio(self) -> float:
        """Pixel aspect ratio as floating point"""
        return self.pixel_aspect_num / self.pixel_aspect_den
    
    @property
    def display_aspect_ratio(self) -> Tuple[int, int]:
        """Display aspect ratio (typically 4:3 for SD video)"""
        return (4, 3)
    
    @property
    def frame_size_bytes(self) -> int:
        """Size of one frame in bytes"""
        return int(self.width * self.height * self.colorspace.bytes_per_pixel)
    
    @property 
    def data_rate_mbps(self) -> float:
        """Uncompressed data rate in megabits per second"""
        bytes_per_second = self.frame_size_bytes * self.frame_rate
        return (bytes_per_second * 8) / 1_000_000
    
    def __str__(self) -> str:
        return (
            f"{self.standard.name} {self.width}x{self.height} "
            f"@ {self.frame_rate:.2f}fps {self.colorspace.name}"
        )


# Pre-defined format constants for convenience
NTSC_RGB24 = VideoFormat.ntsc(ColorSpace.RGB24)
NTSC_YUV422 = VideoFormat.ntsc(ColorSpace.YUV422)
PAL_RGB24 = VideoFormat.pal(ColorSpace.RGB24)
PAL_YUV422 = VideoFormat.pal(ColorSpace.YUV422)
