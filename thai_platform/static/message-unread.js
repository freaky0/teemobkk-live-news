(() => {
  const link = document.querySelector('[data-message-unread-link]');
  if (!link || link.dataset.messageUnreadInitialized === 'true') return;
  link.dataset.messageUnreadInitialized = 'true';

  const endpoint = link.dataset.countUrl;
  const status = link.querySelector('[data-message-unread-status]');
  let currentCount = Number.parseInt(link.dataset.count || '0', 10);
  if (!Number.isInteger(currentCount) || currentCount < 0) currentCount = 0;
  let timer = null;
  let inFlight = false;
  let refreshRequested = false;

  function updateCount(count) {
    if (!Number.isInteger(count) || count < 0 || count === currentCount) return;
    currentCount = count;
    link.dataset.count = String(count);
    link.setAttribute('aria-label', count ? `쪽지, 읽지 않은 쪽지 ${count}개` : '쪽지');
    link.title = count ? `읽지 않은 쪽지 ${count}개` : '쪽지';

    let badge = link.querySelector('.message-unread-badge');
    if (count > 0) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'message-unread-badge';
        badge.setAttribute('aria-hidden', 'true');
        link.insertBefore(badge, status);
      }
      badge.textContent = String(count);
    } else if (badge) {
      badge.remove();
    }

    if (status) {
      status.textContent = count ? `읽지 않은 쪽지가 ${count}개 있습니다.` : '읽지 않은 쪽지가 없습니다.';
    }
  }

  function schedule() {
    if (timer !== null || inFlight || document.visibilityState !== 'visible') return;
    timer = window.setTimeout(() => {
      timer = null;
      refresh();
    }, 30000);
  }

  async function refresh() {
    if (inFlight || document.visibilityState !== 'visible') return;
    inFlight = true;
    try {
      const response = await window.fetch(endpoint, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      if (!response.ok) return;
      const payload = await response.json();
      if (document.visibilityState === 'visible') updateCount(payload.count);
    } catch {
      // Keep the last server-rendered or successfully fetched count on errors.
    } finally {
      inFlight = false;
      if (refreshRequested && document.visibilityState === 'visible') {
        refreshRequested = false;
        refresh();
        return;
      }
      refreshRequested = false;
      schedule();
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
      if (inFlight) refreshRequested = true;
      else refresh();
    } else if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
  });

  schedule();
})();
