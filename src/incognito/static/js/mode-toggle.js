"use strict";

window.ModeToggle = (function () {
  var PASSPHRASE_MIN_LENGTH = 12;
  var _initialized = false;
  var _validityCallback = null;
  var _dirty = false;

  var modeRadios;
  var modeDescription;
  var passphraseGroup;
  var passphraseInput;
  var strengthEl;
  var hintEl;
  var modeOptions;

  var DESCRIPTIONS = {
    irreversible: "Personal data will be permanently deleted.",
    reversible: "Data will be encrypted and recoverable with your passphrase."
  };

  var STRENGTH_LABELS = {weak: "Weak", fair: "Fair", strong: "Strong"};

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

  function getSelectedMode() {
    for (var i = 0; i < modeRadios.length; i++) {
      if (modeRadios[i].checked) return modeRadios[i].value;
    }
    return "irreversible";
  }

  function updateActiveClass() {
    for (var i = 0; i < modeOptions.length; i++) {
      var radio = modeOptions[i].querySelector("input[type=\"radio\"]");
      modeOptions[i].classList.toggle("mode-option--active", radio.checked);
    }
  }

  function updateStrength() {
    var value = passphraseInput.value;
    if (value.length === 0) {
      strengthEl.textContent = "";
      strengthEl.className = "passphrase-strength";
      hintEl.textContent = "";
      return;
    }
    _dirty = true;
    var strength = computeStrength(value);
    strengthEl.textContent = STRENGTH_LABELS[strength];
    strengthEl.className = "passphrase-strength passphrase-strength--" + strength;

    if (value.length < PASSPHRASE_MIN_LENGTH) {
      hintEl.textContent = PASSPHRASE_MIN_LENGTH - value.length + " character(s) remaining";
    } else {
      hintEl.textContent = "";
    }
  }

  function fireValidity() {
    if (_validityCallback) _validityCallback();
  }

  function onModeChange() {
    var mode = getSelectedMode();
    updateActiveClass();
    modeDescription.textContent = DESCRIPTIONS[mode];

    if (mode === "reversible") {
      passphraseGroup.hidden = false;
      passphraseInput.focus();
    } else {
      passphraseGroup.hidden = true;
      passphraseInput.value = "";
      _dirty = false;
      strengthEl.textContent = "";
      strengthEl.className = "passphrase-strength";
      hintEl.textContent = "";
    }
    fireValidity();
  }

  function onPassphraseInput() {
    updateStrength();
    fireValidity();
  }

  function init(onValidityChange) {
    if (_initialized) {
      if (onValidityChange) _validityCallback = onValidityChange;
      fireValidity();
      return;
    }

    modeRadios = document.querySelectorAll("input[name=\"redact-mode\"]");
    modeDescription = document.getElementById("mode-description");
    passphraseGroup = document.getElementById("passphrase-group");
    passphraseInput = document.getElementById("passphrase-input");
    strengthEl = document.getElementById("passphrase-strength");
    hintEl = document.getElementById("passphrase-hint");
    modeOptions = document.querySelectorAll(".mode-option");

    if (onValidityChange) _validityCallback = onValidityChange;

    for (var i = 0; i < modeRadios.length; i++) {
      modeRadios[i].addEventListener("change", onModeChange);
    }
    passphraseInput.addEventListener("input", onPassphraseInput);

    _initialized = true;
    updateActiveClass();
    fireValidity();
  }

  function destroy() {
    if (!_initialized) return;
    passphraseInput.value = "";
    passphraseGroup.hidden = true;
    _dirty = false;
    strengthEl.textContent = "";
    strengthEl.className = "passphrase-strength";
    hintEl.textContent = "";

    for (var i = 0; i < modeRadios.length; i++) {
      if (modeRadios[i].value === "irreversible") modeRadios[i].checked = true;
      modeRadios[i].removeEventListener("change", onModeChange);
    }
    passphraseInput.removeEventListener("input", onPassphraseInput);
    updateActiveClass();
    modeDescription.textContent = DESCRIPTIONS.irreversible;

    _validityCallback = null;
    _initialized = false;
  }

  function getMode() {
    return _initialized ? getSelectedMode() : "irreversible";
  }

  function getPassphrase() {
    if (!_initialized || getSelectedMode() !== "reversible") return null;
    return passphraseInput.value;
  }

  function isValid() {
    if (!_initialized || getSelectedMode() === "irreversible") return true;
    return passphraseInput.value.length >= PASSPHRASE_MIN_LENGTH;
  }

  return {init: init, destroy: destroy, getMode: getMode, getPassphrase: getPassphrase, isValid: isValid};
})();
