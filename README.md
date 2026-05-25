# MLB Tracker

MLB Tracker is a Raspberry Pi e-paper dashboard for baseball fans. It shows
team briefing info, schedule, MLB rankings, pregame/live game screens, running
seconds, live scores, inning state, pitch count, runners, and e-paper friendly
full-screen partial refresh.

The project was originally built as a Dodgers tracker, but the installer now
requires each user to choose their own team and timezone.

## Hardware

- Raspberry Pi Zero W or Zero 2 W
- Waveshare 7.5-inch V2 black-and-white e-paper display
- Python driver: `waveshare_epd.epd7in5_V2`
- Optional GPIO buttons:
  - Left: GPIO 5
  - Center: GPIO 6
  - Right: GPIO 13
  - Live game: GPIO 26

## Install

Use the packaged installer zip from a release:

```bash
unzip mlb-tracker-installer.zip
cd mlb-tracker-installer
sudo ./install.sh
```

The installer copies the app to `~/mlb-tracker`, installs dependencies, enables
SPI, installs the Waveshare driver, creates the `mlb-tracker` systemd service,
and runs the setup wizard.

See `README_INSTALL.md` for fresh-image details.

## Reconfigure Team Or Timezone

```bash
cd ~/mlb-tracker
sudo systemctl stop mlb-tracker
python3 scripts/setup_wizard.py --force
sudo systemctl start mlb-tracker
```

## Service Commands

```bash
sudo systemctl restart mlb-tracker
sudo systemctl status mlb-tracker --no-pager
journalctl -u mlb-tracker -n 150 --no-pager -l
```

## Notes

Fresh installer packages should not include `settings.json`. That file is
created by the setup wizard so every user explicitly chooses their team.
