# MLB Tracker Installer

MLB Tracker is a Raspberry Pi e-paper baseball dashboard for any MLB team.
Fresh installs require the user to choose a team and timezone.

## What You Need

- Raspberry Pi Zero W or Zero 2 W
- Waveshare 7.5-inch V2 black-and-white e-paper display
- Waveshare driver PCB / HAT for Raspberry Pi
- MicroSD card
- Raspberry Pi power supply
- A computer with Raspberry Pi Imager
- Wi-Fi network name and password
- Optional GPIO buttons

## Recommended Pi OS

For Pi Zero W, use Raspberry Pi OS Lite 32-bit.
For Pi Zero 2 W, Raspberry Pi OS Lite 32-bit is still the safest shared image
if you want one card/package to work across both boards.

## 1. Flash The SD Card

1. Install and open Raspberry Pi Imager.
2. Choose your Raspberry Pi model.
3. Choose Raspberry Pi OS Lite 32-bit.
4. Choose your microSD card.
5. Open OS customization before writing the card.
6. Set a hostname, for example:

```text
mlb-tracker
```

7. Set a username and password.
8. Configure Wi-Fi with your network name, password, country, and timezone.
9. Enable SSH.
10. Write the image to the SD card.

## 2. First Boot

1. Put the SD card into the Raspberry Pi.
2. Connect the Waveshare display and driver board.
3. Power on the Raspberry Pi.
4. Wait a few minutes for first boot.

From your computer, connect with SSH. Replace `pi` if you chose a different
username in Raspberry Pi Imager:

```bash
ssh pi@mlb-tracker.local
```

If that hostname does not work, find the Pi's IP address from your router and
connect with:

```bash
ssh pi@YOUR_PI_IP_ADDRESS
```

## 3. Install Required Tools

On the Raspberry Pi:

```bash
sudo apt update
sudo apt install -y git curl unzip
```

## 4. Download MLB Tracker

Download the latest installer release:

```bash
curl -L -o mlb-tracker-installer.zip https://github.com/RETROCUTION/mlb-tracker/releases/download/v0.1.0/mlb-tracker-installer.zip
```

Unzip it:

```bash
unzip mlb-tracker-installer.zip
cd mlb-tracker-installer
```

## 5. Run The Installer

```bash
sudo ./install.sh
```

The installer will:

- install Python dependencies
- enable SPI
- install the Waveshare e-Paper Python driver
- install MLB Tracker to `~/mlb-tracker`
- create `mlb-tracker.service`
- run the setup wizard so the user chooses team and timezone

Follow the setup prompts to choose your team and timezone. If Wi-Fi was not
configured in Raspberry Pi Imager, the setup wizard can help configure it from
an attached keyboard/display.

## 6. Verify It Is Running

```bash
sudo systemctl status mlb-tracker --no-pager
```

To watch logs:

```bash
journalctl -u mlb-tracker -n 150 --no-pager -l
```

The service is enabled automatically and starts again after reboot.

## Button Reconfiguration Shortcut

Hold LEFT and RIGHT together for 3 seconds to show reconfiguration instructions
on the e-paper display. LEFT and RIGHT are primarily used to scroll the schedule
screen.

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

The installer preserves the existing team settings, cache, and output folders
unless you reconfigure with the setup wizard.
