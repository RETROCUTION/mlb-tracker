#!/usr/bin/env python3
"""
Interactive first-run setup for MLB Tracker.

The wizard intentionally does not pick a default team. A user must choose one,
then choose a timezone/location before the tracker service starts.
"""

import argparse
import getpass
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import zoneinfo

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import settings_loader

COMMON_TIMEZONES = [
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Denver",
    "America/Chicago",
    "America/New_York",
    "America/Toronto",
]


def internet_ok(host="statsapi.mlb.com", port=443, timeout=5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run(cmd, check=False):
    print("+ " + " ".join(cmd))
    return subprocess.run(cmd, check=check)


def prompt_yes_no(question, default=True):
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix} ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer y or n.")


def setup_wifi():
    if internet_ok():
        print("Internet connection looks good.")
        return True

    print()
    print("No internet connection detected.")
    print("If you already configured Wi-Fi in Raspberry Pi Imager, wait a bit")
    print("or check your network. Otherwise connect a keyboard and enter Wi-Fi now.")
    print()

    if not prompt_yes_no("Set up Wi-Fi now?", True):
        return False

    country = input("Wi-Fi country code, e.g. US: ").strip().upper() or "US"
    if shutil.which("raspi-config"):
        run(["raspi-config", "nonint", "do_wifi_country", country])

    if shutil.which("nmcli"):
        ssid = input("Wi-Fi network name / SSID: ").strip()
        if not ssid:
            print("No SSID entered.")
            return False
        password = getpass.getpass("Wi-Fi password: ")
        cmd = ["nmcli", "dev", "wifi", "connect", ssid]
        if password:
            cmd += ["password", password]
        result = run(cmd)
        if result.returncode != 0:
            print("nmcli could not connect. You can run nmtui manually and retry.")
            return False
    elif shutil.which("nmtui"):
        print("Opening nmtui. Choose 'Activate a connection' and connect Wi-Fi.")
        run(["nmtui"])
    else:
        print("NetworkManager tools were not found. Run raspi-config manually.")
        return False

    print("Waiting for network...")
    for _ in range(20):
        if internet_ok():
            print("Internet connection is ready.")
            return True
        time.sleep(1)

    print("Still no internet connection.")
    return False


def choose_team():
    teams = sorted(settings_loader.ALL_TEAMS, key=lambda t: t["team_name"])

    print()
    print("Choose the MLB team to track.")
    print()
    for idx, team in enumerate(teams, start=1):
        print(f"{idx:2d}. {team['team_name']} ({team['team_abbr']})")

    by_abbr = {team["team_abbr"].upper(): team for team in teams}
    while True:
        answer = input("Enter team number or abbreviation: ").strip().upper()
        if answer in by_abbr:
            return dict(by_abbr[answer])
        if answer.isdigit():
            idx = int(answer)
            if 1 <= idx <= len(teams):
                return dict(teams[idx - 1])
        print("Please enter a listed number or team abbreviation.")


def choose_timezone(team):
    print()
    print("Choose your location / timezone.")
    print(f"Team timezone is {team['timezone']}. Press Enter to use it,")
    print("or choose one of these common timezones:")
    for idx, tz in enumerate(COMMON_TIMEZONES, start=1):
        print(f"{idx}. {tz}")

    while True:
        answer = input("Timezone number or IANA name: ").strip()
        if not answer:
            tz = team["timezone"]
        elif answer.isdigit() and 1 <= int(answer) <= len(COMMON_TIMEZONES):
            tz = COMMON_TIMEZONES[int(answer) - 1]
        else:
            tz = answer

        try:
            zoneinfo.ZoneInfo(tz)
            return tz
        except Exception:
            print("That timezone was not recognized. Example: America/Los_Angeles")


def write_settings(team, timezone_name):
    data = dict(team)
    data["timezone"] = timezone_name
    settings_loader.save(data)

    owner = os.environ.get("MLB_TRACKER_USER")
    if owner and os.geteuid() == 0:
        run(["chown", owner + ":" + owner, settings_loader.SETTINGS_PATH])

    print()
    print("Saved settings:")
    print(json.dumps(data, indent=2))


def set_system_timezone(timezone_name):
    if shutil.which("timedatectl"):
        run(["timedatectl", "set-timezone", timezone_name])


def finish_first_boot():
    if os.geteuid() != 0 or not shutil.which("systemctl"):
        return

    run(["systemctl", "disable", "mlb-tracker-setup.service"])
    run(["systemctl", "enable", "mlb-tracker.service"])
    run(["systemctl", "restart", "mlb-tracker.service"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-boot", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--wifi-only", action="store_true")
    args = parser.parse_args()

    print()
    print("========================================")
    print(" MLB TRACKER SETUP")
    print("========================================")

    if args.wifi_only:
        ok = setup_wifi()
        return 0 if ok else 1

    if os.path.exists(settings_loader.SETTINGS_PATH) and not args.force:
        print("settings.json already exists. Use --force to reconfigure.")
        if args.first_boot:
            finish_first_boot()
        return 0

    setup_wifi()
    team = choose_team()
    timezone_name = choose_timezone(team)
    write_settings(team, timezone_name)
    set_system_timezone(timezone_name)

    print()
    print("MLB Tracker setup is complete.")

    if args.first_boot:
        finish_first_boot()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
