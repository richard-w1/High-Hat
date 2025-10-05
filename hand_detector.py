import cv2
import numpy as np
import time
import requests
from PIL import Image
import io
import mediapipe as mp

class HandDetector:
    def __init__(self, confidence_threshold=0.5):
        """Initialize MediaPipe for hand detection"""
        try:
            # Initialize MediaPipe hands
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,  # Detect up to 2 hands
                min_detection_confidence=confidence_threshold,
                min_tracking_confidence=0.5
            )
            self.mp_drawing = mp.solutions.drawing_utils
            self.confidence_threshold = confidence_threshold
            print(f"🤖 MediaPipe hand detector initialized with confidence threshold {confidence_threshold}")
        except Exception as e:
            print(f"❌ Error initializing MediaPipe: {e}")
            self.hands = None
        
    def detect_hands_from_camera(self, camera_url):
        """
        Detect hands from Pi camera feed
        Returns: (hands_detected, image_with_detections)
        """
        try:
            # Get image from Pi camera
            response = requests.get(camera_url, timeout=5)
            if response.status_code != 200:
                print(f"❌ Camera request failed: {response.status_code}")
                return False, None
            
            # Convert to OpenCV format
            image_array = np.frombuffer(response.content, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            if image is None:
                print("❌ Failed to decode camera image")
                return False, None
            
            # Detect hands
            has_hand, confidence, hands = self.detect_hands(image)
            
            # Draw detections
            if has_hand:
                image = self.draw_detections(image, hands)
                print(f"🖐️ Detected {len(hands)} hands with confidence {confidence:.2f}")
                return True, image
            else:
                print("👀 No hands detected")
                return False, image
                
        except Exception as e:
            print(f"❌ Error in camera hand detection: {e}")
            return False, None

    def detect_hands(self, frame):
        """
        Detect hands in a frame using MediaPipe
        Returns: (has_hand, confidence, bounding_boxes)
        """
        if self.hands is None:
            return False, 0, []
            
        try:
            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Process the frame
            results = self.hands.process(rgb_frame)
            
            hands_detected = []
            max_confidence = 0
            
            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_handedness):
                    # Get hand label (Left or Right)
                    hand_label = hand_landmarks.classification[0].label
                    confidence = hand_landmarks.classification[0].score
                    
                    if confidence > self.confidence_threshold:
                        # Get hand landmarks
                        landmarks = results.multi_hand_landmarks[idx]
                        
                        # Calculate bounding box from landmarks
                        h, w, _ = frame.shape
                        x_coords = [landmark.x for landmark in landmarks.landmark]
                        y_coords = [landmark.y for landmark in landmarks.landmark]
                        
                        # Convert normalized coordinates to pixel coordinates
                        x_coords = [int(x * w) for x in x_coords]
                        y_coords = [int(y * h) for y in y_coords]
                        
                        # Calculate bounding box
                        x1 = max(0, min(x_coords) - 20)  # Add padding
                        y1 = max(0, min(y_coords) - 20)
                        x2 = min(w, max(x_coords) + 20)
                        y2 = min(h, max(y_coords) + 20)
                        
                        hands_detected.append({
                            'confidence': confidence,
                            'bbox': (x1, y1, x2, y2),
                            'type': f'{hand_label.lower()}_hand',
                            'landmarks': landmarks
                        })
                        
                        max_confidence = max(max_confidence, confidence)
            
            has_hand = len(hands_detected) > 0
            return has_hand, max_confidence, hands_detected
            
        except Exception as e:
            print(f"❌ Error in hand detection: {e}")
            return False, 0, []
    
    def capture_suspicious_images(self, camera_url, num_images=5):
        """
        Capture multiple images when hands are detected
        Returns: list of images (PIL format)
        """
        images = []
        print(f"📸 Capturing {num_images} suspicious images...")
        
        for i in range(num_images):
            try:
                response = requests.get(camera_url, timeout=5)
                if response.status_code == 200:
                    # Convert to PIL Image
                    image = Image.open(io.BytesIO(response.content))
                    images.append(image)
                    print(f"📸 Captured image {i+1}/{num_images}")
                else:
                    print(f"❌ Failed to capture image {i+1}")
                    
            except Exception as e:
                print(f"❌ Error capturing image {i+1}: {e}")
            
            # Small delay between captures
            time.sleep(0.5)
        
        return images
    
    def draw_detections(self, frame, detections):
        """Draw hand landmarks and bounding boxes on frame for visualization"""
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            confidence = detection['confidence']
            hand_type = detection.get('type', 'hand')
            landmarks = detection.get('landmarks')
            
            # Different colors for left and right hands
            if hand_type == 'left_hand':
                color = (0, 255, 0)  # Green for left hand
                label = f"Left Hand: {confidence:.2f}"
            elif hand_type == 'right_hand':
                color = (255, 0, 0)  # Blue for right hand
                label = f"Right Hand: {confidence:.2f}"
            else:
                color = (0, 255, 0)  # Default green
                label = f"Hand: {confidence:.2f}"
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw confidence label
            cv2.putText(frame, label, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw hand landmarks if available
            if landmarks:
                self.mp_drawing.draw_landmarks(
                    frame, landmarks, self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=2),
                    self.mp_drawing.DrawingSpec(color=color, thickness=2)
                )
        
        return frame
