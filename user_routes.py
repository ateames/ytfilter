import math
import uuid
from functools import wraps

from flask import Blueprint, jsonify, make_response, request

from database import get_db, get_setting

user_bp = Blueprint("user", __name__)

USER_ID_COOKIE = "user_id"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def get_or_create_user_id() -> tuple[str, bool]:
    user_id = request.cookies.get(USER_ID_COOKIE)
    if user_id:
        return user_id, False
    return str(uuid.uuid4()), True


def _attach_user_cookie(response, user_id: str, is_new: bool):
    if is_new:
        response.set_cookie(
            USER_ID_COOKIE,
            user_id,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
        )
    return response


def with_user(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id, is_new = get_or_create_user_id()
        result = f(user_id, *args, **kwargs)
        if isinstance(result, tuple):
            body = result[0]
            status = result[1] if len(result) > 1 else 200
            response = make_response(body, status)
        else:
            response = make_response(result)
        return _attach_user_cookie(response, user_id, is_new)

    return decorated


def _min_video_length() -> int:
    return int(get_setting("min_video_length_seconds") or 0)


def _max_daily_watch() -> int:
    return int(get_setting("max_daily_watch_seconds") or 0)


def _video_to_dict(row) -> dict:
    return {
        "video_id": row["video_id"],
        "channel_id": row["channel_id"],
        "title": row["title"],
        "description": row["description"],
        "duration_seconds": row["duration_seconds"],
        "thumbnail_url": row["thumbnail_url"],
        "published_at": row["published_at"],
    }


def _channel_to_dict(row) -> dict:
    return {
        "channel_id": row["channel_id"],
        "channel_name": row["channel_name"],
        "thumbnail_url": row["thumbnail_url"],
        "added_at": row["added_at"],
    }


def _seconds_watched_today(conn, user_id: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(seconds_watched), 0) AS total
        FROM watch_sessions
        WHERE user_id = ? AND started_at >= date('now')
        """,
        (user_id,),
    ).fetchone()
    return int(row["total"])


def _today_breakdown(conn, user_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            ws.video_id,
            v.title,
            SUM(ws.seconds_watched) AS seconds_watched,
            MAX(ws.started_at) AS last_watched
        FROM watch_sessions ws
        JOIN videos v ON ws.video_id = v.video_id
        WHERE ws.user_id = ? AND ws.started_at >= date('now')
        GROUP BY ws.video_id
        ORDER BY last_watched DESC
        LIMIT 5
        """,
        (user_id,),
    ).fetchall()
    return [
        {
            "video_id": row["video_id"],
            "title": row["title"],
            "seconds_watched": int(row["seconds_watched"]),
        }
        for row in rows
    ]


def _watchtime_status(conn, user_id: str) -> dict:
    seconds_watched_today = _seconds_watched_today(conn, user_id)
    limit = _max_daily_watch()
    unlimited = limit == 0
    seconds_remaining = max(0, limit - seconds_watched_today) if not unlimited else 0
    return {
        "seconds_watched_today": seconds_watched_today,
        "seconds_remaining": seconds_remaining,
        "limit": limit,
        "unlimited": unlimited,
        "today_breakdown": _today_breakdown(conn, user_id),
    }


@user_bp.route("/videos", methods=["GET"])
@with_user
def list_videos(user_id):
    channel_id = request.args.get("channel_id")
    search = request.args.get("search", "").strip()
    page = max(1, request.args.get("page", 1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", 24, type=int) or 24, 100))
    min_length = _min_video_length()

    conditions = ["duration_seconds >= ?"]
    params: list = [min_length]

    if channel_id:
        conditions.append("channel_id = ?")
        params.append(channel_id)

    if search:
        conditions.append("(title LIKE ? OR description LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    where = " AND ".join(conditions)

    conn = get_db()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) AS count FROM videos WHERE {where}", params
        ).fetchone()["count"]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f"""
            SELECT * FROM videos
            WHERE {where}
            ORDER BY published_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, per_page, offset],
        ).fetchall()
    finally:
        conn.close()

    pages = math.ceil(total / per_page) if total else 0
    return jsonify(
        {
            "videos": [_video_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "pages": pages,
        }
    )


@user_bp.route("/videos/<video_id>", methods=["GET"])
@with_user
def get_video(user_id, video_id):
    min_length = _min_video_length()
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT * FROM videos
            WHERE video_id = ? AND duration_seconds >= ?
            """,
            (video_id, min_length),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Video not found"}), 404

    return jsonify(_video_to_dict(row))


@user_bp.route("/channels", methods=["GET"])
@with_user
def list_channels(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM channels ORDER BY channel_name ASC"
        ).fetchall()
    finally:
        conn.close()

    return jsonify([_channel_to_dict(row) for row in rows])


@user_bp.route("/watchtime", methods=["GET"])
@with_user
def get_watchtime(user_id):
    conn = get_db()
    try:
        status = _watchtime_status(conn, user_id)
    finally:
        conn.close()

    return jsonify(status)


@user_bp.route("/watchtime", methods=["POST"])
@with_user
def post_watchtime(user_id):
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    video_id = data.get("video_id")
    seconds = data.get("seconds")

    if not video_id or not isinstance(video_id, str):
        return jsonify({"error": "video_id is required"}), 400
    if not isinstance(seconds, int) or seconds < 0:
        return jsonify({"error": "seconds must be a non-negative integer"}), 400

    min_length = _min_video_length()
    conn = get_db()
    try:
        video = conn.execute(
            """
            SELECT 1 FROM videos
            WHERE video_id = ? AND duration_seconds >= ?
            """,
            (video_id, min_length),
        ).fetchone()
        if not video:
            return jsonify({"error": "Video not found"}), 404

        seconds_watched_today = _seconds_watched_today(conn, user_id)
        limit = _max_daily_watch()
        unlimited = limit == 0

        if not unlimited and seconds_watched_today + seconds > limit:
            seconds_remaining = max(0, limit - seconds_watched_today)
            return jsonify(
                {
                    "allowed": False,
                    "seconds_watched_today": seconds_watched_today,
                    "seconds_remaining": seconds_remaining,
                }
            )

        conn.execute(
            """
            INSERT INTO watch_sessions (user_id, video_id, seconds_watched)
            VALUES (?, ?, ?)
            """,
            (user_id, video_id, seconds),
        )
        conn.commit()

        seconds_watched_today += seconds
        seconds_remaining = (
            max(0, limit - seconds_watched_today) if not unlimited else 0
        )
    finally:
        conn.close()

    return jsonify(
        {
            "allowed": True,
            "seconds_watched_today": seconds_watched_today,
            "seconds_remaining": seconds_remaining,
        }
    )


@user_bp.route("/history", methods=["POST"])
@with_user
def post_history(user_id):
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    video_id = data.get("video_id")
    seconds_watched = data.get("seconds_watched")
    completed = data.get("completed")

    if not video_id or not isinstance(video_id, str):
        return jsonify({"error": "video_id is required"}), 400
    if not isinstance(seconds_watched, int) or seconds_watched < 0:
        return jsonify({"error": "seconds_watched must be a non-negative integer"}), 400
    if not isinstance(completed, bool):
        return jsonify({"error": "completed must be a boolean"}), 400

    conn = get_db()
    try:
        video = conn.execute(
            "SELECT 1 FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        if not video:
            return jsonify({"error": "Video not found"}), 404

        conn.execute(
            """
            INSERT INTO watch_history (user_id, video_id, seconds_watched)
            VALUES (?, ?, ?)
            """,
            (user_id, video_id, seconds_watched),
        )
        conn.commit()
    finally:
        conn.close()

    return "", 201


@user_bp.route("/history", methods=["GET"])
@with_user
def get_history(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT
                wh.id,
                wh.video_id,
                wh.watched_at,
                wh.seconds_watched,
                v.title,
                v.thumbnail_url,
                v.channel_id,
                c.channel_name
            FROM watch_history wh
            JOIN videos v ON wh.video_id = v.video_id
            LEFT JOIN channels c ON v.channel_id = c.channel_id
            WHERE wh.user_id = ?
            ORDER BY wh.watched_at DESC
            LIMIT 50
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    return jsonify(
        [
            {
                "id": row["id"],
                "video_id": row["video_id"],
                "watched_at": row["watched_at"],
                "seconds_watched": row["seconds_watched"],
                "title": row["title"],
                "thumbnail_url": row["thumbnail_url"],
                "channel_id": row["channel_id"],
                "channel_name": row["channel_name"],
            }
            for row in rows
        ]
    )
