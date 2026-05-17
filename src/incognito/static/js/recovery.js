"use strict";

window.Recovery = (function () {
  var PASSPHRASE_MIN_LENGTH = 12;
  var STRENGTH_LABELS = {weak: "Weak", fair: "Fair", strong: "Strong"};

  var _initialized = false;
  var _callbacks = null;
  var _file = null;
  var _dragEnterCount = 0;

  var dropZone, fileInput, fileInfo, filenameEl, clearBtn;
  var passphraseGroup, passphraseInput, strengthEl, hintEl;
  var submitBtn;

  function computeStrength(value) {
    if (value.length < PASSPHRASE_MIN_LENGTH) return "weak";
    var classes = 0;
    if (/[a-z]/.test(value)) classes++;
    if (/[A-Z]/.test(value)) classes++;
    if (/[0-9]/.test(value)) classes++;
    if (/[^a-zA-Z0-9]/.test(value)) classes++;
    if (value.length >= 20 || classes >= 3) return "strong";
    if (classes >= 2) return "fair";
    return "weak";
  }

  function updateSubmit() {
    submitBtn.disabled = !_file || passphraseInput.value.length < PASSPHRASE_MIN_LENGTH;
  }

  function updateStrength() {
    var value = passphraseInput.value;
    if (value.length === 0) {
      strengthEl.textContent = "";
      strengthEl.className = "passphrase-strength";
      hintEl.textContent = "";
      updateSubmit();
      return;
    }
    var strength = computeStrength(value);
    strengthEl.textContent = STRENGTH_LABELS[strength];
    strengthEl.className = "passphrase-strength passphrase-strength--" + strength;
    if (value.length < PASSPHRASE_MIN_LENGTH) {
      hintEl.textContent = PASSPHRASE_MIN_LENGTH - value.length + " character(s) remaining";
    } else {
      hintEl.textContent = "";
    }
    updateSubmit();
  }

  function selectFile(file) {
    if (!file.name.toLowerCase().endsWith(".pdfkey")) {
      if (_callbacks) _callbacks.onError("Please select a .pdfkey file.");
      return;
    }
    _file = file;
    filenameEl.textContent = file.name;
    fileInfo.hidden = false;
    dropZone.hidden = true;
    passphraseGroup.hidden = false;
    passphraseInput.focus();
    updateSubmit();
  }

  function clearFile() {
    _file = null;
    fileInput.value = "";
    filenameEl.textContent = "";
    fileInfo.hidden = true;
    dropZone.hidden = false;
    passphraseGroup.hidden = true;
    passphraseInput.value = "";
    strengthEl.textContent = "";
    strengthEl.className = "passphrase-strength";
    hintEl.textContent = "";
    updateSubmit();
  }

  function onDropZoneClick() {
    fileInput.click();
  }

  function onDropZoneKeydown(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  }

  function onDragEnter(e) {
    e.preventDefault();
    _dragEnterCount++;
    dropZone.classList.add("drop-zone--drag-over");
  }

  function onDragOver(e) {
    e.preventDefault();
  }

  function onDragLeave() {
    _dragEnterCount--;
    if (_dragEnterCount <= 0) {
      _dragEnterCount = 0;
      dropZone.classList.remove("drop-zone--drag-over");
    }
  }

  function onDrop(e) {
    e.preventDefault();
    _dragEnterCount = 0;
    dropZone.classList.remove("drop-zone--drag-over");
    if (e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0]);
  }

  function onFileInputChange() {
    if (fileInput.files.length > 0) selectFile(fileInput.files[0]);
    fileInput.value = "";
  }

  function onPassphraseInput() {
    updateStrength();
  }

  function onSubmit() {
    if (!_file || passphraseInput.value.length < PASSPHRASE_MIN_LENGTH) return;

    submitBtn.disabled = true;
    submitBtn.textContent = "Recovering\u2026";
    submitBtn.classList.add("recovering");
    dropZone.classList.add("drop-zone--disabled");

    if (_callbacks) _callbacks.onRecovering();

    var form = new FormData();
    form.append("file", _file);
    form.append("passphrase", passphraseInput.value);

    fetch("/api/recover", {method: "POST", body: form})
      .then(function (resp) {
        if (!resp.ok) return resp.json().then(function (err) { throw err; });
        var cd = resp.headers.get("content-disposition") || "";
        var match = cd.match(/filename="?([^"]+)"?/);
        var filename = match ? match[1] : "recovered.pdf";
        return resp.blob().then(function (blob) {
          return {blob: blob, filename: filename};
        });
      })
      .then(function (result) {
        var url = URL.createObjectURL(result.blob);
        if (_callbacks) _callbacks.onComplete(url, result.filename);
      })
      .catch(function (err) {
        resetSubmitButton();
        if (_callbacks) _callbacks.onError(err.detail || "Recovery failed.");
      });
  }

  function resetSubmitButton() {
    submitBtn.disabled = true;
    submitBtn.textContent = "Recover document";
    submitBtn.classList.remove("recovering");
    dropZone.classList.remove("drop-zone--disabled");
  }

  function init(callbacks) {
    if (_initialized) return;

    _callbacks = callbacks;

    dropZone = document.getElementById("recovery-drop-zone");
    fileInput = document.getElementById("recovery-file-input");
    fileInfo = document.getElementById("recovery-file-info");
    filenameEl = document.getElementById("recovery-filename");
    clearBtn = document.getElementById("recovery-file-clear");
    passphraseGroup = document.getElementById("recovery-passphrase-group");
    passphraseInput = document.getElementById("recovery-passphrase");
    strengthEl = document.getElementById("recovery-strength");
    hintEl = document.getElementById("recovery-hint");
    submitBtn = document.getElementById("recovery-submit");

    dropZone.addEventListener("click", onDropZoneClick);
    dropZone.addEventListener("keydown", onDropZoneKeydown);
    dropZone.addEventListener("dragenter", onDragEnter);
    dropZone.addEventListener("dragover", onDragOver);
    dropZone.addEventListener("dragleave", onDragLeave);
    dropZone.addEventListener("drop", onDrop);
    fileInput.addEventListener("change", onFileInputChange);
    clearBtn.addEventListener("click", clearFile);
    passphraseInput.addEventListener("input", onPassphraseInput);
    submitBtn.addEventListener("click", onSubmit);

    _initialized = true;
  }

  function destroy() {
    if (!_initialized) return;

    dropZone.removeEventListener("click", onDropZoneClick);
    dropZone.removeEventListener("keydown", onDropZoneKeydown);
    dropZone.removeEventListener("dragenter", onDragEnter);
    dropZone.removeEventListener("dragover", onDragOver);
    dropZone.removeEventListener("dragleave", onDragLeave);
    dropZone.removeEventListener("drop", onDrop);
    fileInput.removeEventListener("change", onFileInputChange);
    clearBtn.removeEventListener("click", clearFile);
    passphraseInput.removeEventListener("input", onPassphraseInput);
    submitBtn.removeEventListener("click", onSubmit);

    _file = null;
    _callbacks = null;
    _dragEnterCount = 0;
    fileInput.value = "";
    filenameEl.textContent = "";
    fileInfo.hidden = true;
    dropZone.hidden = false;
    passphraseGroup.hidden = true;
    passphraseInput.value = "";
    strengthEl.textContent = "";
    strengthEl.className = "passphrase-strength";
    hintEl.textContent = "";
    resetSubmitButton();

    _initialized = false;
  }

  return {init: init, destroy: destroy};
})();
