// Chart.js Configuration
Chart.defaults.color = '#a0aec0';
Chart.defaults.borderColor = '#2d3748';
Chart.defaults.font.family = 'Roboto Mono';

let charts = {};

function initCharts() {
  // Detection Timeline Chart
  const detectionCtx = document.getElementById('detectionTimelineChart');
  charts.detectionTimeline = new Chart(detectionCtx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Incidents',
        data: [],
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.4,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } }
      }
    }
  });

  // Threat Distribution Chart (Doughnut)
  const threatCtx = document.getElementById('threatDistributionChart');
  charts.threatDistribution = new Chart(threatCtx, {
    type: 'doughnut',
    data: {
      labels: ['Threats Detected', 'Safe Incidents', 'Pending Analysis'],
      datasets: [{
        data: [0, 0, 0],
        backgroundColor: [
          'rgba(239, 68, 68, 0.8)',
          'rgba(34, 197, 94, 0.8)',
          'rgba(251, 191, 36, 0.8)'
        ],
        borderColor: [
          'rgb(239, 68, 68)',
          'rgb(34, 197, 94)',
          'rgb(251, 191, 36)'
        ],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' }
      }
    }
  });

  // Confidence Distribution Chart (Bar)
  const confidenceCtx = document.getElementById('confidenceDistributionChart');
  charts.confidenceDistribution = new Chart(confidenceCtx, {
    type: 'bar',
    data: {
      labels: ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%'],
      datasets: [{
        label: 'Detection Count',
        data: [0, 0, 0, 0, 0],
        backgroundColor: 'rgba(59, 130, 246, 0.6)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } }
      }
    }
  });

  // Session Duration Chart (Line)
  const durationCtx = document.getElementById('sessionDurationChart');
  charts.sessionDuration = new Chart(durationCtx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Duration (seconds)',
        data: [],
        borderColor: 'rgb(168, 85, 247)',
        backgroundColor: 'rgba(168, 85, 247, 0.1)',
        tension: 0.4,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true }
      }
    }
  });

  // Incidents per Session Chart (Bar)
  const incidentsCtx = document.getElementById('incidentsPerSessionChart');
  charts.incidentsPerSession = new Chart(incidentsCtx, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [{
        label: 'Incidents',
        data: [],
        backgroundColor: 'rgba(251, 146, 60, 0.6)',
        borderColor: 'rgb(251, 146, 60)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } }
      }
    }
  });

  // Escalation Rate Chart (Line)
  const escalationCtx = document.getElementById('escalationRateChart');
  charts.escalationRate = new Chart(escalationCtx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Escalations',
        data: [],
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.4,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 } }
      }
    }
  });
}

async function updateCharts() {
  try {
    const response = await fetch('/api/sessions');
    const data = await response.json();
    const sessions = data.sessions || [];
    
    if (sessions.length === 0) {
      console.log('No sessions available for charts');
      return;
    }
    
    // Sort by date
    sessions.sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
    
    // Last 10 sessions for timeline
    const recentSessions = sessions.slice(-10);
    
    // Detection Timeline
    charts.detectionTimeline.data.labels = recentSessions.map(s => 
      new Date(s.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    );
    charts.detectionTimeline.data.datasets[0].data = recentSessions.map(s => s.total_incidents || 0);
    charts.detectionTimeline.update();
    
    // Threat Distribution
    let threatsDetected = 0;
    let safeIncidents = 0;
    let pendingAnalysis = 0;
    
    for (const session of sessions) {
      try {
        const sessionResponse = await fetch(`/api/sessions/${session.id}`);
        const sessionData = await sessionResponse.json();
        const incidents = sessionData.session.incidents || [];
        
        for (const incident of incidents) {
          if (incident.threat_detected) {
            threatsDetected++;
          } else if (incident.gemini_analyzed) {
            safeIncidents++;
          } else {
            pendingAnalysis++;
          }
        }
      } catch (e) {
        // Skip if error fetching session details
      }
    }
    
    charts.threatDistribution.data.datasets[0].data = [threatsDetected, safeIncidents, pendingAnalysis];
    charts.threatDistribution.update();
    
    // Confidence Distribution
    const confidenceBuckets = [0, 0, 0, 0, 0];
    for (const session of sessions) {
      try {
        const sessionResponse = await fetch(`/api/sessions/${session.id}`);
        const sessionData = await sessionResponse.json();
        const incidents = sessionData.session.incidents || [];
        
        for (const incident of incidents) {
          const conf = incident.max_confidence * 100;
          if (conf < 20) confidenceBuckets[0]++;
          else if (conf < 40) confidenceBuckets[1]++;
          else if (conf < 60) confidenceBuckets[2]++;
          else if (conf < 80) confidenceBuckets[3]++;
          else confidenceBuckets[4]++;
        }
      } catch (e) {
        // Skip if error
      }
    }
    charts.confidenceDistribution.data.datasets[0].data = confidenceBuckets;
    charts.confidenceDistribution.update();
    
    // Session Duration
    charts.sessionDuration.data.labels = recentSessions.map(s => 
      `#${s.id}`
    );
    charts.sessionDuration.data.datasets[0].data = recentSessions.map(s => s.duration_seconds || 0);
    charts.sessionDuration.update();
    
    // Incidents per Session
    charts.incidentsPerSession.data.labels = recentSessions.map(s => `#${s.id}`);
    charts.incidentsPerSession.data.datasets[0].data = recentSessions.map(s => s.total_incidents || 0);
    charts.incidentsPerSession.update();
    
    // Escalation Rate
    charts.escalationRate.data.labels = recentSessions.map(s => `#${s.id}`);
    charts.escalationRate.data.datasets[0].data = recentSessions.map(s => s.total_escalations || 0);
    charts.escalationRate.update();
    
    // Update summary statistics
    updateSummaryStats(sessions, threatsDetected);
    
  } catch (error) {
    console.error('Error updating charts:', error);
  }
}

async function updateSummaryStats(sessions, threatsDetected) {
  document.getElementById('totalSessions').textContent = sessions.length;
  
  const totalIncidents = sessions.reduce((sum, s) => sum + (s.total_incidents || 0), 0);
  document.getElementById('totalIncidents').textContent = totalIncidents;
  
  document.getElementById('totalThreats').textContent = threatsDetected;
  
  const avgDuration = sessions.length > 0 ? 
    sessions.reduce((sum, s) => sum + (s.duration_seconds || 0), 0) / sessions.length : 0;
  const avgDurationText = avgDuration > 60 ? 
    `${Math.floor(avgDuration / 60)}m` : `${Math.floor(avgDuration)}s`;
  document.getElementById('avgDuration').textContent = avgDurationText;
  
  const avgFrames = sessions.length > 0 ?
    Math.round(sessions.reduce((sum, s) => sum + (s.total_frames || 0), 0) / sessions.length) : 0;
  document.getElementById('avgFrames').textContent = avgFrames;
  
  const detectionRate = totalIncidents > 0 ? 
    Math.round((threatsDetected / totalIncidents) * 100) : 0;
  document.getElementById('detectionRate').textContent = `${detectionRate}%`;
}

// Initialize charts on page load
document.addEventListener('DOMContentLoaded', function() {
  initCharts();
  updateCharts();
  
  // Update charts every 10 seconds
  setInterval(updateCharts, 10000);
});

