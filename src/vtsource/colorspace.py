"""
Colorspace conversion utilities

Provides efficient conversion between RGB and YUV colorspaces
using NumPy for performance.
"""

import numpy as np
from numpy.typing import NDArray


# BT.601 conversion coefficients (standard definition video)
# These match what the Video Toaster would have used
BT601_KR = 0.299
BT601_KG = 0.587
BT601_KB = 0.114


def rgb24_to_yuv444(rgb: NDArray[np.uint8]) -> tuple[NDArray, NDArray, NDArray]:
    """
    Convert RGB24 to YUV444 (full resolution Y, U, V planes)
    
    Args:
        rgb: Input array of shape (height, width, 3), dtype uint8
        
    Returns:
        Tuple of (Y, U, V) arrays, each shape (height, width), dtype uint8
    """
    # Convert to float for precision
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    
    # BT.601 conversion
    y = BT601_KR * r + BT601_KG * g + BT601_KB * b
    u = (b - y) / (2 * (1 - BT601_KB)) + 128
    v = (r - y) / (2 * (1 - BT601_KR)) + 128
    
    # Clip and convert back to uint8
    y = np.clip(y, 0, 255).astype(np.uint8)
    u = np.clip(u, 0, 255).astype(np.uint8)
    v = np.clip(v, 0, 255).astype(np.uint8)
    
    return y, u, v


def rgb24_to_yuv422_uyvy(rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """
    Convert RGB24 to YUV422 packed (UYVY format)
    
    UYVY packing: U0 Y0 V0 Y1 | U2 Y2 V2 Y3 | ...
    Each 4-byte group contains 2 pixels.
    
    Args:
        rgb: Input array of shape (height, width, 3), dtype uint8
             Width must be even.
        
    Returns:
        Array of shape (height, width*2), dtype uint8
    """
    height, width = rgb.shape[:2]
    
    if width % 2 != 0:
        raise ValueError(f"Width must be even, got {width}")
    
    y, u, v = rgb24_to_yuv444(rgb)
    
    # Subsample U and V horizontally (average adjacent pixels)
    u_sub = ((u[:, 0::2].astype(np.uint16) + u[:, 1::2].astype(np.uint16)) // 2).astype(np.uint8)
    v_sub = ((v[:, 0::2].astype(np.uint16) + v[:, 1::2].astype(np.uint16)) // 2).astype(np.uint8)
    
    # Pack as UYVY
    uyvy = np.zeros((height, width * 2), dtype=np.uint8)
    uyvy[:, 0::4] = u_sub      # U
    uyvy[:, 1::4] = y[:, 0::2] # Y0
    uyvy[:, 2::4] = v_sub      # V
    uyvy[:, 3::4] = y[:, 1::2] # Y1
    
    return uyvy


def rgb24_to_yuv422_yuyv(rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """
    Convert RGB24 to YUV422 packed (YUYV format)
    
    YUYV packing: Y0 U0 Y1 V0 | Y2 U2 Y3 V2 | ...
    Each 4-byte group contains 2 pixels.
    
    Args:
        rgb: Input array of shape (height, width, 3), dtype uint8
             Width must be even.
        
    Returns:
        Array of shape (height, width*2), dtype uint8
    """
    height, width = rgb.shape[:2]
    
    if width % 2 != 0:
        raise ValueError(f"Width must be even, got {width}")
    
    y, u, v = rgb24_to_yuv444(rgb)
    
    # Subsample U and V horizontally
    u_sub = ((u[:, 0::2].astype(np.uint16) + u[:, 1::2].astype(np.uint16)) // 2).astype(np.uint8)
    v_sub = ((v[:, 0::2].astype(np.uint16) + v[:, 1::2].astype(np.uint16)) // 2).astype(np.uint8)
    
    # Pack as YUYV
    yuyv = np.zeros((height, width * 2), dtype=np.uint8)
    yuyv[:, 0::4] = y[:, 0::2] # Y0
    yuyv[:, 1::4] = u_sub      # U
    yuyv[:, 2::4] = y[:, 1::2] # Y1
    yuyv[:, 3::4] = v_sub      # V
    
    return yuyv


def rgb24_to_yuv420p(rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """
    Convert RGB24 to YUV420P (planar format)
    
    YUV420P layout: [Y plane][U plane][V plane]
    Y: full resolution
    U, V: half resolution in both dimensions
    
    Args:
        rgb: Input array of shape (height, width, 3), dtype uint8
             Width and height must be even.
        
    Returns:
        Flat array of shape (height * width * 1.5,), dtype uint8
    """
    height, width = rgb.shape[:2]
    
    if width % 2 != 0 or height % 2 != 0:
        raise ValueError(f"Width and height must be even, got {width}x{height}")
    
    y, u, v = rgb24_to_yuv444(rgb)
    
    # Subsample U and V in both dimensions (2x2 averaging)
    u_sub = u.reshape(height // 2, 2, width // 2, 2).mean(axis=(1, 3)).astype(np.uint8)
    v_sub = v.reshape(height // 2, 2, width // 2, 2).mean(axis=(1, 3)).astype(np.uint8)
    
    # Concatenate planes
    return np.concatenate([
        y.flatten(),
        u_sub.flatten(),
        v_sub.flatten()
    ])


def yuv422_uyvy_to_rgb24(uyvy: NDArray[np.uint8], height: int, width: int) -> NDArray[np.uint8]:
    """
    Convert YUV422 packed (UYVY) back to RGB24
    
    Args:
        uyvy: Input array from rgb24_to_yuv422_uyvy
        height: Image height
        width: Image width
        
    Returns:
        Array of shape (height, width, 3), dtype uint8
    """
    uyvy = uyvy.reshape(height, width * 2)
    
    # Extract components
    u = uyvy[:, 0::4].astype(np.float32)
    y0 = uyvy[:, 1::4].astype(np.float32)
    v = uyvy[:, 2::4].astype(np.float32)
    y1 = uyvy[:, 3::4].astype(np.float32)
    
    # Expand U and V to full width
    u_full = np.repeat(u, 2, axis=1)
    v_full = np.repeat(v, 2, axis=1)
    
    # Interleave Y values
    y_full = np.zeros((height, width), dtype=np.float32)
    y_full[:, 0::2] = y0
    y_full[:, 1::2] = y1
    
    # Convert to RGB (BT.601 inverse)
    u_full -= 128
    v_full -= 128
    
    r = y_full + 1.402 * v_full
    g = y_full - 0.344136 * u_full - 0.714136 * v_full
    b = y_full + 1.772 * u_full
    
    # Clip and combine
    rgb = np.stack([
        np.clip(r, 0, 255).astype(np.uint8),
        np.clip(g, 0, 255).astype(np.uint8),
        np.clip(b, 0, 255).astype(np.uint8),
    ], axis=2)
    
    return rgb
