import time
import random
import threading
import logging
import RPi.GPIO as GPIO
from contextlib import contextmanager
from typing import List, Tuple, Optional
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
        self.logger = logging.getLogger('led')
        self.lock = threading.Lock()
        self.strip = None
        self.number = count
        self.initialized = False
        self.dma_channel = LED_DMA
        self.gpio_pin = LED_PIN
        self.last_update_time = 0
        self.min_update_interval = 0.016  # 60 FPS max
        self.emergency_shutdown = False
        
        # Hardware conflict detection
        self._check_hardware_conflicts()
        
        try:
            self.strip = PixelStrip(count,
                                    LED_PIN,
                                    LED_FREQ_HZ,
                                    LED_DMA,
                                    LED_INVERT,
                                    LED_BRIGHTNESS,
                                    LED_CHANNEL)
            self.strip.begin()
            self.number = self.strip.numPixels()
            self.initialized = True
            
            # Clear any test patterns that might be left from library initialization
            self.clear()
            self.logger.info(f"LED strip initialized with {self.number} pixels")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LED strip: {e}")
            self.initialized = False
            raise

    def _check_hardware_conflicts(self):
        """Check for potential hardware conflicts"""
        try:
            # Check if GPIO pin is already in use
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gpio_pin, GPIO.IN)
            GPIO.setup(self.gpio_pin, GPIO.OUT)
            GPIO.cleanup()
            
            # Check DMA channel conflicts (simplified check)
            if self.dma_channel in [1, 2, 3, 4, 5]:  # Common audio DMA channels
                self.logger.warning(f"DMA channel {self.dma_channel} may conflict with audio")
                
        except Exception as e:
            self.logger.warning(f"Hardware conflict check failed: {e}")
    
    def _validate_pixel_index(self, led: int) -> bool:
        """Validate pixel index"""
        if not isinstance(led, int) or led < 0 or led >= self.number:
            self.logger.error(f"Invalid pixel index: {led} (valid range: 0-{self.number-1})")
            return False
        return True
    
    def _validate_color(self, color) -> bool:
        """Validate color value"""
        if not isinstance(color, (int, tuple, list)):
            self.logger.error(f"Invalid color type: {type(color)}")
            return False
        return True
    
    def _rate_limit_check(self) -> bool:
        """Check if enough time has passed since last update"""
        current_time = time.time()
        if current_time - self.last_update_time < self.min_update_interval:
            return False
        self.last_update_time = current_time
        return True

    def set_pixel_color(self, led: int, color) -> bool:
        """Set pixel color with validation and thread safety"""
        if self.emergency_shutdown or not self.initialized:
            return False
            
        if not self._validate_pixel_index(led) or not self._validate_color(color):
            return False
            
        with self.lock:
            try:
                self.strip.setPixelColor(led, color)
                return True
            except Exception as e:
                self.logger.error(f"Error setting pixel {led}: {e}")
                return False

    def show_pixels(self) -> bool:
        """Display pixels with rate limiting and thread safety"""
        if self.emergency_shutdown or not self.initialized:
            return False
            
        if not self._rate_limit_check():
            return False
            
        with self.lock:
            try:
                self.strip.show()
                return True
            except Exception as e:
                self.logger.error(f"Error showing pixels: {e}")
                return False

    def set_brightness(self, brightness: int) -> bool:
        """Set brightness with validation"""
        if not isinstance(brightness, int) or brightness < 0 or brightness > 255:
            self.logger.error(f"Invalid brightness value: {brightness}")
            return False
            
        with self.lock:
            try:
                self.strip.setBrightness(brightness)
                return True
            except Exception as e:
                self.logger.error(f"Error setting brightness: {e}")
                return False

    def clear(self) -> bool:
        """Clear all pixels"""
        if not self.initialized:
            return False
            
        with self.lock:
            try:
                for i in range(self.number):
                    self.strip.setPixelColor(i, 0)
                self.strip.show()
                return True
            except Exception as e:
                self.logger.error(f"Error clearing pixels: {e}")
                return False
    
    def set_pixels(self, pixels: List[Tuple[int, int, int]]) -> bool:
        """Set multiple pixels at once for better performance"""
        if not self.initialized or self.emergency_shutdown:
            return False
            
        if len(pixels) != self.number:
            self.logger.error(f"Pixel count mismatch: {len(pixels)} != {self.number}")
            return False
            
        with self.lock:
            try:
                for i, (r, g, b) in enumerate(pixels):
                    self.strip.setPixelColor(i, Color(r, g, b))
                return True
            except Exception as e:
                self.logger.error(f"Error setting pixels: {e}")
                return False
    
    def test_connection(self) -> bool:
        """Test LED strip responsiveness"""
        if not self.initialized:
            return False
            
        try:
            # Quick test pattern
            original_colors = []
            for i in range(min(3, self.number)):
                original_colors.append(self.strip.getPixelColor(i))
                self.strip.setPixelColor(i, Color(255, 0, 0))  # Red
            self.strip.show()
            time.sleep(0.01)
            
            # Restore original colors
            for i, color in enumerate(original_colors):
                self.strip.setPixelColor(i, color)
            self.strip.show()
            
            return True
        except Exception as e:
            self.logger.error(f"LED connection test failed: {e}")
            return False
    
    def emergency_shutdown(self):
        """Emergency shutdown - turn off all LEDs immediately"""
        self.emergency_shutdown = True
        self.logger.critical("Emergency LED shutdown initiated")
        
        try:
            with self.lock:
                for i in range(self.number):
                    self.strip.setPixelColor(i, 0)
                self.strip.show()
        except Exception as e:
            self.logger.error(f"Error during emergency shutdown: {e}")
    
    def get_status(self) -> dict:
        """Get LED strip status"""
        return {
            'initialized': self.initialized,
            'pixel_count': self.number,
            'emergency_shutdown': self.emergency_shutdown,
            'last_update_time': self.last_update_time,
            'dma_channel': self.dma_channel,
            'gpio_pin': self.gpio_pin
        }
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.emergency_shutdown()
        try:
            if hasattr(self, 'strip') and self.strip:
                self.strip._cleanup()
        except:
            pass

    def orange(self) -> bool:
        """Set all pixels to orange"""
        if not self.initialized:
            return False
            
        with self.lock:
            try:
                for i in range(self.number):
                    self.strip.setPixelColor(i, 0xFFA500)
                self.strip.show()
                return True
            except Exception as e:
                self.logger.error(f"Error setting orange: {e}")
                return False


def create_led_strip(count: int) -> LedStrip:
    """Factory function to create LED strip with proper error handling"""
    try:
        return LedStrip(count)
    except Exception as e:
        logging.getLogger('led').error(f"Failed to create LED strip: {e}")
        raise


@contextmanager
def managed_led_strip(count: int):
    """Context manager for LED strip with automatic cleanup"""
    strip = None
    try:
        strip = create_led_strip(count)
        yield strip
    finally:
        if strip:
            strip.emergency_shutdown()
