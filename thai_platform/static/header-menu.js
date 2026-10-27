(() => {
  const menu = document.querySelector('.account-menu');
  if (!menu) return;
  const avatar = menu.querySelector('.header-avatar');
  if (avatar) {
    avatar.addEventListener('error', () => { avatar.hidden = true; });
    if (avatar.complete && !avatar.naturalWidth) avatar.hidden = true;
  }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu.open) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });
})();
