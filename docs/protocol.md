# VTS Protocol Specification

Version 1.0

## Overview

The VTS (Virtual Toaster Source) protocol is a simple text-based command protocol
for controlling video source daemons over TCP. It's designed to be human-readable
for debugging while remaining efficient for programmatic use.

## Connection

- **Transport**: TCP
- **Default Port**: 5400
- **Default name**: VTS
- **Encoding**: UTF-8 for commands, binary for frame data
- **Line Terminator**: `\n` (LF)

## Session Flow

```
Client connects
Server: OK HELLO VTS VTSource 0.1.0

Client: FORMAT NTSC RGB24
Server: OK FORMAT NTSC RGB24

Client: LOAD /path/to/video.mp4
Server: OK LOADED 1800 frames

Client: GETFRAME 0
Server: OK FRAMEDATA 1049760
Server: [16-byte header][frame data]

Client: BYE
Server: OK BYE
Connection closed
```

## Commands

### Connection Management

#### HELLO (implicit)
Server sends on connection:
```
OK HELLO <name> VTSource <version>
```

#### BYE
Disconnect gracefully.
```
Client: BYE
Server: OK BYE
```

### File Operations

#### LIST [path]
List available video files.
```
Client: LIST
Server: OK LIST 3
Server: video1.mp4
Server: video2.mov
Server: test.avi
```

#### LOAD <filepath>
Load a video file.
```
Client: LOAD /videos/sample.mp4
Server: OK LOADED 1800 frames
```

Or with quoted path:
```
Client: LOAD "/path/with spaces/video.mp4"
Server: OK LOADED 900 frames
```

Errors:
```
Server: ERROR 404 File not found: /nonexistent.mp4
```

#### SOURCE
Get information about the currently loaded video file.
```
Client: SOURCE
Server: OK SOURCE "/path/to/video.mp4" 52710 720x486 29.97 h264
```

No file loaded:
```
Client: SOURCE
Server: OK SOURCE NONE
```

Format: `OK SOURCE "<filepath>" <frames> <width>x<height> <fps> <codec>`

### Playback Control

#### PLAY
Begin playback (sets state to PLAYING).
```
Client: PLAY
Server: OK PLAYING
```

#### PAUSE
Pause playback.
```
Client: PAUSE
Server: OK PAUSED
```

#### STOP
Stop playback and return to frame 0.
```
Client: STOP
Server: OK STOPPED
```

### Navigation

#### SEEK <frame>
Seek to specific frame number.
```
Client: SEEK 500
Server: OK SEEKED 500
```

#### NEXT
Advance one frame.
```
Client: NEXT
Server: OK FRAME 501
```

At end of file:
```
Server: OK END
```

#### PREV
Go back one frame.
```
Client: PREV
Server: OK FRAME 499
```

At start of file:
```
Server: OK START
```

### Frame Retrieval

#### GETFRAME [frame]
Get frame data. If frame number omitted, returns current frame.

```
Client: GETFRAME 100
Server: OK FRAMEDATA 1049760
Server: [binary: 16-byte header][binary: frame data]
```

The response consists of:
1. Text line: `OK FRAMEDATA <size>`
2. Binary header (16 bytes)
3. Binary frame data (<size> bytes)

#### FRAMEINFO [frame]
Get metadata about a frame without transferring pixel data.
```
Client: FRAMEINFO
Server: OK FRAMEINFO 0 0 720 486 0 1

Client: FRAMEINFO 1000
Server: OK FRAMEINFO 1000 33367 720 486 0 0
```

Format: `OK FRAMEINFO <frame> <timestamp_ms> <width> <height> <colorspace> <flags>`

Useful for seeking/scanning without the overhead of full frame transfer.

### Configuration

#### FORMAT [standard] [colorspace]
Set or query output format.

Query:
```
Client: FORMAT
Server: OK FORMAT NTSC RGB24
```

Set:
```
Client: FORMAT PAL YUV422
Server: OK FORMAT PAL YUV422
```

Standards: `NTSC`, `PAL`
Colorspaces: `RGB24`, `YUV422`, `YUV420P`

#### LOOP [on|off]
Set or query loop mode.

Query:
```
Client: LOOP
Server: OK LOOP OFF
```

Set:
```
Client: LOOP on
Server: OK LOOP ON
```

### Status

#### STATUS
Get current playback status.
```
Client: STATUS
Server: OK STATUS PLAYING 42 1800
```

Format: `OK STATUS <state> <current_frame> <total_frames>`

States: `STOPPED`, `PLAYING`, `PAUSED`

#### INFO
Get detailed video information.
```
Client: INFO
Server: OK INFO 1920x1080 29.97fps h264 1800 frames 60.06s
```

## Frame Header Format

The frame header is a 16-byte binary structure prepended to frame data:

| Offset | Size | Type   | Description          |
|--------|------|--------|----------------------|
| 0      | 4    | uint32 | Sequence number      |
| 4      | 4    | uint32 | Timestamp (ms)       |
| 8      | 2    | uint16 | Width                |
| 10     | 2    | uint16 | Height               |
| 12     | 1    | uint8  | Colorspace           |
| 13     | 1    | uint8  | Flags                |
| 14     | 2    | uint16 | Reserved             |

All multi-byte values are big-endian.

### Colorspace Values

| Value | Name    | Description                    |
|-------|---------|--------------------------------|
| 0     | RGB24   | 24-bit RGB, 3 bytes/pixel      |
| 1     | YUV422  | 4:2:2 UYVY packed, 2 bytes/pixel |
| 2     | YUV420P | 4:2:0 planar, 1.5 bytes/pixel  |

### Flag Values

| Bit | Name          | Description           |
|-----|---------------|-----------------------|
| 0   | KEYFRAME      | Frame is a keyframe   |
| 1   | FIELD_1       | First field (interlaced) |
| 2   | FIELD_2       | Second field (interlaced) |
| 3   | END_OF_STREAM | Last frame of stream  |

## Error Responses

Errors follow the format:
```
ERROR <code> <message>
```

### Error Codes

| Code | Name             | Description                    |
|------|------------------|--------------------------------|
| 400  | UNKNOWN_COMMAND  | Command not recognized         |
| 401  | INVALID_ARGUMENT | Invalid or missing argument    |
| 404  | FILE_NOT_FOUND   | File or path not found         |
| 500  | INTERNAL_ERROR   | Internal daemon error          |
| 501  | NOT_LOADED       | Operation requires loaded file |

## Frame Data Formats

### RGB24

Raw 24-bit RGB pixels, row-major order, top-to-bottom.

```
Byte order: R0 G0 B0 R1 G1 B1 R2 G2 B2 ...
Size: width × height × 3 bytes
```

NTSC: 720 × 486 × 3 = 1,049,760 bytes
PAL:  720 × 576 × 3 = 1,244,160 bytes

### YUV422 (UYVY)

4:2:2 packed format, also known as UYVY.

```
Byte order: U0 Y0 V0 Y1 | U2 Y2 V2 Y3 | ...
Each 4-byte group contains 2 pixels.
Size: width × height × 2 bytes
```

NTSC: 720 × 486 × 2 = 699,840 bytes
PAL:  720 × 576 × 2 = 829,440 bytes

### YUV420P

4:2:0 planar format.

```
Layout: [Y plane][U plane][V plane]
Y plane: width × height bytes (full resolution)
U plane: (width/2) × (height/2) bytes (quarter resolution)
V plane: (width/2) × (height/2) bytes (quarter resolution)
Size: width × height × 1.5 bytes
```

NTSC: 720 × 486 × 1.5 = 524,880 bytes
PAL:  720 × 576 × 1.5 = 622,080 bytes

## Example Session

```
$ nc localhost 5400
OK HELLO VTS VTSource 0.1.0
FORMAT NTSC RGB24
OK FORMAT NTSC RGB24
LIST
OK LIST 2
test_pattern.mp4
sample_video.mov
LOAD test_pattern.mp4
OK LOADED 300 frames
INFO
OK INFO 1920x1080 30.00fps h264 300 frames 10.00s
STATUS
OK STATUS STOPPED 0 300
SEEK 150
OK SEEKED 150
STATUS
OK STATUS STOPPED 150 300
LOOP on
OK LOOP ON
BYE
OK BYE
```

## Implementation Notes

### Buffering

Clients should buffer received data, as TCP does not preserve message boundaries.
Parse complete lines (terminated by `\n`) before processing.

### Frame Requests

After sending `GETFRAME`, the client must:
1. Read the text response line
2. Parse the frame size from `OK FRAMEDATA <size>`
3. Read exactly 16 bytes (header)
4. Read exactly `<size>` bytes (frame data)

### Timing

The daemon does not automatically push frames during PLAY state.
Clients must poll with GETFRAME or implement their own timing.
Future protocol versions may add streaming modes.

### Concurrency

Current implementation uses a single shared video source.
Multiple clients will see the same video state.
Future versions may support per-client sources.
