from flask import Flask, Response, jsonify, render_template
from flask_cors import CORS
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

# Import new database models and managers
from models import db, Session, Incident, IncidentFrame, GeminiAnalysis, UserAlert
from session_manager import SessionManager, IncidentManager, GeminiAnalysisManager, AlertManager

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///security_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with app
db.init_app(app)

# Initialize database tables
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables initialized")
    except Exception as e:
        print(f"⚠️  Database initialization: {e}")

# Initialize AI components
print("🤖 Initializing AI components...")
hand_detector = HandDetector()
gemini_analyzer = GeminiAnalyzer()
audio_notifier = AudioNotifier()

# Session and monitoring state
is_monitoring = False
current_session_id = None
current_incident_id = None
global_frame_count = 0

# Pi camera URL
PI_CAMERA_URL = "http://100.101.51.31:5000/video_feed"

# Real-time results storage
latest_results = {
    'photo_count': 0,
    'hands_detected': False,
    'hand_count': 0,
    'hand_confidence': 0.0,
    'hand_positions': [],  # List of hand bounding boxes
    'theft_detected': False,
    'theft_confidence': 0.0,
    'explanation': '',
    'timestamp': None,
    'detailed_hands': []  # Detailed hand information
}

# PROPER VIDEO PROCESSING ARCHITECTURE
# Separate threads for video capture and MediaPipe hand detection processing
frame_queue = queue.Queue(maxsize=10)  # Buffer for raw frames
processed_frame_queue = queue.Queue(maxsize=10)  # Buffer for processed frames with hand detections
video_capture_thread = None
detection_processing_thread = None
detection_stream_active = False

# Store latest visualized image
latest_visualized_image = None

# PROPER VIDEO PROCESSING FUNCTIONS
def video_capture_worker():
    """Separate thread for continuous video capture from MJPEG stream"""
    global detection_stream_active, frame_queue
    
    print("🎥 Starting video capture worker...")
    cap = cv2.VideoCapture(PI_CAMERA_URL)
    
    if not cap.isOpened():
        print(f"❌ Failed to open video stream: {PI_CAMERA_URL}")
        return
    
    frame_count = 0
    while detection_stream_active and cap.isOpened():
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

def detection_processing_worker():
    """
    Separate thread for MediaPipe hand detection processing of captured frames
    Also handles incident tracking and escalation logic
    """
    global detection_stream_active, processed_frame_queue, is_monitoring
    global current_session_id, current_incident_id, global_frame_count
    
    print("🤖 Starting MediaPipe hand detection processing worker...")
    frame_count = 0
    detection_frame_count = 0
    last_detections = []
    detection_cooldown = 0
    DETECTION_SAMPLE_RATE = 5  # Process every 5th frame
    
    while detection_stream_active:
        try:
            # Get frame from queue (with timeout)
            frame_id, frame = frame_queue.get(timeout=1.0)
            frame_count += 1
            
            # Only run MediaPipe detection every Nth frame OR when detection cooldown is active
            should_run_detection = (frame_count % DETECTION_SAMPLE_RATE == 0) or (detection_cooldown > 0)
            
            if should_run_detection:
                detection_frame_count += 1
                print(f"🤖 Processing MediaPipe frame #{detection_frame_count} (total #{frame_count})")
                
                # Run MediaPipe hand detection
                has_hand, confidence, detections = hand_detector.detect_hands(frame)
                
                # INCIDENT TRACKING LOGIC (only when monitoring is active)
                if is_monitoring and current_session_id:
                    with app.app_context():
                        # Increment session frame count
                        SessionManager.increment_frame_count(current_session_id)
                        global_frame_count += 1
                        
                        if has_hand and detections:
                            # Hands detected!
                            if not current_incident_id:
                                # Create new incident
                                incident = IncidentManager.create_incident(current_session_id)
                                current_incident_id = incident.id
                                print(f"🆕 NEW INCIDENT #{current_incident_id} - Hands first detected")
                            
                            # Add frame to incident
                            incident_frame, should_escalate = IncidentManager.add_frame_to_incident(
                                incident_id=current_incident_id,
                                global_frame_num=global_frame_count,
                                hand_count=len(detections),
                                hand_confidence=confidence,
                                hand_detections=detections,
                                frame_image=frame  # Store frame image
                            )
                            
                            # Check if we should send batch to Gemini (every 10 frames: 10, 20, 30...)
                            incident = Incident.query.get(current_incident_id)
                            
                            if should_escalate or (incident and incident.total_frames % 10 == 0 and incident.total_frames > 0):
                                batch_num = incident.total_frames // 10
                                print(f"⚠️  BATCH ANALYSIS #{batch_num} - Incident #{current_incident_id} at {incident.total_frames} frames")
                                
                                # Get last 10 frames for Gemini analysis
                                frames_for_analysis = IncidentManager.get_incident_frames_for_analysis(
                                    current_incident_id, last_n_frames=10
                                )
                                
                                # Convert frames to PIL Images for Gemini
                                images_for_gemini = []
                                for inc_frame in frames_for_analysis:
                                    if inc_frame.image_data:
                                        # Decode base64 image
                                        img_bytes = base64.b64decode(inc_frame.image_data)
                                        img = Image.open(io.BytesIO(img_bytes))
                                        images_for_gemini.append(img)
                                
                                if images_for_gemini:
                                    print(f"🤖 Sending {len(images_for_gemini)} frames to Gemini (batch #{batch_num})...")
                                    start_time = time.time()
                                    
                                    # Call Gemini API
                                    is_theft, threat_confidence, explanation = gemini_analyzer.analyze_theft_attempt(images_for_gemini)
                                    
                                    latency_ms = int((time.time() - start_time) * 1000)
                                    print(f"🤖 Gemini response: Threat={is_theft}, Confidence={threat_confidence}%, Latency={latency_ms}ms")
                                    
                                    # Record analysis in database
                                    GeminiAnalysisManager.record_analysis(
                                        incident_id=current_incident_id,
                                        frame_start=frames_for_analysis[0].frame_number,
                                        frame_end=frames_for_analysis[-1].frame_number,
                                        threat_detected=is_theft,
                                        confidence=threat_confidence,
                                        explanation=explanation,
                                        latency_ms=latency_ms
                                    )
                                    
                                    # If real threat detected, END THE INCIDENT
                                    if is_theft and threat_confidence > 60:
                                        print(f"🚨 THREAT CONFIRMED! Ending incident and sending alert...")
                                        
                                        # Mark entire incident as high threat
                                        incident.threat_detected = True
                                        incident.threat_confidence = threat_confidence
                                        incident.threat_explanation = explanation
                                        db.session.commit()
                                        
                                        # Send alert
                                        AlertManager.send_alert(
                                            incident_id=current_incident_id,
                                            alert_type='theft_confirmed',
                                            message=f"Potential theft detected: {explanation}",
                                            audio_played=False,
                                            notification_sent=True
                                        )
                                        
                                        # Trigger audio alert
                                        try:
                                            audio_notifier.send_alert(threat_confidence, explanation)
                                            print(f"🔊 Audio alert sent")
                                        except Exception as e:
                                            print(f"❌ Audio alert failed: {e}")
                                        
                                        # END THE INCIDENT (threat detected by Gemini)
                                        IncidentManager.end_incident(current_incident_id)
                                        print(f"🛑 INCIDENT #{current_incident_id} ENDED - Threat confirmed by Gemini")
                                        current_incident_id = None
                                    else:
                                        print(f"✅ No threat in batch #{batch_num} (Confidence: {threat_confidence}%)")
                                        print(f"   Incident continues - will analyze again at frame {incident.total_frames + 10}...")
                        else:
                            # No hands detected
                            if current_incident_id:
                                # End the current incident
                                IncidentManager.end_incident(current_incident_id)
                                print(f"✅ INCIDENT #{current_incident_id} ENDED - No hands detected")
                                current_incident_id = None
                
                # Update visualization
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
            cv2.putText(frame, f"Frame: {frame_count} | Detection: {detection_frame_count}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add efficiency indicator
            efficiency_text = f"Efficiency: {detection_frame_count}/{frame_count} frames"
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
            print(f"❌ Error in MediaPipe hand detection processing: {e}")
            continue
    
    print("🤖 MediaPipe hand detection processing worker stopped")

# Detection stream processing
detection_stream_active = False

def update_dashboard_results(photo_count, detection_data, theft_detected, theft_confidence, explanation):
    """Update the latest results for dashboard display"""
    global latest_results
    latest_results = {
        'photo_count': photo_count,
        'hands_detected': detection_data['hands_detected'],
        'hand_count': detection_data['hand_count'],
        'hand_confidence': detection_data['max_confidence'] * 100,  # Convert to percentage
        'hand_positions': [hand['bbox'] for hand in detection_data['hands']],
        'detailed_hands': detection_data['hands'],
        'theft_detected': theft_detected,
        'theft_confidence': theft_confidence,
        'explanation': explanation,
        'timestamp': detection_data['timestamp']
    }

def real_monitoring_loop():
    """
    Real AI monitoring loop with proper incident tracking
    
    Workflow:
    1. Process each frame from video stream
    2. Detect hands with MediaPipe
    3. If hands detected:
       - Create incident if none active
       - Add frame to incident
       - Check if 10 frames reached (escalation)
       - If escalated: Send to Gemini for analysis
       - If threat confirmed: Alert user
    4. If no hands detected:
       - End current incident if any
    """
    global is_monitoring, current_session_id, current_incident_id, global_frame_count
    
    print("🔍 Starting AI monitoring loop with incident tracking")
    
    # Use frame_queue from detection_processing_worker instead of creating new connection
    # This monitoring loop just handles the database logic, not video processing
    
    while is_monitoring:
        try:
            # Check if we have detection results from the processing worker
            # This is a lightweight loop that just manages incidents
            time.sleep(0.1)  # Check 10 times per second
            
        except Exception as e:
            print(f"❌ ERROR in monitoring loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)
    
    print("🔍 Monitoring loop ended")

# API Routes
@app.route('/api/start_monitoring', methods=['POST'])
def start_monitoring():
    """Start real AI theft detection monitoring and create new session"""
    global is_monitoring, current_session_id, current_incident_id, global_frame_count
    
    if not is_monitoring:
        # Create new monitoring session
        with app.app_context():
            session = SessionManager.start_session()
            current_session_id = session.id
            current_incident_id = None
            global_frame_count = 0
        
        is_monitoring = True
        
        print(f"🛡️ MONITORING STARTED - Session #{current_session_id}")
        print("   MediaPipe hand detection: Active")
        print("   Gemini analysis: Ready")
        print("   ElevenLabs audio: Ready")
        
        return jsonify({
            'status': 'success',
            'message': 'Monitoring started',
            'session_id': current_session_id
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Already monitoring',
            'session_id': current_session_id
        })

@app.route('/api/stop_monitoring', methods=['POST'])
def stop_monitoring():
    """Stop AI theft detection monitoring and end current session"""
    global is_monitoring, detection_stream_active, current_session_id, current_incident_id
    
    if is_monitoring and current_session_id:
        # End any active incident first
        if current_incident_id:
            with app.app_context():
                IncidentManager.end_incident(current_incident_id)
                print(f"   Incident #{current_incident_id} ended")
                current_incident_id = None
        
        # End the session
        with app.app_context():
            session = SessionManager.end_session(current_session_id)
            print(f"⏹️ MONITORING STOPPED - Session #{current_session_id}")
            print(f"   Duration: {session.ended_at - session.started_at if session.ended_at else 'N/A'}")
            print(f"   Total frames: {session.total_frames}")
            print(f"   Total incidents: {session.total_incidents}")
            print(f"   Total escalations: {session.total_escalations}")
        
        session_id = current_session_id
        current_session_id = None
        
        is_monitoring = False
        detection_stream_active = False
        
        return jsonify({
            'status': 'success',
            'message': 'Monitoring stopped',
            'session_id': session_id
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Not monitoring'
        })

@app.route('/api/incidents')
def get_incidents():
    """Get recent incidents from database"""
    incidents = Incident.query.order_by(Incident.started_at.desc()).limit(20).all()
    return jsonify({'incidents': [incident.to_dict() for incident in incidents]})

@app.route('/api/sessions')
def get_sessions():
    """Get all sessions"""
    sessions = Session.query.order_by(Session.started_at.desc()).all()
    return jsonify({'sessions': [session.to_dict() for session in sessions]})

@app.route('/api/sessions/<int:session_id>')
def get_session_detail(session_id):
    """Get detailed session info with all incidents"""
    session = Session.query.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    session_data = session.to_dict()
    session_data['incidents'] = [incident.to_dict() for incident in session.incidents]
    
    return jsonify({'session': session_data})

@app.route('/api/incidents/<int:incident_id>')
def get_incident_detail(incident_id):
    """Get detailed incident info with all frames and analyses"""
    incident = Incident.query.get(incident_id)
    if not incident:
        return jsonify({'error': 'Incident not found'}), 404
    
    incident_data = incident.to_dict()
    incident_data['frames'] = [frame.to_dict() for frame in incident.frames]
    incident_data['analyses'] = [analysis.to_dict() for analysis in incident.gemini_analyses]
    incident_data['alerts'] = [alert.to_dict() for alert in incident.alerts]
    
    return jsonify({'incident': incident_data})

@app.route('/api/session')
def get_session():
    """Get current session info"""
    global current_session_id
    
    if current_session_id:
        session = Session.query.get(current_session_id)
        if session:
            return jsonify({'session': session.to_dict()})
    
    # No active session
    return jsonify({
        'session': {
            'is_active': False,
            'id': None
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

@app.route('/api/hand_detection_data', methods=['GET'])
def get_hand_detection_data():
    """Get detailed hand detection data for frontend"""
    global latest_results
    hand_data = {
        'hands_detected': latest_results.get('hands_detected', False),
        'hand_count': latest_results.get('hand_count', 0),
        'hand_confidence': latest_results.get('hand_confidence', 0.0),
        'hand_positions': latest_results.get('hand_positions', []),
        'detailed_hands': latest_results.get('detailed_hands', []),
        'timestamp': latest_results.get('timestamp', None),
        'photo_count': latest_results.get('photo_count', 0)
    }
    return jsonify(hand_data)

@app.route('/api/visualized_image', methods=['GET'])
def get_visualized_image():
    """Get the latest image with hand detections"""
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

@app.route('/detection_stream')
def detection_stream():
    """Stream MediaPipe hand detection processed frames using proper multi-threaded architecture"""
    def generate_detection_frames():
        global detection_stream_active, video_capture_thread, detection_processing_thread
        
        # Start background threads if not already running
        if not detection_stream_active:
            detection_stream_active = True
            print("🎥 Starting hand detection stream with proper multi-threading architecture")
            
            # Start video capture thread
            video_capture_thread = threading.Thread(target=video_capture_worker, daemon=True)
            video_capture_thread.start()
            
            # Start MediaPipe hand detection processing thread
            detection_processing_thread = threading.Thread(target=detection_processing_worker, daemon=True)
            detection_processing_thread.start()
            
            print("✅ Background threads started: Video capture + MediaPipe hand detection processing")
        
        # Stream processed frames from the queue
        frame_count = 0
        while detection_stream_active:
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
                print(f"❌ Error in detection stream: {e}")
                # Send error frame
                error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(error_frame, f"Stream Error: {str(e)[:50]}", (50, 200), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                _, buffer = cv2.imencode('.jpg', error_frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        print("🎥 Detection stream ended")
    
    return Response(generate_detection_frames(),
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
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/sessions')
def sessions():
    return render_template('sessions.html')

@app.route('/sessions/all')
def sessions_all():
    return render_template('sessions_all.html')

@app.route('/sessions/<int:session_id>')
def session_detail(session_id):
    return render_template('session_details.html')

@app.route('/incidents/<int:incident_id>')
def incident_detail(incident_id):
    return render_template('incident.html')

if __name__ == '__main__':
    print("🚀 Starting REAL AI-Powered Security System")
    print("🤖 MediaPipe Hand Detection: Ready")
    print("🤖 Gemini API: Ready for real analysis")
    print("🔊 ElevenLabs: Ready for voice alerts")
    print("📹 Pi Camera: http://100.101.51.31:5000/video_feed")
    print("🖥️  Dashboard: http://10.230.40.145:5000")
    print("🎯 REAL AI monitoring with MediaPipe + Gemini + ElevenLabs")
    print("Press Ctrl+C to stop")
    app.run(host='0.0.0.0', port=5000, threaded=True)
