import busio
from board import SCL, SDA


# Import the SSD1306 module.
import adafruit_ssd1306

# Create the I2C interface.
i2c = busio.I2C(SCL, SDA)


class Display:
    def __init__(self):
        self.display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
        self.display.fill(0)
        display.show()


