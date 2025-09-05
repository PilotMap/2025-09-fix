import json
import uvicorn

from fastapi    import FastAPI, Query
from rpi_ws281x import PixelStrip, Color


# LED strip configuration:
LED_COUNT      = 60        # Number of LED pixels.
LED_PIN        = 18          # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10          # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False    # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL     = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53


strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

app = FastAPI()

@app.post("/set")
def set_led(led: int, color:str, show:bool | None=True):
    rgb = int(color,16)
    strip.setPixelColor(led, rgb)
    if show:
        strip.show()
    return {"status":"True"}

@app.post("/fill")
def fill_leds(color:str):
    rgb = int(color, 16)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, rgb)
    strip.show()
    return

@app.post("/show")
def show_leds():
    strip.show()
    return

@app.post("/pattern")
def pattern(leds):
    leds = json.loads(leds)
    for l in range(len(leds)):
        rgb = int(leds[l],16)
        strip.setPixelColor(l, rgb)
    strip.show()

@app.get("/")
def pixel_number():
    return {'pixels':strip.numPixels}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
