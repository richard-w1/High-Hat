from flask import Flask, Response, jsonify, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import io
import time
import threading
import random
import base64
import json
import cv2
import requests
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from dotenv import load_dotenv
import os
import queue
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor

# Import our real AI components
from hand_detector import HandDetector
from gemini_analyzer import GeminiAnalyzer
from audio_notifier import AudioNotifier

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///theft_detection.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

class Incident(db.Model):
    """Store theft detection incidents"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    images_data = db.Column(db.Text, nullable=True)
    resolved = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'confidence': self.confidence,
            'explanation': self.explanation,
            'resolved': self.resolved
        }

# Initialize database
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Database already exists: {e}")

# Initialize AI components
print("🤖 Initializing AI components...")
hand_detector = HandDetector()
gemini_analyzer = GeminiAnalyzer()
audio_notifier = AudioNotifier()

# Demo state
is_monitoring = False
frame_count = 0

# Pi camera URL
PI_CAMERA_URL = "http://100.101.51.31:5000/video_feed"

# Real-time results storage
latest_results = {
    'photo_count': 0,
    'hands_detected': False,
    'hand_confidence': 0.0,
    'theft_detected': False,
    'theft_confidence': 0.0,
    'explanation': '',
    'timestamp': None
}

# PROPER VIDEO PROCESSING ARCHITECTURE
# Separate threads for video capture and YOLO processing
frame_queue = queue.Queue(maxsize=10)  # Buffer for raw frames
processed_frame_queue = queue.Queue(maxsize=10)  # Buffer for YOLO-processed frames
video_capture_thread = None
yolo_processing_thread = None
yolo_stream_active = False

# Store latest visualized image
latest_visualized_image = None

# PROPER VIDEO PROCESSING FUNCTIONS
def video_capture_worker():
    """Separate thread for continuous video capture from MJPEG stream"""
    global yolo_stream_active, frame_queue
    
    print("🎥 Starting video capture worker...")
    cap = cv2.VideoCapture(PI_CAMERA_URL)
    
    if not cap.isOpened():
        print(f"❌ Failed to open video stream: {PI_CAMERA_URL}")
        return
    
    frame_count = 0
    while yolo_stream_active and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to read frame from video stream")
            break
        
        frame_count += 1
        
        # Add frame to queue (non-blocking)
        try:
            frame_queue.put_nowait((frame_count, frame.copy()))
            if frame_count % 30 == 0:  # Log every 30 frames
                print(f"🎥 Captured frame #{frame_count}")
        except queue.Full:
            # Remove oldest frame if queue is full
            try:
                frame_queue.get_nowait()
                frame_queue.put_nowait((frame_count, frame.copy()))
            except queue.Empty:
                pass
        
        # Small delay to prevent overwhelming
        time.sleep(0.033)  # ~30 FPS capture
    
    cap.release()
    print("🎥 Video capture worker stopped")

def yolo_processing_worker():
    """Separate thread for YOLO processing of captured frames"""
    global yolo_stream_active, processed_frame_queue
    
    print("🤖 Starting YOLO processing worker...")
    frame_count = 0
    yolo_frame_count = 0
    last_detections = []
    detection_cooldown = 0
    YOLO_SAMPLE_RATE = 5  # Process every 5th frame
    
    while yolo_stream_active:
        try:
            # Get frame from queue (with timeout)
            frame_id, frame = frame_queue.get(timeout=1.0)
            frame_count += 1
            
            # Only run YOLO every Nth frame OR when detection cooldown is active
            should_run_yolo = (frame_count % YOLO_SAMPLE_RATE == 0) or (detection_cooldown > 0)
            
            if should_run_yolo:
                yolo_frame_count += 1
                print(f"🤖 Processing YOLO frame #{yolo_frame_count} (total #{frame_count})")
                
                # Run YOLO detection
                has_hand, confidence, detections = hand_detector.detect_hands(frame)
                
                if has_hand and detections:
                    last_detections = detections
                    detection_cooldown = 15  # Keep drawing for 15 frames
                    print(f"🖐️ Hands detected: {len(detections)} hands")
                else:
                    detection_cooldown = max(0, detection_cooldown - 1)
            
            # Always draw the last known detections (if any)
            if last_detections and detection_cooldown > 0:
                frame = hand_detector.draw_detections(frame, last_detections)
            
            # Add frame info overlay
            cv2.putText(frame, f"Frame: {frame_count} | YOLO: {yolo_frame_count}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add efficiency indicator
            efficiency_text = f"Efficiency: {yolo_frame_count}/{frame_count} frames"
            cv2.putText(frame, efficiency_text, (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            
            # Put processed frame in output queue
            try:
                processed_frame_queue.put_nowait((frame_id, frame))
            except queue.Full:
                # Remove oldest processed frame if queue is full
                try:
                    processed_frame_queue.get_nowait()
                    processed_frame_queue.put_nowait((frame_id, frame))
                except queue.Empty:
                    pass
            
        except queue.Empty:
            # No frames available, continue
            continue
        except Exception as e:
            print(f"❌ Error in YOLO processing: {e}")
            continue
    
    print("🤖 YOLO processing worker stopped")

# YOLO stream processing
yolo_stream_active = False

def update_dashboard_results(photo_count, hands_detected, hand_confidence, theft_detected, theft_confidence, explanation):
    """Update the latest results for dashboard display"""
    global latest_results
    latest_results = {
        'photo_count': photo_count,
        'hands_detected': hands_detected,
        'hand_confidence': hand_confidence,
        'theft_detected': theft_detected,
        'theft_confidence': theft_confidence,
        'explanation': explanation,
        'timestamp': time.time()
    }

def real_monitoring_loop():
    """Real AI monitoring loop with continuous MJPEG stream processing"""
    global is_monitoring
    print("🔍 DEBUG: Real monitoring loop started - processing MJPEG stream")
    frame_count = 0
    
    while is_monitoring:
        try:
            frame_count += 1
            print(f"🎥 FRAME #{frame_count}: Processing MJPEG stream from Pi camera...")
            print(f"🔍 DEBUG: Attempting to connect to {PI_CAMERA_URL}")
            
            # Get frame from Pi camera and run YOLO detection
            hands_detected, image_with_detections = hand_detector.detect_hands_from_camera(PI_CAMERA_URL)
            
            # Always store the latest visualized image for dashboard (with or without detections)
            global latest_visualized_image
            if image_with_detections is not None:
                try:
                    # Convert OpenCV image to base64 for web display
                    _, buffer = cv2.imencode('.jpg', image_with_detections)
                    img_base64 = base64.b64encode(buffer).decode('utf-8')
                    latest_visualized_image = f"data:image/jpeg;base64,{img_base64}"
                    print(f"🎥 FRAME #{frame_count}: Updated YOLO visualization")
                except Exception as e:
                    print(f"❌ FRAME #{frame_count}: Error encoding image: {e}")
                    latest_visualized_image = None
            
            # Update dashboard with current frame results
            if hands_detected:
                print(f"🖐️ FRAME #{frame_count}: HANDS DETECTED! Confidence: {hands_detected}")
                update_dashboard_results(frame_count, True, 85.0, False, 0.0, "Hands detected in frame")
            else:
                print(f"👀 FRAME #{frame_count}: No hands detected")
                update_dashboard_results(frame_count, False, 0.0, False, 0.0, "No hands detected")
            
            # Only do deep analysis (Gemini) when hands are detected for multiple consecutive frames
            if hands_detected:
                print(f"🖐️ FRAME #{frame_count}: HANDS DETECTED! Capturing suspicious images...")
                
                # Capture multiple images for analysis
                suspicious_images = hand_detector.capture_suspicious_images(PI_CAMERA_URL, num_images=5)
                
                if suspicious_images:
                    print(f"📸 FRAME #{frame_count}: Captured {len(suspicious_images)} suspicious images")
                    
                    # Analyze with Gemini
                    print(f"🤖 FRAME #{frame_count}: Sending images to Gemini for analysis...")
                    is_theft, confidence, explanation = gemini_analyzer.analyze_theft_attempt(suspicious_images)
                    
                    print(f"🤖 FRAME #{frame_count}: Gemini Analysis: Theft={is_theft}, Confidence={confidence}%")
                    print(f"💭 FRAME #{frame_count}: Explanation: {explanation}")
                    
                    # Update dashboard with real-time results
                    update_dashboard_results(frame_count, hands_detected, 85.0, is_theft, confidence, explanation)
                    
                    if is_theft and confidence > 60:  # Threshold for alert
                        print(f"🚨 FRAME #{frame_count}: THEFT DETECTED! Confidence: {confidence}%")
                        
                        # Create incident in database
                        with app.app_context():
                            # Convert images to base64 for storage
                            images_b64 = []
                            for img in suspicious_images:
                                img_buffer = io.BytesIO()
                                img.save(img_buffer, format='JPEG')
                                img_b64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                                images_b64.append(img_b64)
                            
                            incident = Incident(
                                timestamp=time.time(),
                                confidence=confidence,
                                explanation=explanation,
                                images_data=json.dumps(images_b64)
                            )
                            
                            db.session.add(incident)
                            db.session.commit()
                            print(f"💾 FRAME #{frame_count}: Incident saved to database with ID: {incident.id}")
                            
                            # Send audio alert
                            print(f"🔊 FRAME #{frame_count}: Sending audio alert...")
                            audio_notifier.send_alert(confidence, explanation)
                            
                            print(f"🚨 FRAME #{frame_count}: REAL INCIDENT DETECTED: {explanation} (Confidence: {confidence}%)")
                    else:
                        print(f"✅ FRAME #{frame_count}: No theft detected. Confidence: {confidence}%")
                else:
                    print(f"❌ FRAME #{frame_count}: Failed to capture suspicious images")
            
            # Process frames every 0.5 seconds for smooth YOLO detection
            time.sleep(0.5)
                
        except Exception as e:
            print(f"❌ FRAME #{frame_count}: ERROR in monitoring loop: {e}")
            print(f"🔍 DEBUG: Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print(f"🔍 DEBUG: Will retry in 1 second...")
            time.sleep(1)  # Wait 1 second before retrying
    
    print("🔍 DEBUG: Real monitoring loop ended")

# API Routes
@app.route('/api/start_monitoring', methods=['POST'])
def start_monitoring():
    """Start real AI theft detection monitoring"""
    global is_monitoring
    print(f"🔍 DEBUG: Start monitoring called, current state: is_monitoring={is_monitoring}")
    
    if not is_monitoring:
        is_monitoring = True
        print("🔍 DEBUG: Setting is_monitoring to True")
        # Start real monitoring thread
        monitor_thread = threading.Thread(target=real_monitoring_loop, daemon=True)
        monitor_thread.start()
        print("🔍 DEBUG: Real monitoring thread started")
        print("🔍 DEBUG: Thread is alive:", monitor_thread.is_alive())
        print("🛡️ REAL AI Monitoring started - YOLO + Gemini + ElevenLabs active")
        return jsonify({'status': 'success', 'message': 'Real AI monitoring started'})
    else:
        print("🔍 DEBUG: Already monitoring, returning error")
        return jsonify({'status': 'error', 'message': 'Already monitoring'})

@app.route('/api/stop_monitoring', methods=['POST'])
def stop_monitoring():
    """Stop AI theft detection monitoring"""
    global is_monitoring, yolo_stream_active
    is_monitoring = False
    yolo_stream_active = False
    print("⏹️ AI Monitoring stopped")
    return jsonify({'status': 'success', 'message': 'AI monitoring stopped'})

@app.route('/api/incidents')
def get_incidents():
    """Get recent incidents from database"""
    incidents = Incident.query.order_by(Incident.timestamp.desc()).limit(10).all()
    return jsonify({'incidents': [incident.to_dict() for incident in incidents]})

@app.route('/api/session')
def get_session():
    """Get current session info"""
    return jsonify({
        'session': {
            'is_active': is_monitoring,
            'total_incidents': Incident.query.count(),
            'start_time': time.time() - 3600 if is_monitoring else None
        }
    })

@app.route('/api/latest_results', methods=['GET'])
def get_latest_results():
    """Get the latest photo analysis results"""
    global latest_results
    print(f"🔍 DEBUG: Latest results requested - Photo #{latest_results['photo_count']}, Hands: {latest_results['hands_detected']}, Theft: {latest_results['theft_detected']}")
    return jsonify({
        'results': latest_results
    })

@app.route('/api/visualized_image', methods=['GET'])
def get_visualized_image():
    """Get the latest image with YOLO detections"""
    global latest_visualized_image
    print(f"🔍 DEBUG: Visualized image requested, has_image: {latest_visualized_image is not None}")
    if latest_visualized_image:
        return jsonify({
            'image': latest_visualized_image,
            'has_image': True
        })
    else:
        return jsonify({
            'image': None,
            'has_image': False
        })

@app.route('/yolo_stream')
def yolo_stream():
    """Stream YOLO-processed frames using proper multi-threaded architecture"""
    def generate_yolo_frames():
        global yolo_stream_active, video_capture_thread, yolo_processing_thread
        
        # Start background threads if not already running
        if not yolo_stream_active:
            yolo_stream_active = True
            print("🎥 Starting YOLO stream with proper multi-threading architecture")
            
            # Start video capture thread
            video_capture_thread = threading.Thread(target=video_capture_worker, daemon=True)
            video_capture_thread.start()
            
            # Start YOLO processing thread
            yolo_processing_thread = threading.Thread(target=yolo_processing_worker, daemon=True)
            yolo_processing_thread.start()
            
            print("✅ Background threads started: Video capture + YOLO processing")
        
        # Stream processed frames from the queue
        frame_count = 0
        while yolo_stream_active:
            try:
                # Get processed frame from queue (with timeout)
                frame_id, processed_frame = processed_frame_queue.get(timeout=2.0)
                frame_count += 1
                
                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', processed_frame)
                frame_bytes = buffer.tobytes()
                
                # Yield MJPEG frame
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                if frame_count % 30 == 0:  # Log every 30 frames
                    print(f"📡 Streamed frame #{frame_count} (ID: {frame_id})")
                
            except queue.Empty:
                # No processed frames available, send placeholder
                placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, "Waiting for frames...", (150, 200), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                cv2.putText(placeholder, f"Queue size: {processed_frame_queue.qsize()}", (150, 250), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                _, buffer = cv2.imencode('.jpg', placeholder)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                print(f"❌ Error in YOLO stream: {e}")
                # Send error frame
                error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(error_frame, f"Stream Error: {str(e)[:50]}", (50, 200), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                _, buffer = cv2.imencode('.jpg', error_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        print("🎥 YOLO stream ended")
    
    return Response(generate_yolo_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/test_incident', methods=['POST'])
def test_incident():
    """Force create a test incident for debugging"""
    print("🔍 DEBUG: Test incident endpoint called")
    try:
        with app.app_context():
            # Create a test incident
            incident = Incident(
                timestamp=time.time(),
                confidence=85.0,
                explanation="TEST: Hand detected reaching toward backpack - potential theft attempt",
                images_data=json.dumps(["test_image_data"])
            )
            
            db.session.add(incident)
            db.session.commit()
            print(f"🔍 DEBUG: Test incident created with ID: {incident.id}")
            
            return jsonify({'status': 'success', 'message': f'Test incident created with ID {incident.id}'})
    except Exception as e:
        print(f"❌ ERROR creating test incident: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/test_hand_detection', methods=['POST'])
def test_hand_detection():
    """Test hand detection from Pi camera"""
    print("🔍 DEBUG: Testing hand detection from Pi camera...")
    try:
        hands_detected, image = hand_detector.detect_hands_from_camera(PI_CAMERA_URL)
        return jsonify({
            'status': 'success',
            'hands_detected': hands_detected,
            'message': f'Hand detection test: {"Hands detected" if hands_detected else "No hands detected"}'
        })
    except Exception as e:
        print(f"❌ ERROR in hand detection test: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/test_gemini', methods=['POST'])
def test_gemini():
    """Test Gemini API with sample images"""
    print("🔍 DEBUG: Testing Gemini API...")
    try:
        # Create a simple test image
        test_image = Image.new('RGB', (640, 480), color=(100, 100, 100))
        test_images = [test_image]
        
        is_theft, confidence, explanation = gemini_analyzer.analyze_theft_attempt(test_images)
        
        return jsonify({
            'status': 'success',
            'is_theft': is_theft,
            'confidence': confidence,
            'explanation': explanation,
            'message': f'Gemini test: {"Theft detected" if is_theft else "No theft detected"} ({confidence}%)'
        })
    except Exception as e:
        print(f"❌ ERROR in Gemini test: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/test_audio', methods=['POST'])
def test_audio():
    """Test ElevenLabs audio generation"""
    print("🔍 DEBUG: Testing ElevenLabs audio...")
    try:
        audio_notifier.send_alert(85, "Test alert - system is working correctly")
        return jsonify({'status': 'success', 'message': 'Audio test completed'})
    except Exception as e:
        print(f"❌ ERROR in audio test: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/')
def index():
    return render_template('dashboard.html')

if __name__ == '__main__':
    print("🚀 Starting REAL AI-Powered Backpack Security System")
    print("🤖 YOLO Hand Detection: Ready")
    print("🤖 Gemini API: Ready for real analysis")
    print("🔊 ElevenLabs: Ready for voice alerts")
    print("📹 Pi Camera: http://100.101.51.31:5000/video_feed")
    print("🖥️  Dashboard: http://10.230.40.145:5000")
    print("🎯 REAL AI monitoring with YOLO + Gemini + ElevenLabs")
    print("Press Ctrl+C to stop")
    app.run(host='0.0.0.0', port=5000, threaded=True)
