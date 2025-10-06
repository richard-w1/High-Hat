# High-Hat - HackUTA 2025


https://www.youtube.com/watch?v=kCthLFBD2vs

<img width="768" height="385" alt="image" src="https://github.com/user-attachments/assets/d34c4f7e-c252-4867-8ab7-f670f7df7247" />


**High-Hat** is a security monitoring system designed to detect and prevent personal backpack/pickpocket theft using computer vision, generative AI, and voice alerts.

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
