import * as pdfjsLib from "/js/vendor/pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "/js/vendor/pdfjs/pdf.worker.min.mjs";

var RENDER_SCALE = 1.5;
var pdfDoc = null;
var container = null;
var initialized = false;

function init(sessionId) {
  container = document.getElementById("pdf-preview-container");
  if (!container) return;

  if (initialized) destroy();
  initialized = true;

  container.innerHTML =
    '<p class="pdf-preview-loading">Loading preview\u2026</p>';

  fetch("/api/pdf/" + sessionId)
    .then(function (resp) {
      if (!resp.ok) throw new Error(resp.status);
      return resp.arrayBuffer();
    })
    .then(function (buf) {
      return pdfjsLib.getDocument({ data: new Uint8Array(buf) }).promise;
    })
    .then(function (doc) {
      pdfDoc = doc;
      container.innerHTML = "";
      return renderAllPages(doc);
    })
    .catch(function () {
      if (container) {
        container.innerHTML =
          '<p class="pdf-preview-error">Failed to load PDF preview.</p>';
      }
    });
}

function renderAllPages(doc) {
  var chain = Promise.resolve();
  for (var i = 1; i <= doc.numPages; i++) {
    chain = chain.then(renderPage.bind(null, doc, i, doc.numPages));
  }
  return chain;
}

function renderPage(doc, pageNum, totalPages) {
  return doc.getPage(pageNum).then(function (page) {
    var viewport = page.getViewport({ scale: RENDER_SCALE });

    var wrapper = document.createElement("div");
    wrapper.className = "pdf-page-wrapper";

    var canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    var label = document.createElement("p");
    label.className = "pdf-page-label";
    label.textContent = "Page " + pageNum + " / " + totalPages;

    wrapper.appendChild(canvas);
    wrapper.appendChild(label);
    container.appendChild(wrapper);

    return page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  });
}

function destroy() {
  if (pdfDoc) {
    pdfDoc.destroy();
    pdfDoc = null;
  }
  if (container) {
    container.innerHTML = "";
  }
  initialized = false;
}

window.PdfPreview = { init: init, destroy: destroy };

if (window.currentState === "reviewing" && window.sessionId) {
  init(window.sessionId);
}
