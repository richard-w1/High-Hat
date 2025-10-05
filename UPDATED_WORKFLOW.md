# 🔄 Updated Incident Workflow

## Key Changes

Based on your clarification, I've updated the incident tracking logic:

---

## 📋 New Workflow

### **Incident Lifecycle:**

```
1. Hand detected → CREATE INCIDENT

2. Hand continues → ADD FRAMES to incident
   ├─ Frame 10 → Send batch #1 to Gemini
   ├─ Frame 20 → Send batch #2 to Gemini  
   ├─ Frame 30 → Send batch #3 to Gemini
   └─ ...continues every 10 frames

3. Incident ENDS when:
   ⛔ No hands detected in next frame, OR
   ✅ Gemini returns threat_detected=True

4. If threat detected:
   🚨 Mark entire incident as "HIGH THREAT"
   🔊 Send alert to user
   🛑 END INCIDENT immediately
```

---

## 🎯 Detailed Flow

### **Phase 1: Incident Creation**
```python
Frame #1: Hand detected
  ↓
if no active incident:
    IncidentManager.create_incident(session_id)
    current_incident_id = incident.id
    print("🆕 NEW INCIDENT #X")

Add frame to incident:
    IncidentManager.add_frame_to_incident(...)
    incident.total_frames = 1
```

### **Phase 2: Continuous Analysis (Every 10 Frames)**
```python
Frame #10: (Batch #1)
  ↓
if incident.total_frames % 10 == 0:
    print("⚠️  BATCH ANALYSIS #1 at 10 frames")
    
    Get last 10 frames
    Send to Gemini
    Record GeminiAnalysis
    
    if Gemini says threat AND confidence > 60:
        ✅ Mark incident as HIGH THREAT
        🔊 Send alert
        🛑 END INCIDENT
        current_incident_id = None
    else:
        ✅ No threat detected
        📝 Incident continues...

Frame #20: (Batch #2)
  ↓
if incident.total_frames % 10 == 0:
    print("⚠️  BATCH ANALYSIS #2 at 20 frames")
    
    [Same process repeats]
    
    if threat:
        END INCIDENT
    else:
        Incident continues...

Frame #30, #40, #50... (Continues indefinitely until threat or no hand)
```

### **Phase 3: Incident Termination**

**Option A: No Hands Detected**
```python
Frame #N: No hand detected
  ↓
if current_incident_id:
    IncidentManager.end_incident(current_incident_id)
    print("✅ INCIDENT ENDED - No hands detected")
    current_incident_id = None
```

**Option B: Threat Confirmed**
```python
Gemini returns: threat_detected=True, confidence=85%
  ↓
# Mark incident as high threat
incident.threat_detected = True
incident.threat_confidence = 85
incident.threat_explanation = "Hand reaching toward backpack"
db.session.commit()

# Send alert
AlertManager.send_alert(...)
audio_notifier.send_alert(...)

# End incident
IncidentManager.end_incident(current_incident_id)
print("🛑 INCIDENT ENDED - Threat confirmed")
current_incident_id = None
```

---

## 📊 Example Scenario

**Scenario: Someone hovering near backpack**

```
Frame #1-9: Hand detected
  → Incident #1 created
  → Frames added

Frame #10: BATCH #1
  → Send 10 frames to Gemini
  → Gemini: "No threat, just someone nearby" (Confidence: 30%)
  → ✅ Incident continues

Frame #11-19: Hand still detected
  → More frames added

Frame #20: BATCH #2
  → Send frames 11-20 to Gemini
  → Gemini: "Hand reaching toward bag" (Confidence: 75%)
  → 🚨 THREAT CONFIRMED!
  → Mark incident as HIGH THREAT
  → Send alert to user
  → 🛑 END INCIDENT #1

Frame #21: (No active incident anymore)
  → If hand still detected → Create NEW incident #2
```

---

## 🗄️ Database Impact

### **Incident Record:**
```sql
-- Normal incident (no threat)
INSERT INTO incidents (
    id, session_id, started_at, ended_at,
    total_frames, is_escalated,
    threat_detected, threat_confidence, threat_explanation
) VALUES (
    1, 1, '2025-10-05 14:23:10', '2025-10-05 14:23:18',
    25, true,
    false, null, null
);

-- High threat incident
INSERT INTO incidents (
    id, session_id, started_at, ended_at,
    total_frames, is_escalated,
    threat_detected, threat_confidence, threat_explanation
) VALUES (
    2, 1, '2025-10-05 14:25:30', '2025-10-05 14:25:52',
    45, true,
    true, 85.5, 'Hand reaching toward backpack, potential theft attempt'
);
```

### **Multiple Gemini Analyses Per Incident:**
```sql
-- Incident #2 had 3 batch analyses before threat was confirmed

-- Batch #1 (frames 1-10)
INSERT INTO gemini_analyses VALUES (
    1, 2, '2025-10-05 14:25:35',
    1, 10, 10,
    false, 25.0, 'Person nearby, no suspicious behavior'
);

-- Batch #2 (frames 11-20)
INSERT INTO gemini_analyses VALUES (
    2, 2, '2025-10-05 14:25:42',
    11, 20, 10,
    false, 45.0, 'Hand near bag but no clear threat'
);

-- Batch #3 (frames 21-30)
INSERT INTO gemini_analyses VALUES (
    3, 2, '2025-10-05 14:25:49',
    21, 30, 10,
    true, 85.5, 'Hand reaching into bag, potential theft'
);
-- After this → Incident ended
```

---

## ✨ Key Features

### ✅ Continuous Monitoring
- Incident doesn't end after first 10 frames
- Keeps analyzing every 10 frames
- Can run indefinitely (10, 20, 30, 40, 50+ frames)

### ✅ Early Threat Detection
- As soon as Gemini confirms threat → Incident ends
- No need to wait for hands to disappear
- Faster alert response time

### ✅ High Threat Labeling
- `incident.threat_detected = True` marks the entire incident
- Easy to query high-threat incidents from database
- Dashboard can highlight critical incidents

### ✅ Multiple Analyses
- One incident can have many `GeminiAnalysis` records
- Track how threat perception changed over time
- Useful for debugging and analysis

---

## 🎯 Code Changes

### **Modified Section:**
`real_ai_app.py` → `detection_processing_worker()` → Lines 184-258

**Key Changes:**
1. ✅ Fixed typo: `is_threat` → `is_theft`
2. ✅ Changed condition: `if should_escalate` → `if should_escalate OR (total_frames % 10 == 0)`
3. ✅ Added batch number tracking
4. ✅ Added incident termination when threat detected
5. ✅ Added incident threat field updates
6. ✅ Added continuation message when no threat

---

## 📝 Testing Checklist

To verify the new workflow:

1. **Start monitoring** → Session created ✅

2. **Wave hand** → Incident created ✅

3. **Keep hand visible for 10 frames** → Batch #1 sent to Gemini ✅

4. **If no threat detected** → Check logs:
   ```
   ✅ No threat in batch #1 (Confidence: 30%)
      Incident continues - will analyze again at frame 20...
   ```

5. **Keep hand visible to frame 20** → Batch #2 sent to Gemini ✅

6. **If threat detected** → Check logs:
   ```
   🚨 THREAT CONFIRMED! Ending incident and sending alert...
   🛑 INCIDENT #1 ENDED - Threat confirmed by Gemini
   ```

7. **Check database**:
   ```sql
   SELECT id, total_frames, threat_detected, threat_confidence 
   FROM incidents;
   
   SELECT incident_id, threat_detected, confidence, frame_start, frame_end
   FROM gemini_analyses
   ORDER BY analyzed_at;
   ```

---

## 🚀 Ready to Test!

The updated workflow is now live. The system will:
- ✅ Analyze every 10 frames
- ✅ Continue indefinitely until threat or no hand
- ✅ End incident immediately when threat confirmed
- ✅ Mark high-threat incidents for easy querying

**Start the server and test with your Pi camera!** 🎯

