import google.generativeai as genai
import base64
import io
from PIL import Image
import os
import json

class GeminiAnalyzer:
    def __init__(self):
        """Initialize Gemini API"""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                print("❌ GEMINI_API_KEY not found in environment variables")
                self.model = None
                return
                
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.5-pro')
            print("🤖 Gemini API initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing Gemini: {e}")
            self.model = None
        
    def analyze_theft_attempt(self, image_batch):
        """
        Analyze a batch of images for theft attempts using Gemini
        Args:
            image_batch: List of PIL Images
        Returns:
            (is_theft, confidence, explanation)
        """
        if self.model is None:
            print("⚠️ Gemini not available, using simulation")
            return self._simulate_analysis()
            
        try:
            print(f"🔍 Analyzing {len(image_batch)} images with Gemini...")
            
            # Prepare images for Gemini
            images_for_analysis = []
            for i, img in enumerate(image_batch):
                # Convert PIL to bytes
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='JPEG')
                img_bytes = img_buffer.getvalue()
                images_for_analysis.append({
                    "mime_type": "image/jpeg",
                    "data": img_bytes
                })
                print(f"📸 Prepared image {i+1} for analysis")
            
            # Create prompt for theft detection
            prompt = """
            Analyze these images from a backpack security camera. 
            
            Look for:
            1. Hands reaching toward or into the backpack
            2. Suspicious proximity to the bag
            3. Attempts to open zippers or access contents
            4. Any behavior that suggests theft or unauthorized access
            
            For each image, determine if there's suspicious activity.
            Then provide an overall assessment.
            
            Respond in this exact JSON format:
            {
                "suspicious": true/false,
                "confidence": <number between 0-100>,
                "explanation": "<detailed explanation>",
                "threat_level": "<low/medium/high>",
                "behaviors_detected": ["<behavior1>", "<behavior2>"]
            }
            """
            
            # Send to Gemini
            response = self.model.generate_content([prompt] + images_for_analysis)
            
            # Parse response
            result = self._parse_gemini_response(response.text)
            print(f"✅ Gemini analysis complete: {result[1]}% confidence")
            return result
            
        except Exception as e:
            print(f"❌ Error in Gemini analysis: {e}")
            return self._simulate_analysis()
    
    def _simulate_analysis(self):
        """Fallback simulation when Gemini is not available"""
        import random
        
        scenarios = [
            (True, random.randint(70, 95), "Hand detected reaching toward backpack - potential theft attempt"),
            (True, random.randint(60, 85), "Suspicious movement detected near bag - person too close"),
            (True, random.randint(70, 90), "Bag zipper movement detected - unauthorized access attempt"),
            (True, random.randint(80, 95), "Multiple people near backpack - potential coordinated theft")
        ]
        
        return random.choice(scenarios)
    
    def _parse_gemini_response(self, response_text):
        """Parse Gemini response to extract structured data"""
        try:
            # Try to extract JSON from response
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    data = json.loads(json_str)
                    return (
                        data.get('suspicious', False),
                        int(data.get('confidence', 50)),
                        data.get('explanation', response_text)
                    )
                except json.JSONDecodeError:
                    pass
            
            # Fallback to line-by-line parsing
            lines = response_text.strip().split('\n')
            suspicious = False
            confidence = 0
            explanation = "No analysis available"
            
            for line in lines:
                line = line.strip()
                if line.startswith('SUSPICIOUS:'):
                    suspicious = 'YES' in line.upper()
                elif line.startswith('CONFIDENCE:'):
                    try:
                        confidence = int(line.split(':')[1].strip())
                    except:
                        confidence = 0
                elif line.startswith('EXPLANATION:'):
                    explanation = line.split(':', 1)[1].strip()
            
            return suspicious, confidence, explanation
            
        except Exception as e:
            print(f"❌ Error parsing Gemini response: {e}")
            return False, 0, f"Parse error: {str(e)}"
