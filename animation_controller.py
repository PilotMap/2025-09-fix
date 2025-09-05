"""
LiveSectional Animation Controller

Centralized animation engine to eliminate timing conflicts and resource contention
in LED effects. Provides coordinated timing, frame rate limiting, and bounded resource usage.
"""

import time
import threading
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
import logging
from abc import ABC, abstractmethod

from reliability_manager import get_reliability_manager, FrameRateLimiter, SharedClock
from logging_config import get_logger


class AnimationState(Enum):
    """Animation state enumeration"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class EffectPriority(Enum):
    """Effect priority levels"""
    CRITICAL = 1    # Weather alerts
    HIGH = 2        # Wind effects
    MEDIUM = 3      # Homeport effects
    LOW = 4         # Heat map effects


@dataclass
class AnimationFrame:
    """Single animation frame data"""
    timestamp: float
    pixels: List[tuple]  # List of (r, g, b) tuples
    indices: List[int]   # List of pixel indices for this frame
    brightness: float
    effect_id: str


class BaseEffect(ABC):
    """Base class for all animation effects"""
    
    def __init__(self, effect_id: str, priority: EffectPriority = EffectPriority.MEDIUM):
        self.effect_id = effect_id
        self.priority = priority
        self.state = AnimationState.STOPPED
        self.start_time = 0
        self.duration = 0
        self.timeout = 30  # Maximum effect duration
        self.logger = get_logger('animation')
        
    @abstractmethod
    def update(self, current_time: float, clock: SharedClock) -> Optional[AnimationFrame]:
        """Update effect and return frame data"""
        pass
        
    @abstractmethod
    def is_complete(self, current_time: float) -> bool:
        """Check if effect is complete"""
        pass
        
    def start(self, current_time: float):
        """Start the effect"""
        self.state = AnimationState.RUNNING
        self.start_time = current_time
        self.logger.debug(f"Started effect: {self.effect_id}")
        
    def stop(self):
        """Stop the effect"""
        self.state = AnimationState.STOPPED
        self.logger.debug(f"Stopped effect: {self.effect_id}")
        
    def pause(self):
        """Pause the effect"""
        self.state = AnimationState.PAUSED
        self.logger.debug(f"Paused effect: {self.effect_id}")
        
    def resume(self):
        """Resume the effect"""
        self.state = AnimationState.RUNNING
        self.logger.debug(f"Resumed effect: {self.effect_id}")
        
    def is_timed_out(self, current_time: float) -> bool:
        """Check if effect has timed out"""
        return current_time - self.start_time > self.timeout


class BlinkEffect(BaseEffect):
    """Blinking effect for wind alerts and warnings"""
    
    def __init__(self, effect_id: str, color: tuple, duty_cycle: float = 0.5, 
                 blink_rate: float = 2.0, pixel_indices: List[int] = None):
        super().__init__(effect_id, EffectPriority.HIGH)
        self.color = color
        self.duty_cycle = duty_cycle
        self.blink_rate = blink_rate
        self.pixel_indices = pixel_indices or []
        self.period = 1.0 / blink_rate
        
    def update(self, current_time: float, clock: SharedClock) -> Optional[AnimationFrame]:
        """Update blinking effect"""
        if self.state != AnimationState.RUNNING:
            return None
            
        elapsed = current_time - self.start_time
        cycle_position = (elapsed % self.period) / self.period
        
        # Determine if we should be on or off
        is_on = cycle_position < self.duty_cycle
        
        if is_on:
            pixels = [self.color for _ in self.pixel_indices]
        else:
            pixels = [(0, 0, 0) for _ in self.pixel_indices]
            
        return AnimationFrame(
            timestamp=current_time,
            pixels=pixels,
            indices=self.pixel_indices,
            brightness=1.0,
            effect_id=self.effect_id
        )
        
    def is_complete(self, current_time: float) -> bool:
        """Blink effects run until explicitly stopped"""
        return self.is_timed_out(current_time)


class WeatherEffect(BaseEffect):
    """Weather effect for rain, snow, lightning, etc."""
    
    def __init__(self, effect_id: str, effect_type: str, intensity: float = 1.0,
                 pixel_indices: List[int] = None):
        super().__init__(effect_id, EffectPriority.CRITICAL)
        self.effect_type = effect_type
        self.intensity = intensity
        self.pixel_indices = pixel_indices or []
        self.phase = 0.0
        
    def update(self, current_time: float, clock: SharedClock) -> Optional[AnimationFrame]:
        """Update weather effect"""
        if self.state != AnimationState.RUNNING:
            return None
            
        elapsed = current_time - self.start_time
        self.phase = elapsed * 2.0  # Speed of animation
        
        pixels = []
        for i in self.pixel_indices:
            if self.effect_type == "rain":
                pixel = self._rain_pixel(i, self.phase)
            elif self.effect_type == "snow":
                pixel = self._snow_pixel(i, self.phase)
            elif self.effect_type == "lightning":
                pixel = self._lightning_pixel(i, self.phase)
            else:
                pixel = (0, 0, 0)
            pixels.append(pixel)
            
        return AnimationFrame(
            timestamp=current_time,
            pixels=pixels,
            indices=self.pixel_indices,
            brightness=self.intensity,
            effect_id=self.effect_id
        )
        
    def _rain_pixel(self, index: int, phase: float) -> tuple:
        """Generate rain effect pixel"""
        # Simple rain effect with blue drops
        drop_phase = (phase + index * 0.1) % (2 * 3.14159)
        intensity = max(0, 0.5 + 0.5 * (1 - abs(drop_phase - 3.14159) / 3.14159))
        return (0, 0, int(255 * intensity * self.intensity))
        
    def _snow_pixel(self, index: int, phase: float) -> tuple:
        """Generate snow effect pixel"""
        # White snowflakes
        flake_phase = (phase + index * 0.2) % (2 * 3.14159)
        intensity = max(0, 0.3 + 0.7 * (1 - abs(flake_phase - 3.14159) / 3.14159))
        value = int(255 * intensity * self.intensity)
        return (value, value, value)
        
    def _lightning_pixel(self, index: int, phase: float) -> tuple:
        """Generate lightning effect pixel"""
        # Random bright flashes
        if (phase + index) % 10 < 0.1:  # Random flash
            return (255, 255, 255)
        return (0, 0, 0)
        
    def is_complete(self, current_time: float) -> bool:
        """Weather effects run until explicitly stopped"""
        return self.is_timed_out(current_time)


class FadeEffect(BaseEffect):
    """Fading effect for homeport and other smooth transitions"""
    
    def __init__(self, effect_id: str, start_color: tuple, end_color: tuple,
                 fade_duration: float = 2.0, pixel_indices: List[int] = None):
        super().__init__(effect_id, EffectPriority.MEDIUM)
        self.start_color = start_color
        self.end_color = end_color
        self.fade_duration = fade_duration
        self.pixel_indices = pixel_indices or []
        
    def update(self, current_time: float, clock: SharedClock) -> Optional[AnimationFrame]:
        """Update fading effect"""
        if self.state != AnimationState.RUNNING:
            return None
            
        elapsed = current_time - self.start_time
        progress = min(1.0, elapsed / self.fade_duration)
        
        # Smooth fade using easing function
        eased_progress = self._ease_in_out(progress)
        
        # Interpolate colors
        pixels = []
        for i in self.pixel_indices:
            r = int(self.start_color[0] + (self.end_color[0] - self.start_color[0]) * eased_progress)
            g = int(self.start_color[1] + (self.end_color[1] - self.start_color[1]) * eased_progress)
            b = int(self.start_color[2] + (self.end_color[2] - self.start_color[2]) * eased_progress)
            pixels.append((r, g, b))
            
        return AnimationFrame(
            timestamp=current_time,
            pixels=pixels,
            indices=self.pixel_indices,
            brightness=1.0,
            effect_id=self.effect_id
        )
        
    def _ease_in_out(self, t: float) -> float:
        """Easing function for smooth transitions"""
        return t * t * (3.0 - 2.0 * t)
        
    def is_complete(self, current_time: float) -> bool:
        """Fade effect is complete when duration is reached"""
        return current_time - self.start_time >= self.fade_duration


class HeatMapEffect(BaseEffect):
    """Heat map effect with controlled fade loops"""
    
    def __init__(self, effect_id: str, data: List[float], max_iterations: int = 100, pixel_indices: List[int] = None):
        super().__init__(effect_id, EffectPriority.LOW)
        self.data = data
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.fade_speed = 0.02
        self.pixel_indices = pixel_indices or list(range(len(data)))
        
    def update(self, current_time: float, clock: SharedClock) -> Optional[AnimationFrame]:
        """Update heat map effect"""
        if self.state != AnimationState.RUNNING:
            return None
            
        # Bounded iteration count to prevent infinite loops
        if self.current_iteration >= self.max_iterations:
            return None
            
        self.current_iteration += 1
        
        # Generate heat map colors
        pixels = []
        for value in self.data:
            # Map value to color (blue -> green -> yellow -> red)
            if value < 0.25:
                r = 0
                g = int(255 * value * 4)
                b = 255
            elif value < 0.5:
                r = 0
                g = 255
                b = int(255 * (1 - (value - 0.25) * 4))
            elif value < 0.75:
                r = int(255 * (value - 0.5) * 4)
                g = 255
                b = 0
            else:
                r = 255
                g = int(255 * (1 - (value - 0.75) * 4))
                b = 0
                
            pixels.append((r, g, b))
            
        return AnimationFrame(
            timestamp=current_time,
            pixels=pixels,
            indices=self.pixel_indices,
            brightness=1.0,
            effect_id=self.effect_id
        )
        
    def is_complete(self, current_time: float) -> bool:
        """Heat map effect is complete when max iterations reached"""
        return self.current_iteration >= self.max_iterations


class AnimationController:
    """Centralized animation controller managing all LED effects"""
    
    def __init__(self, led_controller, target_fps: int = 30):
        self.led_controller = led_controller
        self.target_fps = target_fps
        self.frame_limiter = FrameRateLimiter(target_fps)
        self.shared_clock = SharedClock()
        self.effects = {}
        self.effect_queue = []
        self.current_frame = None
        self.state = AnimationState.STOPPED
        self.logger = get_logger('animation')
        self.reliability_manager = get_reliability_manager()
        self.lock = threading.Lock()
        
        # Performance tracking
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0
        
    def add_effect(self, effect: BaseEffect) -> bool:
        """Add an effect to the animation controller"""
        with self.lock:
            if effect.effect_id in self.effects:
                self.logger.warning(f"Effect {effect.effect_id} already exists")
                return False
                
            self.effects[effect.effect_id] = effect
            self.logger.info(f"Added effect: {effect.effect_id}")
            return True
            
    def remove_effect(self, effect_id: str) -> bool:
        """Remove an effect from the animation controller"""
        with self.lock:
            if effect_id not in self.effects:
                return False
                
            effect = self.effects[effect_id]
            effect.stop()
            del self.effects[effect_id]
            self.logger.info(f"Removed effect: {effect_id}")
            return True
            
    def start_effect(self, effect_id: str) -> bool:
        """Start a specific effect"""
        with self.lock:
            if effect_id not in self.effects:
                return False
                
            effect = self.effects[effect_id]
            effect.start(self.shared_clock.get_time())
            self.logger.info(f"Started effect: {effect_id}")
            return True
            
    def stop_effect(self, effect_id: str) -> bool:
        """Stop a specific effect"""
        with self.lock:
            if effect_id not in self.effects:
                return False
                
            effect = self.effects[effect_id]
            effect.stop()
            self.logger.info(f"Stopped effect: {effect_id}")
            return True
            
    def stop_all_effects(self):
        """Stop all effects"""
        with self.lock:
            for effect in self.effects.values():
                effect.stop()
            self.logger.info("Stopped all effects")
            
    def start_animation(self):
        """Start the animation controller"""
        with self.lock:
            self.state = AnimationState.RUNNING
            self.shared_clock.resume()
            self.logger.info("Animation controller started")
            
    def stop_animation(self):
        """Stop the animation controller"""
        with self.lock:
            self.state = AnimationState.STOPPED
            self.stop_all_effects()
            self.shared_clock.pause()
            self.logger.info("Animation controller stopped")
            
    def update(self) -> bool:
        """Update animation and render frame"""
        if self.state != AnimationState.RUNNING:
            return False
            
        # Frame rate limiting
        if not self.frame_limiter.wait_for_next_frame():
            return False
            
        current_time = self.shared_clock.get_time()
        
        with self.lock:
            # Update all effects
            active_effects = []
            for effect in self.effects.values():
                if effect.state == AnimationState.RUNNING:
                    try:
                        frame = effect.update(current_time, self.shared_clock)
                        if frame:
                            active_effects.append(frame)
                    except Exception as e:
                        self.logger.error(f"Error updating effect {effect.effect_id}: {e}")
                        effect.state = AnimationState.ERROR
                        
                # Check for completion
                if effect.is_complete(current_time):
                    effect.stop()
                    
            # Combine effects by priority
            if active_effects:
                combined_frame = self._combine_effects(active_effects)
                self._render_frame(combined_frame)
                
        # Update performance metrics
        self._update_performance_metrics()
        
        return True
        
    def _combine_effects(self, frames: List[AnimationFrame]) -> AnimationFrame:
        """Combine multiple effect frames by priority"""
        if not frames:
            return None
            
        # Sort by priority (lower number = higher priority)
        frames.sort(key=lambda f: self.effects[f.effect_id].priority.value)
        
        # Start with the highest priority frame
        combined = frames[0]
        
        # Create a full-length pixel buffer
        if self.led_controller:
            full_pixels = [(0, 0, 0) for _ in range(self.led_controller.number)]
            full_indices = list(range(self.led_controller.number))
        else:
            # Fallback if no LED controller
            max_index = max(max(frame.indices) for frame in frames) if frames else 0
            full_pixels = [(0, 0, 0) for _ in range(max_index + 1)]
            full_indices = list(range(max_index + 1))
        
        # Apply all frames to the full buffer
        for frame in frames:
            for i, pixel in enumerate(frame.pixels):
                if i < len(frame.indices):
                    pixel_index = frame.indices[i]
                    if pixel_index < len(full_pixels):
                        # Simple alpha blending
                        alpha = 0.5  # Could be based on effect priority
                        cr, cg, cb = full_pixels[pixel_index]
                        r, g, b = pixel
                        full_pixels[pixel_index] = (
                            int(cr * (1 - alpha) + r * alpha),
                            int(cg * (1 - alpha) + g * alpha),
                            int(cb * (1 - alpha) + b * alpha)
                        )
        
        # Create combined frame
        return AnimationFrame(
            timestamp=combined.timestamp,
            pixels=full_pixels,
            indices=full_indices,
            brightness=combined.brightness,
            effect_id="combined"
        )
        
    def _render_frame(self, frame: AnimationFrame):
        """Render frame to LED strip"""
        if not frame or not self.led_controller:
            return
            
        try:
            # Apply brightness
            if frame.brightness != 1.0:
                frame.pixels = [
                    (int(r * frame.brightness), int(g * frame.brightness), int(b * frame.brightness))
                    for r, g, b in frame.pixels
                ]
                
            # Update LED strip - set only the specific pixels
            for i, (r, g, b) in zip(frame.indices, frame.pixels):
                self.led_controller.set_pixel_color(i, (r, g, b))
            self.led_controller.show_pixels()  # Ensure pixels are displayed
            self.current_frame = frame
            
        except Exception as e:
            self.logger.error(f"Error rendering frame: {e}")
            
    def _update_performance_metrics(self):
        """Update performance tracking metrics"""
        self.frame_count += 1
        current_time = time.time()
        
        if current_time - self.last_fps_time >= 1.0:
            self.current_fps = self.frame_count
            self.frame_count = 0
            self.last_fps_time = current_time
            
            # Log performance metrics
            if self.current_fps < self.target_fps * 0.8:  # 80% of target
                self.logger.warning(f"Low FPS: {self.current_fps}/{self.target_fps}")
                
    def get_status(self) -> Dict[str, Any]:
        """Get animation controller status"""
        with self.lock:
            return {
                'state': self.state.value,
                'target_fps': self.target_fps,
                'current_fps': self.current_fps,
                'active_effects': len([e for e in self.effects.values() if e.state == AnimationState.RUNNING]),
                'total_effects': len(self.effects),
                'effects': {
                    effect_id: {
                        'state': effect.state.value,
                        'priority': effect.priority.value,
                        'duration': time.time() - effect.start_time if effect.start_time else 0
                    }
                    for effect_id, effect in self.effects.items()
                }
            }
            
    def emergency_shutdown(self):
        """Emergency shutdown of all animations"""
        self.logger.critical("Emergency animation shutdown")
        self.stop_animation()
        
        # Turn off all LEDs
        if self.led_controller:
            try:
                self.led_controller.clear()
            except Exception as e:
                self.logger.error(f"Error during emergency LED shutdown: {e}")


# Global animation controller instance
_animation_controller = None


def get_animation_controller(led_controller=None, target_fps: int = 30) -> AnimationController:
    """Get the global animation controller instance"""
    global _animation_controller
    if _animation_controller is None:
        _animation_controller = AnimationController(led_controller, target_fps)
    return _animation_controller


def create_blink_effect(effect_id: str, color: tuple, **kwargs) -> BlinkEffect:
    """Create a blinking effect"""
    return BlinkEffect(effect_id, color, **kwargs)


def create_weather_effect(effect_id: str, effect_type: str, **kwargs) -> WeatherEffect:
    """Create a weather effect"""
    return WeatherEffect(effect_id, effect_type, **kwargs)


def create_fade_effect(effect_id: str, start_color: tuple, end_color: tuple, **kwargs) -> FadeEffect:
    """Create a fade effect"""
    return FadeEffect(effect_id, start_color, end_color, **kwargs)


def create_heat_map_effect(effect_id: str, data: List[float], **kwargs) -> HeatMapEffect:
    """Create a heat map effect"""
    return HeatMapEffect(effect_id, data, **kwargs)
