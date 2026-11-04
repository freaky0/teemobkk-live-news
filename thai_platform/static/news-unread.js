(() => {
  const roots = Array.from(document.querySelectorAll('[data-news-live]'));
  if (!roots.length) return;

  const keyFor = (article) => String(article.id || article.source_url || article.title + '|' + article.published_at);
  const timestamp = (article) => Date.parse(article.published_at || '');
  const safeImage = (value) => {
    try {
      const url = new URL(String(value || ''), window.location.href);
      return url.protocol === 'https:' ? url.href : '';
    } catch (_) {
      return '';
    }
  };
  const shortText = (value, limit) => {
    const chars = Array.from(String(value || '').trim());
    return chars.length > limit ? chars.slice(0, limit - 1).join('') + '…' : chars.join('');
  };
  const ictTime = (value) => {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Bangkok', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(date).reduce((out, part) => {
      out[part.type] = part.value;
      return out;
    }, {});
    return `${parts.month}.${parts.day} ${parts.hour}:${parts.minute} ICT`;
  };

  roots.forEach((root) => {
    const button = root.matches('[data-news-update]') ? root : root.querySelector('[data-news-update]');
    const list = root.dataset.newsListTarget
      ? document.querySelector(root.dataset.newsListTarget)
      : root.querySelector('[data-news-list]');
    const api = root.dataset.newsApi;
    const view = root.dataset.newsView;
    if (!button || !list || !api || (view === 'list' && Number(root.dataset.newsPage) !== 1)) return;

    const detailTemplate = root.dataset.newsDetailTemplate || '';
    const limit = Math.max(1, Number(root.dataset.newsLimit) || (view === 'home' ? 5 : 20));
    const since = Date.parse(root.dataset.newsSince || '');
    let cursor = Number.isFinite(since) ? since : Date.now();
    let baselineReady = false;
    let busy = false;
    let pendingTotal = null;
    const seen = new Set(Array.from(list.querySelectorAll('[data-news-article]'))
      .map((article) => String(article.dataset.newsId || '')).filter(Boolean));
    const pending = new Map();
    const query = new URLSearchParams({ page: '1' });
    if (root.dataset.newsQuery) query.set('q', root.dataset.newsQuery);
    if (root.dataset.newsCategory) query.set('category', root.dataset.newsCategory);
    if (root.dataset.newsRegion) query.set('region', root.dataset.newsRegion);
    const url = `${api}?${query.toString()}`;

    const updateButton = () => {
      const count = pending.size;
      button.textContent = count ? `새 뉴스 ${count}건 보기` : '';
      button.hidden = !count;
      button.dataset.count = String(count);
    };

    const articleNode = (article) => {
      const id = keyFor(article);
      if (!id || !String(article.title || '').trim()) return null;
      const imageUrl = safeImage(article.image_url);
      const item = document.createElement('article');
      item.className = `news-item${imageUrl || article.video_kind ? ' has-image' : ''}${article.video_kind ? ' has-video' : ''}`;
      item.dataset.newsArticle = '';
      item.dataset.newsId = id;
      item.dataset.newsInserted = '1';
      item.tabIndex = -1;

      if (imageUrl || article.video_kind) {
        const thumbnail = document.createElement('div');
        thumbnail.className = `news-thumbnail${imageUrl ? '' : ' no-poster'}`;
        if (imageUrl) {
          const image = document.createElement('img');
          image.className = 'news-image';
          image.src = imageUrl;
          image.alt = '';
          image.loading = 'lazy';
          image.decoding = 'async';
          image.referrerPolicy = 'no-referrer';
          thumbnail.append(image);
        } else {
          const placeholder = document.createElement('div');
          placeholder.className = 'news-poster-placeholder';
          placeholder.setAttribute('role', 'img');
          placeholder.setAttribute('aria-label', '정지 썸네일 없음');
          thumbnail.append(placeholder);
        }
        if (article.video_kind) {
          const badge = document.createElement('span');
          badge.className = 'video-badge';
          badge.setAttribute('aria-hidden', 'true');
          badge.textContent = '▶';
          thumbnail.append(badge);
        }
        item.append(thumbnail);
      }

      const copy = document.createElement('div');
      copy.className = 'news-copy';
      const meta = document.createElement('div');
      meta.className = 'news-meta';
      const category = document.createElement('span');
      category.className = 'tag';
      category.textContent = article.category || '태국 소식';
      const time = document.createElement('time');
      time.dateTime = String(article.published_at || '');
      time.textContent = ictTime(article.published_at);
      const fresh = document.createElement('span');
      fresh.className = 'news-live-tag';
      fresh.textContent = '새 뉴스';
      meta.append(category, time, fresh);

      const heading = document.createElement('h3');
      const link = document.createElement('a');
      const detailHref = detailTemplate.replace('news-placeholder', encodeURIComponent(id));
      const back = view === 'list' && window.location.search
        ? `?from=${encodeURIComponent(window.location.search)}` : '';
      link.href = detailHref + back;
      link.textContent = article.title;
      heading.append(link);

      const summary = document.createElement('p');
      summary.textContent = shortText(article.summary, 160);
      const source = document.createElement('span');
      source.className = 'meta';
      source.textContent = article.source || '';
      copy.append(meta, heading, summary, source);
      item.append(copy);
      return item;
    };

    const queue = (articles, total) => {
      articles.forEach((article) => {
        const id = keyFor(article);
        if (id) pending.set(id, article);
      });
      if (total != null) pendingTotal = total;
      updateButton();
    };

    const poll = async () => {
      if (busy || document.hidden) return;
      busy = true;
      try {
        const response = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('news feed unavailable');
        const payload = await response.json();
        const articles = Array.isArray(payload.results) ? payload.results : [];

        if (!baselineReady) {
          const justPublished = articles.filter((article) => {
            const time = timestamp(article);
            return !seen.has(keyFor(article)) && Number.isFinite(time) && time > cursor;
          });
          articles.forEach((article) => seen.add(keyFor(article)));
          baselineReady = true;
          queue(justPublished, payload.count);
          return;
        }

        const fresh = articles.filter((article) => !seen.has(keyFor(article)));
        articles.forEach((article) => seen.add(keyFor(article)));
        if (fresh.length) queue(fresh, payload.count);
      } catch (_) {
        // A failed background check stays quiet; the next visible-tab poll retries.
      } finally {
        busy = false;
      }
    };

    button.addEventListener('click', () => {
      if (!pending.size) return;
      const arrivals = Array.from(pending.values()).sort((a, b) => timestamp(b) - timestamp(a));
      const existingIds = new Set(Array.from(list.querySelectorAll('[data-news-article]'))
        .map((article) => String(article.dataset.newsId || '')).filter(Boolean));
      const additions = arrivals.filter((article) => !existingIds.has(keyFor(article)));
      list.querySelector('.panel.empty')?.remove();

      for (const article of additions.slice().reverse()) {
        const node = articleNode(article);
        if (!node) continue;
        if (view === 'home') {
          const card = document.createElement('div');
          card.className = 'home-news-card';
          card.append(node);
          list.insertBefore(card, list.firstChild);
        } else {
          list.insertBefore(node, list.firstChild);
        }
        seen.add(keyFor(article));
      }

      const rows = view === 'home'
        ? Array.from(list.children).filter((node) => node.classList.contains('home-news-card'))
        : Array.from(list.children).filter((node) => node.matches('[data-news-article]'));
      if (view === 'home') {
        rows.slice(limit).forEach((node) => node.remove());
        rows.slice(0, limit).forEach((node, index) => node.classList.toggle('is-featured', index === 0));
      }

      if (pendingTotal != null) {
        const count = document.querySelector('[data-news-count]');
        if (count) {
          count.dataset.total = String(pendingTotal);
          count.textContent = view === 'list'
            ? `${list.querySelectorAll('[data-news-article]').length.toLocaleString('ko-KR')} / ${Number(pendingTotal).toLocaleString('ko-KR')}개 기사 표시 중`
            : `${pendingTotal}개 기사 · 1페이지`;
        }
      }
      additions.forEach((article) => {
        const time = timestamp(article);
        if (Number.isFinite(time)) cursor = Math.max(cursor, time);
      });
      pending.clear();
      pendingTotal = null;
      updateButton();

      const first = list.querySelector('[data-news-inserted]');
      if (first) {
        first.scrollIntoView({
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
          block: 'start'
        });
        first.focus({ preventScroll: true });
      }
    });

    poll();
    window.setInterval(poll, 120000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) poll();
    });
  });
})();
