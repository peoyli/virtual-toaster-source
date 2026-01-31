"""
VTS Daemon - Video source server

Serves video frames over TCP to clients.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .formats import VideoFormat, ColorSpace, VideoStandard
from .video_source import VideoSource, PlayState
from .protocol import (
    FrameHeader, FrameFlags, Command, Response, ErrorCode,
    parse_command, format_error, format_status
)


logger = logging.getLogger(__name__)


class DaemonProtocol(asyncio.Protocol):
    """
    Protocol handler for daemon client connections
    
    Each client connection gets its own protocol instance,
    but shares the video source (for now - could be extended
    to per-client sources).
    """
    
    def __init__(self, source: VideoSource, media_root: Optional[Path] = None):
        """
        Initialize protocol handler
        
        Args:
            source: Shared video source instance
            media_root: Optional root directory for media files
        """
        self.source = source
        self.media_root = media_root
        self.transport: Optional[asyncio.Transport] = None
        self.buffer = b''
        self.peername: str = "unknown"
    
    def connection_made(self, transport: asyncio.Transport):
        """Called when client connects"""
        self.transport = transport
        self.peername = str(transport.get_extra_info('peername'))
        logger.info(f"Connection from {self.peername}")
        self.send_line(f"{Response.HELLO} VTSource 0.1.0")
    
    def connection_lost(self, exc: Optional[Exception]):
        """Called when client disconnects"""
        logger.info(f"Connection closed: {self.peername}")
        if exc:
            logger.debug(f"Connection error: {exc}")
    
    def data_received(self, data: bytes):
        """Called when data received from client"""
        self.buffer += data
        
        # Process complete lines
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                command_line = line.decode('utf-8').strip()
                if command_line:
                    self.handle_command(command_line)
            except UnicodeDecodeError:
                self.send_error(ErrorCode.INVALID_ARGUMENT, "Invalid UTF-8")
    
    def handle_command(self, line: str):
        """Parse and execute a command"""
        logger.debug(f"[{self.peername}] Command: {line}")
        
        cmd, args = parse_command(line)
        
        handlers = {
            Command.LOAD: self.cmd_load,
            Command.PLAY: self.cmd_play,
            Command.PAUSE: self.cmd_pause,
            Command.STOP: self.cmd_stop,
            Command.SEEK: self.cmd_seek,
            Command.NEXT: self.cmd_next,
            Command.PREV: self.cmd_prev,
            Command.GETFRAME: self.cmd_getframe,
            Command.STATUS: self.cmd_status,
            Command.INFO: self.cmd_info,
            Command.SOURCE: self.cmd_source,
            Command.FRAMEINFO: self.cmd_frameinfo,
            Command.LOOP: self.cmd_loop,
            Command.FORMAT: self.cmd_format,
            Command.LIST: self.cmd_list,
            Command.BYE: self.cmd_bye,
        }
        
        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            self.send_error(ErrorCode.UNKNOWN_COMMAND, f"Unknown command: {cmd}")
    
    # === Command handlers ===
    
    def cmd_load(self, args: list[str]):
        """LOAD <filepath> - Load a video file"""
        if not args:
            self.send_error(ErrorCode.INVALID_ARGUMENT, "LOAD requires filename")
            return
        
        filepath = Path(' '.join(args))
        
        # If relative and media_root set, resolve against it
        if not filepath.is_absolute() and self.media_root:
            filepath = self.media_root / filepath
        
        if not filepath.exists():
            self.send_error(ErrorCode.FILE_NOT_FOUND, f"File not found: {filepath}")
            return
        
        if self.source.load(filepath):
            self.send_line(f"{Response.LOADED} {self.source.total_frames} frames")
        else:
            self.send_error(ErrorCode.INTERNAL_ERROR, "Failed to load file")
    
    def cmd_play(self, args: list[str]):
        """PLAY - Start playback"""
        if not self.source.is_loaded:
            self.send_error(ErrorCode.NOT_LOADED, "No file loaded")
            return
        self.source.state = PlayState.PLAYING
        self.send_line(Response.PLAYING)
    
    def cmd_pause(self, args: list[str]):
        """PAUSE - Pause playback"""
        self.source.state = PlayState.PAUSED
        self.send_line(Response.PAUSED)
    
    def cmd_stop(self, args: list[str]):
        """STOP - Stop and return to beginning"""
        self.source.state = PlayState.STOPPED
        self.source.seek(0)
        self.send_line(Response.STOPPED)
    
    def cmd_seek(self, args: list[str]):
        """SEEK <frame> - Seek to frame number"""
        if not args:
            self.send_error(ErrorCode.INVALID_ARGUMENT, "SEEK requires frame number")
            return
        
        try:
            frame = int(args[0])
        except ValueError:
            self.send_error(ErrorCode.INVALID_ARGUMENT, "Invalid frame number")
            return
        
        if frame < 0:
          frame = self.source.info.frame_count + frame

        if self.source.seek(frame):
            self.send_line(f"{Response.SEEKED} {self.source.current_frame}")
        else:
            self.send_error(ErrorCode.INTERNAL_ERROR, "Seek failed")
    
    def cmd_next(self, args: list[str]):
        """NEXT - Advance one frame"""
        if self.source.advance():
            self.send_line(f"OK FRAME {self.source.current_frame}")
        else:
            self.send_line("OK END")
    
    def cmd_prev(self, args: list[str]):
        """PREV - Go back one frame"""
        if self.source.retreat():
            self.send_line(f"OK FRAME {self.source.current_frame}")
        else:
            self.send_line("OK START")
    
    def cmd_getframe(self, args: list[str]):
        """GETFRAME [frame] - Get frame data"""
        frame_num = None
        if args:
            try:
                frame_num = int(args[0])
            except ValueError:
                self.send_error(ErrorCode.INVALID_ARGUMENT, "Invalid frame number")
                return
        
        frame_data = self.source.get_frame(frame_num)
        
        if frame_data is None:
            self.send_error(ErrorCode.INTERNAL_ERROR, "Frame not available")
            return
        
        # Prepare header
        fmt = self.source.output_format
        header = FrameHeader(
            sequence=self.source.current_frame,
            timestamp_ms=int(self.source.current_frame * fmt.frame_duration_ms),
            width=fmt.width,
            height=fmt.height,
            colorspace=fmt.colorspace.value,
            flags=FrameFlags.KEYFRAME,
        )
        
        frame_bytes = frame_data.tobytes()
        
        # Send text response
        self.send_line(f"{Response.FRAMEDATA} {len(frame_bytes)}")
        
        # Send binary header + data
        self.transport.write(header.pack())
        self.transport.write(frame_bytes)
    
    def cmd_status(self, args: list[str]):
        """STATUS - Get current status"""
        self.send_line(format_status(
            self.source.state.name,
            self.source.current_frame,
            self.source.total_frames
        ))
    
    def cmd_info(self, args: list[str]):
        """INFO - Get detailed video info"""
        info = self.source.info
        if info:
            self.send_line(
                f"OK INFO {info.width}x{info.height} "
                f"{info.frame_rate:.2f}fps {info.codec} "
                f"{info.frame_count} frames {info.duration_seconds:.2f}s"
            )
        else:
            self.send_line("OK INFO none")

    def cmd_source(self, args: list[str]):
        """SOURCE - Get information about loaded source"""
        if not self.source.is_loaded:
            self.send_line("OK SOURCE NONE")
            return

        info = self.source.info
        if not info:
            self.send_line("OK SOURCE NONE")
            return

        filepath = info.filepath or "unknown"
        self.send_line(
            f'OK SOURCE "{filepath}" {info.frame_count} '
            f'{info.width}x{info.height} {info.frame_rate:.2f} {info.codec}'
        )

    def cmd_frameinfo(self, args: list[str]):
        """FRAMEINFO [frame] - Get frame metadata without pixel data"""
        if not self.source.is_loaded:
            self.send_error(ErrorCode.NOT_LOADED, "No file loaded")
            return

        # Parse frame number
        if args:
            try:
                frame_num = int(args[0])
            except ValueError:
                self.send_error(ErrorCode.INVALID_ARGUMENT, f"Invalid frame number: {args[0]}")
                return
        else:
            frame_num = self.source.current_frame

        # Validate range
        if frame_num < 0 or frame_num >= self.source.total_frames:
            self.send_error(ErrorCode.INVALID_ARGUMENT, f"Frame out of range: {frame_num}")
            return

        # Get output format info
        fmt = self.source.output_format
        timestamp_ms = int(frame_num * fmt.frame_duration_ms)

        # Flags
        flags = FrameFlags.KEYFRAME if frame_num == 0 else FrameFlags.NONE
        if frame_num == self.source.total_frames - 1:
            flags |= FrameFlags.END_OF_STREAM

        self.send_line(
            f"OK FRAMEINFO {frame_num} {timestamp_ms} "
            f"{fmt.width} {fmt.height} {fmt.colorspace.value} {flags}"
        )
    
    def cmd_loop(self, args: list[str]):
        """LOOP [on|off] - Set loop mode"""
        if args and args[0].upper() in ('ON', 'TRUE', '1', 'YES'):
            self.source.loop = True
            self.send_line("OK LOOP ON")
        elif args and args[0].upper() in ('OFF', 'FALSE', '0', 'NO'):
            self.source.loop = False
            self.send_line("OK LOOP OFF")
        else:
            # Toggle or query
            status = "ON" if self.source.loop else "OFF"
            self.send_line(f"OK LOOP {status}")
    
    def cmd_format(self, args: list[str]):
        """FORMAT <NTSC|PAL> [RGB24|YUV422|YUV420P] - Set output format"""
        if not args:
            # Query current format
            fmt = self.source.output_format
            self.send_line(f"OK FORMAT {fmt.standard.name} {fmt.colorspace.name}")
            return
        
        standard = args[0].upper()
        colorspace = ColorSpace.RGB24
        
        if len(args) > 1:
            cs_name = args[1].upper()
            try:
                colorspace = ColorSpace[cs_name]
            except KeyError:
                self.send_error(ErrorCode.INVALID_ARGUMENT, 
                              f"Unknown colorspace: {cs_name}")
                return
        
        if standard == 'NTSC':
            self.source.output_format = VideoFormat.ntsc(colorspace)
        elif standard == 'PAL':
            self.source.output_format = VideoFormat.pal(colorspace)
        else:
            self.send_error(ErrorCode.INVALID_ARGUMENT, 
                          f"Unknown format: {standard}")
            return
        
        self.send_line(f"OK FORMAT {standard} {colorspace.name}")
    
    def cmd_list(self, args: list[str]):
        """LIST [path] - List available video files"""
        search_path = self.media_root or Path('.')
        if args:
            search_path = Path(args[0])
            if not search_path.is_absolute() and self.media_root:
                search_path = self.media_root / search_path
        
        if not search_path.exists():
            self.send_error(ErrorCode.FILE_NOT_FOUND, 
                          f"Path not found: {search_path}")
            return
        
        # Find video files
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        files = []
        
        if search_path.is_file():
            files = [search_path.name]
        else:
            for f in search_path.iterdir():
                if f.is_file() and f.suffix.lower() in video_extensions:
                    files.append(f.name)
        
        files.sort()
        self.send_line(f"OK LIST {len(files)}")
        for f in files:
            self.send_line(f)
    
    def cmd_bye(self, args: list[str]):
        """BYE - Disconnect"""
        self.send_line(Response.BYE)
        self.transport.close()
    
    # === Helper methods ===
    
    def send_line(self, message: str):
        """Send a line of text to client"""
        if self.transport and not self.transport.is_closing():
            self.transport.write(f"{message}\n".encode('utf-8'))
    
    def send_error(self, code: ErrorCode, message: str):
        """Send an error response"""
        self.send_line(format_error(code, message))


async def run_daemon(
    host: str = '0.0.0.0',
    port: int = 5400,
    video_format: VideoFormat = None,
    media_root: Path = None,
):
    """
    Run the VTS daemon
    
    Args:
        host: Bind address
        port: Bind port
        video_format: Default output format
        media_root: Root directory for media files
    """
    if video_format is None:
        video_format = VideoFormat.ntsc()
    
    source = VideoSource(video_format)
    
    loop = asyncio.get_event_loop()
    
    server = await loop.create_server(
        lambda: DaemonProtocol(source, media_root),
        host, port
    )
    
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f"VTS Daemon listening on {addrs}")
    logger.info(f"Default format: {video_format}")
    if media_root:
        logger.info(f"Media root: {media_root}")
    
    async with server:
        await server.serve_forever()
