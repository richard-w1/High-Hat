"""
Database models for Security Monitoring System

Session Management:
- Each monitoring session has a unique ID
- Sessions track start/end times and are always recorded

Incident Management:
- Incidents are created when hands are detected
- Each incident continues as long as hands remain in consecutive frames
- Incidents track individual frames with hand detection data
- After 10 frames, incidents are escalated with Gemini analysis
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class Session(db.Model):
    """Monitoring session - created when user starts monitoring"""
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Statistics
    total_frames = db.Column(db.Integer, default=0)
    total_incidents = db.Column(db.Integer, default=0)
    total_escalations = db.Column(db.Integer, default=0)
    
    # Relationships
    incidents = db.relationship('Incident', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        # Check if any incidents have threats detected
        has_threat = any(incident.threat_detected for incident in self.incidents)
        
        return {
            'id': self.id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'is_active': self.is_active,
            'total_frames': self.total_frames,
            'total_incidents': self.total_incidents,
            'total_escalations': self.total_escalations,
            'has_threat': has_threat,  # True if any incident detected a threat
            'duration_seconds': (
                (self.ended_at - self.started_at).total_seconds() 
                if self.ended_at else 
                (datetime.utcnow() - self.started_at).total_seconds()
            ) if self.started_at else 0
        }


class Incident(db.Model):
    """Hand detection incident - created when hand first appears"""
    __tablename__ = 'incidents'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    
    # Timing
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Detection data
    total_frames = db.Column(db.Integer, default=0)
    max_hand_count = db.Column(db.Integer, default=0)
    max_confidence = db.Column(db.Float, default=0.0)
    
    # Escalation tracking
    is_escalated = db.Column(db.Boolean, default=False)
    escalation_threshold = db.Column(db.Integer, default=10)  # Frames before escalation
    
    # Gemini analysis (populated after escalation)
    gemini_analyzed = db.Column(db.Boolean, default=False)
    threat_detected = db.Column(db.Boolean, default=False)
    threat_confidence = db.Column(db.Float, nullable=True)
    threat_explanation = db.Column(db.Text, nullable=True)
    
    # Alert tracking
    user_alerted = db.Column(db.Boolean, default=False)
    alert_sent_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    frames = db.relationship('IncidentFrame', backref='incident', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'is_active': self.is_active,
            'total_frames': self.total_frames,
            'max_hand_count': self.max_hand_count,
            'max_confidence': self.max_confidence,
            'is_escalated': self.is_escalated,
            'gemini_analyzed': self.gemini_analyzed,
            'threat_detected': self.threat_detected,
            'threat_confidence': self.threat_confidence,
            'threat_explanation': self.threat_explanation,
            'user_alerted': self.user_alerted,
            'alert_sent_at': self.alert_sent_at.isoformat() if self.alert_sent_at else None,
            'duration_seconds': (
                (self.ended_at - self.started_at).total_seconds() 
                if self.ended_at else 
                (datetime.utcnow() - self.started_at).total_seconds()
            ) if self.started_at else 0
        }


class IncidentFrame(db.Model):
    """Individual frame data within an incident"""
    __tablename__ = 'incident_frames'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    
    # Frame metadata
    frame_number = db.Column(db.Integer, nullable=False)  # Frame # within incident
    global_frame_number = db.Column(db.Integer, nullable=True)  # Frame # within entire session
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # MediaPipe detection data
    hands_detected = db.Column(db.Boolean, default=False)
    hand_count = db.Column(db.Integer, default=0)
    hand_confidence = db.Column(db.Float, default=0.0)
    
    # Hand data (stored as JSON)
    # Format: [{'type': 'left_hand'/'right_hand', 'confidence': 0.95, 'bbox': [x1,y1,x2,y2], 'landmarks': [...]}]
    hand_data = db.Column(db.Text, nullable=True)  # JSON string
    
    # Image data (base64 encoded JPEG)
    image_data = db.Column(db.Text, nullable=True)  # Base64 string (optional, can be heavy)
    
    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'frame_number': self.frame_number,
            'global_frame_number': self.global_frame_number,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'hands_detected': self.hands_detected,
            'hand_count': self.hand_count,
            'hand_confidence': self.hand_confidence,
            'hand_data': json.loads(self.hand_data) if self.hand_data else []
        }
    
    def set_hand_data(self, hand_list):
        """Store hand detection data as JSON"""
        # Convert landmarks to serializable format (remove MediaPipe objects)
        serializable_hands = []
        for hand in hand_list:
            serializable_hand = {
                'type': hand.get('type'),
                'confidence': hand.get('confidence'),
                'bbox': hand.get('bbox')
                # Note: landmarks are MediaPipe objects and can't be easily serialized
                # If needed, convert to list of [x, y, z] coordinates
            }
            serializable_hands.append(serializable_hand)
        
        self.hand_data = json.dumps(serializable_hands)
    
    def get_hand_data(self):
        """Retrieve hand detection data from JSON"""
        if self.hand_data:
            return json.loads(self.hand_data)
        return []


class GeminiAnalysis(db.Model):
    """Gemini analysis results for escalated incidents"""
    __tablename__ = 'gemini_analyses'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    
    # Analysis timing
    analyzed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Frames analyzed
    frame_start = db.Column(db.Integer, nullable=False)  # Starting frame number
    frame_end = db.Column(db.Integer, nullable=False)    # Ending frame number
    total_frames_analyzed = db.Column(db.Integer, nullable=False)
    
    # Gemini response
    threat_detected = db.Column(db.Boolean, default=False)
    confidence = db.Column(db.Float, nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    raw_response = db.Column(db.Text, nullable=True)  # Full Gemini JSON response
    
    # API metadata
    api_latency_ms = db.Column(db.Integer, nullable=True)
    tokens_used = db.Column(db.Integer, nullable=True)
    
    # Relationship
    incident = db.relationship('Incident', backref='gemini_analyses', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'frame_start': self.frame_start,
            'frame_end': self.frame_end,
            'total_frames_analyzed': self.total_frames_analyzed,
            'threat_detected': self.threat_detected,
            'confidence': self.confidence,
            'explanation': self.explanation,
            'api_latency_ms': self.api_latency_ms
        }


class UserAlert(db.Model):
    """Track alerts sent to user"""
    __tablename__ = 'user_alerts'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    
    # Alert details
    alert_type = db.Column(db.String(50), nullable=False)  # 'hand_detected', 'escalation', 'theft_confirmed'
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Alert channels
    audio_played = db.Column(db.Boolean, default=False)
    notification_sent = db.Column(db.Boolean, default=False)
    
    # Message content
    message = db.Column(db.Text, nullable=True)
    
    # User response
    acknowledged = db.Column(db.Boolean, default=False)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    incident = db.relationship('Incident', backref='alerts', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'incident_id': self.incident_id,
            'alert_type': self.alert_type,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'audio_played': self.audio_played,
            'notification_sent': self.notification_sent,
            'message': self.message,
            'acknowledged': self.acknowledged,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None
        }

