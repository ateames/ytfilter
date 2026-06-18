from flask import (
    Flask,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from admin_routes import admin_bp
import config
from config import Config
from database import get_db, get_setting, init_db
from user_routes import (
    _attach_user_cookie,
    _watchtime_status,
    get_or_create_user_id,
    user_bp,
)

app = Flask(__name__)
app.config.from_object(Config)
app.jinja_env.globals["base_url"] = config.APP_BASE_URL
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(user_bp, url_prefix="/api")


@app.route("/blocked")
def blocked():
    blocked_from = request.args.get("from", "")
    return render_template("blocked.html", blocked_from=blocked_from)


@app.route("/setup")
def setup():
    ua = request.headers.get("User-Agent", "").lower()
    if "iphone" in ua or "ipad" in ua:
        device = "ios"
    elif "android" in ua:
        device = "android"
    else:
        device = "desktop"
    return render_template("setup.html", device=device)


@app.route("/")
def index():
    host = request.headers.get("Host", "")
    if "youtube.com" in host:
        return redirect(url_for("blocked"))

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT channel_id, channel_name, thumbnail_url FROM channels "
            "ORDER BY channel_name ASC"
        ).fetchall()
        channels = [dict(row) for row in rows]
    finally:
        conn.close()
    return render_template("index.html", channels=channels)


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/watchtime")
def watchtime():
    return render_template("watchtime.html")


@app.route("/admin")
def admin():
    token = request.args.get("token")
    if not token or not Config.ADMIN_TOKEN or token != Config.ADMIN_TOKEN:
        return render_template("access_denied.html"), 403

    settings = {
        "min_video_length_minutes": int(get_setting("min_video_length_seconds") or 0) // 60,
        "min_watch_time_minutes": int(get_setting("min_watch_time_seconds") or 0) // 60,
        "max_daily_watch_minutes": int(get_setting("max_daily_watch_seconds") or 0) // 60,
    }
    return render_template("admin.html", settings=settings)


@app.route("/watch/<video_id>")
def watch(video_id):
    user_id, is_new = get_or_create_user_id()

    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT v.*, c.channel_name
            FROM videos v
            LEFT JOIN channels c ON v.channel_id = c.channel_id
            WHERE v.video_id = ?
            """,
            (video_id,),
        ).fetchone()

        if not row:
            abort(404)

        watchtime = _watchtime_status(conn, user_id)
        min_watch_time_seconds = int(get_setting("min_watch_time_seconds") or 0)
        max_daily_watch_seconds = int(get_setting("max_daily_watch_seconds") or 0)
    finally:
        conn.close()

    if (
        max_daily_watch_seconds > 0
        and watchtime["seconds_watched_today"] >= max_daily_watch_seconds
    ):
        flash("Daily limit reached", "message")
        response = make_response(redirect(url_for("index")))
        return _attach_user_cookie(response, user_id, is_new)

    player_config = {
        "videoId": video_id,
        "minWatchTimeSeconds": min_watch_time_seconds,
        "maxDailyWatchSeconds": max_daily_watch_seconds,
        "secondsRemaining": watchtime["seconds_remaining"],
        "unlimited": watchtime["unlimited"],
    }

    response = make_response(
        render_template(
            "watch.html",
            video=dict(row),
            player_config=player_config,
        )
    )
    return _attach_user_cookie(response, user_id, is_new)


init_db()

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=False)
