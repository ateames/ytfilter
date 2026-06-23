# ytfilter

A self-hosted Flask app for curating YouTube content. Add approved channels, cache their videos locally, and serve a filtered browse experience with optional daily watch-time limits.

Designed for households that want a controlled YouTube library—parents manage channels and policies through a web-based admin panel, while viewers browse only videos that meet the configured rules.

## Features

- **Curated channels** — Add YouTube channels by ID or URL; metadata and uploads are fetched via the YouTube Data API and stored in SQLite.
- **Video filtering** — Hide videos shorter than a configurable minimum duration.
- **Minimum watch time** — Optionally require viewers to watch a minimum amount of each video before they can leave the player.
- **Daily watch limits** — Optionally cap how many seconds a user can watch per day (0 = unlimited).
- **Anonymous users** — Viewers are tracked with a cookie-based `user_id`; no login required.
- **Watch history** — Record and retrieve recent viewing sessions per user, with dedicated History and Watch Time pages.
- **Browse UI** — Channel filter, search, and paginated video grid on the home page.
- **Admin panel** — Web UI at `/admin` for managing settings, channels, and viewing usage stats.
- **Block page** — `/blocked` landing page when visitors arrive via a `youtube.com` host header (used with Pi-hole DNS hijacking).
- **Device setup guide** — `/setup` walks users through bookmarking or adding the app to their home screen.
- **Home network deployment** — Optional Pi-hole DNS and nginx configs to serve the app at `https://youtube.home` and redirect `youtube.com` traffic.

## Requirements

- Python 3.11+
- A [YouTube Data API v3](https://developers.google.com/youtube/v3/getting-started) key (required for adding and refreshing channels)

For a full home-network deployment (recommended on a Raspberry Pi):

- [Pi-hole](https://pi-hole.net/) (or another DNS server using dnsmasq) to resolve local domain names to your host
- [nginx](https://nginx.org/) to terminate TLS and reverse-proxy to Flask
- A locally trusted TLS certificate (e.g. via [mkcert](https://github.com/FiloSottile/mkcert))

## Setup

1. **Clone and enter the project**

   ```bash
   cd ytfilter
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:

   | Variable          | Description                                                                 |
   | ----------------- | --------------------------------------------------------------------------- |
   | `YOUTUBE_API_KEY` | YouTube Data API key (required for adding/refreshing channels)              |
   | `SECRET_KEY`      | Flask session secret (change in production)                                 |
   | `ADMIN_TOKEN`     | Secret token for admin panel access and admin API requests                  |
   | `HOST`            | Bind address (default: `0.0.0.0`)                                           |
   | `PORT`            | Server port (default: `5000`)                                               |
   | `APP_BASE_URL`    | Public URL used for links in templates (default: `https://youtube.home`)    |
   | `FLASK_APP`       | Flask app module (default: `app.py`)                                        |

   For local development, set `APP_BASE_URL=http://localhost:5000`.

   Generate `SECRET_KEY` and `ADMIN_TOKEN` in your terminal:

   ```bash
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32)); print('ADMIN_TOKEN=' + secrets.token_urlsafe(32))"
   ```

4. **Run the app**

   The SQLite database is created automatically on first run.

   ```bash
   python app.py
   ```

   Or with Flask's CLI:

   ```bash
   flask run --port 5000
   ```

   Or use the helper script:

   ```bash
   ./run.sh
   ```

   Open [http://localhost:5000](http://localhost:5000) in your browser.

## Admin panel

The admin panel is the primary way to configure ytfilter. It is not linked from the public navigation—access is gated by your `ADMIN_TOKEN`.

### Configure access

1. Set `ADMIN_TOKEN` in `.env` (see [Setup](#setup) above). The app will not grant admin access if this value is missing or empty.
2. Set `YOUTUBE_API_KEY` in `.env`. Channel add and refresh operations call the YouTube Data API and will fail without a valid key.
3. Start the server and open the admin panel with your token in the query string:

   ```
   http://localhost:5000/admin?token=YOUR_ADMIN_TOKEN
   ```

   Replace `YOUR_ADMIN_TOKEN` with the exact value from `.env`. On a home-network deployment, use your `APP_BASE_URL` instead of `localhost`.

4. **Bookmark this URL** for future visits. The token is read from the URL on each page load and sent as an `X-Admin-Token` header on admin API requests made by the panel.

If the token is missing or incorrect, you will see an "Access denied" page instead of the panel.

### What you can manage

The admin panel has three sections:

**Settings** — Values are entered in minutes in the UI and stored as seconds in the database.

| Setting (UI label)              | Stored as                    | Description                                                        |
| ------------------------------- | ---------------------------- | ------------------------------------------------------------------ |
| Minimum video length            | `min_video_length_seconds`   | Videos shorter than this are excluded when channels are cached and from browse results |
| Minimum watch time per video    | `min_watch_time_seconds`     | Viewers must watch at least this long before leaving a video (`0` = no minimum) |
| Daily watch limit               | `max_daily_watch_seconds`    | Maximum seconds a user may watch per day (`0` = unlimited)         |

Click **Save Settings** after changing values. Changing the minimum video length does not automatically re-filter already cached videos—use **Refresh** on a channel to re-fetch and apply the new threshold.

**Channels** — Add channels by pasting a channel ID (`UC…`) or a full YouTube channel URL. The panel extracts the ID automatically. Each new channel is fetched from YouTube and its qualifying videos are cached locally. Use **Refresh** to re-sync a channel's video list, or **Remove** to delete the channel and all of its cached videos.

**Stats** — Shows total cached videos, total channels, and watch sessions recorded today.

### Security notes

- Treat `ADMIN_TOKEN` like a password. Anyone with the token can change settings and manage channels.
- The token appears in the admin URL and may be stored in browser history. Use a long, random value and avoid sharing the bookmarked link.
- The admin panel is intended for trusted administrators on a private network. Use HTTPS in production (see [Home network deployment](#home-network-deployment) below).

## Home network deployment

For an always-on host (e.g. a Raspberry Pi), ytfilter is designed to run behind nginx with TLS, with Pi-hole handling local DNS.

### Architecture

```
Client → Pi-hole DNS (youtube.home, youtube.com → Pi IP)
       → nginx :443 (TLS termination)
       → Flask :5000
```

- **`youtube.home`** — friendly URL for the curated app (`APP_BASE_URL`)
- **`youtube.com`** — nginx redirects to `https://youtube.home` (see `nginx/ytfilter.conf`)
- Flask listens on port **5000** only; nginx binds ports 80 and 443

### 1. Configure environment

Set these in `.env` on the host:

```env
PORT=5000
APP_BASE_URL=https://youtube.home
```

### 2. Run as a systemd service

```bash
sudo cp ytfilter.service /etc/systemd/system/
# Edit WorkingDirectory in ytfilter.service if your install path differs
sudo systemctl enable ytfilter
sudo systemctl start ytfilter
```

### 3. Set up Pi-hole DNS

Follow [pihole-config/INSTALL.md](pihole-config/INSTALL.md). Update `192.168.1.50` in `pihole-config/02-ytfilter-block.conf` to your host's static IP before copying it to Pi-hole.

### 4. Set up nginx with HTTPS

Follow [nginx/INSTALL.md](nginx/INSTALL.md). Generate TLS certificates for `youtube.com`, `www.youtube.com`, `m.youtube.com`, and `youtube.home`, then install the nginx site config.

Install the CA certificate on every client device (phones, tablets, laptops) so browsers trust your local HTTPS cert.

### 5. Verify

```bash
curl -k https://youtube.home -I
curl -k https://youtube.com -I   # should 302 to https://youtube.home
```

Open `https://youtube.home` from a device on your network. The admin panel is at:

```
https://youtube.home/admin?token=YOUR_ADMIN_TOKEN
```

### Alternative: gunicorn

For production without the built-in Flask server, you can use gunicorn instead:

```bash
gunicorn -w 2 -b 127.0.0.1:5000 app:app
```

Update `ytfilter.service` `ExecStart` accordingly. nginx still proxies to port 5000.

## Project structure

```
ytfilter/
├── app.py                  # Flask app entry point and page routes
├── config.py               # Environment-based configuration
├── database.py             # SQLite schema and helpers
├── youtube_service.py      # YouTube Data API client
├── user_routes.py          # Public user API (/api)
├── admin_routes.py         # Admin API (/api/admin)
├── run.sh                  # Simple run script
├── ytfilter.service        # systemd unit file
├── nginx/
│   ├── ytfilter.conf       # nginx reverse proxy + TLS config
│   └── INSTALL.md
├── pihole-config/
│   ├── 02-ytfilter-block.conf
│   └── INSTALL.md
├── templates/
│   ├── admin.html          # Admin panel
│   ├── access_denied.html
│   ├── blocked.html        # YouTube block landing page
│   ├── setup.html          # Device bookmark / home screen guide
│   ├── index.html          # Browse page
│   ├── watch.html          # Video player
│   ├── history.html
│   ├── watchtime.html
│   └── base.html
├── static/
│   ├── css/style.css
│   └── js/                 # admin.js, main.js, player.js, history.js, watchtime.js
├── data/                   # SQLite database (gitignored)
└── requirements.txt
```

## Admin API

The admin panel uses these endpoints. You can also call them directly (e.g. for scripting). All admin endpoints require the `X-Admin-Token` header set to your `ADMIN_TOKEN` value.

### Settings

| Method | Endpoint              | Description          |
| ------ | --------------------- | -------------------- |
| `GET`  | `/api/admin/settings` | Get current settings |
| `POST` | `/api/admin/settings` | Update settings      |

Settings (all values are non-negative integers in **seconds**; `0` disables a limit):

- `min_video_length_seconds` — Videos shorter than this are excluded from browse results and channel caching.
- `min_watch_time_seconds` — Minimum seconds a viewer must watch per video before leaving the player (`0` = no minimum).
- `max_daily_watch_seconds` — Maximum seconds a user may watch per day (`0` = unlimited).

**Example — set a 10-minute minimum video length and 2-hour daily limit:**

```bash
curl -X POST http://localhost:5000/api/admin/settings \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: your_admin_token_here" \
  -d '{
    "min_video_length_seconds": 600,
    "min_watch_time_seconds": 0,
    "max_daily_watch_seconds": 7200
  }'
```

### Channels

| Method   | Endpoint                                   | Description                             |
| -------- | ------------------------------------------ | --------------------------------------- |
| `GET`    | `/api/admin/channels`                      | List all channels                       |
| `POST`   | `/api/admin/channels`                      | Add a channel and cache its videos      |
| `DELETE` | `/api/admin/channels/<channel_id>`         | Remove a channel and its cached videos  |
| `POST`   | `/api/admin/channels/<channel_id>/refresh` | Re-fetch and cache videos for a channel |

**Example — add a channel:**

```bash
curl -X POST http://localhost:5000/api/admin/channels \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: your_admin_token_here" \
  -d '{"channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw"}'
```

Channel IDs can be passed as a bare `UC…` ID or embedded in a YouTube channel URL.

### Stats

| Method | Endpoint            | Description                                              |
| ------ | ------------------- | -------------------------------------------------------- |
| `GET`  | `/api/admin/stats`  | Total videos, channels, and watch sessions today         |

## User API

These endpoints are used by the web UI. A `user_id` cookie is set automatically on first request.

| Method | Endpoint                 | Description                                                       |
| ------ | ------------------------ | ----------------------------------------------------------------- |
| `GET`  | `/api/videos`            | List videos (supports `channel_id`, `search`, `page`, `per_page`) |
| `GET`  | `/api/videos/<video_id>` | Get a single video                                                |
| `GET`  | `/api/channels`          | List approved channels                                            |
| `GET`  | `/api/watchtime`         | Get today's watch-time status for the current user                |
| `POST` | `/api/watchtime`         | Report seconds watched; returns whether viewing is still allowed  |
| `GET`  | `/api/history`           | Get the user's recent watch history (last 50 entries)             |
| `POST` | `/api/history`           | Record a completed or partial viewing session                     |

**Example — check remaining watch time:**

```bash
curl http://localhost:5000/api/watchtime \
  --cookie "user_id=your-user-uuid"
```

## YouTube service CLI

`youtube_service.py` can be run standalone to inspect a channel:

```bash
python youtube_service.py UC_x5XG1OV2P6uZZ5FSM9Ttw
```

## Development notes

- The SQLite database is stored at `data/ytfilter.db` and is listed in `.gitignore`.
- `apscheduler` is included in `requirements.txt` for future scheduled channel refreshes; it is not wired up yet.
- `APP_BASE_URL` is exposed to all templates as `{{ base_url }}` for navigation and setup links.
- Page routes:
  - Browse (`/`)
  - History (`/history`)
  - Watch Time (`/watchtime`)
  - Video player (`/watch/<video_id>`)
  - Block page (`/blocked`)
  - Device setup (`/setup`)
  - Admin panel (`/admin?token=…`)

## License

No license file is included. Add one if you plan to distribute this project.
