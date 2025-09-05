

class GPIO:
    def setmode(mode):
        return

    def setup(self, **args):
        return

    def input(self):
        return 1

def Color(r, g, b):
    """
    The code has Color all over, but never defined. It just returns a set to pass back to the
    Adafruit library calls
    """
    return int("0x{:02x}{:02x}{:02x}".format(r, g, b), 16)

class PixelStrip:

    def __init__(self, count, pin, freq_hz, dma, invert, brightness, channel):
        self.count = count
        self.pin = pin
        self.freq_hz = freq_hz
        self.dma = dma
        self.invert = invert
        self.brightness = brightness
        self.channel = channel

    def begin(self):
        return

    def numPixels(self):
        return self.count

    def setPixelColor(self, led, color):
        print(f"Fake: Setting LED {led} to color {color}")
        return

    def show(self):
        print("Fake: show() called - LEDs would be updated here")
        return

    def setBrightness(self, brightness):
        print(f"Fake: Setting brightness to {brightness}")
        self.brightness = brightness
