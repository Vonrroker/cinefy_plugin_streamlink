"""
$description Cinefy (cinefy.gg) video and live streaming platform plugin for Streamlink.
$url cinefy.gg
$type live, vod
$metadata id
$metadata author
$metadata title
$metadata category
"""

from __future__ import annotations

import os
import re
from typing import ClassVar
from urllib.parse import urlparse

from streamlink.exceptions import FatalPluginError, NoStreamsError, PluginError
from streamlink.logger import getLogger
from streamlink.plugin import Plugin, pluginargument, pluginmatcher
from streamlink.plugin.api import validate
from streamlink.stream.hls import HLSStream
from streamlink.stream.http import HTTPStream

log = getLogger(__name__)


@pluginmatcher(
    name="vod",
    pattern=re.compile(r"https?://(?:www\.)?cinefy\.gg/(?:watch|video)/(?P<video_id>[a-zA-Z0-9_\-]+)/?$"),
)
@pluginmatcher(
    name="channel_live",
    pattern=re.compile(r"https?://(?:www\.)?cinefy\.gg/(?P<channel>[a-zA-Z0-9_\-]+)/live/?$"),
)
@pluginmatcher(
    name="channel",
    pattern=re.compile(
        r"https?://(?:www\.)?cinefy\.gg/(?!(?:watch|video|login|register|explore|search|settings|api|terms|help)(?:/|$))(?P<channel>[a-zA-Z0-9_\-]+)/?$"
    ),
)
@pluginargument(
    "token",
    sensitive=True,
    metavar="TOKEN",
    help="Bearer token used to authenticate with cinefy.gg. Can also be set via CINEFY_TOKEN or BEARER_TOKEN environment variable, or in a .env file.",
)
@pluginargument(
    "latest-vod",
    action="store_true",
    help="Play the latest VOD/video if the channel is currently offline.",
)
class Cinefy(Plugin):
    _API_BASE: ClassVar[str] = "https://api.cinefy.gg"
    _URL_CONSTANTS: ClassVar[str] = "https://cinefy.gg/api/constants"

    _video_schema = validate.Schema(
        {
            "id": str,
            "title": str,
            validate.optional("description"): validate.any(str, None),
            validate.optional("type"): validate.any(str, None),
            validate.optional("media"): validate.any(
                {
                    validate.optional("title"): validate.any(str, None),
                    validate.optional("originalTitle"): validate.any(str, None),
                    validate.optional("type"): validate.any(str, None),
                },
                None,
            ),
            validate.optional("author"): validate.any(
                {
                    validate.optional("id"): str,
                    validate.optional("username"): str,
                    validate.optional("displayName"): str,
                    validate.optional("slug"): str,
                },
                None,
            ),
            validate.optional("stream"): validate.any(
                {
                    validate.optional("id"): validate.any(str, None),
                    validate.optional("playbackUrl"): validate.any(str, None),
                    validate.optional("baseUrl"): validate.any(str, None),
                    validate.optional("authorization"): validate.any(str, None),
                    validate.optional("resolutions"): validate.any(list, None),
                    validate.optional("hasOriginal"): validate.any(bool, None),
                    validate.optional("hasMP4Fallback"): validate.any(bool, None),
                },
                None,
            ),
            validate.optional("liveStream"): validate.any(
                {
                    validate.optional("id"): validate.any(str, None),
                    validate.optional("platform"): validate.any(str, None),
                    validate.optional("embed"): validate.any(dict, None),
                },
                None,
            ),
        }
    )

    _user_schema = validate.Schema(
        {
            "id": str,
            "username": str,
            "slug": str,
            validate.optional("displayName"): validate.any(str, None),
            validate.optional("liveStreamVideo"): validate.any(dict, None),
        }
    )

    _videos_list_schema = validate.Schema(
        {
            "data": [
                {
                    "id": str,
                    "title": str,
                    validate.optional("type"): validate.any(str, None),
                    validate.optional("stream"): validate.any(dict, None),
                }
            ]
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._token: str | None = None
        self._setup_session()

    def _find_token(self) -> str | None:
        # 1. Plugin CLI argument
        cli_token = self.get_option("token")
        if cli_token:
            return cli_token.strip()

        # 2. Environment variables
        for env_var in ("CINEFY_TOKEN", "BEARER_TOKEN", "bearer_token"):
            if env_val := os.environ.get(env_var):
                return env_val.strip()

        # 3. .env file in cwd or parent dirs
        current_dir = os.getcwd()
        for _ in range(4):
            env_file = os.path.join(current_dir, ".env")
            if os.path.isfile(env_file):
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("#") or "=" not in line:
                                continue
                            key, val = line.split("=", 1)
                            key = key.strip().lower()
                            val = val.strip().strip("'\"")
                            if key in ("bearer_token", "cinefy_token", "token"):
                                return val
                except Exception as err:
                    log.debug(f"Failed to read .env file at {env_file}: {err}")
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent

        return None

    def _setup_session(self):
        self.session.http.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://cinefy.gg/",
            "Origin": "https://cinefy.gg",
            "Accept": "application/json, text/plain, */*",
        })

        token = self._find_token()
        if token:
            self._token = token
            # Normalize Bearer token header
            auth_header = token if token.lower().startswith("bearer ") else f"Bearer {token}"
            self.session.http.headers.update({"Authorization": auth_header})
            log.debug("Authentication token loaded successfully")
        else:
            log.warning("No authentication token provided. Subscribed channels/VODs may be unavailable.")

    def _query_api(self, endpoint: str, schema: validate.Schema):
        url = f"{self._API_BASE}{endpoint}" if endpoint.startswith("/") else endpoint
        res = self.session.http.get(url, raise_for_status=False)

        if res.status_code == 401:
            raise FatalPluginError("Authentication failed (401 Unauthorized). Please provide a valid Cinefy Bearer token.")
        if res.status_code == 403:
            raise FatalPluginError("Access forbidden (403 Forbidden). A subscription may be required to view this content.")
        if res.status_code == 404:
            return None

        try:
            res.raise_for_status()
        except Exception as err:
            raise PluginError(f"API request to {url} failed: {err}") from err

        return self.session.http.json(res, schema=schema)

    def _get_streams_from_video(self, video_id: str):
        video_data = self._query_api(f"/v1/video/{video_id}", self._video_schema)
        if not video_data:
            raise PluginError(f"Video {video_id} was not found.")

        # Set metadata
        self.id = video_data.get("id")
        self.title = video_data.get("title")

        if author := video_data.get("author"):
            self.author = author.get("displayName") or author.get("username")

        if media := video_data.get("media"):
            self.category = media.get("title") or media.get("originalTitle")

        stream_info = video_data.get("stream")
        if not stream_info:
            # Check if it's an external live stream embed
            if live_stream := video_data.get("liveStream"):
                platform = live_stream.get("platform")
                embed = live_stream.get("embed") or {}
                username = embed.get("username")
                if platform == "kick" and username:
                    log.info(f"Stream is hosted on Kick (https://kick.com/{username})")
                    return self.session.streams(f"https://kick.com/{username}")
                elif platform == "twitch" and username:
                    log.info(f"Stream is hosted on Twitch (https://twitch.tv/{username})")
                    return self.session.streams(f"https://twitch.tv/{username}")
            raise NoStreamsError

        playback_url = stream_info.get("playbackUrl")
        if not playback_url:
            base_url = stream_info.get("baseUrl")
            auth_param = stream_info.get("authorization") or ""
            stream_id = stream_info.get("id")
            if base_url and stream_id:
                auth_part = f"{auth_param}/" if auth_param else ""
                playback_url = f"{base_url}/{auth_part}{stream_id}/playlist.m3u8"

        if not playback_url:
            if not self._token:
                raise FatalPluginError(
                    "No playback URL found and no authentication token was provided. "
                    "Please provide your Cinefy Bearer token via --cinefy-token, CINEFY_TOKEN env var, or .env file."
                )
            raise FatalPluginError(
                "No playback URL found. An active channel subscription may be required or the Bearer token may be invalid/expired."
            )

        log.debug(f"HLS Playback URL: {playback_url}")
        hls_headers = {
            "Referer": "https://cinefy.gg/",
            "Origin": "https://cinefy.gg",
            "User-Agent": self.session.http.headers.get("User-Agent"),
        }

        streams = HLSStream.parse_variant_playlist(
            self.session,
            playback_url,
            headers=hls_headers,
        )

        return streams

    def _get_streams_channel(self, channel_slug: str):
        user_data = self._query_api(f"/v1/user/{channel_slug}", self._user_schema)
        if not user_data:
            raise PluginError(f"Channel '{channel_slug}' not found.")

        channel_id = user_data["id"]
        channel_name = user_data.get("displayName") or user_data.get("username") or channel_slug
        self.author = channel_name

        live_video = user_data.get("liveStreamVideo")
        if live_video and live_video.get("id"):
            log.info(f"Channel '{channel_name}' is currently LIVE.")
            return self._get_streams_from_video(live_video["id"])

        log.info(f"Channel '{channel_name}' is currently offline.")

        if self.get_option("latest_vod"):
            log.info(f"Searching for the latest VOD for '{channel_name}'...")
            videos_data = self._query_api(f"/v1/videos?author={channel_id}&perPage=1", self._videos_list_schema)
            if videos_data and videos_data.get("data"):
                latest = videos_data["data"][0]
                log.info(f"Playing latest VOD: {latest.get('title')} ({latest['id']})")
                return self._get_streams_from_video(latest["id"])
            log.info(f"No VODs found for '{channel_name}'.")

        raise NoStreamsError

    def _get_streams(self):
        if self.matches["vod"]:
            video_id = self.match.group("video_id")
            return self._get_streams_from_video(video_id)

        if self.matches["channel_live"] or self.matches["channel"]:
            channel = self.match.group("channel")
            return self._get_streams_channel(channel)


__plugin__ = Cinefy
