#!/usr/bin/env bash
# Set wallpaper
feh --bg-scale /home/Kam/Pictures/rings-around-the-fractal-planet-53886-1920x1080.jpg
# Start compositor
picom &

# Start NetworkManager TUI (optional, comment if not needed)
# nmtui &
nm-applet &

# Other startup programs
xbacklight -set 50 &
pavucontrol &
blueman-applet &
xfce4-power-manager &
