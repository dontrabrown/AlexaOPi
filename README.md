# AlexaOPi (R2D2 version)
 
---
 
### Contributors
 
* Sam Machin
* Dontze
* GadgetReactor	
 
---
 
This is the code needed to Turn an Orange Pi into a client for Amazon's Alexa service.
Runs on voice activation, and responds to either Artoo or Alexa. Modify the init.d script accordingly for the Snowboy model of choice - default is Artoo.

There's no button to press in this implementation.  

It will chirp and chime like an R2D2. For your own voice models, go to kitt.ai/snowboy and grab your model or update mine. 

Tested and should be working out of the box. Let me know if any issues. I will be moving to a Pocketsphinx implementation. 
---
 
### Requirements

You will need:
* A Orange Pi PC or Orange Pi PC Plus
* An SD Card with a fresh install of Armbian (tested against Armbian v.5.20 Jessie Desktop)
* An External Speaker with 3.5mm Jack
* (Optional) A Dual colour LED (or 2 signle LEDs) Connected to GPIO PA8 & PA9

Next you need to obtain a set of credentials from Amazon to use the Alexa Voice service, login at http://developer.amazon.com and Goto Alexa then Alexa Voice Service
You need to create a new product type as a Device, for the ID use something like AlexaPi, create a new security profile and under the web settings allowed origins put http://localhost:5000 and as a return URL put http://localhost:5000/code you can also create URLs replacing localhost with the IP of your Pi  eg http://192.168.1.123:5000
Make a note of these credentials you will be asked for them during the install process

### Installation

Boot your fresh Pi and setup WiFi.

Make sure you are in /opt

Clone this repo to the Pi
`git clone https://github.com/gadgetreactor/AlexaOPi.git`
Run the setup script
`sudo ./setup.sh`

Follow instructions....

Enjoy :)

