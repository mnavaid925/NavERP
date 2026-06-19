/* NavERP — app behaviours: icons, nav, search, toasts, HTMX defaults. */
(function () {
  "use strict";

  function initIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initIcons();

    // Expand/collapse sidebar nav groups
    document.querySelectorAll(".nav-group > .nav-link").forEach(function (link) {
      link.addEventListener("click", function (e) {
        var group = link.closest(".nav-group");
        if (group && group.querySelector(".nav-sub")) {
          e.preventDefault();
          group.classList.toggle("open");
        }
      });
    });

    // Keep the active group open on load
    var active = document.querySelector(".nav-sub a.active");
    if (active) {
      var g = active.closest(".nav-group");
      if (g) g.classList.add("open");
    }

    // ⌘K / Ctrl-K focuses the search box
    var search = document.getElementById("global-search");
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (search) search.focus();
      }
    });

    // Auto-dismiss toasts
    document.querySelectorAll(".toast").forEach(function (t) {
      window.setTimeout(function () {
        t.style.transition = "opacity .4s ease";
        t.style.opacity = "0";
        window.setTimeout(function () { t.remove(); }, 400);
      }, 4500);
    });
  });

  // Re-init icons after any HTMX swap
  document.body.addEventListener && document.addEventListener("htmx:afterSwap", initIcons);
})();
