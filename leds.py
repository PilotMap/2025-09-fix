import time
import random
try:
    from rpi_ws281x import PixelStrip, Color
except ModuleNotFoundError:
    from fakes import PixelStrip, Color

# LED strip configuration:
LED_PIN        = 18       # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000   # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10       # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255      # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL     = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

'''
def Color(r, g, b):
    """
    The code has Color all over, but never defined. It just returns a set to pass back to the
    Adafruit library calls
    """
    return int("0x{:02x}{:02x}{:02x}".format(r, g, b), 16)
'''

class LedStrip:
    def __init__(self, count):
        self.strip = PixelStrip(count,
                                LED_PIN,
                                LED_FREQ_HZ,
                                LED_DMA,
                                LED_INVERT,
                                LED_BRIGHTNESS,
                                LED_CHANNEL)
        self.strip.begin()
        self.number = self.strip.numPixels()
        
        # Clear any test patterns that might be left from library initialization
        for i in range(self.number):
            self.strip.setPixelColor(i, 0)
        self.strip.show()

    def set_pixel_color(self, led, color):
        self.strip.setPixelColor(led, color)

    def show_pixels(self):
        self.strip.show()

    def set_brightness(self, brightness):
        self.strip.setBrightness(brightness)

    def rainbow(self, times,delay):
        for _ in range(times):
            for i in range(self.number):
                self.set_pixel_color(i, Color(random.randint(0, 255),
                                              random.randint(0, 255),
                                              random.randint(0, 255)))
            self.show_pixels()
            time.sleep(delay)

    def orange(self):
        for i in range(self.number):
            self.set_pixel_color(i, 0xFFA500)
        self.show_pixels()
