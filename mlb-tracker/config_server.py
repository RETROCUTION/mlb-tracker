import html
import json
import logging
import os
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import settings_loader

logger = logging.getLogger(__name__)

PORT = 8765
_server = None
_thread = None
_on_saved = None


def start(on_saved=None):
    global _server, _thread, _on_saved

    _on_saved = on_saved
    if _server:
        return config_url()

    _server = ThreadingHTTPServer(("", PORT), _Handler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    logger.info("Config server started at %s", config_url())
    return config_url()


def stop():
    global _server, _thread

    if _server:
        _server.shutdown()
        _server.server_close()
    _server = None
    _thread = None


def config_url():
    return f"http://{_local_hostname()}:{PORT}"


def _local_hostname():
    try:
        return socket.gethostname() + ".local"
    except Exception:
        return "mlb-tracker.local"


def _local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return ""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info("Config web: " + fmt, *args)

    def do_GET(self):
        self._send_html(_render_form())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body)

        result = _save_config(form)
        self._send_html(_render_done(result))

        if result["saved"] and _on_saved:
            threading.Timer(2.0, _on_saved).start()

    def _send_html(self, body):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _current_settings():
    try:
        return settings_loader.load()
    except Exception:
        return {}


def _render_form():
    settings = _current_settings()
    current_abbr = settings.get("team_abbr", "")
    current_tz = settings.get("timezone", "")

    team_options = []
    for team in sorted(settings_loader.ALL_TEAMS, key=lambda t: t["team_name"]):
        selected = " selected" if team["team_abbr"] == current_abbr else ""
        label = f"{team['team_name']} ({team['team_abbr']})"
        team_options.append(
            f'<option value="{html.escape(team["team_abbr"])}"{selected}>'
            f"{html.escape(label)}</option>"
        )

    zones = sorted({
        "America/Los_Angeles",
        "America/Phoenix",
        "America/Denver",
        "America/Chicago",
        "America/New_York",
        "America/Toronto",
        current_tz,
    })
    tz_options = []
    for zone in zones:
        if not zone:
            continue
        selected = " selected" if zone == current_tz else ""
        tz_options.append(
            f'<option value="{html.escape(zone)}"{selected}>{html.escape(zone)}</option>'
        )

    ip = _local_ip()
    ip_note = f"<p>IP address: <code>http://{html.escape(ip)}:{PORT}</code></p>" if ip else ""
    wifi_options = _wifi_options()
    wifi_select = "".join(
        f'<option value="{html.escape(ssid)}">{html.escape(ssid)}</option>'
        for ssid in wifi_options
    )

    return f"""<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLB Tracker Config</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; max-width: 760px; }}
    label {{ display: block; font-weight: 700; margin-top: 18px; }}
    select, input {{ box-sizing: border-box; font-size: 16px; margin-top: 6px; padding: 10px; width: 100%; }}
    button {{ font-size: 17px; font-weight: 700; margin-top: 24px; padding: 12px 16px; }}
    .note {{ background: #f2f2f2; border-left: 4px solid #111; padding: 12px; }}
  </style>
</head>
<body>
  <h1>MLB Tracker Config</h1>
  <p class="note">Change the tracked team, timezone, or Wi-Fi. Saving team/timezone restarts MLB Tracker automatically.</p>
  {ip_note}
  <form method="post">
    <label for="team">Team</label>
    <select id="team" name="team_abbr">{''.join(team_options)}</select>

    <label for="timezone">Timezone</label>
    <select id="timezone" name="timezone">{''.join(tz_options)}</select>

    <label for="ssid_select">Wi-Fi network</label>
    <select id="ssid_select" name="ssid_select">
      <option value="">Keep current Wi-Fi</option>
      {wifi_select}
    </select>

    <label for="ssid">Other Wi-Fi network name / SSID</label>
    <input id="ssid" name="ssid" autocomplete="off" placeholder="Use only if your network is not listed">

    <label for="wifi_password">Wi-Fi password</label>
    <input id="wifi_password" name="wifi_password" type="password" autocomplete="new-password" placeholder="Leave blank to keep current Wi-Fi">

    <button type="submit">Save Settings</button>
  </form>
</body>
</html>"""


def _render_done(result):
    messages = "".join(f"<li>{html.escape(msg)}</li>" for msg in result["messages"])
    return f"""<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLB Tracker Config Saved</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; max-width: 760px; }}
    a {{ display: inline-block; margin-top: 18px; }}
  </style>
</head>
<body>
  <h1>{'Saved' if result['saved'] else 'Not Saved'}</h1>
  <ul>{messages}</ul>
  <p>If team or timezone changed, the tracker will restart and load the new settings.</p>
  <a href="/">Back to config</a>
</body>
</html>"""


def _save_config(form):
    messages = []
    saved = False

    team_abbr = _first(form, "team_abbr").upper()
    timezone_name = _first(form, "timezone")
    team = next((t for t in settings_loader.ALL_TEAMS if t["team_abbr"] == team_abbr), None)

    if not team:
        return {"saved": False, "messages": ["Unknown team selection."]}

    data = dict(team)
    data["timezone"] = timezone_name or team["timezone"]
    settings_loader.save(data)
    saved = True
    messages.append(f"Tracking {data['team_name']} in {data['timezone']}.")

    ssid = _first(form, "ssid") or _first(form, "ssid_select")
    wifi_password = _first(form, "wifi_password")
    if ssid:
        ok, message = _connect_wifi(ssid, wifi_password)
        messages.append(message)
        if not ok:
            messages.append("Team/timezone were still saved.")

    return {"saved": saved, "messages": messages}


def _wifi_options():
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        )
    except Exception:
        return []

    seen = set()
    out = []
    for line in result.stdout.splitlines():
        ssid = line.replace("\\:", ":").strip()
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        out.append(ssid)
    return out[:20]


def _first(form, key):
    values = form.get(key, [""])
    return values[0].strip()


def _connect_wifi(ssid, password):
    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45,
        )
    except FileNotFoundError:
        return False, "Wi-Fi change failed: nmcli is not installed."
    except Exception as e:
        return False, f"Wi-Fi change failed: {e}"

    if result.returncode == 0:
        return True, f"Wi-Fi connected to {ssid}."

    err = result.stderr.strip() or result.stdout.strip() or "unknown error"
    return False, f"Wi-Fi change failed: {err}"
