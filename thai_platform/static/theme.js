(() => {
  'use strict';
  const storageKey = 'post-theme';
  const root = document.documentElement;
  const button = document.querySelector('[data-theme-toggle]');
  let saved = null;
  try {
    saved = localStorage.getItem(storageKey);
  } catch {
    // The system preference still works when browser storage is unavailable.
  }
  const systemDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  const initial = saved === 'light' || saved === 'dark' ? saved : (systemDark ? 'dark' : 'light');

  function applyTheme(theme) {
    root.dataset.theme = theme;
    if (!button) return;
    const nextLabel = theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환';
    button.setAttribute('aria-label', nextLabel);
    button.setAttribute('title', nextLabel);
    button.setAttribute('aria-pressed', String(theme === 'dark'));
  }

  applyTheme(initial);
  button?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      // Keep the current page usable even if preference persistence is blocked.
    }
  });
})();
