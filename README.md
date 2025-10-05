## High-Hat

High-Hat is a real-time hand gesture detection application built using Python and YOLOv8. It leverages computer vision techniques to recognize and respond to hand movements, providing an interactive experience.

## Features

* **Real-Time Hand Gesture Detection**: Utilizes YOLOv8 for accurate hand tracking.
* **Audio Feedback**: Provides auditory cues in response to detected gestures.
* **Modular Architecture**: Designed with separate modules for easy maintenance and extension.
* **Sense HAT Integration**: Requires a Raspberry Pi Sense HAT for additional sensor-based input.
* **API Integration**: Uses Gemini 2.5 Pro API for advanced image analysis and ElevenLabs API for audio feedback.

## Installation

### Prerequisites

Ensure you have Python 3.12+ installed. It's recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

You also need a Sense HAT connected to your Raspberry Pi.

### Clone the Repository

```bash
git clone https://github.com/richard-w1/High-Hat.git
cd High-Hat
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### API Keys

Set up your environment with the necessary API keys:

* **Gemini 2.5 Pro API Key**: Required for image analysis.
* **ElevenLabs API Key**: Required for text-to-speech audio feedback.

```bash
export GEMINI_API_KEY='your_gemini_api_key_here'
export ELEVENLABS_API_KEY='your_elevenlabs_api_key_here'
```
<img width="1671" height="596" alt="image" src="https://github.com/user-attachments/assets/36909f17-147c-4d8e-b1d4-6b687cdc899c" />


## Usage

Start the application by running:

```bash
python real_ai_app.py
```

This will launch the application, and you should see a window displaying the camera feed with hand gesture detection.

## Project Structure

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/fd99b740-54f4-4bd7-9a3f-8f2c4de46687" />


* `app.py`: Main application entry point.
* `audio_notifier.py`: Handles audio feedback using ElevenLabs API.
* `gemini_analyzer.py`: Contains logic for analyzing hand gestures and images using Gemini 2.5 Pro API.
* `hand_detector.py`: Implements hand detection using YOLOv8.
* `real_ai_app.py`: Integrates various modules for the real-time application.
* `yolov8n.pt`: Pre-trained YOLOv8 model weights.
* `requirements.txt`: Python dependencies for the project.

## Directory Skeleton

# High-Hat/
* ├── real_ai_app.py           # Main Flask app orchestrating all modules
* ├── hand_detector.py         # MediaPipe-based hand tracking logic
* ├── gemini_analyzer.py       # AI reasoning using Gemini Vision API
* ├── audio_notifier.py        # ElevenLabs text-to-speech audio alerts
* ├── models.py                # SQLAlchemy ORM models (Session, Incident, etc.)
* ├── migrate_database.py      # Initializes the SQLite schema
* │
* ├── templates/               # HTML (Flask Jinja templates)
* │   ├── layout.html
* │   ├── dashboard.html
* │   ├── index.html
* │   ├── incident.html
* │   ├── sessions_all.html
* │
* ├── static/                  # Frontend assets
* │   ├── styles.css
* │   ├── dashboard.js
* │   ├── audit-table.js
* │   └── placeholder.svg
* │
* └── requirements.txt         # Python dependencies


## Contributing

Contributions are welcome! Please fork the repository, make your changes, and submit a pull request.

## License

This project is licensed under the MIT License.





