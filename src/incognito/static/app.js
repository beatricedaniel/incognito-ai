"use strict";

var State = {
  IDLE: "idle",
  UPLOADING: "uploading",
  PROCESSING: "processing",
  REVIEWING: "reviewing",
  REDACTING: "redacting",
  RECOVERING: "recovering",
  COMPLETE: "complete",
  ERROR: "error",
};

var FUNNY_MESSAGES = [
  "Teaching AI to forget names\u2026",
  "Putting tiny masks on every letter\u2026",
  "Shredding digital fingerprints\u2026",
  "Convincing pixels to look the other way\u2026",
  "Deploying army of redaction robots\u2026",
  "Asking Gemma to unsee things\u2026",
  "Alphabetizing your secrets\u2026",
  "Training black bars for duty\u2026",
  "Polishing the invisibility cloak\u2026",
  "Whispering \u2018you saw nothing\u2019 to the PDF\u2026"
];

var currentState = State.IDLE;
var ollamaReady = false;
var sessionId = null;
var eventSource = null;
var dragEnterCount = 0;
var activeTab = "anonymise";
var funnyInterval = null;
var funnyIndex = 0;

var dropZone = document.getElementById("drop-zone");
var dropLabel = document.getElementById("drop-zone-label");
var dropHint = document.querySelector(".drop-zone-hint");
var fileInput = document.getElementById("file-input");
var statusBar = document.getElementById("status-bar");
var errorEl = document.getElementById("error-message");
var reviewPanel = document.getElementById("review-panel");
var redactButton = document.getElementById("redact-button");
var completePanel = document.getElementById("complete-panel");
var completeMessage = document.getElementById("complete-message");
var downloadLink = document.getElementById("download-link");
var resetButton = document.getElementById("reset-button");
var tabBar = document.getElementById("tab-bar");
var tabAnonymise = document.getElementById("tab-anonymise");
var tabRecover = document.getElementById("tab-recover");
var panelRecover = document.getElementById("panel-recover");
var processingStage = document.getElementById("processing-stage");
var processingFunny = document.getElementById("processing-funny");
var processingWarning = document.getElementById("processing-warning");

// — Processing messages —

function warnBeforeUnload(e) { e.preventDefault(); }

function startFunnyMessages() {
  funnyIndex = 0;
  processingFunny.textContent = FUNNY_MESSAGES[0];
  funnyInterval = setInterval(function () {
    funnyIndex = (funnyIndex + 1) % FUNNY_MESSAGES.length;
    processingFunny.textContent = FUNNY_MESSAGES[funnyIndex];
  }, 4000);
}

function stopFunnyMessages() {
  if (funnyInterval) { clearInterval(funnyInterval); funnyInterval = null; }
}

function showProcessingUI() {
  dropLabel.hidden = true;
  dropHint.hidden = true;
  processingStage.hidden = false;
  processingFunny.hidden = false;
  processingWarning.hidden = false;
  dropZone.classList.remove("drop-zone--disabled");
  dropZone.classList.add("drop-zone--processing");
  startFunnyMessages();
  window.addEventListener("beforeunload", warnBeforeUnload);
}

function hideProcessingUI() {
  processingStage.hidden = true;
  processingFunny.hidden = true;
  processingWarning.hidden = true;
  dropZone.classList.remove("drop-zone--processing");
  dropLabel.hidden = false;
  stopFunnyMessages();
  window.removeEventListener("beforeunload", warnBeforeUnload);
}

// — State machine —

function transition(next) {
  currentState = next;
  render();
}

function render() {
  var reviewing = currentState === State.REVIEWING || currentState === State.REDACTING;
  var recovering = currentState === State.RECOVERING;
  var showTabs = currentState === State.IDLE || currentState === State.ERROR || recovering;

  errorEl.hidden = currentState !== State.ERROR;
  reviewPanel.hidden = !reviewing;
  completePanel.hidden = currentState !== State.COMPLETE;
  tabBar.hidden = !showTabs;

  dropZone.hidden = reviewing || currentState === State.COMPLETE || recovering
    || activeTab !== "anonymise";
  panelRecover.hidden = activeTab !== "recover"
    || !(currentState === State.IDLE || currentState === State.ERROR || recovering);

  if (currentState === State.PROCESSING) {
    showProcessingUI();
  } else {
    hideProcessingUI();
    if (currentState === State.IDLE) {
      dropLabel.textContent = "Drop a PDF here";
      dropHint.hidden = false;
      dropZone.classList.remove("drop-zone--disabled");
    } else if (currentState === State.UPLOADING) {
      dropLabel.textContent = "Uploading\u2026";
      dropHint.hidden = true;
      dropZone.classList.add("drop-zone--disabled");
    } else if (currentState === State.ERROR) {
      dropLabel.textContent = "Drop a PDF here";
      dropHint.hidden = false;
      dropZone.classList.remove("drop-zone--disabled");
    }
  }

  redactButton.disabled = currentState !== State.REVIEWING ||
    (window.ModeToggle && !window.ModeToggle.isValid());
  if (currentState === State.REDACTING) {
    redactButton.textContent = "Anonymizing\u2026";
    redactButton.classList.add("redacting");
  } else {
    redactButton.textContent = "Anonymize";
    redactButton.classList.remove("redacting");
  }

  document.querySelector("main").classList.toggle(
    "reviewing--active", reviewing
  );

  if (currentState === State.REVIEWING) {
    if (window.ModeToggle) window.ModeToggle.init(function () {
      redactButton.disabled = currentState !== State.REVIEWING || !window.ModeToggle.isValid();
    });
    if (window.PdfPreview) window.PdfPreview.init(sessionId);
    if (window.DetectionSidebar) window.DetectionSidebar.init(sessionId);
  } else if (currentState !== State.REDACTING) {
    if (window.ModeToggle) window.ModeToggle.destroy();
    if (window.PdfPreview) window.PdfPreview.destroy();
    if (window.DetectionSidebar) window.DetectionSidebar.destroy();
  }
}

// — Status polling —

function renderStatus() {
  var localBadge = '<span class="badge badge-local">100% local \u2014 no data leaves your machine</span>';

  if (ollamaReady) {
    statusBar.innerHTML =
      '<span class="badge badge-ready">Ready</span>' + localBadge;
  } else {
    statusBar.innerHTML =
      '<p class="status-warning">Please start Ollama with Gemma 4 E4B</p>' + localBadge;
  }
}

function pollStatus() {
  fetch("/api/status")
    .then(function (resp) { return resp.json(); })
    .then(function (data) { ollamaReady = data.ollama_ready; })
    .catch(function () { ollamaReady = false; })
    .finally(renderStatus);
}

pollStatus();
setInterval(pollStatus, 5000);

// — Drop zone —

dropZone.addEventListener("click", function () {
  if (currentState === State.IDLE) fileInput.click();
});

dropZone.addEventListener("keydown", function (e) {
  if ((e.key === "Enter" || e.key === " ") && currentState === State.IDLE) {
    e.preventDefault();
    fileInput.click();
  }
});

dropZone.addEventListener("dragenter", function (e) {
  e.preventDefault();
  dragEnterCount++;
  dropZone.classList.add("drop-zone--drag-over");
});

dropZone.addEventListener("dragover", function (e) {
  e.preventDefault();
});

dropZone.addEventListener("dragleave", function () {
  dragEnterCount--;
  if (dragEnterCount <= 0) {
    dragEnterCount = 0;
    dropZone.classList.remove("drop-zone--drag-over");
  }
});

dropZone.addEventListener("drop", function (e) {
  e.preventDefault();
  dragEnterCount = 0;
  dropZone.classList.remove("drop-zone--drag-over");
  handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener("change", function () {
  handleFiles(fileInput.files);
  fileInput.value = "";
});

// — Upload —

function isPdf(file) {
  if (file.type === "application/pdf") return true;
  if (!file.type && file.name.toLowerCase().endsWith(".pdf")) return true;
  return false;
}

function handleFiles(files) {
  if (currentState !== State.IDLE) return;
  if (!files || files.length === 0) return;

  var file = files[0];
  if (file.name.toLowerCase().endsWith(".pdfkey")) {
    showError("This .pdfkey file is for recovery. Use the \u201cRecover\u201d tab.");
    return;
  }
  if (!isPdf(file)) {
    showError("Please select a PDF file.");
    return;
  }

  transition(State.UPLOADING);

  var form = new FormData();
  form.append("file", file);

  fetch("/api/upload", { method: "POST", body: form })
    .then(function (resp) {
      if (!resp.ok) return resp.json().then(function (err) { throw err; });
      return resp.json();
    })
    .then(function (data) {
      sessionId = data.session_id;
      connectEvents(data.events_url);
    })
    .catch(function (err) {
      showError(err.detail || "Upload failed.");
    });
}

// — SSE —

function connectEvents(url) {
  transition(State.PROCESSING);
  processingStage.textContent = "Processing\u2026";

  var source = new EventSource(url);
  eventSource = source;

  source.addEventListener("stage_update", function (e) {
    var data = JSON.parse(e.data);
    processingStage.textContent = data.message;
  });

  source.addEventListener("pipeline_complete", function () {
    source.close();
    eventSource = null;
    transition(State.REVIEWING);
  });

  source.addEventListener("pipeline_error", function (e) {
    source.close();
    eventSource = null;
    var data = JSON.parse(e.data);
    showError(data.detail || "Processing error.");
  });

  source.onerror = function () {
    source.close();
    eventSource = null;
    if (currentState === State.PROCESSING) {
      showError("Connection lost.");
    }
  };
}

window.addEventListener("beforeunload", function () {
  if (eventSource) eventSource.close();
});

// — Redact —

redactButton.addEventListener("click", function () {
  if (currentState !== State.REVIEWING) return;
  transition(State.REDACTING);

  var mode = window.ModeToggle ? window.ModeToggle.getMode() : "irreversible";
  var payload = {mode: mode};
  if (mode === "reversible") payload.passphrase = window.ModeToggle.getPassphrase();

  fetch("/api/redact/" + sessionId, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  })
    .then(function (resp) {
      if (!resp.ok) return resp.json().then(function (err) { throw err; });
      var cd = resp.headers.get("content-disposition") || "";
      var match = cd.match(/filename="?([^"]+)"?/);
      var filename = match ? match[1] : "redacted.pdf";
      return resp.blob().then(function (blob) {
        return {blob: blob, filename: filename};
      });
    })
    .then(function (result) {
      var url = URL.createObjectURL(result.blob);
      downloadLink.href = url;
      downloadLink.download = result.filename;
      downloadLink.textContent = result.filename;
      downloadLink.hidden = false;
      completeMessage.textContent = "Anonymization complete.";
      transition(State.COMPLETE);
      downloadLink.click();
    })
    .catch(function (err) {
      showError(err.detail || "Anonymization failed.");
    });
});

// — Reset —

resetButton.addEventListener("click", function () {
  if (downloadLink.href) URL.revokeObjectURL(downloadLink.href);
  downloadLink.hidden = true;
  sessionId = null;
  if (window.Recovery) window.Recovery.destroy();
  activeTab = "anonymise";
  applyTabUI();
  transition(State.IDLE);
});

// — Error —

function showError(message) {
  transition(State.ERROR);
  errorEl.textContent = message;
  errorEl.hidden = false;
}

// — Tabs —

var recoveryCallbacks = {
  onRecovering: function () { transition(State.RECOVERING); },
  onError: function (msg) { showError(msg); },
  onComplete: function (url, filename) {
    downloadLink.href = url;
    downloadLink.download = filename;
    downloadLink.textContent = filename;
    downloadLink.hidden = false;
    completeMessage.textContent = "Recovery complete.";
    transition(State.COMPLETE);
  }
};

function applyTabUI() {
  var isAnonymise = activeTab === "anonymise";
  tabAnonymise.setAttribute("aria-selected", isAnonymise ? "true" : "false");
  tabAnonymise.classList.toggle("tab--active", isAnonymise);
  tabAnonymise.tabIndex = isAnonymise ? 0 : -1;
  tabRecover.setAttribute("aria-selected", !isAnonymise ? "true" : "false");
  tabRecover.classList.toggle("tab--active", !isAnonymise);
  tabRecover.tabIndex = !isAnonymise ? 0 : -1;
}

function switchTab(tab) {
  if (currentState !== State.IDLE && currentState !== State.ERROR) return;
  if (currentState === State.ERROR) {
    errorEl.hidden = true;
    currentState = State.IDLE;
  }
  activeTab = tab;
  applyTabUI();
  if (tab === "recover") {
    if (window.Recovery) window.Recovery.init(recoveryCallbacks);
  } else {
    if (window.Recovery) window.Recovery.destroy();
  }
  render();
}

tabAnonymise.addEventListener("click", function () { switchTab("anonymise"); });
tabRecover.addEventListener("click", function () { switchTab("recover"); });
tabBar.addEventListener("keydown", function (e) {
  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    e.preventDefault();
    var next = activeTab === "anonymise" ? "recover" : "anonymise";
    switchTab(next);
    document.getElementById("tab-" + (next === "anonymise" ? "anonymise" : "recover")).focus();
  }
});
