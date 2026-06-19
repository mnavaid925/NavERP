/* NavERP — layout engine & customizer.
   Persists UI preferences to localStorage and reflects them as data-* attributes
   on <html>, so theme.css can style every variant from PROMPT.md §Dashboard Requirements:
   layout (vertical/horizontal/detached), mode (light/dark), width (fluid/boxed),
   sidebar size (default/compact/small-icon/icon-hovered) & color (light/colored),
   topbar (light/dark), position (fixed/scrollable), direction (LTR/RTL), preloader. */
(function () {
  "use strict";
  var root = document.documentElement;

  // key -> {attr, default}
  var SETTINGS = {
    layout:        { attr: "data-layout",        def: "vertical" },
    mode:          { attr: "class-dark",          def: "light" },   // special: toggles .dark class
    width:         { attr: "data-width",          def: "fluid" },
    sidebar:       { attr: "data-sidebar",        def: "default" },
    sidebarColor:  { attr: "data-sidebar-color",  def: "light" },
    topbar:        { attr: "data-topbar",         def: "light" },
    position:      { attr: "data-position",       def: "fixed" },
    direction:     { attr: "dir",                 def: "ltr" },
    preloader:     { attr: "data-preloader",      def: "off" }
  };
  var STORE = "naverp.ui";

  function load() {
    try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch (e) { return {}; }
  }
  function save(state) {
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {}
  }
  function apply(state) {
    Object.keys(SETTINGS).forEach(function (key) {
      var cfg = SETTINGS[key];
      var val = state[key] != null ? state[key] : cfg.def;
      if (cfg.attr === "class-dark") {
        root.classList.toggle("dark", val === "dark");
      } else {
        root.setAttribute(cfg.attr, val);
      }
    });
    syncCustomizer(state);
  }
  function set(key, val) {
    var state = load();
    state[key] = val;
    save(state);
    apply(state);
  }

  function syncCustomizer(state) {
    document.querySelectorAll("[data-opt-key]").forEach(function (btn) {
      var k = btn.getAttribute("data-opt-key");
      var v = btn.getAttribute("data-opt-val");
      var cur = state[k] != null ? state[k] : (SETTINGS[k] ? SETTINGS[k].def : null);
      btn.classList.toggle("active", String(cur) === String(v));
    });
  }

  // Apply ASAP (also called inline in <head> to avoid flash — see base.html).
  apply(load());

  document.addEventListener("DOMContentLoaded", function () {
    // Customizer option buttons
    document.querySelectorAll("[data-opt-key]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        set(btn.getAttribute("data-opt-key"), btn.getAttribute("data-opt-val"));
      });
    });

    // Open / close customizer
    var cz = document.getElementById("customizer");
    var czBack = document.getElementById("customizer-backdrop");
    function toggleCz(open) {
      if (!cz) return;
      cz.classList.toggle("open", open);
      if (czBack) czBack.classList.toggle("open", open);
    }
    var openBtn = document.getElementById("customizer-open");
    var closeBtn = document.getElementById("customizer-close");
    if (openBtn) openBtn.addEventListener("click", function () { toggleCz(true); });
    if (closeBtn) closeBtn.addEventListener("click", function () { toggleCz(false); });
    if (czBack) czBack.addEventListener("click", function () { toggleCz(false); });
    var resetBtn = document.getElementById("customizer-reset");
    if (resetBtn) resetBtn.addEventListener("click", function () { save({}); apply({}); });

    // Dark-mode toggle (topbar)
    var darkBtn = document.getElementById("dark-toggle");
    if (darkBtn) darkBtn.addEventListener("click", function () {
      set("mode", root.classList.contains("dark") ? "light" : "dark");
    });

    // Sidebar collapse (topbar)
    var collapseBtn = document.getElementById("sidebar-toggle");
    if (collapseBtn) collapseBtn.addEventListener("click", function () {
      if (window.matchMedia("(max-width: 768px)").matches) {
        root.setAttribute("data-mobile-open",
          root.getAttribute("data-mobile-open") === "true" ? "false" : "true");
      } else {
        root.setAttribute("data-collapsed",
          root.getAttribute("data-collapsed") === "true" ? "false" : "true");
      }
    });

    // Preloader: hide once the page is ready
    var pre = document.getElementById("preloader");
    if (pre) window.setTimeout(function () { pre.classList.add("hidden"); }, 350);
  });

  window.NavERPLayout = { set: set, apply: apply, load: load };
})();
