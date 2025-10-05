"""
Session and Incident Management Service

This module handles the business logic for:
- Creating and managing monitoring sessions
- Creating and tracking incidents when hands are detected
- Managing incident frames
- Escalating incidents after 10 frames
- Coordinating Gemini analysis
- Triggering user alerts
"""

from models import db, Session, Incident, IncidentFrame, GeminiAnalysis, UserAlert
from datetime import datetime
import base64
import cv2
import numpy as np


class SessionManager:
    """Manages monitoring sessions"""
    
    @staticmethod
    def start_session():
        """Create a new monitoring session"""
        session = Session(
            started_at=datetime.utcnow(),
            is_active=True,
            total_frames=0,
            total_incidents=0,
            total_escalations=0
        )
        db.session.add(session)
        db.session.commit()
        
        print(f"🎬 Session #{session.id} started at {session.started_at}")
        return session
    
    @staticmethod
    def end_session(session_id):
        """End an active monitoring session"""
        session = Session.query.get(session_id)
        if not session:
            raise ValueError(f"Session #{session_id} not found")
        
        if not session.is_active:
            raise ValueError(f"Session #{session_id} is already ended")
        
        # Close any active incidents
        active_incidents = Incident.query.filter_by(
            session_id=session_id,
            is_active=True
        ).all()
        
        for incident in active_incidents:
            IncidentManager.end_incident(incident.id)
        
        # End session
        session.ended_at = datetime.utcnow()
        session.is_active = False
        db.session.commit()
        
        print(f"🛑 Session #{session_id} ended at {session.ended_at}")
        print(f"   Duration: {(session.ended_at - session.started_at).total_seconds():.1f}s")
        print(f"   Total frames: {session.total_frames}")
        print(f"   Total incidents: {session.total_incidents}")
        print(f"   Total escalations: {session.total_escalations}")
        
        return session
    
    @staticmethod
    def get_active_session():
        """Get the currently active session"""
        return Session.query.filter_by(is_active=True).first()
    
    @staticmethod
    def increment_frame_count(session_id):
        """Increment the frame count for a session"""
        session = Session.query.get(session_id)
        if session:
            session.total_frames += 1
            db.session.commit()
            return session.total_frames
        return 0


class IncidentManager:
    """Manages hand detection incidents"""
    
    @staticmethod
    def create_incident(session_id):
        """Create a new incident when hands are first detected"""
        incident = Incident(
            session_id=session_id,
            started_at=datetime.utcnow(),
            is_active=True,
            total_frames=0,
            max_hand_count=0,
            max_confidence=0.0,
            is_escalated=False,
            escalation_threshold=10
        )
        db.session.add(incident)
        
        # Update session incident count
        session = Session.query.get(session_id)
        if session:
            session.total_incidents += 1
        
        db.session.commit()
        
        print(f"🖐️ Incident #{incident.id} created in Session #{session_id}")
        return incident
    
    @staticmethod
    def get_active_incident(session_id):
        """Get the currently active incident for a session"""
        return Incident.query.filter_by(
            session_id=session_id,
            is_active=True
        ).first()
    
    @staticmethod
    def end_incident(incident_id):
        """End an active incident (no hands detected in next frame)"""
        incident = Incident.query.get(incident_id)
        if not incident:
            return None
        
        incident.ended_at = datetime.utcnow()
        incident.is_active = False
        db.session.commit()
        
        duration = (incident.ended_at - incident.started_at).total_seconds()
        print(f"✅ Incident #{incident_id} ended after {incident.total_frames} frames ({duration:.1f}s)")
        
        return incident
    
    @staticmethod
    def add_frame_to_incident(incident_id, global_frame_num, hand_count, hand_confidence, hand_detections, frame_image=None):
        """
        Add a frame to an incident
        
        Args:
            incident_id: ID of the incident
            global_frame_num: Frame number in the entire session
            hand_count: Number of hands detected
            hand_confidence: Maximum confidence score
            hand_detections: List of hand detection dicts from MediaPipe
            frame_image: Optional numpy array of the frame (will be converted to base64)
        
        Returns:
            IncidentFrame object
        """
        incident = Incident.query.get(incident_id)
        if not incident:
            raise ValueError(f"Incident #{incident_id} not found")
        
        # Increment incident frame count
        incident.total_frames += 1
        frame_number = incident.total_frames
        
        # Update incident max values
        if hand_count > incident.max_hand_count:
            incident.max_hand_count = hand_count
        if hand_confidence > incident.max_confidence:
            incident.max_confidence = hand_confidence
        
        # Convert frame image to base64 (optional, can be heavy)
        # Only encode if frame_image is provided (we skip every 4th frame to reduce lag)
        image_data_b64 = None
        if frame_image is not None:
            _, buffer = cv2.imencode('.jpg', frame_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_data_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Create frame record
        frame = IncidentFrame(
            incident_id=incident_id,
            frame_number=frame_number,
            global_frame_number=global_frame_num,
            timestamp=datetime.utcnow(),
            hands_detected=hand_count > 0,
            hand_count=hand_count,
            hand_confidence=hand_confidence,
            image_data=image_data_b64
        )
        
        # Store hand detection data
        frame.set_hand_data(hand_detections)
        
        db.session.add(frame)
        db.session.commit()
        
        saved_status = "with image" if image_data_b64 else "metadata only"
        print(f"   📸 Frame #{frame_number} added to Incident #{incident_id} (global #{global_frame_num}, {saved_status})")
        
        # Check if we should escalate
        if not incident.is_escalated and incident.total_frames >= incident.escalation_threshold:
            print(f"   ⚠️  Incident #{incident_id} reached {incident.total_frames} frames - ESCALATING!")
            incident.is_escalated = True
            
            # Update session escalation count
            session = Session.query.get(incident.session_id)
            if session:
                session.total_escalations += 1
            
            db.session.commit()
            
            # Return True to signal escalation needed
            return frame, True
        
        return frame, False
    
    @staticmethod
    def get_incident_frames_for_analysis(incident_id, last_n_frames=10):
        """Get the last N frames of an incident for Gemini analysis"""
        frames = IncidentFrame.query.filter_by(
            incident_id=incident_id
        ).order_by(IncidentFrame.frame_number.desc()).limit(last_n_frames).all()
        
        # Reverse to get chronological order
        frames.reverse()
        
        print(f"   📦 Retrieved {len(frames)} frames for analysis (Incident #{incident_id})")
        return frames


class GeminiAnalysisManager:
    """Manages Gemini analysis for escalated incidents"""
    
    @staticmethod
    def record_analysis(incident_id, frame_start, frame_end, threat_detected, confidence, explanation, raw_response=None, latency_ms=None):
        """Record a Gemini analysis result"""
        analysis = GeminiAnalysis(
            incident_id=incident_id,
            analyzed_at=datetime.utcnow(),
            frame_start=frame_start,
            frame_end=frame_end,
            total_frames_analyzed=frame_end - frame_start + 1,
            threat_detected=threat_detected,
            confidence=confidence,
            explanation=explanation,
            raw_response=raw_response,
            api_latency_ms=latency_ms
        )
        db.session.add(analysis)
        
        # Update incident with analysis results
        incident = Incident.query.get(incident_id)
        if incident:
            incident.gemini_analyzed = True
            
            # Only update threat status if a threat is detected
            # Once a threat is detected, keep it marked as threat
            if threat_detected:
                incident.threat_detected = True
                incident.threat_confidence = confidence
                incident.threat_explanation = explanation
            # If no previous threat was detected, update confidence/explanation anyway
            elif not incident.threat_detected:
                incident.threat_confidence = confidence
                incident.threat_explanation = explanation
        
        db.session.commit()
        
        print(f"   🤖 Gemini analysis recorded for Incident #{incident_id}")
        print(f"      Threat: {threat_detected}, Confidence: {confidence}%")
        
        return analysis


class AlertManager:
    """Manages user alerts"""
    
    @staticmethod
    def send_alert(incident_id, alert_type, message, audio_played=False, notification_sent=False):
        """Record an alert sent to the user"""
        alert = UserAlert(
            incident_id=incident_id,
            alert_type=alert_type,
            sent_at=datetime.utcnow(),
            audio_played=audio_played,
            notification_sent=notification_sent,
            message=message,
            acknowledged=False
        )
        db.session.add(alert)
        
        # Mark incident as alerted
        incident = Incident.query.get(incident_id)
        if incident:
            incident.user_alerted = True
            incident.alert_sent_at = datetime.utcnow()
        
        db.session.commit()
        
        print(f"   🚨 Alert sent for Incident #{incident_id}: {alert_type}")
        
        return alert
    
    @staticmethod
    def acknowledge_alert(alert_id):
        """Mark an alert as acknowledged by the user"""
        alert = UserAlert.query.get(alert_id)
        if alert:
            alert.acknowledged = True
            alert.acknowledged_at = datetime.utcnow()
            db.session.commit()
            print(f"   ✅ Alert #{alert_id} acknowledged")
        return alert

