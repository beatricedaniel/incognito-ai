"use strict";

var State = {
  IDLE: "idle",
  UPLOADING: "uploading",
  PROCESSING: "processing",
  REVIEWING: "reviewing",
  REDACTING: "redacting",
  COMPLETE: "complete",
  ERROR: "error",
};

var currentState = State.IDLE;
var ollamaReady = false;
var sessionId = null;
var eventSource = null;
var dragEnterCount = 0;

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

// — State machine —

function transition(next) {
  currentState = next;
  render();
}

function render() {
  var reviewing = currentState === State.REVIEWING || currentState === State.REDACTING;

  errorEl.hidden = currentState !== State.ERROR;
  reviewPanel.hidden = !reviewing;
  completePanel.hidden = currentState !== State.COMPLETE;
  dropZone.hidden = reviewing || currentState === State.COMPLETE;

  if (currentState === State.IDLE) {
    dropLabel.textContent = "Déposez un PDF ici";
    dropHint.hidden = false;
    dropZone.classList.remove("drop-zone--disabled");
  } else if (currentState === State.UPLOADING) {
    dropLabel.textContent = "Envoi en cours\u2026";
    dropHint.hidden = true;
    dropZone.classList.add("drop-zone--disabled");
  } else if (currentState === State.PROCESSING) {
    dropHint.hidden = true;
    dropZone.classList.add("drop-zone--disabled");
  } else if (currentState === State.ERROR) {
    dropLabel.textContent = "Déposez un PDF ici";
    dropHint.hidden = false;
    dropZone.classList.remove("drop-zone--disabled");
  }

  redactButton.disabled = currentState !== State.REVIEWING;
  if (currentState === State.REDACTING) {
    redactButton.textContent = "Anonymisation en cours\u2026";
    redactButton.classList.add("redacting");
  } else {
    redactButton.textContent = "Anonymiser";
    redactButton.classList.remove("redacting");
  }

  document.querySelector("main").classList.toggle(
    "reviewing--active", reviewing
  );

  if (currentState === State.REVIEWING) {
    if (window.PdfPreview) window.PdfPreview.init(sessionId);
    if (window.DetectionSidebar) window.DetectionSidebar.init(sessionId);
  } else if (currentState !== State.REDACTING) {
    if (window.PdfPreview) window.PdfPreview.destroy();
    if (window.DetectionSidebar) window.DetectionSidebar.destroy();
  }
}

// — Status polling —

function renderStatus() {
  var localBadge = '<span class="badge badge-local">100% local \u2014 aucune donn\u00e9e ne quitte votre machine</span>';

  if (ollamaReady) {
    statusBar.innerHTML =
      '<span class="badge badge-ready">Ready</span>' + localBadge;
  } else {
    statusBar.innerHTML =
      '<p class="status-warning">Veuillez d\u00e9marrer Ollama avec Gemma\u00a04 E4B</p>' + localBadge;
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
  if (!isPdf(file)) {
    showError("Veuillez sélectionner un fichier PDF.");
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
      showError(err.detail || "L\u2019envoi a \u00e9chou\u00e9.");
    });
}

// — SSE —

function connectEvents(url) {
  transition(State.PROCESSING);
  dropLabel.textContent = "Traitement en cours\u2026";

  var source = new EventSource(url);
  eventSource = source;

  source.addEventListener("stage_update", function (e) {
    var data = JSON.parse(e.data);
    dropLabel.textContent = data.message;
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
    showError(data.detail || "Erreur lors du traitement.");
  });

  source.onerror = function () {
    source.close();
    eventSource = null;
    if (currentState === State.PROCESSING) {
      showError("Connexion au serveur perdue.");
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

  fetch("/api/redact/" + sessionId, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({mode: "irreversible"})
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
      completeMessage.textContent = "Anonymisation termin\u00e9e.";
      transition(State.COMPLETE);
      downloadLink.click();
    })
    .catch(function (err) {
      showError(err.detail || "Erreur lors de l\u2019anonymisation.");
    });
});

// — Reset —

resetButton.addEventListener("click", function () {
  if (downloadLink.href) URL.revokeObjectURL(downloadLink.href);
  downloadLink.hidden = true;
  sessionId = null;
  transition(State.IDLE);
});

// — Error —

function showError(message) {
  transition(State.ERROR);
  errorEl.textContent = message;
  errorEl.hidden = false;
}
