# High-Hat - HackUTA 2025 

https://devpost.com/software/high-hat

**High-Hat** is a security monitoring system designed to detect and prevent personal backpack/pickpocket theft using computer vision, generative AI, and voice alerts.

[![Link to Youtube](https://private-user-images.githubusercontent.com/101631956/497924634-d34c4f7e-c252-4867-8ab7-f670f7df7247.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NTk3NzE3OTAsIm5iZiI6MTc1OTc3MTQ5MCwicGF0aCI6Ii8xMDE2MzE5NTYvNDk3OTI0NjM0LWQzNGM0ZjdlLWMyNTItNDg2Ny04YWI3LWY2NzBmN2RmNzI0Ny5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUxMDA2JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MTAwNlQxNzI0NTBaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT1kMWUxNGZmZGE2ZTkzYmFmNDZlODA3YmM1OTU5YjA2OTNmYjc1N2U2ZTYwNjgyYzA3YWYzNGZlOWY5OTZmZjQ3JlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.EqrbES8kxNu2nPWVWjCQ_f2mIkPvF7i9E1KaDLzdS-8)](https://www.youtube.com/watch?v=kCthLFBD2vs "High_Hat")

<div style="display: flex; gap: 10px;">
  <img width="400" height="268" alt="image" src="https://github.com/user-attachments/assets/fcb899cc-ba18-497e-871e-62f3fa6aef74" />
  <img width="400" height="342" alt="image" src="https://github.com/user-attachments/assets/1b011e17-e3e7-4c16-8e8f-cea3b01109e1" />
</div>

<div style="display: flex; gap: 10px;">
  <img width="400" height="275" alt="image" src="https://github.com/user-attachments/assets/6125309c-ff62-4109-afad-523700fd4b63" />
  <img width="400" height="239" alt="image" src="https://github.com/user-attachments/assets/ea75e45b-2aaf-4ee1-9de1-651723c1fe6b" />
</div>


## Features

- Raspberry Pi camera streaming and Sense HAT LED
- Real-time hand detection using MediaPipe and threat analysis via Google Gemini
- Natural voice alerts through ElevenLabs text-to-speech
- Live video dashboard and incident tracking and escalation

## How It Works

1. **Capture**: Pi streams video via MJPEG
2. **Detect**: Server uses MediaPipe processes for hand detection
3. **Track**: Incident created and tracks frames continuously
4. **Escalate**: After a long incident, batch sent to Gemini for analysis
5. **Analyze**: Gemini determines if behavior is suspicious
6. **Alert**: If Gemini determines a threat, ElevenLabs generates voice alert

### Backend
- Flask
- Flask-SQLAlchemy
- Flask-CORS
- OpenCV
- MediaPipe
- Pillow
- NumPy

### AI Services
- Google Gemini 2.5 Pro
- ElevenLabs

### Frontend
- HTML/CSS/JavaScript
- Real-time video streaming
- REST API consumption
- Audio playback

## System Architecture

```
┌─────────────────┐
│  Raspberry Pi   │
│   + Camera      │  ──────> Video Stream (MJPEG)
│   + Sense HAT   │
└─────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│        Main Server (Flask App)          │
│                                         │
│  ┌────────────────────────────────────┐ │
│  │  • Video Capture Thread            │ │
│  │  • MediaPipe Detection Thread      │ │
│  │  • Non-blocking Frame Queues       │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌────────────────────────────────────┐ │
│  │  • Background Gemini Analysis      │ │
│  │  • Immediate ElevenLabs TTS Alert  │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Web Dashboard  │
│  • Live Video   │
│  • Incidents    │
│  • Threats      │
│  • Analytics    │
└─────────────────┘
```

### Requirements

- **Raspberry Pi** (3/4/5) with camera module
- **Sense HAT** (optional, for LED patterns)
- Network connection (Wi-Fi or Ethernet)

- Python 3.8+
- Raspberry Pi OS
- Windows/Linux/Mac

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/High-Hat.git
   cd High-Hat
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ```

4. **Set up Raspberry Pi camera**
   ```bash
   # On Raspberry Pi
   python pi_video.py
   ```

5. **Update camera URL in app.py**
   
   Edit `app.py` line 61:
   ```python
   PI_CAMERA_URL = "http://YOUR_PI_IP:5000/video_feed"
   ```

6. **Run the main application**
   ```bash
   python app.py
   ```

7. **Access the dashboard**
   

   Open your browser to `http://localhost:5000` or `http://YOUR_SERVER_IP:5000`


