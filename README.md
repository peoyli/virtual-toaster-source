# Virtual Toaster Source

Video source system for Video Toaster emulation, providing video input capabilities for the emulated Amiga Video Toaster hardware.

## Projects

| Directory | Description |
|-----------|-------------|
| [vts-daemon](./vts-daemon/) | Video source daemon - serves video frames over TCP/IP |

## Overview

The Virtual Toaster Source system provides video inputs for an emulated Video Toaster. The daemon (`vtsd`) manages video sources (files, capture devices, test patterns) and serves frames to clients over TCP/IP.

## Architecture

```
┌─────────────┐                       
│   Sources   │                       
├─────────────┤                       
│ • Files     │                       
│ • Capture   │                       
│ • Patterns  │                       
└──────┬──────┘                       
       │ video frames                 
       ▼                              
┌─────────────┐      TCP/IP       ┌──────────────┐
│  vts-daemon │ ─────────────────►│   Clients    │
│   (vtsd)    │                   ├──────────────┤
└─────────────┘                   │ • vtsp       │
                                  │ • WinUAE(*)  │
                                  └──────────────┘

(*) Future: Video Toaster card emulation plugin
```

## Quick Start

```bash
cd vts-daemon
pip install -e .
vtsd --help
```

See [vts-daemon/README.md](./vts-daemon/README.md) for detailed usage.

## License

MIT
