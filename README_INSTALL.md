# MLB Tracker Fresh Install Guide

This guide starts with a blank microSD card and ends with MLB Tracker running
automatically on boot.

After you SSH into the Raspberry Pi, all terminal commands in this guide are
run on the Raspberry Pi.

## What You Need

- Raspberry Pi Zero W or Raspberry Pi Zero 2 W
- Waveshare 7.5-inch V2 black-and-white e-paper display
- Waveshare driver PCB / HAT for Raspberry Pi
- MicroSD card
- Raspberry Pi power supply
- A computer with Raspberry Pi Imager
- Wi-Fi network name and password
- Optional momentary push buttons

## Recommended Raspberry Pi OS

Use Raspberry Pi OS Lite 32-bit. This is the non-desktop version, and it works
well for Pi Zero W and Pi Zero 2 W.

## 1. Flash The SD Card

1. Install and open Raspberry Pi Imager.
2. Choose your Raspberry Pi model.
3. Choose Raspberry Pi OS Lite 32-bit. This is the non-desktop version.
4. Choose your microSD card.
5. Open OS customization before writing the card.
6. Set the hostname to `mlb-tracker`.
7. Set a username and password.
8. Configure Wi-Fi with your network name, password, country, and timezone.
9. Enable SSH.
10. Write the image to the SD card.

The hostname `mlb-tracker` lets you connect later with:

```bash
ssh pi@mlb-tracker.local
```

It also lets the config screen show:

```text
http://mlb-tracker.local:8765
```

## 2. First Boot

1. Put the SD card into the Raspberry Pi.
2. Connect the Waveshare display and driver board.
3. Power on the Raspberry Pi.
4. Wait a few minutes for first boot. It is normal for SSH to take several
   minutes before it works the first time.

## 3. Connect With SSH

From your computer, open Terminal and run:

```bash
ssh pi@mlb-tracker.local
```

If you chose a username other than `pi`, replace `pi` with your username.

If the hostname does not work, find the Pi's IP address in your router and run:

```bash
ssh pi@YOUR_PI_IP_ADDRESS
```

## 4. Install MLB Tracker

Copy and paste this whole block into the Raspberry Pi terminal:

```bash
sudo apt update
sudo apt install -y curl unzip
curl -L -o mlb-tracker-installer.zip https://github.com/RETROCUTION/mlb-tracker/releases/download/v0.1.0/mlb-tracker-installer.zip
unzip mlb-tracker-installer.zip
cd mlb-tracker-installer
sudo ./install.sh
```

What this does:

- `sudo apt update` refreshes the Raspberry Pi package list.
- `sudo apt install -y curl unzip` installs tools for downloading and unzipping.
- `curl -L -o mlb-tracker-installer.zip ...` downloads MLB Tracker from GitHub.
- `unzip mlb-tracker-installer.zip` extracts the installer files.
- `cd mlb-tracker-installer` opens the installer folder.
- `sudo ./install.sh` runs the installer.

The installer:

- Installs required Raspberry Pi packages.
- Enables SPI for the Waveshare display.
- Installs the Waveshare e-paper Python driver.
- Copies MLB Tracker to `~/mlb-tracker`.
- Creates the `mlb-tracker` system service.
- Starts the setup wizard.

Choose your team and timezone when prompted.

## 5. Check That It Is Running

```bash
sudo systemctl status mlb-tracker --no-pager
```

This shows whether the service is active.

To view recent logs:

```bash
journalctl -u mlb-tracker -n 150 --no-pager -l
```

Logs help diagnose display, Wi-Fi, or MLB API connection issues.

## Reconfigure Later

### With Buttons

Use this when the Raspberry Pi is already connected to Wi-Fi.

Hold Left and Right together for 3 seconds. The display shows the local config
address. Open that address on a phone or computer on the same Wi-Fi network to
change team or timezone.

This method cannot help if the Pi is not connected to Wi-Fi, because your phone
or computer will not be able to reach the config page.

### With Keyboard Or Terminal

Use this for Wi-Fi changes, team changes, timezone changes, or Wi-Fi recovery.

If Wi-Fi still works, SSH into the Raspberry Pi. If Wi-Fi is broken, connect a
keyboard and HDMI display to the Pi, log in, and run:

```bash
cd ~/mlb-tracker
sudo systemctl stop mlb-tracker
python3 scripts/setup_wizard.py --force
sudo systemctl start mlb-tracker
```

What this does:

- Opens the installed project folder.
- Stops the display service while settings are changed.
- Runs the setup wizard again for Wi-Fi, team, and timezone.
- Starts the display service again.

## Service Commands

Check service status:

```bash
sudo systemctl status mlb-tracker --no-pager
```

Restart the tracker:

```bash
sudo systemctl restart mlb-tracker
```

View recent logs:

```bash
journalctl -u mlb-tracker -n 150 --no-pager -l
```

## Quick Update Later

After MLB Tracker is already installed, use the quick updater:

```bash
curl -fsSL https://raw.githubusercontent.com/RETROCUTION/mlb-tracker/main/update.sh | sudo bash
```

This updates the app files, keeps your team settings/cache/output, and restarts
the service. It skips the slower first-time installer steps.

## Full Reinstall Or Repair

Use this if the first install did not finish, dependencies are missing, or you
are setting up a fresh image:

```bash
curl -L -o mlb-tracker-installer.zip https://github.com/RETROCUTION/mlb-tracker/releases/download/v0.1.0/mlb-tracker-installer.zip
unzip -o mlb-tracker-installer.zip
cd mlb-tracker-installer
sudo ./install.sh
```

The installer keeps your existing team settings, cache, and output folders
unless you run the setup wizard again.
