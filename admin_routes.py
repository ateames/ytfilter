import re
from functools import wraps

import requests
from flask import Blueprint, jsonify, request

import youtube_service
from config import Config
from database import DEFAULT_SETTINGS, get_db, get_setting, set_setting

admin_bp = Blueprint("admin", __name__)

SETTING_KEYS = list(DEFAULT_SETTINGS.keys())


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Admin-Token")
        if not token or not Config.ADMIN_TOKEN or token != Config.ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return decorated


def parse_channel_id(value: str) -> str | None:
    value = value.strip()
    match = re.search(r"UC[\w-]{22}", value)
    return match.group(0) if match else None


def _channel_to_dict(row) -> dict:
    return {
        "channel_id": row["channel_id"],
        "channel_name": row["channel_name"],
        "thumbnail_url": row["thumbnail_url"],
        "added_at": row["added_at"],
        "video_count": row["video_count"] if "video_count" in row.keys() else 0,
    }


def _get_all_settings() -> dict:
    conn = get_db()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: int(row["value"]) for row in rows}
    finally:
        conn.close()


def _validate_settings_body(data) -> tuple[dict | None, tuple | None]:
    if not data or not isinstance(data, dict):
        return None, (jsonify({"error": "Request body must be a JSON object"}), 400)

    validated = {}
    for key in SETTING_KEYS:
        if key not in data:
            return None, (jsonify({"error": f"Missing field: {key}"}), 400)

        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None, (
                jsonify({"error": f"{key} must be a non-negative integer"}),
                400,
            )
        validated[key] = value

    return validated, None


def _cache_channel_videos(channel_id: str) -> int:
    min_length = int(get_setting("min_video_length_seconds") or 0)
    videos = youtube_service.get_channel_videos(channel_id)
    filtered = [v for v in videos if v["duration_seconds"] >= min_length]

    conn = get_db()
    try:
        for video in filtered:
            conn.execute(
                """
                INSERT OR REPLACE INTO videos (
                    video_id, channel_id, title, description,
                    duration_seconds, thumbnail_url, published_at, cached_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    video["video_id"],
                    video["channel_id"],
                    video["title"],
                    video["description"],
                    video["duration_seconds"],
                    video["thumbnail_url"],
                    video["published_at"],
                ),
            )
        conn.commit()
        return len(filtered)
    finally:
        conn.close()


def _get_channel_row(channel_id: str):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
    finally:
        conn.close()


@admin_bp.route("/settings", methods=["GET"])
@require_admin
def get_settings():
    return jsonify(_get_all_settings())


@admin_bp.route("/settings", methods=["POST"])
@require_admin
def update_settings():
    data = request.get_json(silent=True)
    validated, error = _validate_settings_body(data)
    if error:
        return error

    for key, value in validated.items():
        set_setting(key, value)

    return jsonify(_get_all_settings())


@admin_bp.route("/stats", methods=["GET"])
@require_admin
def get_stats():
    conn = get_db()
    try:
        total_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        total_channels = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        sessions_today = conn.execute(
            """
            SELECT COUNT(*) FROM watch_sessions
            WHERE date(started_at) = date('now', 'localtime')
            """
        ).fetchone()[0]
        return jsonify(
            {
                "total_videos": total_videos,
                "total_channels": total_channels,
                "sessions_today": sessions_today,
            }
        )
    finally:
        conn.close()


@admin_bp.route("/channels", methods=["GET"])
@require_admin
def list_channels():
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(v.video_id) AS video_count
            FROM channels c
            LEFT JOIN videos v ON c.channel_id = v.channel_id
            GROUP BY c.channel_id
            ORDER BY c.added_at DESC
            """
        ).fetchall()
        return jsonify([_channel_to_dict(row) for row in rows])
    finally:
        conn.close()


@admin_bp.route("/channels", methods=["POST"])
@require_admin
def add_channel():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    channel_id = data.get("channel_id")
    if not channel_id or not isinstance(channel_id, str):
        return jsonify({"error": "channel_id is required"}), 400

    channel_id = parse_channel_id(channel_id)
    if not channel_id:
        return jsonify({"error": "Invalid channel ID or URL"}), 400

    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT 1 FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        if existing:
            return jsonify({"error": "Channel already exists"}), 409
    finally:
        conn.close()

    try:
        info = youtube_service.get_channel_info(channel_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except requests.RequestException as exc:
        return jsonify({"error": f"YouTube API error: {exc}"}), 502

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO channels (channel_id, channel_name, thumbnail_url)
            VALUES (?, ?, ?)
            """,
            (info["channel_id"], info["channel_name"], info["thumbnail_url"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
    finally:
        conn.close()

    try:
        video_count = _cache_channel_videos(channel_id)
    except requests.RequestException as exc:
        return jsonify({"error": f"YouTube API error: {exc}"}), 502

    channel = _channel_to_dict(row)
    channel["video_count"] = video_count
    return jsonify(channel), 201


@admin_bp.route("/channels/<channel_id>", methods=["DELETE"])
@require_admin
def delete_channel(channel_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Channel not found"}), 404

        conn.execute("DELETE FROM videos WHERE channel_id = ?", (channel_id,))
        conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        conn.commit()
    finally:
        conn.close()

    return "", 204


@admin_bp.route("/channels/<channel_id>/refresh", methods=["POST"])
@require_admin
def refresh_channel(channel_id):
    if not _get_channel_row(channel_id):
        return jsonify({"error": "Channel not found"}), 404

    conn = get_db()
    try:
        conn.execute("DELETE FROM videos WHERE channel_id = ?", (channel_id,))
        conn.commit()
    finally:
        conn.close()

    try:
        count = _cache_channel_videos(channel_id)
    except requests.RequestException as exc:
        return jsonify({"error": f"YouTube API error: {exc}"}), 502

    return jsonify({"videos_cached": count})
