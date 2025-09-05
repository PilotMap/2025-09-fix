# Make sure you run this as sudo
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y git emacs-nox
sudo apt install -y python3-pip python3-venv uwsgi uwsgi-plugin-python3 nginx python3-numpy libopenjp2-7
sudo raspi-config nonint do_i2c 0

python3 -m venv --system-site-packages livesectional
cd livesectional
source bin/activate

git clone https://github.com/PilotMap/livesectional.git
cd livesectional
git checkout cleanup
pip3 install adafruit-circuitpython-neopixel
pip3 install --force-reinstall adafruit-blinka
pip3 install -r requirements.txt


# For Model 3 A plus because rpi_ws281x does not support it
# git clone --recurse-submodules https://github.com/rpi-ws281x/rpi-ws281x-python
# edit library/lib/rpihw.c and add this https://github.com/jgarff/rpi_ws281x/pull/542/files
# these are the full instructions https://github.com/jgarff/rpi_ws281x/issues/483
# Do it in the virtualenv, not as sudo

# Install BTWifi
# sudo curl  -L https://raw.githubusercontent.com/nksan/Rpi-SetWiFi-viaBluetooth/main/btwifisetInstall.sh | bash

# Install BerryLan
#echo -e "deb http://repository.nymea.io $(lsb_release -s -c) main" | sudo tee /etc/apt/sources.list.d/nymea.list
#sudo wget -O /etc/apt/trusted.gpg.d/nymea.gpg https://repository.nymea.io/nymea.gpg
#sudo apt update
#sudo apt install -y nymea-networkmanager dirmngr


chmod +x /home/pi/livesectional/livesectional/etc/install.sh
sudo /home/pi/livesectional/livesectional/etc/install.sh
