"use strict";

var ENTITY_META = {
  person:  { label: "Person",   cssClass: "badge-person" },
  address: { label: "Address",  cssClass: "badge-address" },
  phone:   { label: "Phone",    cssClass: "badge-phone" },
  email:   { label: "Email",    cssClass: "badge-email" },
};

var SNIPPET_MAX = 40;

var sidebarEl = null;
var activeSessionId = null;

function destroy() {
  if (sidebarEl) {
    sidebarEl.innerHTML = "";
  }
  activeSessionId = null;
}

function createBadge(entityType) {
  var meta = ENTITY_META[entityType];
  var span = document.createElement("span");
  span.className = "badge " + (meta ? meta.cssClass : "badge-unknown");
  span.textContent = meta ? meta.label : entityType;
  return span;
}

function truncate(text) {
  if (text.length <= SNIPPET_MAX) return text;
  return text.slice(0, SNIPPET_MAX) + "\u2026";
}

function renderSummary(detections) {
  var counts = {};
  for (var i = 0; i < detections.length; i++) {
    var t = detections[i].entity_type;
    counts[t] = (counts[t] || 0) + 1;
  }

  var region = document.createElement("div");
  region.className = "sidebar-summary";
  region.setAttribute("role", "region");
  region.setAttribute("aria-label", "Detection summary");

  var title = document.createElement("h2");
  title.className = "sidebar-summary-title";
  title.textContent = detections.length + " detection" + (detections.length !== 1 ? "s" : "");
  region.appendChild(title);

  var ul = document.createElement("ul");
  ul.className = "summary-counts";
  ul.setAttribute("aria-label", "Count by type");

  var types = Object.keys(ENTITY_META);
  for (var j = 0; j < types.length; j++) {
    var type = types[j];
    if (!counts[type]) continue;
    var li = document.createElement("li");
    li.appendChild(createBadge(type));
    li.appendChild(document.createTextNode(" " + counts[type]));
    ul.appendChild(li);
  }

  region.appendChild(ul);
  return region;
}

function renderList(detections) {
  var nav = document.createElement("nav");
  nav.setAttribute("aria-label", "Detections by page");

  var currentPage = -1;
  var section = null;
  var ul = null;

  for (var i = 0; i < detections.length; i++) {
    var d = detections[i];

    if (d.page !== currentPage) {
      currentPage = d.page;
      section = document.createElement("section");
      var headingId = "page-heading-" + currentPage;
      section.setAttribute("aria-labelledby", headingId);

      var h3 = document.createElement("h3");
      h3.id = headingId;
      h3.className = "sidebar-page-heading";
      h3.textContent = "Page " + currentPage;
      section.appendChild(h3);

      ul = document.createElement("ul");
      ul.className = "detection-list";
      section.appendChild(ul);
      nav.appendChild(section);
    }

    var li = document.createElement("li");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "detection-item";
    btn.setAttribute("data-detection-id", d.id);

    btn.appendChild(createBadge(d.entity_type));

    var textSpan = document.createElement("span");
    textSpan.className = "detection-text";
    textSpan.textContent = truncate(d.text);
    if (d.text.length > SNIPPET_MAX) {
      textSpan.title = d.text;
    }
    btn.appendChild(textSpan);

    var pageSpan = document.createElement("span");
    pageSpan.className = "detection-page";
    pageSpan.textContent = "p.\u00a0" + d.page;
    btn.appendChild(pageSpan);

    var dismissBtn = document.createElement("button");
    dismissBtn.type = "button";
    dismissBtn.className = "detection-dismiss";
    dismissBtn.textContent = "\u00d7";
    dismissBtn.title = "Dismiss";
    dismissBtn.setAttribute("data-detection-id", d.id);
    dismissBtn.setAttribute("data-entity-type", d.entity_type);

    li.appendChild(btn);
    li.appendChild(dismissBtn);
    ul.appendChild(li);
  }

  return nav;
}

function init(sessionId) {
  destroy();

  sidebarEl = document.getElementById("detection-sidebar");
  if (!sidebarEl) return;

  activeSessionId = sessionId;
  sidebarEl.innerHTML = '<p class="sidebar-loading">Loading detections\u2026</p>';

  fetch("/api/detections/" + sessionId)
    .then(function (resp) {
      if (!resp.ok) throw new Error(resp.statusText);
      return resp.json();
    })
    .then(function (data) {
      if (activeSessionId !== sessionId) return;

      var detections = data.detections.filter(function (d) {
        return !d.dismissed;
      });

      sidebarEl.innerHTML = "";

      if (detections.length === 0) {
        var p = document.createElement("p");
        p.className = "sidebar-empty";
        p.textContent = "No detections found.";
        sidebarEl.appendChild(p);
        return;
      }

      sidebarEl.appendChild(renderSummary(detections));
      sidebarEl.appendChild(renderList(detections));

      sidebarEl.addEventListener("click", function (e) {
        var dismiss = e.target.closest(".detection-dismiss");
        if (!dismiss) return;

        var detectionId = dismiss.getAttribute("data-detection-id");
        var entityType = dismiss.getAttribute("data-entity-type");

        fetch("/api/detections/" + sessionId + "/" + detectionId, {
          method: "DELETE",
        }).then(function (resp) {
          if (!resp.ok) return;

          var li = dismiss.closest("li");
          var section = li.closest("section");
          li.remove();

          if (section && section.querySelector(".detection-list").children.length === 0) {
            section.remove();
          }

          var remaining = sidebarEl.querySelectorAll(".detection-item").length;
          if (remaining === 0) {
            sidebarEl.innerHTML = "";
            var p = document.createElement("p");
            p.className = "sidebar-empty";
            p.textContent = "No detections found.";
            sidebarEl.appendChild(p);
            return;
          }

          var titleEl = sidebarEl.querySelector(".sidebar-summary-title");
          titleEl.textContent = remaining + " detection" + (remaining !== 1 ? "s" : "");

          var countItems = sidebarEl.querySelectorAll(".summary-counts li");
          for (var i = 0; i < countItems.length; i++) {
            if (countItems[i].querySelector(".badge-" + entityType)) {
              var num = parseInt(countItems[i].textContent.replace(/\D/g, ""), 10) - 1;
              if (num <= 0) {
                countItems[i].remove();
              } else {
                countItems[i].lastChild.textContent = " " + num;
              }
              break;
            }
          }
        });
      });
    })
    .catch(function () {
      if (activeSessionId !== sessionId) return;
      sidebarEl.innerHTML = '<p class="sidebar-error">Failed to load detections.</p>';
    });
}

window.DetectionSidebar = { init: init, destroy: destroy };
