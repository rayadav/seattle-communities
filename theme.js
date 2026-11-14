// Theme toggle & cross-tab synchronization (light / dark / system default)
(function () {
  'use strict';

  const STORAGE_KEY = 'sc-theme';
  const metaEl = document.querySelector('meta[name="color-scheme"]');
  const mql = window.matchMedia('(prefers-color-scheme: dark)');

  function getStoredTheme() {
    try {
      const val = localStorage.getItem(STORAGE_KEY);
      return val === 'light' || val === 'dark' ? val : null;
    } catch (_) {
      return null;
    }
  }

  function getEffectiveTheme() {
    return getStoredTheme() || (mql.matches ? 'dark' : 'light');
  }

  function applyTheme(stored) {
    if (metaEl) {
      metaEl.content = stored || 'light dark';
    }
    if (stored === 'light' || stored === 'dark') {
      document.documentElement.setAttribute('data-theme', stored);
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    syncToggleUI();
  }

  function syncToggleUI() {
    const btn = document.getElementById('theme-switch-btn');
    if (!btn) return;
    const effective = getEffectiveTheme();
    const nextLabel = effective === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
    btn.setAttribute('aria-label', nextLabel);
    btn.setAttribute('data-effective-theme', effective);

    const textEl = document.getElementById('theme-switch-label');
    if (textEl) {
      textEl.textContent = effective === 'dark' ? 'Light' : 'Dark';
    }
  }

  function toggleTheme() {
    const currentEffective = getEffectiveTheme();
    const target = currentEffective === 'dark' ? 'light' : 'dark';
    const systemTheme = mql.matches ? 'dark' : 'light';

    if (target === systemTheme) {
      // Target matches current system preference: revert to system default
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch (_) {}
      applyTheme(null);
    } else {
      try {
        localStorage.setItem(STORAGE_KEY, target);
      } catch (_) {}
      applyTheme(target);
    }
  }

  // Initialize UI once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      syncToggleUI();
      const btn = document.getElementById('theme-switch-btn');
      if (btn) btn.addEventListener('click', toggleTheme);
    });
  } else {
    syncToggleUI();
    const btn = document.getElementById('theme-switch-btn');
    if (btn) btn.addEventListener('click', toggleTheme);
  }

  // Keep in sync when system preference changes (never deletes a stored override)
  mql.addEventListener('change', () => {
    if (!getStoredTheme()) {
      syncToggleUI();
    }
  });

  // Sync across tabs via storage event
  window.addEventListener('storage', (e) => {
    if (e.key === STORAGE_KEY) {
      applyTheme(e.newValue === 'light' || e.newValue === 'dark' ? e.newValue : null);
    }
  });
})();
