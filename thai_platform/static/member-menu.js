(() => {
  const menus = [...document.querySelectorAll('.member-menu')];
  let active = null;
  const close = (restore = false) => {
    if (!active) return;
    const menu = active;
    active = null;
    menu.open = false;
    if (restore) menu.querySelector('summary').focus();
  };
  const position = () => {
    if (!active || !active.open) return;
    const anchor = active.querySelector('summary').getBoundingClientRect();
    const panel = active.querySelector('.member-menu-actions');
    const gap = 6, margin = 8;
    const width = Math.min(272, window.innerWidth - margin * 2);
    panel.style.width = `${width}px`;
    panel.style.maxHeight = `${window.innerHeight - margin * 2}px`;
    const height = panel.getBoundingClientRect().height;
    const left = Math.max(margin, Math.min(anchor.left, window.innerWidth - width - margin));
    const below = anchor.bottom + gap;
    const top = below + height <= window.innerHeight - margin ? below : Math.max(margin, anchor.top - height - gap);
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  };
  menus.forEach(menu => menu.addEventListener('toggle', () => {
    if (menu.open) {
      if (active && active !== menu) close();
      active = menu;
      position();
    } else if (active === menu) active = null;
  }));
  document.addEventListener('click', event => {
    if (active && !active.contains(event.target)) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && active) { event.preventDefault(); close(true); }
  });
  window.addEventListener('resize', position);
  window.addEventListener('scroll', position, true);
})();
