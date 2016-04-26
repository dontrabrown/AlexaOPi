#! /bin/bash

git clone https://github.com/duxingkei33/orangepi_PC_gpio_pyH3.git
python orangepi_PC_gpio_pyH3/setup.py install 
wget --output-document vlc.py "http://git.videolan.org/?p=vlc/bindings/python.git;a=blob_plain;f=generated/vlc.py;hb=HEAD"
apt-get update
apt-get install libasound2-dev memcached python-pip python-alsaaudio vlc -y
pip install -r requirements.txt
cp initd_alexa.sh /etc/init.d/AlexaPi
update-rc.d AlexaPi defaults
touch /var/log/alexa.log

echo "Enter your ProductID:"
read productid
echo ProductID = \"$productid\" >> creds.py

echo "Enter your Security Profile Description:"
read spd
echo Security_Profile_Description = \"$spd\" >> creds.py

echo "Enter your Security Profile ID:"
read spid
echo Security_Profile_ID = \"$spid\" >> creds.py

echo "Enter your Security Client ID:"
read cid
echo Client_ID = \"$cid\" >> creds.py

echo "Enter your Security Client Secret:"
read secret
echo Client_Secret = \"$secret\" >> creds.py

ip=`ifconfig eth0 | grep "inet addr" | cut -d ':' -f 2 | cut -d ' ' -f 1`
python ./auth_web.py 
echo "Open http://$ip:5000"

echo "You can now reboot"

