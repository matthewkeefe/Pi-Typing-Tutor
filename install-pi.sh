#!/usr/bin/env bash
#
# Turn a stock Raspberry Pi OS Lite install into a locked typing-tutor
# appliance. Run once, on the Pi, as root:
#
#     sudo ./install-pi.sh
#
# What it does:
#   * disables wifi and Bluetooth at the firmware level (before Linux boots)
#   * blacklists the wireless kernel modules as a second layer
#   * creates an unprivileged 'typist' user with no shell access
#   * autologins tty1 as typist and launches the tutor in a respawn loop
#   * removes tty2-tty6 so Ctrl+Alt+F2 can't reach a prompt
#
# Ethernet is left working on purpose -- that's your maintenance path.
# Just don't leave a cable plugged in during normal use.
#
set -euo pipefail

APP_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR=/opt/typing-tutor
DATA_DIR=/var/lib/typing-tutor
USER_NAME=typist

if [[ $EUID -ne 0 ]]; then
    echo "Run this with sudo." >&2
    exit 1
fi

# Recent Raspberry Pi OS moved the boot partition; support both.
if   [[ -f /boot/firmware/config.txt ]]; then BOOT_CFG=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]];          then BOOT_CFG=/boot/config.txt
else
    echo "Can't find config.txt -- is this Raspberry Pi OS?" >&2
    exit 1
fi

say() { printf '\n=== %s\n' "$1"; }

# ---------------------------------------------------------------- wifi off
say "Disabling wifi and Bluetooth in $BOOT_CFG"
for overlay in disable-wifi disable-bt; do
    if grep -q "^dtoverlay=${overlay}$" "$BOOT_CFG"; then
        echo "  already set: $overlay"
    else
        echo "dtoverlay=${overlay}" >> "$BOOT_CFG"
        echo "  added: $overlay"
    fi
done

say "Blacklisting wireless kernel modules"
cat > /etc/modprobe.d/no-wireless.conf <<'EOF'
# Typing tutor appliance: no wireless, by design.
blacklist brcmfmac
blacklist brcmutil
blacklist cfg80211
blacklist mac80211
blacklist btbcm
blacklist hci_uart
blacklist bluetooth
EOF

systemctl disable --now wpa_supplicant.service 2>/dev/null || true
systemctl disable --now bluetooth.service      2>/dev/null || true
systemctl mask    wpa_supplicant.service       2>/dev/null || true

# ---------------------------------------------------------------- the app
say "Installing the app to $APP_DIR"
mkdir -p "$APP_DIR"
cp -r "$APP_SRC"/main.py "$APP_SRC"/core "$APP_SRC"/modes "$APP_DIR"/
mkdir -p "$APP_DIR/data"
# Keep an existing passages.txt rather than clobbering the parent's edits.
if [[ -f "$APP_SRC/data/passages.txt" && ! -f "$DATA_DIR/passages.txt" ]]; then
    mkdir -p "$DATA_DIR"
    cp "$APP_SRC/data/passages.txt" "$DATA_DIR/passages.txt"
fi
find "$APP_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

if ! command -v python3 >/dev/null; then
    say "Installing python3"
    apt-get update && apt-get install -y python3
fi

# ---------------------------------------------------------------- the user
say "Creating the '$USER_NAME' user"
if id "$USER_NAME" &>/dev/null; then
    echo "  already exists"
else
    adduser --disabled-password --gecos "Typing Tutor" "$USER_NAME"
fi
mkdir -p "$DATA_DIR"
chown -R "$USER_NAME:$USER_NAME" "$DATA_DIR"

say "Setting the launch loop"
cat > "/home/$USER_NAME/.bash_profile" <<EOF
# Launch the typing tutor on the console and never let go of it.
if [ "\$(tty)" = "/dev/tty1" ]; then
    trap '' INT TSTP QUIT
    while true; do
        TYPING_TUTOR_DATA=$DATA_DIR TERM=linux python3 $APP_DIR/main.py
        sleep 1
    done
fi
EOF
chown "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.bash_profile"

# ---------------------------------------------------------------- autologin
say "Enabling console autologin on tty1"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER_NAME --noclear %I \$TERM
EOF

say "Removing the spare virtual terminals"
if grep -q '^#*NAutoVTs=' /etc/systemd/logind.conf; then
    sed -i 's/^#*NAutoVTs=.*/NAutoVTs=1/' /etc/systemd/logind.conf
else
    echo 'NAutoVTs=1' >> /etc/systemd/logind.conf
fi

systemctl set-default multi-user.target
systemctl daemon-reload

cat <<EOF

=== Done.

Reboot and it comes up straight into the tutor.

    sudo reboot

Maintenance, when you need it:
  * plug in ethernet and SSH in as your normal user
  * or pull the card and edit it on the Mac
  * save data lives in $DATA_DIR/profiles.json
  * memorize passages live in $DATA_DIR/passages.txt

To undo the lockdown:
  sudo rm /etc/systemd/system/getty@tty1.service.d/autologin.conf
  sudo rm /etc/modprobe.d/no-wireless.conf
  # then remove the two dtoverlay lines from $BOOT_CFG

EOF
