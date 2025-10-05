import os
import time
import requests
import json
import base64
from datetime import datetime

class AudioNotifier:
    def __init__(self):
        """Initialize ElevenLabs for voice notifications"""
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        self.voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')  # Default voice
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Store latest alert for frontend to fetch
        self.latest_alert = None
        self.alert_timestamp = None
        
        if not self.api_key:
            print("❌ ELEVENLABS_API_KEY not found in environment variables")
            self.api_key = None
        else:
            print("🔊 ElevenLabs API initialized successfully")
        
    def _create_short_alert_message(self, confidence, explanation):
        """
        Create a SHORT, natural alert message from Gemini's potentially long explanation.
        Just describe what happened and tell user to check their things.
        """
        # Extract key threat indicators from explanation
        explanation_lower = explanation.lower()
        
        # Determine threat description based on keywords
        if "reaching" in explanation_lower or "hand reaching" in explanation_lower:
            threat_description = "Someone is reaching toward your backpack"
        elif "grabbing" in explanation_lower or "taking" in explanation_lower:
            threat_description = "Someone is grabbing your backpack"
        elif "touching" in explanation_lower:
            threat_description = "Someone is touching your backpack"
        elif "opening" in explanation_lower or "unzipping" in explanation_lower:
            threat_description = "Someone is opening your backpack"
        elif "theft" in explanation_lower or "stealing" in explanation_lower:
            threat_description = "Possible theft attempt detected"
        elif "tampering" in explanation_lower:
            threat_description = "Someone is tampering with your backpack"
        elif "suspicious hand" in explanation_lower or "unauthorized" in explanation_lower:
            threat_description = "Suspicious hand movement near your backpack"
        else:
            # Generic threat message
            threat_description = "Suspicious activity near your backpack"
        
        # Create short, natural message
        message = f"{threat_description}. Check your belongings immediately."
        
        return message
    
    def generate_theft_alert(self, confidence, explanation):
        """
        Generate and return audio alert for threat detection.
        Creates a SHORT, descriptive message based on Gemini's analysis.
        """
        if not self.api_key:
            print("⚠️ ElevenLabs not available, using simulation")
            return self._simulate_audio()
            
        try:
            # Create SHORT alert message (not the full Gemini response)
            message = self._create_short_alert_message(confidence, explanation)
            
            print(f"🔊 Generating SHORT audio alert: {message}")
            print(f"   (Original Gemini explanation was {len(explanation)} chars)")
            
            # Generate audio using ElevenLabs API
            url = f"{self.base_url}/text-to-speech/{self.voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": message,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.7,      # Higher stability for clearer urgent message
                    "similarity_boost": 0.75  # Higher similarity for consistency
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                print("✅ Audio generated successfully")
                return response.content
            else:
                print(f"❌ ElevenLabs API error: {response.status_code}")
                return self._simulate_audio()
            
        except Exception as e:
            print(f"❌ Error generating audio alert: {e}")
            return self._simulate_audio()
    
    def _simulate_audio(self):
        """Simulate audio generation when ElevenLabs is not available"""
        print("🔊 [SIMULATED] Audio alert would play here")
        return b"simulated_audio"
    
    def play_alert(self, audio_data):
        """Play audio alert"""
        try:
            if audio_data == b"simulated_audio":
                print("🔊 [SIMULATED] Playing audio alert...")
                time.sleep(2)  # Simulate audio duration
                return
                
            # For real implementation, you would use pygame or similar
            print("🔊 Playing audio alert...")
            time.sleep(2)  # Simulate audio duration
            print("✅ Audio playback complete")
            
        except Exception as e:
            print(f"❌ Error playing audio: {e}")
    
    def send_alert(self, confidence, explanation):
        """Generate audio alert and make it available for frontend"""
        print(f"🚨 Sending REAL-TIME audio alert: {confidence}% - {explanation[:100]}...")
        
        # Generate SHORT message for audio and display
        short_message = self._create_short_alert_message(confidence, explanation)
        
        # Generate audio with short message
        audio_data = self.generate_theft_alert(confidence, explanation)
        
        if audio_data and audio_data != b"simulated_audio":
            # Convert to base64 for frontend consumption
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            self.latest_alert = {
                'audio': audio_base64,
                'confidence': confidence,
                'short_message': short_message,  # SHORT message for display
                'full_explanation': explanation,  # Full explanation for reference
                'timestamp': datetime.utcnow().isoformat()
            }
            self.alert_timestamp = datetime.utcnow()
            print(f"✅ Audio alert ready for frontend (size: {len(audio_data)} bytes)")
            print(f"   Short message: {short_message}")
        else:
            print("❌ Failed to generate audio alert")
    
    def get_latest_alert(self):
        """
        Get the latest alert for frontend consumption.
        Returns None if alert is older than 15 seconds (real-time only).
        """
        if not self.latest_alert or not self.alert_timestamp:
            return None
        
        # Check if alert is still fresh (within 15 seconds)
        age_seconds = (datetime.utcnow() - self.alert_timestamp).total_seconds()
        
        if age_seconds > 15:
            # Alert is too old - clear it and return None
            print(f"⚠️  Alert expired ({age_seconds:.1f}s old) - clearing")
            self.clear_alert()
            return None
        
        return self.latest_alert
    
    def clear_alert(self):
        """Clear the current alert after it's been played"""
        self.latest_alert = None
        self.alert_timestamp = None
    
    def generate_test_alert(self):
        """Generate a test alert for system verification"""
        try:
            message = "Security system activated. Backpack monitoring is now active."
            
            if not self.api_key:
                print("⚠️ ElevenLabs not available, using simulation")
                return self._simulate_audio()
            
            url = f"{self.base_url}/text-to-speech/{self.voice_id}"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": message,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                return response.content
            else:
                return self._simulate_audio()
            
        except Exception as e:
            print(f"❌ Error generating test alert: {e}")
            return self._simulate_audio()
