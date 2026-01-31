"""Tests for protocol handling"""

import pytest
from vtsource.protocol import (
    FrameHeader, FrameFlags, Command, Response, ErrorCode,
    parse_command, format_error, format_status
)


class TestFrameHeader:
    
    def test_header_size(self):
        """Header should be exactly 16 bytes"""
        assert FrameHeader.SIZE == 16
    
    def test_pack_unpack_roundtrip(self):
        """Packing and unpacking should preserve values"""
        header = FrameHeader(
            sequence=12345,
            timestamp_ms=67890,
            width=720,
            height=486,
            colorspace=0,
            flags=FrameFlags.KEYFRAME,
        )
        
        packed = header.pack()
        assert len(packed) == FrameHeader.SIZE
        
        unpacked = FrameHeader.unpack(packed)
        assert unpacked.sequence == 12345
        assert unpacked.timestamp_ms == 67890
        assert unpacked.width == 720
        assert unpacked.height == 486
        assert unpacked.colorspace == 0
        assert unpacked.flags == FrameFlags.KEYFRAME
    
    def test_is_keyframe(self):
        header = FrameHeader(0, 0, 720, 486, 0, FrameFlags.KEYFRAME)
        assert header.is_keyframe
        
        header2 = FrameHeader(0, 0, 720, 486, 0, 0)
        assert not header2.is_keyframe
    
    def test_is_end_of_stream(self):
        header = FrameHeader(0, 0, 720, 486, 0, FrameFlags.END_OF_STREAM)
        assert header.is_end_of_stream


class TestParseCommand:
    
    def test_simple_command(self):
        cmd, args = parse_command("PLAY")
        assert cmd == "PLAY"
        assert args == []
    
    def test_command_with_args(self):
        cmd, args = parse_command("SEEK 100")
        assert cmd == "SEEK"
        assert args == ["100"]
    
    def test_command_case_insensitive(self):
        cmd, args = parse_command("play")
        assert cmd == "PLAY"
    
    def test_quoted_path(self):
        cmd, args = parse_command('LOAD "/path/with spaces/video.mp4"')
        assert cmd == "LOAD"
        assert args == ["/path/with spaces/video.mp4"]
    
    def test_multiple_args(self):
        cmd, args = parse_command("FORMAT NTSC RGB24")
        assert cmd == "FORMAT"
        assert args == ["NTSC", "RGB24"]
    
    def test_empty_line(self):
        cmd, args = parse_command("")
        assert cmd == ""
        assert args == []
    
    def test_whitespace_handling(self):
        cmd, args = parse_command("  PLAY  ")
        assert cmd == "PLAY"


class TestFormatters:
    
    def test_format_error(self):
        result = format_error(ErrorCode.FILE_NOT_FOUND, "Not found")
        assert result == "ERROR 404 Not found"
    
    def test_format_status(self):
        result = format_status("PLAYING", 42, 1000)
        assert result == "OK STATUS PLAYING 42 1000"
