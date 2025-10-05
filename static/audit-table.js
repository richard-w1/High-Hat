// Modern Audit Table with Advanced Features
class AuditTable {
  constructor() {
    this.data = [];
    this.filteredData = [];
    this.currentPage = 1;
    this.itemsPerPage = 10;
    this.sortColumn = 'timestamp';
    this.sortDirection = 'desc';
    
    this.init();
  }

  init() {
    this.loadData();
    this.setupEventListeners();
    this.renderTable();
  }

  loadData() {
    // Start with empty data - will be populated by real monitoring data
    this.data = [];
    this.filteredData = [...this.data];
  }

  setupEventListeners() {
    // Filter event listeners
    document.getElementById('statusFilter')?.addEventListener('change', () => this.filterTable());
    document.getElementById('confidenceFilter')?.addEventListener('change', () => this.filterTable());
    document.getElementById('dateFilter')?.addEventListener('change', () => this.filterTable());
    
    // Pagination event listeners
    document.getElementById('prevBtn')?.addEventListener('click', () => this.previousPage());
    document.getElementById('nextBtn')?.addEventListener('click', () => this.nextPage());
    
    // Export functionality
    window.exportTable = () => this.exportCSV();
    window.refreshTable = () => this.refreshTable();
    window.filterTable = () => this.filterTable();
    window.previousPage = () => this.previousPage();
    window.nextPage = () => this.nextPage();
  }

  filterTable() {
    const statusFilter = document.getElementById('statusFilter')?.value;
    const confidenceFilter = document.getElementById('confidenceFilter')?.value;
    const dateFilter = document.getElementById('dateFilter')?.value;
    
    this.filteredData = this.data.filter(item => {
      let matches = true;
      
      // Status filter
      if (statusFilter && item.status !== statusFilter) {
        matches = false;
      }
      
      // Confidence filter
      if (confidenceFilter) {
        const confidence = item.confidence;
        if (confidenceFilter === 'high' && confidence < 80) matches = false;
        if (confidenceFilter === 'medium' && (confidence < 60 || confidence >= 80)) matches = false;
        if (confidenceFilter === 'low' && confidence >= 60) matches = false;
      }
      
      // Date filter
      if (dateFilter) {
        const itemDate = item.timestamp.toISOString().split('T')[0];
        if (itemDate !== dateFilter) matches = false;
      }
      
      return matches;
    });
    
    this.currentPage = 1;
    this.renderTable();
  }

  sortTable(column) {
    if (this.sortColumn === column) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = column;
      this.sortDirection = 'desc';
    }
    
    this.filteredData.sort((a, b) => {
      let aVal = a[column];
      let bVal = b[column];
      
      if (column === 'timestamp') {
        aVal = new Date(aVal);
        bVal = new Date(bVal);
      }
      
      if (this.sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });
    
    this.renderTable();
  }

  renderTable() {
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;
    
    const startIndex = (this.currentPage - 1) * this.itemsPerPage;
    const endIndex = startIndex + this.itemsPerPage;
    const pageData = this.filteredData.slice(startIndex, endIndex);
    
    if (pageData.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 2rem; color: var(--muted-foreground);">
            <div style="display: flex; flex-direction: column; align-items: center; gap: 1rem;">
              <span class="material-icons" style="font-size: 3rem; opacity: 0.5;">table_chart</span>
              <div style="font-size: 1.2rem; font-weight: 600;">No audit data yet</div>
              <div>Start monitoring to begin collecting security audit logs</div>
            </div>
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = pageData.map(item => `
        <tr>
          <td>${this.formatTimestamp(item.timestamp)}</td>
          <td>#${item.photoNumber}</td>
          <td>
            <span class="status ${item.handsDetected ? 'detected' : 'not-detected'}">
              ${item.handsDetected ? 'Yes' : 'No'}
            </span>
            ${item.handCount > 0 ? ` (${item.handCount})` : ''}
          </td>
          <td>
            <span class="confidence-${this.getConfidenceClass(item.confidence)}">
              ${item.confidence.toFixed(1)}%
            </span>
          </td>
          <td title="${item.explanation}">${item.theftAnalysis}</td>
          <td>
            <span class="status ${item.status}">
              ${this.getStatusText(item.status)}
            </span>
          </td>
          <td>
            <button class="btn table-action-btn" onclick="viewDetails(${item.id})">View</button>
            <button class="btn table-action-btn danger" onclick="deleteRecord(${item.id})">Delete</button>
          </td>
        </tr>
      `).join('');
    }
    
    this.updatePagination();
  }

  updatePagination() {
    const totalPages = Math.ceil(this.filteredData.length / this.itemsPerPage);
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageInfo = document.getElementById('pageInfo');
    
    if (prevBtn) prevBtn.disabled = this.currentPage === 1;
    if (nextBtn) nextBtn.disabled = this.currentPage === totalPages;
    if (pageInfo) pageInfo.textContent = `Page ${this.currentPage} of ${totalPages}`;
  }

  previousPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
      this.renderTable();
    }
  }

  nextPage() {
    const totalPages = Math.ceil(this.filteredData.length / this.itemsPerPage);
    if (this.currentPage < totalPages) {
      this.currentPage++;
      this.renderTable();
    }
  }

  refreshTable() {
    this.loadData();
    this.filterTable();
  }

  // Add new audit entry from real monitoring data
  addAuditEntry(data) {
    const newEntry = {
      id: Date.now(), // Simple ID generation
      timestamp: new Date(),
      photoNumber: data.photo_number || 0,
      handsDetected: data.hands_detected || false,
      handCount: data.hand_count || 0,
      confidence: data.hand_confidence || 0,
      theftAnalysis: data.theft_analysis || 'No analysis',
      status: data.hands_detected ? 'detected' : 'not-detected',
      explanation: data.explanation || 'No details available'
    };
    
    this.data.unshift(newEntry); // Add to beginning
    this.filteredData = [...this.data];
    this.currentPage = 1; // Reset to first page
    this.renderTable();
  }

  exportCSV() {
    const headers = ['Timestamp', 'Photo #', 'Hands Detected', 'Hand Count', 'Confidence', 'Theft Analysis', 'Status', 'Explanation'];
    const csvContent = [
      headers.join(','),
      ...this.filteredData.map(item => [
        this.formatTimestamp(item.timestamp),
        item.photoNumber,
        item.handsDetected ? 'Yes' : 'No',
        item.handCount,
        item.confidence.toFixed(1),
        `"${item.theftAnalysis}"`,
        this.getStatusText(item.status),
        `"${item.explanation}"`
      ].join(','))
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-log-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  }

  formatTimestamp(timestamp) {
    return new Date(timestamp).toLocaleString();
  }

  getConfidenceClass(confidence) {
    if (confidence >= 80) return 'high';
    if (confidence >= 60) return 'medium';
    return 'low';
  }

  getStatusText(status) {
    const statusMap = {
      'detected': 'Detected',
      'not-detected': 'Not Detected',
      'monitoring': 'Monitoring'
    };
    return statusMap[status] || status;
  }
}

// Global functions for table actions
window.viewDetails = function(id) {
  alert(`Viewing details for record ${id}`);
};

window.deleteRecord = function(id) {
  if (confirm('Are you sure you want to delete this record?')) {
    alert(`Deleting record ${id}`);
  }
};

// Global audit table instance
let auditTableInstance = null;

// Initialize the audit table when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  auditTableInstance = new AuditTable();
});

// Global function to add audit entries
window.addAuditEntry = function(data) {
  if (auditTableInstance) {
    auditTableInstance.addAuditEntry(data);
  }
};
