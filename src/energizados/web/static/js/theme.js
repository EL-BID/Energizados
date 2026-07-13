/*
 * Theme toggle for the Energizados web console.
 *
 * Light is the default. The user's choice is persisted in localStorage
 * under "theme" (values: "light" | "dark"). An inline script in <head> applies
 * the stored theme BEFORE first paint to avoid a flash of the wrong theme;
 * this module wires the toggle button(s) and keeps their icon/label in sync.
 *
 * Toggling sets both data-bs-theme (Bootstrap 5.3 native — drives Bootstrap's
 * own dark styles) and data-theme (alias used by app.css) on <html>.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var DARK = "dark";
  var LIGHT = "light";

  function normalize(theme) {
    return theme === DARK ? DARK : LIGHT;
  }

  function currentTheme() {
    var attr = document.documentElement.getAttribute("data-bs-theme");
    return normalize(attr);
  }

  function applyTheme(theme) {
    var t = normalize(theme);
    var html = document.documentElement;
    html.setAttribute("data-bs-theme", t);
    html.setAttribute("data-theme", t);
    syncToggles(t);
    return t;
  }

  function syncToggles(theme) {
    var nodes = document.querySelectorAll("[data-theme-toggle]");
    nodes.forEach(function (btn) {
      var icon = btn.querySelector("[data-theme-toggle-icon]");
      var label = btn.querySelector("[data-theme-toggle-label]");
      // Icon shows the action the user will take on click.
      if (icon) { icon.textContent = theme === DARK ? "☀" : "🌙"; }
      if (label) { label.textContent = theme === DARK ? "Light" : "Dark"; }
      btn.setAttribute("aria-pressed", String(theme === DARK));
      btn.setAttribute(
        "aria-label",
        theme === DARK ? "Switch to light theme" : "Switch to dark theme"
      );
    });
  }

  function toggle() {
    var next = currentTheme() === DARK ? LIGHT : DARK;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (e) {
      // localStorage may be unavailable (private mode) — keep a session-only toggle.
    }
    applyTheme(next);
  }

  function init() {
    // The inline head script already applied the stored theme; just sync UI.
    syncToggles(currentTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      if (btn.dataset.themeBound === "1") { return; }
      btn.dataset.themeBound = "1";
      btn.addEventListener("click", toggle);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Expose for debugging / programmatic control (also helps HTMX-swapped
  // toggles rebind if ever needed).
  window.EnergizadosTheme = {
    applyTheme: applyTheme,
    currentTheme: currentTheme,
    toggle: toggle,
    syncToggles: syncToggles,
  };
})();
