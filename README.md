# Streamlink Plugin for Cinefy (cinefy.gg)

Custom plugin for [Streamlink](https://streamlink.github.io/) with support for the [Cinefy](https://cinefy.gg) streaming platform.

## Features

- **Live Channels**: Supports channel URLs in the format `https://cinefy.gg/<channel>` and `https://cinefy.gg/<channel>/live`.
- **Videos / VODs**: Direct support for on-demand videos with URLs such as `https://cinefy.gg/watch/<video_id>`.
- **Latest VOD Fallback**: Optional `--cinefy-latest-vod` flag to automatically play the most recent recorded video if the channel is currently offline.
- **Flexible Authentication**:
  - Automatic token detection from `.env` file (`bearer_token=...` or `CINEFY_TOKEN=...`).
  - Environment variable support via `CINEFY_TOKEN` or `BEARER_TOKEN`.
  - Command-line argument via `--cinefy-token <token>`.
- **Multiple Resolutions**: Automatically parses available HLS stream qualities (e.g. `480p`, `720p`, `1080p`, `best`, `worst`).
- **Metadata**: Extracts video title, channel/creator name, and media category.

---

## Installation

### Option 1: Run directly from the project directory
You can point Streamlink to the folder containing `cinefy.py` using the `--plugin-dirs` argument:

```powershell
streamlink --plugin-dirs . https://cinefy.gg/minerva
```

### Option 2: Install permanently in Streamlink

Copy `cinefy.py` to Streamlink's plugin directory on your system:

- **Windows**: `%APPDATA%\streamlink\plugins\cinefy.py`
  *(e.g., `C:\Users\<Username>\AppData\Roaming\streamlink\plugins\cinefy.py`)*
- **Linux**: `~/.local/share/streamlink/plugins/cinefy.py`
- **macOS**: `~/Library/Application Support/streamlink/plugins/cinefy.py`

Once installed, passing `--plugin-dirs .` is no longer required.

---

## Authentication

To access subscriber-only channels or content (such as `minerva`):

1. **`.env` File (Automatic)**:
   Place a `.env` file in the current working directory with:
   ```env
   bearer_token=YOUR_TOKEN_HERE
   ```

2. **Command Line Argument**:
   ```powershell
   streamlink --plugin-dirs . https://cinefy.gg/watch/<video_id> --cinefy-token YOUR_TOKEN_HERE best
   ```

3. **Environment Variable**:
   ```powershell
   $env:CINEFY_TOKEN = "YOUR_TOKEN_HERE"
   ```

---

## Usage Examples

### 1. Watch or check a live channel:
```powershell
streamlink --plugin-dirs . https://cinefy.gg/minerva best
```

### 2. Play the latest recorded video (VOD) if the channel is offline:
```powershell
streamlink --plugin-dirs . https://cinefy.gg/minerva --cinefy-latest-vod best
```

### 3. Watch a specific VOD / video directly:
```powershell
streamlink --plugin-dirs . https://cinefy.gg/watch/cZOb3InQubpUL best
```

### 4. Open in VLC, MPV, or your preferred media player:
```powershell
streamlink --plugin-dirs . https://cinefy.gg/watch/cZOb3InQubpUL best --player vlc
```

### 5. Record/download the stream directly to a file:
```powershell
streamlink --plugin-dirs . https://cinefy.gg/watch/cZOb3InQubpUL best -o "minerva_video.mp4"
```
