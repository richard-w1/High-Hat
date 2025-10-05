from flask import Flask, Response
from picamera2 import Picamera2
import libcamera
import io
import time
import atexit
import signal
import sys
import threading
import random
from sense_hat import SenseHat

app = Flask(__name__)

# Initialize camera with proper cleanup
picam2 = None
sense = None
led_thread = None

def cleanup_camera():
    """Properly close camera and Sense HAT on shutdown"""
    global picam2, sense, led_thread
    if picam2 is not None:
        try:
            picam2.stop()
            picam2.close()
            print("Camera properly closed")
        except Exception as e:
            print(f"Error closing camera: {e}")
    
    if sense is not None:
        try:
            sense.clear()
            print("Sense HAT cleared")
        except Exception as e:
            print(f"Error clearing Sense HAT: {e}")
    
    if led_thread is not None:
        try:
            led_thread.join(timeout=1)
            print("LED thread stopped")
        except Exception as e:
            print(f"Error stopping LED thread: {e}")

def init_camera():
    """Initialize camera with proper FOV and zoom settings"""
    global picam2
    try:
        picam2 = Picamera2()
        
        # Get camera properties to understand sensor capabilities
        camera_props = picam2.camera_properties
        print(f"Camera properties: {camera_props}")
        
        # Create configuration with optimal settings for wide FOV
        config = picam2.create_preview_configuration(
            main={
                "size": (1640, 1232),  # Use full sensor resolution
                "format": "YUV420"     # Better color accuracy
            },
            lores={
                "size": (640, 480),    # Lower resolution for streaming
                "format": "YUV420"
            },
            transform=libcamera.Transform(hflip=0, vflip=0)  # No rotation/crop
        )
        
        # Configure camera with optimal settings
        picam2.configure(config)
        
        # Get available controls first
        available_controls = picam2.camera_controls
        print(f"Available controls: {list(available_controls.keys())}")
        
        # Set controls for best FOV - only use available controls
        controls = {}
        
        # Only add controls that exist
        if "ExposureTime" in available_controls:
            controls["ExposureTime"] = 10000  # 10ms exposure
        if "AnalogueGain" in available_controls:
            controls["AnalogueGain"] = 1.0  # Minimal gain
        if "AeEnable" in available_controls:
            controls["AeEnable"] = True  # Auto exposure
        if "AwbEnable" in available_controls:
            controls["AwbEnable"] = True  # Auto white balance
        if "NoiseReductionMode" in available_controls:
            controls["NoiseReductionMode"] = 0  # Disable noise reduction
        if "ScalerCrop" in available_controls:
            controls["ScalerCrop"] = (0, 0, 1640, 1232)  # Use full sensor area
        
        print(f"Setting controls: {controls}")
        
        # Apply controls
        if controls:
            picam2.set_controls(controls)
        
        picam2.start()
        print("Camera initialized with optimal FOV settings")
        print(f"Active camera: {picam2.camera}")
        print(f"Camera controls: {picam2.camera_controls}")
        
    except Exception as e:
        print(f"Error initializing camera: {e}")
        sys.exit(1)

def init_sense_hat():
    """Initialize Sense HAT for LED patterns"""
    global sense
    try:
        sense = SenseHat()
        sense.clear()
        print("Sense HAT initialized")
        return True
    except Exception as e:
        print(f"Error initializing Sense HAT: {e}")
        return False

def rainbow_wave():
    """Create a rainbow wave pattern"""
    for i in range(8):
        for j in range(8):
            hue = (i + j + time.time() * 2) % 360
            r, g, b = hsv_to_rgb(hue / 360.0, 1.0, 1.0)
            sense.set_pixel(i, j, r, g, b)
        time.sleep(0.1)

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB"""
    import math
    h = h * 6.0
    i = int(h)
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    if i == 0:
        return (int(v * 255), int(t * 255), int(p * 255))
    elif i == 1:
        return (int(q * 255), int(v * 255), int(p * 255))
    elif i == 2:
        return (int(p * 255), int(v * 255), int(t * 255))
    elif i == 3:
        return (int(p * 255), int(q * 255), int(v * 255))
    elif i == 4:
        return (int(t * 255), int(p * 255), int(v * 255))
    else:
        return (int(v * 255), int(p * 255), int(q * 255))

def fire_pattern():
    """Create a fire-like pattern"""
    for i in range(8):
        for j in range(8):
            intensity = random.randint(0, 255)
            r = min(255, intensity)
            g = max(0, intensity - 100)
            b = max(0, intensity - 200)
            sense.set_pixel(i, j, r, g, b)
        time.sleep(0.05)

def matrix_rain():
    """Create a Matrix-style rain effect"""
    # Clear the display
    sense.clear()
    
    # Create falling characters
    for col in range(8):
        for row in range(8):
            if random.random() < 0.3:  # 30% chance of a character
                # Green color with varying intensity
                intensity = random.randint(50, 255)
                sense.set_pixel(col, row, 0, intensity, 0)
            else:
                sense.set_pixel(col, row, 0, 0, 0)
        time.sleep(0.02)

def spiral_pattern():
    """Create a colorful spiral pattern"""
    colors = [
        (255, 0, 0),    # Red
        (255, 165, 0),  # Orange
        (255, 255, 0),  # Yellow
        (0, 255, 0),     # Green
        (0, 0, 255),    # Blue
        (75, 0, 130),    # Indigo
        (148, 0, 211),   # Violet
    ]
    
    # Create spiral pattern
    for i in range(8):
        for j in range(8):
            distance = abs(i - 3.5) + abs(j - 3.5)
            color_index = int((distance + time.time() * 2) % len(colors))
            r, g, b = colors[color_index]
            sense.set_pixel(i, j, r, g, b)
        time.sleep(0.05)

def led_animation_worker():
    """LED animation worker thread"""
    global sense
    if sense is None:
        return
    
    patterns = [rainbow_wave, fire_pattern, matrix_rain, spiral_pattern]
    pattern_names = ["Rainbow Wave", "Fire", "Matrix Rain", "Spiral"]
    
    while True:
        try:
            # Choose a random pattern
            pattern_index = random.randint(0, len(patterns) - 1)
            pattern = patterns[pattern_index]
            pattern_name = pattern_names[pattern_index]
            
            print(f"🎨 Running LED pattern: {pattern_name}")
            
            # Run the pattern for a few cycles
            for _ in range(3):
                pattern()
                time.sleep(0.1)
            
            # Brief pause between patterns
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error in LED animation: {e}")
            time.sleep(1)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down gracefully...")
    cleanup_camera()
    sys.exit(0)

# Register cleanup handlers
atexit.register(cleanup_camera)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Initialize camera
init_camera()

# Initialize Sense HAT and start LED animations
if init_sense_hat():
    led_thread = threading.Thread(target=led_animation_worker, daemon=True)
    led_thread.start()
    print("🎨 LED animations started!")
else:
    print("⚠️  Sense HAT not available - LED animations disabled")

def generate():
    while True:
        try:
            # Use the lores stream for better performance and wider FOV
            stream = io.BytesIO()
            picam2.capture_file(stream, format='jpeg')
            stream.seek(0)
            frame_data = stream.read()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        except Exception as e:
            print(f"Error capturing frame: {e}")
            # Send a placeholder frame on error
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9' + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return "<h1>PiCam3 MJPEG Stream</h1><img src='/video_feed' width='640' height='480'>"

if __name__ == '__main__':
    print("🎥 Starting PiCam3 MJPEG server with LED animations...")
    print("🎨 Sense HAT LED patterns will run automatically!")
    print("📡 Access the stream at: http://your-pi-ip:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True)   
