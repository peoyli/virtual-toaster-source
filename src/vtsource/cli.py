"""
Command-line interfaces for VTS
"""

import argparse
import asyncio
import logging
import socket
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .formats import VideoFormat, ColorSpace
from .protocol import FrameHeader


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def main_daemon():
    """Entry point for vts-daemon command"""
    parser = argparse.ArgumentParser(
        description='VTS - Virtual Toaster Source Daemon',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vts-daemon                          # Start with defaults (NTSC, port 5400)
  vts-daemon --format pal             # Start with PAL format
  vts-daemon --port 5401 --media ~/Videos  # Custom port and media directory
        """
    )
    
    parser.add_argument(
        '--host', 
        default='0.0.0.0',
        help='Bind address (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=5400,
        help='Bind port (default: 5400)'
    )
    parser.add_argument(
        '--format', 
        choices=['ntsc', 'pal'], 
        default='ntsc',
        help='Default video format (default: ntsc)'
    )
    parser.add_argument(
        '--colorspace',
        choices=['rgb24', 'yuv422', 'yuv420p'],
        default='rgb24',
        help='Default colorspace (default: rgb24)'
    )
    parser.add_argument(
        '--media', 
        type=Path,
        default=None,
        help='Media root directory'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Build format
    colorspace = ColorSpace[args.colorspace.upper()]
    if args.format == 'ntsc':
        video_format = VideoFormat.ntsc(colorspace)
    else:
        video_format = VideoFormat.pal(colorspace)
    
    # Import here to avoid circular imports
    from .daemon import run_daemon
    
    try:
        asyncio.run(run_daemon(
            host=args.host,
            port=args.port,
            video_format=video_format,
            media_root=args.media,
        ))
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


def main_test_client():
    """Entry point for vts-test-client command"""
    parser = argparse.ArgumentParser(
        description='VTS Test Client - Capture frames from daemon'
    )
    
    parser.add_argument(
        'video_file',
        help='Video file to load (path on daemon)'
    )
    parser.add_argument(
        '--host',
        default='localhost',
        help='Daemon host (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5400,
        help='Daemon port (default: 5400)'
    )
    parser.add_argument(
        '--frames',
        type=int,
        default=10,
        help='Number of frames to capture (default: 10)'
    )
    parser.add_argument(
        '--start',
        type=int,
        default=0,
        help='Starting frame number (default: 0)'
    )
    parser.add_argument(
        '--output',
        default='frame_{:04d}.png',
        help='Output filename pattern (default: frame_{:04d}.png)'
    )
    parser.add_argument(
        '--format',
        choices=['ntsc', 'pal'],
        default='ntsc',
        help='Video format (default: ntsc)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    run_test_client(args)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Receive exactly n bytes"""
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data


def recv_line(sock: socket.socket) -> str:
    """Receive a line of text"""
    data = b''
    while not data.endswith(b'\n'):
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data.decode('utf-8').strip()


def run_test_client(args):
    """Run the test client"""
    logger = logging.getLogger('test-client')
    
    # Determine output dimensions based on format
    if args.format == 'ntsc':
        width, height = 720, 486
    else:
        width, height = 720, 576
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        logger.info(f"Connecting to {args.host}:{args.port}")
        sock.connect((args.host, args.port))
        
        # Read hello
        response = recv_line(sock)
        logger.info(f"Server: {response}")
        
        # Set format
        sock.sendall(f"FORMAT {args.format.upper()} RGB24\n".encode())
        response = recv_line(sock)
        logger.info(f"Format: {response}")
        
        # Load file
        sock.sendall(f"LOAD {args.video_file}\n".encode())
        response = recv_line(sock)
        logger.info(f"Load: {response}")
        
        if not response.startswith("OK"):
            logger.error("Failed to load file")
            sys.exit(1)
        
        # Get status
        sock.sendall(b"STATUS\n")
        response = recv_line(sock)
        logger.info(f"Status: {response}")
        
        # Capture frames
        logger.info(f"Capturing {args.frames} frames starting at {args.start}")
        
        for i in range(args.frames):
            frame_num = args.start + i
            sock.sendall(f"GETFRAME {frame_num}\n".encode())
            response = recv_line(sock)
            
            if not response.startswith("OK FRAMEDATA"):
                logger.error(f"Frame {frame_num} failed: {response}")
                continue
            
            # Parse frame size
            frame_size = int(response.split()[-1])
            
            # Receive header
            header_data = recv_exact(sock, FrameHeader.SIZE)
            header = FrameHeader.unpack(header_data)
            
            # Receive frame data
            frame_data = recv_exact(sock, frame_size)
            
            # Convert to image
            frame = np.frombuffer(frame_data, dtype=np.uint8)
            frame = frame.reshape((header.height, header.width, 3))
            
            # Save
            img = Image.fromarray(frame)
            filename = args.output.format(frame_num)
            img.save(filename)
            logger.info(f"Saved: {filename} ({header.width}x{header.height})")
        
        # Disconnect
        sock.sendall(b"BYE\n")
        response = recv_line(sock)
        logger.debug(f"Bye: {response}")
        
        logger.info("Done!")
        
    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        sock.close()


if __name__ == '__main__':
    main_daemon()
