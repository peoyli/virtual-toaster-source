"""Tests for video format specifications"""

import pytest
from vtsd.formats import VideoFormat, ColorSpace, VideoStandard


class TestVideoFormat:
    
    def test_ntsc_defaults(self):
        fmt = VideoFormat.ntsc()
        assert fmt.width == 720
        assert fmt.height == 486
        assert fmt.frame_rate_num == 30000
        assert fmt.frame_rate_den == 1001
        assert fmt.colorspace == ColorSpace.RGB24
        assert fmt.standard == VideoStandard.NTSC
    
    def test_pal_defaults(self):
        fmt = VideoFormat.pal()
        assert fmt.width == 720
        assert fmt.height == 576
        assert fmt.frame_rate_num == 25
        assert fmt.frame_rate_den == 1
        assert fmt.colorspace == ColorSpace.RGB24
        assert fmt.standard == VideoStandard.PAL
    
    def test_ntsc_frame_rate(self):
        fmt = VideoFormat.ntsc()
        assert abs(fmt.frame_rate - 29.97) < 0.01
    
    def test_pal_frame_rate(self):
        fmt = VideoFormat.pal()
        assert fmt.frame_rate == 25.0
    
    def test_ntsc_frame_duration(self):
        fmt = VideoFormat.ntsc()
        # 1001/30000 * 1000 ≈ 33.367 ms
        assert abs(fmt.frame_duration_ms - 33.367) < 0.01
    
    def test_pal_frame_duration(self):
        fmt = VideoFormat.pal()
        assert fmt.frame_duration_ms == 40.0
    
    def test_frame_size_rgb24(self):
        fmt = VideoFormat.ntsc(ColorSpace.RGB24)
        assert fmt.frame_size_bytes == 720 * 486 * 3
    
    def test_frame_size_yuv422(self):
        fmt = VideoFormat.ntsc(ColorSpace.YUV422)
        assert fmt.frame_size_bytes == 720 * 486 * 2
    
    def test_format_string(self):
        fmt = VideoFormat.ntsc()
        s = str(fmt)
        assert "NTSC" in s
        assert "720x486" in s
        assert "29.97" in s


class TestColorSpace:
    
    def test_bytes_per_pixel(self):
        assert ColorSpace.RGB24.bytes_per_pixel == 3.0
        assert ColorSpace.YUV422.bytes_per_pixel == 2.0
        assert ColorSpace.YUV420P.bytes_per_pixel == 1.5
