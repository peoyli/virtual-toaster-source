# Virtual Toaster Source (VTS)

A networked video source daemon designed to provide virtual video inputs for 
Video Toaster emulation—and potentially other retro video production systems.

## What is this?

The NewTek Video Toaster (1990-1998) was a revolutionary video production system 
for the Commodore Amiga. While the Amiga can be emulated, the Toaster's video 
input functionality cannot—it requires actual video signals.

This project aims to solve that problem by:

1. **Daemon**: Serving video frames from files (or capture devices) over a network
2. **Protocol**: A simple, documented protocol for requesting and receiving frames
3. **Integration**: (Future) Connecting to emulators like WinUAE to provide virtual video inputs

Even without emulator integration, VTS is useful for:
- Understanding historical video production workflows
- Testing and development of video tools
- Educational purposes
- Retro video production simulation

## Project Status

🚧 **Early Development** 🚧

- [x] Protocol specification
- [x] Basic daemon implementation
- [x] Test client
- [ ] Multi-source support
- [ ] GUI preview client
- [ ] WinUAE integration
- [ ] Live capture support

## Quick Start

### Requirements

- Python 3.10+
- ffmpeg libraries (for PyAV)

### Installation

```bash
# Clone the repository
git clone https://github.com/peoyli/virtual-toaster-source.git
cd virtual-toaster-source

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Running the Daemon

```bash
# Start daemon with default settings (NTSC, port 5400)
vts-daemon

# Or specify options
vts-daemon --port 5400 --format ntsc --host 0.0.0.0
```

### Test Client

```bash
# Capture frames from a video file
vts-test-client path/to/video.mp4 --frames 30 --output frames/frame_{:04d}.png
```

## Protocol Overview

VTS uses a simple text-based command protocol over TCP:

```
Client: LOAD /path/to/video.mp4
Server: OK LOADED 1800 frames

Client: FORMAT NTSC RGB24
Server: OK FORMAT NTSC RGB24

Client: GETFRAME 0
Server: OK FRAMEDATA 1049760
Server: [16-byte header][frame data]

Client: PLAY
Server: OK PLAYING

Client: STATUS
Server: OK STATUS PLAYING 42 1800

Client: BYE
Server: OK BYE
```

See [docs/protocol.md](docs/protocol.md) for full specification.

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Video Files    │         │  Capture Device │
│  (MP4, MOV...)  │         │  (Future)       │
└────────┬────────┘         └────────┬────────┘
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────┐
│              VTS Daemon                     │
│  ┌─────────────────────────────────────┐   │
│  │  Video Decoder (PyAV/ffmpeg)        │   │
│  │  Frame Scaler (NTSC/PAL)            │   │
│  │  Colorspace Converter               │   │
│  │  Frame Cache                        │   │
│  └─────────────────────────────────────┘   │
│                    │                        │
│                    ▼                        │
│  ┌─────────────────────────────────────┐   │
│  │  Network Protocol Handler           │   │
│  │  (TCP, async)                       │   │
│  └─────────────────────────────────────┘   │
└─────────────────────┬───────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Test Client    │     │  WinUAE Plugin  │
│  (Python)       │     │  (Future)       │
└─────────────────┘     └─────────────────┘
```

## Video Formats

### NTSC
- Resolution: 720 × 486
- Frame rate: 29.97 fps (30000/1001)
- Pixel aspect ratio: 0.9091 (10:11)

### PAL
- Resolution: 720 × 576
- Frame rate: 25 fps
- Pixel aspect ratio: 1.0926 (59:54)

### Output Colorspaces
- RGB24: 24-bit RGB (default)
- YUV422: 4:2:2 packed (UYVY)
- YUV420P: 4:2:0 planar

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where help is especially appreciated:
- WinUAE integration expertise
- Video engineering knowledge
- Testing on various platforms
- Documentation improvements

## Background

This project was inspired by discussions about Video Toaster preservation and 
the challenges of emulating hardware that depends on external video signals.

For extensive background on the Video Toaster and its significance, see:
- [Article A405: Video Toaster in Emulation](docs/article_a405.md)
- [The Future Was Here](https://mitpress.mit.edu/books/future-was-here) by Jimmy Maher

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- NewTek for creating the Video Toaster
- The Amiga community for keeping the platform alive
- Toni Wilen and WinUAE contributors
- The ffmpeg project
