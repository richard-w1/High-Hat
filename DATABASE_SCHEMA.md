# Database Schema Documentation

## Overview

The security monitoring system uses a relational SQLite database to track monitoring sessions, hand detection incidents, frame-by-frame analysis, Gemini AI evaluations, and user alerts.

## Database File

- **Production**: `security_monitor.db`
- **Old/Legacy**: `theft_detection.db` (deprecated)

## Tables

### 1. `sessions` - Monitoring Sessions

Tracks each monitoring session when the user starts/stops monitoring.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-increment session ID |
| `started_at` | DATETIME | When monitoring started |
| `ended_at` | DATETIME | When monitoring ended (NULL if active) |
| `is_active` | BOOLEAN | Whether session is currently active |
| `total_frames` | INTEGER | Total frames processed in this session |
| `total_incidents` | INTEGER | Total incidents detected in this session |
| `total_escalations` | INTEGER | Total incidents that reached escalation threshold |

**Relationships**:
- Has many `incidents`

---

### 2. `incidents` - Hand Detection Incidents

Created when a hand is first detected. Continues as long as hands remain in consecutive frames.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-increment incident ID |
| `session_id` | INTEGER (FK) | Reference to parent session |
| `started_at` | DATETIME | When incident started (first hand detected) |
| `ended_at` | DATETIME | When incident ended (NULL if active) |
| `is_active` | BOOLEAN | Whether incident is currently active |
| `total_frames` | INTEGER | Number of frames in this incident |
| `max_hand_count` | INTEGER | Maximum hands detected in any frame |
| `max_confidence` | FLOAT | Maximum confidence score across all frames |
| `is_escalated` | BOOLEAN | Whether incident has been escalated |
| `escalation_threshold` | INTEGER | Frames needed for escalation (default: 10) |
| `gemini_analyzed` | BOOLEAN | Whether Gemini has analyzed this incident |
| `threat_detected` | BOOLEAN | Gemini's verdict on threat presence |
| `threat_confidence` | FLOAT | Gemini's confidence percentage |
| `threat_explanation` | TEXT | Gemini's explanation of the threat |
| `user_alerted` | BOOLEAN | Whether user has been alerted |
| `alert_sent_at` | DATETIME | When alert was sent |

**Relationships**:
- Belongs to one `session`
- Has many `incident_frames`
- Has many `gemini_analyses`
- Has many `user_alerts`

**Business Logic**:
- Incident starts when hands are detected
- Incident continues as long as hands are in consecutive frames
- Incident ends when no hands detected in next frame
- After 10 frames, incident is escalated → triggers Gemini analysis
- If Gemini confirms threat → triggers user alert

---

### 3. `incident_frames` - Individual Frames

Stores data for each frame within an incident.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-increment frame ID |
| `incident_id` | INTEGER (FK) | Reference to parent incident |
| `frame_number` | INTEGER | Frame # within this incident (1, 2, 3...) |
| `global_frame_number` | INTEGER | Frame # within entire session |
| `timestamp` | DATETIME | When frame was captured |
| `hands_detected` | BOOLEAN | Whether hands were detected |
| `hand_count` | INTEGER | Number of hands detected (0-2) |
| `hand_confidence` | FLOAT | Maximum confidence score |
| `hand_data` | TEXT (JSON) | Detailed hand detection data (see format below) |
| `image_data` | TEXT (Base64) | Optional: Base64-encoded JPEG image |

**Hand Data Format** (JSON):
```json
[
  {
    "type": "left_hand",
    "confidence": 0.95,
    "bbox": [x1, y1, x2, y2]
  },
  {
    "type": "right_hand",
    "confidence": 0.87,
    "bbox": [x1, y1, x2, y2]
  }
]
```

**Relationships**:
- Belongs to one `incident`

---

### 4. `gemini_analyses` - Gemini AI Analysis

Records Gemini API analysis results for escalated incidents.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-increment analysis ID |
| `incident_id` | INTEGER (FK) | Reference to analyzed incident |
| `analyzed_at` | DATETIME | When analysis was performed |
| `frame_start` | INTEGER | Starting frame number analyzed |
| `frame_end` | INTEGER | Ending frame number analyzed |
| `total_frames_analyzed` | INTEGER | Number of frames sent to Gemini |
| `threat_detected` | BOOLEAN | Whether Gemini detected a threat |
| `confidence` | FLOAT | Gemini's confidence percentage |
| `explanation` | TEXT | Gemini's explanation |
| `raw_response` | TEXT | Full JSON response from Gemini API |
| `api_latency_ms` | INTEGER | API response time in milliseconds |
| `tokens_used` | INTEGER | Number of tokens used |

**Relationships**:
- Belongs to one `incident`

---

### 5. `user_alerts` - User Alerts

Tracks all alerts sent to the user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-increment alert ID |
| `incident_id` | INTEGER (FK) | Reference to incident that triggered alert |
| `alert_type` | VARCHAR(50) | Type of alert (see types below) |
| `sent_at` | DATETIME | When alert was sent |
| `audio_played` | BOOLEAN | Whether audio notification was played |
| `notification_sent` | BOOLEAN | Whether notification was sent |
| `message` | TEXT | Alert message content |
| `acknowledged` | BOOLEAN | Whether user acknowledged the alert |
| `acknowledged_at` | DATETIME | When alert was acknowledged |

**Alert Types**:
- `hand_detected` - First hand detected (incident started)
- `escalation` - Incident reached 10 frames
- `theft_confirmed` - Gemini confirmed potential theft

**Relationships**:
- Belongs to one `incident`

---

## Workflow

### 1. Start Monitoring
```
User clicks "Start Monitoring"
  → Create new Session (is_active=True)
  → Start processing video frames
```

### 2. Hand Detected
```
MediaPipe detects hand
  → Check if active incident exists
  → If no: Create new Incident
  → Create IncidentFrame with detection data
  → Increment incident.total_frames
```

### 3. Continuing Incident
```
Next frame: Hand still detected
  → Add new IncidentFrame to same incident
  → Update max_hand_count, max_confidence
  → Check if total_frames >= 10
    → If yes: Escalate incident
```

### 4. Escalation (10 frames)
```
Incident reaches 10 frames
  → Set incident.is_escalated = True
  → Retrieve last 10 IncidentFrames
  → Send frames to Gemini API
  → Record GeminiAnalysis result
  → If threat detected: Send UserAlert
```

### 5. No Hand Detected
```
Next frame: No hand detected
  → End current incident (is_active=False)
  → Set ended_at timestamp
```

### 6. Stop Monitoring
```
User clicks "Stop Monitoring"
  → End any active incidents
  → End session (is_active=False)
  → Set ended_at timestamp
```

---

## API Endpoints (Suggested)

### Session Management
- `POST /api/sessions/start` - Start new session
- `POST /api/sessions/:id/end` - End session
- `GET /api/sessions/:id` - Get session details
- `GET /api/sessions/active` - Get active session

### Incidents
- `GET /api/incidents` - List all incidents
- `GET /api/incidents/:id` - Get incident details
- `GET /api/incidents/:id/frames` - Get incident frames
- `GET /api/sessions/:session_id/incidents` - Get incidents for session

### Alerts
- `GET /api/alerts` - List all alerts
- `POST /api/alerts/:id/acknowledge` - Acknowledge alert

---

## Migration

To set up the database:

```bash
python migrate_database.py
```

This will:
1. Create `security_monitor.db`
2. Create all tables with proper schema
3. Set up relationships and indexes

---

## Notes

### Image Storage
- `incident_frames.image_data` stores Base64-encoded JPEG images
- **Warning**: This can make the database large
- Consider storing only escalated incident frames
- Alternative: Store images in separate files and reference paths

### Performance
- Add indexes on frequently queried columns:
  - `sessions.is_active`
  - `incidents.session_id`, `incidents.is_active`
  - `incident_frames.incident_id`
  - `gemini_analyses.incident_id`

### Cleanup
- Periodically archive old sessions
- Delete frame images after X days
- Keep only escalated incident data long-term

