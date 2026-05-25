# MLB Tracker Installer

MLB Tracker is a Raspberry Pi e-paper baseball dashboard for any MLB team.
It was originally built as a Dodgers tracker, but fresh installs now require
the user to choose a team and timezone.

## Recommended Pi OS

For Pi Zero W, use Raspberry Pi OS Lite 32-bit.
For Pi Zero 2 W, Raspberry Pi OS Lite 32-bit is still the safest shared image
if you want one card/package to work across both boards.

## Fresh Install

1. Flash Raspberry Pi OS Lite 32-bit with Raspberry Pi Imager.
2. Configure Wi-Fi/SSH in Imager if you can. If not, the installer can prompt
   for Wi-Fi when run from a keyboard/terminal.
3. Copy `mlb-tracker-installer.zip` to the Pi.
4. On the Pi:

```bash
unzip mlb-tracker-installer.zip
cd mlb-tracker-installer
sudo ./install.sh
```

The installer will:

- install Python dependencies
- enable SPI
- install the Waveshare e-Paper Python driver
- install MLB Tracker to `~/mlb-tracker`
- create `mlb-tracker.service`
- run the setup wizard so the user chooses team and timezone

If the installer is run without an interactive terminal and no settings exist,
it enables `mlb-tracker-setup.service`. On next boot, connect a keyboard and
display to the Pi and complete the first-run wizard on the console.

## Reconfigure Later

```bash
cd ~/mlb-tracker
sudo systemctl stop mlb-tracker
python3 scripts/setup_wizard.py --force
sudo systemctl start mlb-tracker
```

## Useful Commands

```bash
sudo systemctl status mlb-tracker --no-pager
sudo systemctl restart mlb-tracker
journalctl -u mlb-tracker -n 150 --no-pager -l
```

## Updating

Unzip a newer installer package and run:

```bash
sudo ./install.sh
```

The installer preserves the existing `settings.json`, cache, and output
folders unless you reconfigure with the setup wizard.
