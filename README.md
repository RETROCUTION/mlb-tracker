# MLB Tracker

MLB Tracker is a Raspberry Pi e-paper dashboard for baseball fans. It shows
team briefing info, schedule, MLB rankings, pregame/live game screens, running
seconds, live scores, inning state, pitch count, runners, and e-paper friendly
full-screen partial refresh.

Fresh installs require each user to choose their own team and timezone.

## Parts List

Disclosure: Some product links may be affiliate links. As an Amazon Associate,
the project maintainer may earn from qualifying purchases.

Replace `YOURTAG-20` with your Amazon Associates tracking ID before publishing
affiliate links.

- [Raspberry Pi Zero 2 W](https://www.amazon.com/s?k=Raspberry+Pi+Zero+2+W&tag=YOURTAG-20)
- [Raspberry Pi Zero W](https://www.amazon.com/s?k=Raspberry+Pi+Zero+W&tag=YOURTAG-20)
- [Waveshare 7.5-inch V2 black-and-white e-paper display](https://www.amazon.com/s?k=Waveshare+7.5+inch+e-Paper+V2&tag=YOURTAG-20)
- [MicroSD card](https://www.amazon.com/s?k=microSD+card+32GB&tag=YOURTAG-20)
- [5V Raspberry Pi power supply](https://www.amazon.com/s?k=Raspberry+Pi+5V+power+supply&tag=YOURTAG-20)
- [GPIO momentary push buttons](https://www.amazon.com/s?k=GPIO+momentary+push+button&tag=YOURTAG-20)

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
