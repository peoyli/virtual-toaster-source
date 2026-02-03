# VTS Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VTS ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                        VTS DAEMON                                │  │
│   │                                                                  │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │  │
│   │  │   Protocol   │  │    Video     │  │   Format     │          │  │
│   │  │   Handler    │◄─┤   Source     │◄─┤  Converter   │          │  │
│   │  │  (asyncio)   │  │  (PyAV)      │  │  (NumPy)     │          │  │
│   │  └──────┬───────┘  └──────┬───────┘  └──────────────┘          │  │
│   │         │                 │                                      │  │
│   │         │                 ▼                                      │  │
│   │         │          ┌──────────────┐                             │  │
│   │         │          │    Frame     │                             │  │
│   │         │          │    Cache     │                             │  │
│   │         │          │   (LRU)      │                             │  │
│   │         │          └──────────────┘                             │  │
│   │         │                                                        │  │
│   └─────────┼────────────────────────────────────────────────────────┘  │
│             │                                                           │
│             │ TCP :5400                                                 │
│             │                                                           │
│   ┌─────────┴─────────────────────────────────────────────────────────┐│
│   │                                                                    ││
│   │    ┌──────────┐    ┌──────────┐    ┌──────────┐                  ││
│   │    │  Test    │    │  Preview │    │  WinUAE  │                  ││
│   │    │  Client  │    │  Client  │    │  Plugin  │                  ││
│   │    │          │    │  (GUI)   │    │ (Future) │                  ││
│   │    └──────────┘    └──────────┘    └──────────┘                  ││
│   │                                                                    ││
│   │                         CLIENTS                                    ││
│   └────────────────────────────────────────────────────────────────────┘│
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### VideoSource

The `VideoSource` class manages video file loading and frame extraction.

**Responsibilities:**
- Load video files via PyAV (ffmpeg bindings)
- Seek to specific frames
- Decode frames to RGB24
- Scale frames to output resolution
- Convert colorspace (RGB24 → YUV422/YUV420P)
- Cache recently accessed frames

**Key Design Decisions:**
- Uses PyAV for direct ffmpeg access with frame-level control
- Decodes to RGB24 first, then converts (simpler, good enough performance)
- LRU cache avoids redundant decoding for repeated frame requests
- PIL/Pillow for high-quality scaling (LANCZOS)

### Protocol Handler

The `DaemonProtocol` class handles network communication.

**Responsibilities:**
- Accept TCP connections
- Parse text commands
- Execute commands via VideoSource
- Send responses (text and binary)

**Key Design Decisions:**
- asyncio for efficient I/O multiplexing
- Simple text protocol for debuggability
- Binary frame data for efficiency
- Stateless command handling (state lives in VideoSource)

### Frame Cache

The `FrameCache` class implements LRU caching for decoded frames.

**Responsibilities:**
- Store recently decoded frames
- Evict oldest frames when capacity reached
- Quick lookup by frame number

**Key Design Decisions:**
- OrderedDict for O(1) access with LRU ordering
- Configurable size (default 30 frames ≈ 1 second)
- Stores converted frames (post-colorspace conversion)

## Data Flow

### Frame Request Flow

```
Client                    Daemon                     VideoSource
  │                         │                            │
  │  GETFRAME 100           │                            │
  │────────────────────────►│                            │
  │                         │  get_frame(100)            │
  │                         │───────────────────────────►│
  │                         │                            │
  │                         │        [cache miss]        │
  │                         │                            │
  │                         │                      seek(100)
  │                         │                      decode()
  │                         │                      scale()
  │                         │                      convert()
  │                         │                      cache.put()
  │                         │                            │
  │                         │◄───────────────────────────│
  │                         │       frame_data           │
  │                         │                            │
  │  OK FRAMEDATA 1049760   │                            │
  │◄────────────────────────│                            │
  │  [header][frame_data]   │                            │
  │◄────────────────────────│                            │
  │                         │                            │
```

### Colorspace Conversion Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Decoded    │     │   Scaled    │     │  Converted  │
│  Frame      │────►│   Frame     │────►│   Frame     │
│  (native)   │     │  (720×486)  │     │  (output)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
   Variable           720×486×3           Depends on
   resolution           RGB24             colorspace
```

## Threading Model

VTS uses Python's asyncio for concurrency:

```
┌─────────────────────────────────────────────────┐
│              Main Event Loop                    │
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Client  │  │ Client  │  │ Client  │        │
│  │ Handler │  │ Handler │  │ Handler │        │
│  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │              │
│       └────────────┼────────────┘              │
│                    │                           │
│                    ▼                           │
│           ┌───────────────┐                   │
│           │  VideoSource  │                   │
│           │   (shared)    │                   │
│           └───────────────┘                   │
│                                                │
└─────────────────────────────────────────────────┘
```

**Current Limitation:** Single shared VideoSource means all clients see
the same video state. This is intentional for the initial implementation
targeting Toaster emulation (one "switcher" controlling multiple sources).

**Future Enhancement:** Per-client VideoSource instances for independent
control, or a multi-source manager for the full Toaster input model.

## Memory Considerations

### Frame Buffer Sizes

| Format | Resolution | Colorspace | Size/Frame |
|--------|------------|------------|------------|
| NTSC   | 720×486    | RGB24      | 1.05 MB    |
| NTSC   | 720×486    | YUV422     | 0.70 MB    |
| NTSC   | 720×486    | YUV420P    | 0.52 MB    |
| PAL    | 720×576    | RGB24      | 1.24 MB    |
| PAL    | 720×576    | YUV422     | 0.83 MB    |
| PAL    | 720×576    | YUV420P    | 0.62 MB    |

### Cache Memory Usage

With default 30-frame cache:
- NTSC RGB24: ~31 MB
- NTSC YUV422: ~21 MB
- PAL RGB24: ~37 MB

Adjust `cache_size` parameter based on available memory.

## Extending VTS

### Adding New Colorspaces

1. Add enum value to `ColorSpace` in `formats.py`
2. Implement conversion in `colorspace.py`
3. Add case in `VideoSource._convert_colorspace()`

### Adding Live Capture

1. Create `CaptureSource` class with same interface as `VideoSource`
2. Use v4l2 (Linux) or DirectShow (Windows) for capture
3. Implement frame callback to feed into source

### WinUAE Integration

The daemon side is ready. Integration requires:

1. WinUAE plugin or modification to:
   - Connect to VTS daemon
   - Request frames at video rate
   - Present frames to emulated Toaster hardware

2. Shared memory alternative:
   - Daemon writes frames to shared memory
   - WinUAE reads from shared memory
   - Avoids network overhead for local operation

See `docs/winuae_integration.md` (future) for detailed integration guide.
