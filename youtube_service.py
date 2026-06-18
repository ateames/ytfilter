import re
import sys

import requests

from config import Config

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def _api_get(endpoint: str, params: dict) -> dict:
    params = {**params, "key": Config.YOUTUBE_API_KEY}
    response = requests.get(f"{YOUTUBE_API_BASE}/{endpoint}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def _best_thumbnail(thumbnails: dict) -> str | None:
    for quality in ("maxres", "standard", "high", "medium", "default"):
        if quality in thumbnails:
            return thumbnails[quality]["url"]
    return None


def parse_iso_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration (e.g. PT12M30S) into total seconds."""
    match = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        duration_str,
    )
    if not match:
        raise ValueError(f"Invalid ISO 8601 duration: {duration_str}")

    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def get_channel_info(channel_id: str) -> dict:
    data = _api_get(
        "channels",
        {"part": "id,snippet", "id": channel_id},
    )
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")

    channel = items[0]
    snippet = channel["snippet"]
    return {
        "channel_id": channel["id"],
        "channel_name": snippet["title"],
        "thumbnail_url": _best_thumbnail(snippet.get("thumbnails", {})),
    }


def _get_uploads_playlist_id(channel_id: str) -> str:
    data = _api_get(
        "channels",
        {"part": "contentDetails", "id": channel_id},
    )
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Channel not found: {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def _fetch_playlist_video_ids(playlist_id: str, max_results: int) -> list[str]:
    video_ids: list[str] = []
    page_token = None

    while len(video_ids) < max_results:
        params: dict = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(50, max_results - len(video_ids)),
        }
        if page_token:
            params["pageToken"] = page_token

        data = _api_get("playlistItems", params)
        for item in data.get("items", []):
            video_ids.append(item["snippet"]["resourceId"]["videoId"])

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def _fetch_video_details(video_ids: list[str]) -> list[dict]:
    videos: list[dict] = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        data = _api_get(
            "videos",
            {"part": "id,snippet,contentDetails", "id": ",".join(batch)},
        )
        for item in data.get("items", []):
            snippet = item["snippet"]
            videos.append(
                {
                    "video_id": item["id"],
                    "channel_id": snippet["channelId"],
                    "title": snippet["title"],
                    "description": snippet.get("description", ""),
                    "duration_seconds": parse_iso_duration(
                        item["contentDetails"]["duration"]
                    ),
                    "thumbnail_url": _best_thumbnail(snippet.get("thumbnails", {})),
                    "published_at": snippet["publishedAt"],
                }
            )

    return videos


def get_channel_videos(channel_id: str, max_results: int = 50) -> list[dict]:
    playlist_id = _get_uploads_playlist_id(channel_id)
    video_ids = _fetch_playlist_video_ids(playlist_id, max_results)
    return _fetch_video_details(video_ids)


def _format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <channel_id>")
        sys.exit(1)

    channel_id = sys.argv[1]

    info = get_channel_info(channel_id)
    print(f"Channel: {info['channel_name']} ({info['channel_id']})")
    print(f"Thumbnail: {info['thumbnail_url']}")
    print()

    videos = get_channel_videos(channel_id, max_results=5)
    print(f"First {len(videos)} videos:")
    for video in videos:
        duration = _format_duration(video["duration_seconds"])
        print(f"  - {video['title']} ({duration})")
