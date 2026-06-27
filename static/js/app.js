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

    // Global search — live Google-style suggestions dropdown
    (function () {
      var input = document.getElementById("global-search");
      var panel = document.getElementById("search-results");
      var form = input && input.closest("form");
      if (!input || !panel || !form) return;
      var suggestUrl = form.getAttribute("data-suggest-url") || "";
      var timer = null, results = [], active = -1;

      function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }
      function open() { panel.hidden = false; input.setAttribute("aria-expanded", "true"); }
      function close() { panel.hidden = true; panel.innerHTML = ""; results = []; active = -1; input.setAttribute("aria-expanded", "false"); }

      function render(groups) {
        results = [];
        if (!groups || !groups.length) { panel.innerHTML = '<div class="search-empty">No matches</div>'; open(); return; }
        var html = "";
        groups.forEach(function (g) {
          html += '<div class="search-group-label">' + esc(g.group) + '</div>';
          g.items.forEach(function (it) {
            var idx = results.length; results.push(it);
            html += '<a class="search-item" href="' + esc(it.url) + '" data-idx="' + idx + '">' +
                    '<i data-lucide="' + esc(g.icon) + '"></i>' +
                    '<span class="search-item-text"><span class="search-item-title">' + esc(it.title) + '</span>' +
                    (it.subtitle ? '<span class="search-item-sub">' + esc(it.subtitle) + '</span>' : '') +
                    '</span></a>';
          });
        });
        panel.innerHTML = html; active = -1;
        if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
        open();
      }

      function fetchSuggest(q) {
        fetch(suggestUrl + "?q=" + encodeURIComponent(q), { headers: { "X-Requested-With": "XMLHttpRequest" } })
          .then(function (r) { return r.ok ? r.json() : { groups: [] }; })
          .then(function (data) { if (input.value.trim() === q) render(data.groups); })
          .catch(function () {});
      }

      function setActive(i) {
        var nodes = panel.querySelectorAll(".search-item");
        if (!nodes.length) return;
        active = (i + nodes.length) % nodes.length;
        nodes.forEach(function (n, j) { n.classList.toggle("active", j === active); });
        nodes[active].scrollIntoView({ block: "nearest" });
      }

      input.addEventListener("input", function () {
        var q = input.value.trim();
        window.clearTimeout(timer);
        if (q.length < 2) { close(); return; }
        timer = window.setTimeout(function () { fetchSuggest(q); }, 200);
      });
      input.addEventListener("keydown", function (e) {
        if (panel.hidden) return;
        if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
        else if (e.key === "Enter") { if (active >= 0 && results[active]) { e.preventDefault(); window.location.href = results[active].url; } }
        else if (e.key === "Escape") { close(); }
      });
      input.addEventListener("focus", function () { if (input.value.trim().length >= 2 && panel.innerHTML) open(); });
      document.addEventListener("click", function (e) { if (!form.contains(e.target)) close(); });
    })();

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
