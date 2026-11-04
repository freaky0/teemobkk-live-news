(() => {
  const list = document.querySelector("#news-list");
  const more = document.querySelector("#news-load-more");
  const count = document.querySelector("#news-count");
  const status = document.querySelector("#news-load-status");
  const topButton = document.querySelector("#news-back-to-top");
  if (!list) return;

  let loading = false;
  const moreLabel = more?.dataset.label || more?.textContent.trim() || "더 보기";

  const articleKey = (article, baseUrl = window.location.href) => {
    if (article.dataset.newsId) return String(article.dataset.newsId);
    const link = article.querySelector(".news-copy h3 a, h3 a");
    if (!link) return article.textContent.trim();
    try {
      return new URL(link.getAttribute("href"), baseUrl).pathname;
    } catch (_error) {
      return link.getAttribute("href") || article.textContent.trim();
    }
  };

  if (more) {
    more.addEventListener("click", async event => {
      event.preventDefault();
      if (loading) return;
      loading = true;
      more.setAttribute("aria-busy", "true");
      more.setAttribute("aria-disabled", "true");
      more.textContent = "불러오는 중…";

      try {
        const response = await fetch(more.href, {
          credentials: "same-origin",
          cache: "no-store",
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) throw new Error(`News request failed (${response.status})`);

        const documentText = await response.text();
        const nextDocument = new DOMParser().parseFromString(documentText, "text/html");
        const nextList = nextDocument.querySelector("#news-list");
        if (!nextList) throw new Error("News list was missing from the response");

        const responseUrl = response.url || more.href;
        const existing = new Set(
          Array.from(list.querySelectorAll(":scope > .news-item"), article => articleKey(article)),
        );
        const fragment = document.createDocumentFragment();
        let added = 0;
        for (const article of nextList.querySelectorAll(":scope > .news-item")) {
          const key = articleKey(article, responseUrl);
          if (existing.has(key)) continue;
          existing.add(key);
          fragment.append(article.cloneNode(true));
          added += 1;
        }
        list.append(fragment);

        const nextMore = nextDocument.querySelector("#news-load-more");
        if (nextMore) {
          more.href = new URL(nextMore.getAttribute("href"), responseUrl).href;
          more.textContent = moreLabel;
          more.removeAttribute("aria-disabled");
        } else {
          more.remove();
        }

        const loaded = list.querySelectorAll(":scope > .news-item").length;
        const total = Number(count?.dataset.total || 0);
        if (count) {
          count.textContent = total
            ? `${loaded.toLocaleString("ko-KR")} / ${total.toLocaleString("ko-KR")}개 기사 표시 중`
            : `${loaded.toLocaleString("ko-KR")}개 기사 표시 중`;
        }
        if (status) status.textContent = `${added}개 기사를 목록 아래에 추가했습니다.`;
      } catch (_error) {
        more.textContent = "다시 시도";
        more.removeAttribute("aria-disabled");
        if (status) status.textContent = "뉴스를 불러오지 못했습니다. 다시 시도해 주세요.";
      } finally {
        loading = false;
        if (more.isConnected) more.removeAttribute("aria-busy");
      }
    });
  }

  if (topButton) {
    const updateTopButton = () => {
      topButton.hidden = window.scrollY < 400;
    };
    window.addEventListener("scroll", updateTopButton, { passive: true });
    updateTopButton();
    topButton.addEventListener("click", () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
    });
  }
})();
