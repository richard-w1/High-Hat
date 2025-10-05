import os
import time
import requests
import json

class AudioNotifier:
    def __init__(self):
        """Initialize ElevenLabs for voice notifications"""
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        self.voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')  # Default voice
        self.base_url = "https://api.elevenlabs.io/v1"
        
        if not self.api_key:
            print("❌ ELEVENLABS_API_KEY not found in environment variables")
            self.api_key = None
        else:
            print("🔊 ElevenLabs API initialized successfully")
        
    def generate_theft_alert(self, confidence, explanation):
        """
        Generate and return audio alert for theft detection
        """
        if not self.api_key:
            print("⚠️ ElevenLabs not available, using simulation")
            return self._simulate_audio()
            
        try:
            # Create alert message
            message = f"SECURITY ALERT! Suspicious activity detected near your backpack. Confidence level: {confidence} percent. {explanation}. Please check your belongings immediately."
            
            print(f"🔊 Generating audio alert: {message}")
            
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
                    "stability": 0.5,
                    "similarity_boost": 0.5
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
        """Generate and play audio alert"""
        print(f"🚨 Sending audio alert: {confidence}% - {explanation}")
        audio_data = self.generate_theft_alert(confidence, explanation)
        if audio_data:
            self.play_alert(audio_data)
        else:
            print("❌ Failed to generate audio alert")
    
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
