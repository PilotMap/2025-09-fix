# shutoff.py - by Mark Harris
#     Updated to work with Python 3.7
#     shutoff the LED's and if equipped the Oled display
#     Added Logging capabilities which is stored in /NeoSectional/logfile.log

#import libraries
import requests

import config   #holds user settings shared among scripts

#OLED libraries
import smbus2
from Adafruit_GPIO import I2C
import Adafruit_SSD1306
from PIL import Image
from PIL import ImageDraw
import RPi.GPIO as GPIO

from RPLCD.gpio import CharLCD

from log import logger

# LED strip configuration:
LED_COUNT = config.LED_COUNT                    #from config.py. Number of LED pixels.


#Setup Display
lcdused = config.lcddisplay                     #from config.py. 1 = Yes, 0 = No.
oledused = config.oledused                      #from config.py. 1 = Yes, 0 = No.
numofdisplays = config.numofdisplays            #from config.py. Number of OLED displays used.

RST = None                                      #on the PiOLED this pin isnt used
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST) #128x64 or 128x32 - disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)
TCA_ADDR = 0x70                                 #use cmd i2cdetect -y 1 to ensure multiplexer shows up at addr 0x70
tca = I2C.get_i2c_device(address=TCA_ADDR)
port = 1                                        #Default port. set to 0 for original RPi or Orange Pi, etc
bus = smbus2.SMBus(port)                        #From smbus2 set bus number
border = 0                                      #Set border to black
backcolor = 0                                   #Set backcolor to black

#Create blank image for drawing.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))         #Make sure to create image with mode '1' for 1-bit color.

#Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

logger.info('Shutoff Settings Loaded')

# Define functions
def turnoff(strip):
    requests.post('http://localhost:8000', data=dict(fill=0x000000))

#Functions for OLED display
def tca_select(channel):
    if channel > 7:
        return
    if numofdisplays == 1:
        return

    tca.writeRaw8(1 << channel)                 #from Adafruit_GPIO I2C

#Initialize library.
def initializeoleds():
    for j in range(numofdisplays):
        tca_select(j)                           #select display to write to
        disp.begin()

def clearoleddisplays():
    for j in range(numofdisplays):
        tca_select(j)
        disp.clear()
        draw.rectangle((0,0,width-1,height-1), outline=border, fill=backcolor)
        disp.image(image)
        disp.display()

# Main program
if __name__ == '__main__':
    # Create NeoPixel object with appropriate configuration.
    # Intialize the library (must be called once before other functions).

    logger.info("LED's Have Been Turned Off")

    if oledused:                                #check to see if oleds are used
        initializeoleds()
        clearoleddisplays()
        logger.info('OLED Display Has Been Turned Off')

    if lcdused:                                 #check to see if LCD is displayed
        lcd = CharLCD(numbering_mode=GPIO.BCM, cols=16, rows=2, pin_rs=26, pin_e=19, pins_data=[13, 6, 5 ,11], compat_mode = True)
        lcd.clear()
        logger.info('LCD Display Has Been Turned Off')

    logger.info('shutoff.py Completed')
