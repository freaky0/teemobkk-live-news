(() => {
  'use strict';
  const form = document.querySelector('form[data-editor]');
  const editor = form?.querySelector('[data-rich-editor]');
  const textarea = editor?.querySelector('textarea[name="body"]');
  if (!form || !editor || !textarea) return;

  const preview = editor.querySelector('[data-editor-preview]');
  const previewButton = editor.querySelector('[data-preview-toggle]');
  const category = form.elements.category;
  const title = form.elements.title;
  const bodyLabel = editor.querySelector('label[for="id_body"]');
  const copy = {
    market: ['상품·거래 내용', '상품 상태, 희망 가격과 거래 방법을 적어 주세요.', '상품명과 상태를 제목에 적어 주세요.'],
    jobs: ['채용·구직 내용', '담당 업무, 근무 지역, 시간과 보상 조건을 적어 주세요.', '직무와 근무 지역을 제목에 적어 주세요.'],
    foodtravel: ['맛집 경험과 메뉴', '장소 분위기, 추천 메뉴, 가격대와 방문 팁을 적어 주세요.', '장소명과 추천 메뉴를 제목에 적어 주세요.'],
    default: ['내용', '상황과 경험을 자세히 적어 주세요.', '제목을 입력해 주세요.'],
  };

  function syncCopy() {
    const [bodyText, bodyPlaceholder, titlePlaceholder] = copy[category?.value] || copy.default;
    if (bodyLabel) bodyLabel.textContent = bodyText;
    textarea.placeholder = bodyPlaceholder;
    if (title) title.placeholder = titlePlaceholder;
  }
  syncCopy();
  category?.addEventListener('change', syncCopy);

  function replaceSelection(text) {
    textarea.setRangeText(text, textarea.selectionStart, textarea.selectionEnd, 'end');
    textarea.focus();
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function wrapSelection(before, after = before, fallback = '내용을 입력하세요') {
    const selected = textarea.value.slice(textarea.selectionStart, textarea.selectionEnd) || fallback;
    replaceSelection(`${before}${selected}${after}`);
  }

  function prefixLines(prefix) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const lineStart = textarea.value.lastIndexOf('\n', Math.max(0, start - 1)) + 1;
    const nextNewline = textarea.value.indexOf('\n', end);
    const lineEnd = nextNewline < 0 ? textarea.value.length : nextNewline;
    const selected = textarea.value.slice(lineStart, lineEnd) || '내용을 입력하세요';
    textarea.setRangeText(selected.split('\n').map(line => `${prefix}${line}`).join('\n'), lineStart, lineEnd, 'select');
    textarea.focus();
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function promptUrl(label) {
    const value = window.prompt(`${label}의 HTTPS 주소를 입력하세요.`);
    if (!value) return '';
    try {
      const url = new URL(value);
      if (url.protocol === 'https:' && !url.username && !url.password) return url.href;
    } catch { /* show a clear prompt below */ }
    window.alert('사용자 정보가 포함되지 않은 HTTPS 주소를 입력해 주세요.');
    return '';
  }

  function insertLink() {
    const url = promptUrl('연결할 링크');
    if (!url) return;
    const label = textarea.value.slice(textarea.selectionStart, textarea.selectionEnd) || '링크 문구';
    replaceSelection(`[${label}](${url})`);
  }

  function insertImage() {
    const url = promptUrl('이미지');
    if (!url) return;
    const alt = window.prompt('이미지를 설명하는 문구를 입력하세요.', '게시글 이미지') || '게시글 이미지';
    replaceSelection(`![${alt}](${url})`);
  }

  function appendText(parent, text) {
    if (text) parent.append(document.createTextNode(text));
  }

  const tokenPattern = /!\[([^\]]*)\]\((https:\/\/[^\s)]+)\)|\[([^\]]+)\]\((https:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|(https:\/\/[^\s<>]+)/g;
  function renderInline(parent, source) {
    const text = source.replace(/&#x20;/gi, ' ').replace(/\\([()[\]:])/g, '$1');
    let cursor = 0;
    for (const match of text.matchAll(tokenPattern)) {
      const index = match.index ?? 0;
      appendText(parent, text.slice(cursor, index));
      const [, alt, imageUrl, label, linkUrl, bold, italic, code, rawUrl] = match;
      let element;
      if (imageUrl) {
        element = document.createElement('img');
        element.src = imageUrl;
        element.alt = alt;
        element.loading = 'lazy';
        element.referrerPolicy = 'no-referrer';
      } else if (linkUrl || rawUrl) {
        const url = linkUrl || rawUrl;
        if (rawUrl && /\.(?:jpe?g|png|gif|webp|avif)(?:[?#]|$)/i.test(rawUrl)) {
          element = document.createElement('img');
          element.src = url;
          element.alt = '';
          element.loading = 'lazy';
          element.referrerPolicy = 'no-referrer';
        } else {
          element = document.createElement('a');
          element.href = url;
          element.rel = 'noopener noreferrer';
          element.target = '_blank';
          element.textContent = label || rawUrl;
        }
      } else if (bold || italic || code) {
        element = document.createElement(code ? 'code' : bold ? 'strong' : 'em');
        element.textContent = bold || italic || code;
      }
      if (element) parent.append(element);
      cursor = index + match[0].length;
    }
    appendText(parent, text.slice(cursor));
  }

  function renderPreview() {
    preview.replaceChildren();
    let paragraph = [];
    let list = null;
    const flushParagraph = () => {
      if (!paragraph.length) return;
      const p = document.createElement('p');
      paragraph.forEach((line, index) => {
        if (index) p.append(document.createElement('br'));
        renderInline(p, line);
      });
      preview.append(p);
      paragraph = [];
    };
    const flushList = () => { if (list) { preview.append(list); list = null; } };

    const source = textarea.value.replace(/\r\n?/g, '\n').replace(/\\[ \t]*\n/g, '\n').replace(/(?<!\\)\\[ \t]*$/gm, '').replace(/\\([()[\]:])/g, '$1').replace(/&#x20;/gi, ' ');
    for (const line of source.split('\n')) {
      if (!line.trim()) { flushParagraph(); flushList(); continue; }
      const bullet = line.match(/^\s*[-*]\s+(.+)$/);
      const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
      if (bullet || numbered) {
        flushParagraph();
        const kind = bullet ? 'ul' : 'ol';
        if (!list || list.tagName.toLowerCase() !== kind) { flushList(); list = document.createElement(kind); }
        const li = document.createElement('li');
        renderInline(li, (bullet || numbered)[1]);
        list.append(li);
        continue;
      }
      flushList();
      const quote = line.match(/^\s*>\s?(.*)$/);
      const heading = line.match(/^\s*(#{1,3})\s+(.+)$/);
      const section = line.match(/^\s*\[([^\]]{2,100})\]\s*$/);
      if (quote || heading || section) {
        flushParagraph();
        const block = document.createElement(quote ? 'blockquote' : `h${heading ? heading[1].length + 1 : 3}`);
        renderInline(block, quote ? quote[1] : heading ? heading[2] : section[1]);
        preview.append(block);
      } else paragraph.push(line);
    }
    flushParagraph();
    flushList();
  }

  editor.querySelectorAll('[data-format]').forEach(button => button.addEventListener('click', () => {
    switch (button.dataset.format) {
      case 'bold': wrapSelection('**'); break;
      case 'italic': wrapSelection('*'); break;
      case 'quote': prefixLines('> '); break;
      case 'list': prefixLines('- '); break;
      case 'link': insertLink(); break;
      case 'image': insertImage(); break;
    }
  }));

  previewButton?.addEventListener('click', () => {
    renderPreview();
    preview.hidden = !preview.hidden;
    previewButton.setAttribute('aria-pressed', String(!preview.hidden));
    previewButton.textContent = preview.hidden ? '미리 보기' : '미리 보기 닫기';
    if (!preview.hidden) preview.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });
  textarea.addEventListener('input', () => { if (!preview.hidden) renderPreview(); });
})();
