To start create a new SD card with the headless (no GUI) Bookworm OS. 
When creating the SD with the
Raspberry Pi image create a new user pi and password raspberry (or what ever you like)
and hostname raspberrypi

Insert the SD in the Pi Zero and use a program LanScan to find the raspberrypi device
on your network. It may take time, since bookworm does a lot of startup the first 
time the device boots up. Once you see the device on network, ssh into using the pi
user eg. ssh pi@192.168.0.133. Use the raspberry password to login

Use an editor such as nano or vi and copy install.sh into a file called install.sh
Use the command "chmod +x install.sh"
then run ./install.sh

The script will run and eventually ask for input when btwifiset runs. Hit the return 
key until it starts again

Once its all complete run the following commands to insure everything is running
sudo systemctl status app
sudo systemctl status metar-v4
sudo systemctl status metar-display-v4



