(() => {
  'use strict';

  const root = document.documentElement;
  const button = document.getElementById('landing-theme-toggle');
  let theme = 'light';
  try {
    theme = localStorage.getItem('tbn-theme') === 'dark' ? 'dark' : 'light';
  } catch {
    // Keep the page usable if browser storage is unavailable.
  }
  root.dataset.theme = theme;

  function updateButton() {
    if (!button) return;
    const dark = root.dataset.theme === 'dark';
    const label = dark ? '라이트 모드로 전환' : '다크 모드 켜기';
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
    button.setAttribute('aria-pressed', String(dark));
  }

  button?.addEventListener('click', () => {
    theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = theme;
    try {
      localStorage.setItem('tbn-theme', theme);
    } catch {
      // Keep the current page usable if browser storage is unavailable.
    }
    updateButton();
  });
  updateButton();
})();
