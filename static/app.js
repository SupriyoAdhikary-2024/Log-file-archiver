/**
 * Frontend client logic for Log File Error Archiver.
 * Handles drag-and-drop uploads, Chart.js analytics, paginated error browsing, and CSV export.
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentPage = 1;
  const pageSize = 15;
  let currentSeverity = "";
  let currentSearchQuery = "";
  let severityChart = null;

  // DOM Elements
  const alertContainer = document.getElementById("alertContainer");
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const selectedFileName = document.getElementById("selectedFileName");
  const uploadSubmitBtn = document.getElementById("uploadSubmitBtn");
  const clearFileBtn = document.getElementById("clearFileBtn");
  const uploadForm = document.getElementById("uploadForm");

  const statCountCritical = document.getElementById("statCountCritical");
  const statCountError = document.getElementById("statCountError");
  const statCountWarning = document.getElementById("statCountWarning");
  const statCountTotal = document.getElementById("statCountTotal");
  const totalUploadsBadge = document.getElementById("totalUploadsBadge");

  const searchInput = document.getElementById("searchInput");
  const severityFilter = document.getElementById("severityFilter");
  const exportCsvBtn = document.getElementById("exportCsvBtn");

  const errorTableBody = document.getElementById("errorTableBody");
  const tableLoading = document.getElementById("tableLoading");
  const tableEmpty = document.getElementById("tableEmpty");

  const pageRange = document.getElementById("pageRange");
  const totalRecordsCount = document.getElementById("totalRecordsCount");
  const pageIndicator = document.getElementById("pageIndicator");
  const prevPageBtn = document.getElementById("prevPageBtn");
  const nextPageBtn = document.getElementById("nextPageBtn");

  // Notifications
  function showAlert(message, type = "info", durationMs = 5000) {
    const alert = document.createElement("div");
    alert.className = `alert alert-${type}`;

    const textSpan = document.createElement("span");
    textSpan.textContent = message;
    alert.appendChild(textSpan);

    const closeBtn = document.createElement("button");
    closeBtn.className = "alert-close";
    closeBtn.innerHTML = "&times;";
    closeBtn.onclick = () => alert.remove();
    alert.appendChild(closeBtn);

    alertContainer.appendChild(alert);

    if (durationMs > 0) {
      setTimeout(() => {
        if (alert.parentNode) {
          alert.remove();
        }
      }, durationMs);
    }
  }

  // File Handling
  function setSelectedFile(file) {
    if (!file) {
      fileInput.value = "";
      selectedFileName.textContent = "";
      uploadSubmitBtn.disabled = true;
      clearFileBtn.style.display = "none";
      return;
    }

    selectedFileName.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    uploadSubmitBtn.disabled = false;
    clearFileBtn.style.display = "inline-flex";
  }

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      setSelectedFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      setSelectedFile(fileInput.files[0]);
    } else {
      setSelectedFile(null);
    }
  });

  clearFileBtn.addEventListener("click", () => {
    setSelectedFile(null);
  });

  // Upload Form Submit
  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!fileInput.files || fileInput.files.length === 0) {
      showAlert("Please select a file to upload.", "error");
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);

    uploadSubmitBtn.disabled = true;
    uploadSubmitBtn.textContent = "Processing...";

    try {
      const response = await fetch("/api/uploads", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `Upload failed with status ${response.status}`);
      }

      showAlert(
        `Successfully processed "${data.filename}". Processed ${data.total_lines} lines; archived ${data.archived_count} errors (${data.ignored_count} ignored).`,
        "success",
        6000
      );

      setSelectedFile(null);
      await loadStats();
      currentPage = 1;
      await loadErrors();
    } catch (err) {
      showAlert(err.message, "error", 7000);
    } finally {
      uploadSubmitBtn.disabled = false;
      uploadSubmitBtn.textContent = "Upload & Process";
    }
  });

  // Chart.js Setup
  function initOrUpdateChart(statsBySeverity) {
    const ctx = document.getElementById("severityChart").getContext("2d");
    const counts = [
      statsBySeverity.CRITICAL || 0,
      statsBySeverity.ERROR || 0,
      statsBySeverity.WARNING || 0,
    ];
    const total = counts.reduce((a, b) => a + b, 0);

    const chartData = {
      labels: ["Critical", "Error", "Warning"],
      datasets: [
        {
          data: total === 0 ? [1] : counts,
          backgroundColor: total === 0 ? ["#e2e8f0"] : ["#dc2626", "#ea580c", "#d97706"],
          borderWidth: 2,
          borderColor: "#ffffff",
        },
      ],
    };

    if (severityChart) {
      severityChart.data = chartData;
      severityChart.update();
    } else {
      severityChart = new Chart(ctx, {
        type: "doughnut",
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context) => {
                  if (total === 0) return "No errors yet";
                  return ` ${context.label}: ${context.raw}`;
                },
              },
            },
          },
          cutout: "68%",
        },
      });
    }
  }

  // Load Statistics
  async function loadStats() {
    try {
      const response = await fetch("/api/stats");
      if (!response.ok) throw new Error("Failed to load statistics.");
      const data = await response.json();

      statCountCritical.textContent = data.by_severity.CRITICAL || 0;
      statCountError.textContent = data.by_severity.ERROR || 0;
      statCountWarning.textContent = data.by_severity.WARNING || 0;
      statCountTotal.textContent = data.total_errors || 0;
      totalUploadsBadge.textContent = `${data.total_uploads || 0} Upload${data.total_uploads === 1 ? "" : "s"}`;

      initOrUpdateChart(data.by_severity);
    } catch (err) {
      console.error(err);
    }
  }

  // Load Errors Table
  async function loadErrors() {
    tableLoading.style.display = "flex";
    tableEmpty.style.display = "none";
    errorTableBody.innerHTML = "";

    const params = new URLSearchParams({
      page: currentPage,
      page_size: pageSize,
    });

    if (currentSeverity) params.append("severity", currentSeverity);
    if (currentSearchQuery) params.append("q", currentSearchQuery);

    try {
      const response = await fetch(`/api/errors?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch error records.");
      const data = await response.json();

      tableLoading.style.display = "none";

      if (!data.records || data.records.length === 0) {
        tableEmpty.style.display = "flex";
        pageRange.textContent = "0 - 0";
        totalRecordsCount.textContent = "0";
        pageIndicator.textContent = "Page 1 of 1";
        prevPageBtn.disabled = true;
        nextPageBtn.disabled = true;
        return;
      }

      // Populate Table Rows safely using DOM nodes
      data.records.forEach((rec) => {
        const tr = document.createElement("tr");

        // Timestamp
        const tdTime = document.createElement("td");
        tdTime.className = "timestamp-cell";
        tdTime.textContent = rec.occurred_at || "";
        tr.appendChild(tdTime);

        // Severity Badge
        const tdSev = document.createElement("td");
        const badge = document.createElement("span");
        const sevClass = (rec.severity || "").toLowerCase();
        badge.className = `badge badge-${sevClass}`;
        badge.textContent = rec.severity || "";
        tdSev.appendChild(badge);
        tr.appendChild(tdSev);

        // Message
        const tdMsg = document.createElement("td");
        tdMsg.className = "message-cell";
        tdMsg.textContent = rec.message || "";
        tr.appendChild(tdMsg);

        // Source File
        const tdFile = document.createElement("td");
        tdFile.className = "source-cell";
        tdFile.title = rec.source_file || "";
        tdFile.textContent = rec.source_file || "";
        tr.appendChild(tdFile);

        // Line #
        const tdLine = document.createElement("td");
        tdLine.className = "line-cell";
        tdLine.textContent = rec.line_number ?? "";
        tr.appendChild(tdLine);

        errorTableBody.appendChild(tr);
      });

      // Update Pagination info
      const startIdx = (data.page - 1) * data.page_size + 1;
      const endIdx = Math.min(startIdx + data.records.length - 1, data.total_records);
      pageRange.textContent = `${startIdx} - ${endIdx}`;
      totalRecordsCount.textContent = data.total_records;
      pageIndicator.textContent = `Page ${data.page} of ${data.total_pages}`;

      prevPageBtn.disabled = data.page <= 1;
      nextPageBtn.disabled = data.page >= data.total_pages;
    } catch (err) {
      tableLoading.style.display = "none";
      showAlert("Error loading records: " + err.message, "error");
    }
  }

  // Filter & Search Handlers
  severityFilter.addEventListener("change", () => {
    currentSeverity = severityFilter.value;
    currentPage = 1;
    loadErrors();
  });

  // Clicking Stat Pills filters by severity
  document.querySelectorAll(".stat-pill[data-severity]").forEach((pill) => {
    pill.addEventListener("click", () => {
      const targetSeverity = pill.getAttribute("data-severity");
      severityFilter.value = targetSeverity;
      currentSeverity = targetSeverity;
      currentPage = 1;
      loadErrors();
    });
  });

  let debounceTimer = null;
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      currentSearchQuery = searchInput.value.trim();
      currentPage = 1;
      loadErrors();
    }, 300);
  });

  // Pagination Handlers
  prevPageBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      loadErrors();
    }
  });

  nextPageBtn.addEventListener("click", () => {
    currentPage++;
    loadErrors();
  });

  // CSV Export
  exportCsvBtn.addEventListener("click", () => {
    const params = new URLSearchParams();
    if (currentSeverity) params.append("severity", currentSeverity);
    if (currentSearchQuery) params.append("q", currentSearchQuery);
    window.location.href = `/api/export?${params.toString()}`;
  });

  // Initial Load
  loadStats();
  loadErrors();
});
