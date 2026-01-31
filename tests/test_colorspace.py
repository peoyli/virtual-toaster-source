"""Tests for colorspace conversion"""

import pytest
import numpy as np
from vtsource.colorspace import (
    rgb24_to_yuv444,
    rgb24_to_yuv422_uyvy,
    rgb24_to_yuv420p,
    yuv422_uyvy_to_rgb24,
)


class TestRGBtoYUV:
    
    def test_rgb_to_yuv444_black(self):
        """Black should convert to Y=0, U=128, V=128"""
        rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        y, u, v = rgb24_to_yuv444(rgb)
        
        assert y.shape == (2, 2)
        assert np.all(y == 0)
        assert np.all(u == 128)
        assert np.all(v == 128)
    
    def test_rgb_to_yuv444_white(self):
        """White should convert to Y=255, U=128, V=128"""
        rgb = np.full((2, 2, 3), 255, dtype=np.uint8)
        y, u, v = rgb24_to_yuv444(rgb)
        
        assert np.all(y == 255)
        assert np.allclose(u, 128, atol=2)
        assert np.allclose(v, 128, atol=2)
    
    def test_rgb_to_yuv422_shape(self):
        """YUV422 should be width*2 bytes per row"""
        rgb = np.zeros((480, 720, 3), dtype=np.uint8)
        yuv = rgb24_to_yuv422_uyvy(rgb)
        
        assert yuv.shape == (480, 1440)
    
    def test_rgb_to_yuv422_odd_width_fails(self):
        """YUV422 requires even width"""
        rgb = np.zeros((480, 721, 3), dtype=np.uint8)
        
        with pytest.raises(ValueError):
            rgb24_to_yuv422_uyvy(rgb)
    
    def test_rgb_to_yuv420p_shape(self):
        """YUV420P should be 1.5 * width * height bytes"""
        rgb = np.zeros((480, 720, 3), dtype=np.uint8)
        yuv = rgb24_to_yuv420p(rgb)
        
        expected_size = 720 * 480 + (720 * 480 // 4) * 2
        assert yuv.shape == (expected_size,)


class TestRoundTrip:
    
    def test_yuv422_roundtrip(self):
        """Converting RGB->YUV422->RGB should be close to original"""
        # Create test pattern
        rgb = np.zeros((4, 4, 3), dtype=np.uint8)
        rgb[0:2, 0:2] = [255, 0, 0]    # Red
        rgb[0:2, 2:4] = [0, 255, 0]    # Green
        rgb[2:4, 0:2] = [0, 0, 255]    # Blue
        rgb[2:4, 2:4] = [255, 255, 0]  # Yellow
        
        yuv = rgb24_to_yuv422_uyvy(rgb)
        rgb2 = yuv422_uyvy_to_rgb24(yuv, 4, 4)
        
        # Should be close but not exact due to chroma subsampling
        # Allow some tolerance
        assert np.allclose(rgb, rgb2, atol=30)
