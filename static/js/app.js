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

    // Expand/collapse modules (level 1)
    document.querySelectorAll(".nav-group > .nav-link").forEach(function (link) {
      link.addEventListener("click", function (e) {
        var group = link.closest(".nav-group");
        if (group && group.querySelector(".nav-sub")) {
          e.preventDefault();
          // If the sidebar is collapsed to the icon rail, a click should expand it and open this
          // module's submenu — the accordion is invisible while collapsed, so toggling it is useless.
          if (document.documentElement.getAttribute("data-collapsed") === "true") {
            document.documentElement.setAttribute("data-collapsed", "false");
            group.classList.add("open");
            return;
          }
          group.classList.toggle("open");
        }
      });
    });

    // Expand/collapse sub-modules (level 2)
    document.querySelectorAll(".nav-subgroup > .nav-sublink").forEach(function (link) {
      link.addEventListener("click", function (e) {
        var sub = link.closest(".nav-subgroup");
        if (sub) {
          e.preventDefault();
          sub.classList.toggle("open");
        }
      });
    });

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
