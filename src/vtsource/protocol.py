"""
VTS Network Protocol

Defines the protocol for communication between VTS daemon and clients.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class FrameFlags(IntEnum):
    """Flags for frame header"""
    NONE = 0
    KEYFRAME = 1 << 0
    FIELD_1 = 1 << 1   # First field (for interlaced)
    FIELD_2 = 1 << 2   # Second field (for interlaced)
    END_OF_STREAM = 1 << 3


@dataclass
class FrameHeader:
    """
    Header prepended to each frame transmission
    
    Format (16 bytes, big-endian):
        uint32  sequence     - Frame sequence number
        uint32  timestamp_ms - Timestamp in milliseconds
        uint16  width        - Frame width in pixels
        uint16  height       - Frame height in pixels
        uint8   colorspace   - ColorSpace enum value
        uint8   flags        - FrameFlags bitmap
        uint16  reserved     - Reserved for future use
    """
    sequence: int
    timestamp_ms: int
    width: int
    height: int
    colorspace: int
    flags: int
    reserved: int = 0
    
    FORMAT = '>IIHHHBB'  # Big-endian
    SIZE = struct.calcsize(FORMAT)  # Should be 16 bytes
    
    def pack(self) -> bytes:
        """Serialize header to bytes"""
        return struct.pack(
            self.FORMAT,
            self.sequence,
            self.timestamp_ms,
            self.width,
            self.height,
            self.colorspace,
            self.flags,
            self.reserved
        )
    
    @classmethod
    def unpack(cls, data: bytes) -> 'FrameHeader':
        """Deserialize header from bytes"""
        if len(data) < cls.SIZE:
            raise ValueError(f"Header requires {cls.SIZE} bytes, got {len(data)}")
        
        seq, ts, w, h, cs, flags, reserved = struct.unpack(cls.FORMAT, data[:cls.SIZE])
        return cls(seq, ts, w, h, cs, flags, reserved)
    
    @property
    def is_keyframe(self) -> bool:
        return bool(self.flags & FrameFlags.KEYFRAME)
    
    @property
    def is_end_of_stream(self) -> bool:
        return bool(self.flags & FrameFlags.END_OF_STREAM)


class Command:
    """Protocol command definitions"""
    
    # Connection management
    HELLO = "HELLO"
    BYE = "BYE"
    
    # File operations
    LIST = "LIST"
    LOAD = "LOAD"
    
    # Playback control
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    STOP = "STOP"
    
    # Navigation
    SEEK = "SEEK"
    NEXT = "NEXT"
    PREV = "PREV"
    
    # Frame retrieval
    GETFRAME = "GETFRAME"
    
    # Configuration
    FORMAT = "FORMAT"
    LOOP = "LOOP"
    
    # Status
    STATUS = "STATUS"
    INFO = "INFO"

    # Extended status
    SOURCE = "SOURCE"
    FRAMEINFO = "FRAMEINFO"

class Response:
    """Protocol response definitions"""
    
    OK = "OK"
    ERROR = "ERROR"
    
    # Specific OK responses
    HELLO = "OK HELLO"
    BYE = "OK BYE"
    LOADED = "OK LOADED"
    PLAYING = "OK PLAYING"
    PAUSED = "OK PAUSED"
    STOPPED = "OK STOPPED"
    SEEKED = "OK SEEKED"
    FRAMEDATA = "OK FRAMEDATA"
    STATUS = "OK STATUS"


class ErrorCode(IntEnum):
    """Error codes for ERROR responses"""
    UNKNOWN_COMMAND = 400
    INVALID_ARGUMENT = 401
    FILE_NOT_FOUND = 404
    INTERNAL_ERROR = 500
    NOT_LOADED = 501


def parse_command(line: str) -> tuple[str, list[str]]:
    """
    Parse a command line into command and arguments
    
    Args:
        line: Command line string
        
    Returns:
        Tuple of (command, [arguments])
    """
    parts = line.strip().split(maxsplit=1)
    if not parts:
        return "", []
    
    command = parts[0].upper()
    
    if len(parts) > 1:
        # Handle quoted arguments for file paths with spaces
        args = []
        remainder = parts[1]
        
        while remainder:
            remainder = remainder.lstrip()
            if not remainder:
                break
                
            if remainder.startswith('"'):
                # Quoted argument
                end = remainder.find('"', 1)
                if end == -1:
                    args.append(remainder[1:])
                    break
                args.append(remainder[1:end])
                remainder = remainder[end+1:]
            else:
                # Unquoted argument
                space = remainder.find(' ')
                if space == -1:
                    args.append(remainder)
                    break
                args.append(remainder[:space])
                remainder = remainder[space+1:]
        
        return command, args
    
    return command, []


def format_error(code: ErrorCode, message: str) -> str:
    """Format an error response"""
    return f"{Response.ERROR} {code.value} {message}"


def format_status(state: str, frame: int, total: int) -> str:
    """Format a status response"""
    return f"{Response.STATUS} {state} {frame} {total}"
