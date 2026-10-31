(() => {
  'use strict';

  const form = document.querySelector('form[data-editor]');
  const editorField = form?.querySelector('[data-rich-editor]');
  const textarea = editorField?.querySelector('textarea[name="body"]');
  if (!form || !editorField || !textarea || !window.EasyMDE) return;

  const status = editorField.querySelector('[data-inline-image-status]');
  const category = form.elements.category;
  const title = form.elements.title;
  const bodyLabel = editorField.querySelector('label[for="id_body"]');
  const uploadInput = form.querySelector('input[type="file"][name="image_uploads"]');
  const imageUrlsInput = form.querySelector('textarea[name="image_urls"]');
  const dialog = document.querySelector('[data-editor-insert-dialog]');
  const dialogForm = dialog?.querySelector('[data-editor-insert-form]');
  const dialogUrl = dialog?.querySelector('[name="url"]');
  const dialogLabel = dialog?.querySelector('[name="label"]');
  const copy = {
    market: ['상품·거래 내용', '상품 상태, 희망 가격과 거래 방법을 적어 주세요.', '상품명과 상태를 제목에 적어 주세요.'],
    jobs: ['채용·구직 내용', '담당 업무, 근무 지역, 시간과 보상 조건을 적어 주세요.', '직무와 근무 지역을 제목에 적어 주세요.'],
    foodtravel: ['맛집 경험과 메뉴', '장소 분위기, 추천 메뉴, 가격대와 방문 팁을 적어 주세요.', '장소명과 추천 메뉴를 제목에 적어 주세요.'],
    default: ['내용', '상황과 경험을 자세히 적어 주세요.', '제목을 입력해 주세요.'],
  };
  const MAX_IMAGES = 5;
  const MAX_FILE_BYTES = 5 * 1024 * 1024;
  const imageFiles = Array.from(uploadInput?.files || []);
  const imagePreviewUrls = new Map();
  let editor;
  let pendingInsert = null;
  let updatingFileInput = false;

  function setStatus(message) {
    if (status) status.textContent = message;
  }

  function usedImageCount() {
    const existing = form.querySelectorAll('.existing-image').length;
    const removed = form.querySelectorAll('.existing-image input[name="remove_image_ids"]:checked').length;
    const external = (imageUrlsInput?.value || '').split(/\r?\n/).filter(line => line.trim()).length;
    return existing - removed + imageFiles.length + external;
  }

  function syncFileInput() {
    if (!uploadInput || !window.DataTransfer) return false;
    try {
      const transfer = new DataTransfer();
      imageFiles.forEach(file => transfer.items.add(file));
      updatingFileInput = true;
      uploadInput.files = transfer.files;
      uploadInput.dispatchEvent(new Event('change', { bubbles: true }));
      updatingFileInput = false;
      return true;
    } catch {
      updatingFileInput = false;
      return false;
    }
  }

  function validateImage(file) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return 'JPG, PNG, WebP 사진만 본문에 넣을 수 있어요.';
    if (file.size > MAX_FILE_BYTES) return '사진 한 장은 5MB 이하여야 해요.';
    if (usedImageCount() >= MAX_IMAGES) return '게시글 사진은 최대 5장까지 올릴 수 있어요. 기존 사진이나 링크를 줄여 주세요.';
    return '';
  }

  function addInlineImage(file, onSuccess, onError) {
    const error = validateImage(file);
    if (error) {
      setStatus(error);
      onError(error);
      return;
    }
    imageFiles.push(file);
    if (!syncFileInput()) {
      imageFiles.pop();
      const message = '이 브라우저에서는 사진을 첨부할 수 없어요. 최신 Chrome 또는 Edge에서 다시 시도해 주세요.';
      setStatus(message);
      onError(message);
      return;
    }
    const marker = `teemobkk-upload:${imageFiles.length - 1}.png`;
    imagePreviewUrls.set(marker, URL.createObjectURL(file));
    onSuccess(marker);
    setStatus(`${file.name || '사진'}을 본문에 넣었습니다. 저장하면 게시글에 함께 업로드됩니다.`);
  }

  function setFileInputFromSelection() {
    if (!uploadInput || updatingFileInput) return;
    const selected = Array.from(uploadInput.files || []);
    const newlyAdded = selected.filter(file => !imageFiles.includes(file));
    for (const file of newlyAdded) {
      const error = validateImage(file);
      if (error) {
        setStatus(error);
        continue;
      }
      imageFiles.push(file);
    }
    if (newlyAdded.length) syncFileInput();
    if (newlyAdded.length && imageFiles.length) {
      setStatus(`사진 ${imageFiles.length}장을 글 아래 사진 모음에 첨부했습니다. 본문에 넣으려면 사진을 도구 모음에서 추가해 주세요.`);
    }
  }

  function syncBoardCopy() {
    const [bodyText, bodyPlaceholder, titlePlaceholder] = copy[category?.value] || copy.default;
    if (bodyLabel) bodyLabel.textContent = bodyText;
    textarea.placeholder = bodyPlaceholder;
    if (title) title.placeholder = titlePlaceholder;
    if (editor) editor.codemirror.setOption('placeholder', bodyPlaceholder);
  }

  function safeWebUrl(value) {
    try {
      const url = new URL(value, window.location.href);
      if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) return url.href;
    } catch { /* invalid or unsafe URL */ }
    return '';
  }

  function markdownUrl(value) {
    return value.replace(/\)/g, '%29');
  }

  const internalImagePath = /^\/(?:[A-Za-z0-9_-]+\/)*community\/images\/[1-9]\d*\/$/;
  const inlinePattern = /~~([^~]+)~~|!\[([^\]]*)\]\((teemobkk-upload:\d+\.png|https?:\/\/[^\s)]+|\/(?:[A-Za-z0-9_-]+\/)*community\/images\/[1-9]\d*\/)\)|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|(https?:\/\/[^\s<>]+)/g;

  function safeImageUrl(value) {
    if (internalImagePath.test(value)) return new URL(value, window.location.href).href;
    return safeWebUrl(value);
  }

  function renderInline(parent, line) {
    const text = line.replace(/\\([()[\]:])/g, '$1');
    let cursor = 0;
    for (const match of text.matchAll(inlinePattern)) {
      const index = match.index ?? 0;
      if (index > cursor) parent.append(document.createTextNode(text.slice(cursor, index)));
      const [, strike, alt, imageSource, linkLabel, linkSource, bold, italic, code, rawUrl] = match;
      let element;
      if (imageSource) {
        const src = imagePreviewUrls.get(imageSource) || safeImageUrl(imageSource);
        if (src) {
          element = document.createElement('img');
          element.src = src;
          element.alt = alt || '';
          element.loading = 'lazy';
          element.referrerPolicy = 'no-referrer';
        }
      } else if (linkSource) {
        const href = safeWebUrl(linkSource);
        if (href) {
          element = document.createElement('a');
          element.href = href;
          element.rel = 'noopener noreferrer';
          element.target = '_blank';
          element.textContent = linkLabel;
        }
      } else if (strike || bold || italic || code) {
        element = document.createElement(strike ? 'del' : code ? 'code' : bold ? 'strong' : 'em');
        element.textContent = strike || bold || italic || code;
      } else {
        const href = safeWebUrl(rawUrl);
        if (href && /\.(?:jpe?g|png|gif|webp|avif)(?:[?#]|$)/i.test(href)) {
          element = document.createElement('img');
          element.src = href;
          element.alt = '';
          element.loading = 'lazy';
          element.referrerPolicy = 'no-referrer';
        } else if (href) {
          element = document.createElement('a');
          element.href = href;
          element.rel = 'noopener noreferrer';
          element.target = '_blank';
          element.textContent = rawUrl;
        }
      }
      if (element) parent.append(element);
      else parent.append(document.createTextNode(match[0]));
      cursor = index + match[0].length;
    }
    if (cursor < text.length) parent.append(document.createTextNode(text.slice(cursor)));
  }

  function renderMarkdownPreview(value) {
    const container = document.createElement('div');
    const source = String(value || '').replace(/\r\n?/g, '\n').replace(/\\[ \t]*\n/g, '\n').replace(/(?<!\\)\\[ \t]*$/gm, '');
    let paragraph = [];
    let list = null;
    const flushParagraph = () => {
      if (!paragraph.length) return;
      const p = document.createElement('p');
      paragraph.forEach((line, index) => {
        if (index) p.append(document.createElement('br'));
        renderInline(p, line);
      });
      container.append(p);
      paragraph = [];
    };
    const flushList = () => {
      if (list) container.append(list);
      list = null;
    };

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
        container.append(block);
      } else paragraph.push(line);
    }
    flushParagraph();
    flushList();
    return container.innerHTML;
  }

  function openInsertDialog(instance, mode) {
    if (!dialog || !dialogForm || !dialogUrl || !dialogLabel) return;
    const selectedText = instance.codemirror.getSelection();
    dialog.dataset.mode = mode;
    dialog.querySelector('[data-editor-insert-title]').textContent = mode === 'image' ? '본문에 이미지 주소 삽입' : '본문에 링크 삽입';
    dialog.querySelector('[data-insert-label-caption]').textContent = mode === 'image' ? '이미지 설명' : '표시할 문구';
    dialogLabel.value = selectedText;
    dialogLabel.placeholder = mode === 'image' ? '예: 추천 메뉴 사진' : '선택한 글자 또는 링크 문구';
    dialogUrl.value = '';
    pendingInsert = { instance, mode, selectedText };
    dialog.showModal();
    dialogUrl.focus();
  }

  function toolbarButton(name, title, action) {
    return { name, title, action, className: `tb-icon tb-${name}`, attributes: { 'aria-label': title } };
  }

  const toolbar = [
    toolbarButton('undo', '실행 취소', EasyMDE.undo),
    toolbarButton('redo', '다시 실행', EasyMDE.redo),
    '|',
    toolbarButton('bold', '굵게', EasyMDE.toggleBold),
    toolbarButton('italic', '기울임', EasyMDE.toggleItalic),
    toolbarButton('strikethrough', '취소선', EasyMDE.toggleStrikethrough),
    toolbarButton('heading', '제목 단계', EasyMDE.toggleHeadingSmaller),
    '|',
    toolbarButton('quote', '인용문', EasyMDE.toggleBlockquote),
    toolbarButton('unordered-list', '글머리 기호', EasyMDE.toggleUnorderedList),
    toolbarButton('ordered-list', '번호 목록', EasyMDE.toggleOrderedList),
    '|',
    toolbarButton('link', '링크 주소 삽입', instance => openInsertDialog(instance, 'link')),
    toolbarButton('image', '이미지 주소 삽입', instance => openInsertDialog(instance, 'image')),
    toolbarButton('upload-image', '사진 업로드 후 본문에 삽입', EasyMDE.drawUploadedImage),
    toolbarButton('preview', '미리 보기', EasyMDE.togglePreview),
    toolbarButton('side-by-side', '편집과 미리 보기 나란히 보기', EasyMDE.toggleSideBySide),
    toolbarButton('fullscreen', '편집기 크게 보기', EasyMDE.toggleFullScreen),
  ];

  syncBoardCopy();
  editor = new EasyMDE({
    element: textarea,
    autoDownloadFontAwesome: false,
    autosave: { enabled: false },
    spellChecker: false,
    nativeSpellcheck: true,
    status: false,
    autofocus: false,
    placeholder: textarea.placeholder,
    toolbar,
    toolbarTips: true,
    toolbarButtonClassPrefix: 'teemo',
    renderingConfig: { singleLineBreaks: true },
    previewRender: renderMarkdownPreview,
    previewImagesInEditor: true,
    imagesPreviewHandler: source => imagePreviewUrls.get(source) || safeImageUrl(source) || '',
    uploadImage: true,
    imageMaxSize: MAX_FILE_BYTES,
    imageAccept: 'image/jpeg,image/png,image/webp',
    imageUploadFunction: addInlineImage,
    imageTexts: {
      sbInit: '사진을 붙여넣거나 끌어 놓아 본문에 추가하세요.',
      sbOnDragEnter: '사진을 놓으면 커서 위치에 들어갑니다.',
      sbOnDrop: '사진을 처리하고 있습니다.',
      sbOnUploaded: '#image_name#을 본문에 넣었습니다.',
    },
    errorCallback: setStatus,
  });
  editor.codemirror.on('change', () => editor.codemirror.save());
  editor.codemirror.save();
  syncBoardCopy();
  category?.addEventListener('change', syncBoardCopy);
  uploadInput?.addEventListener('change', setFileInputFromSelection);
  imageUrlsInput?.addEventListener('input', () => {
    const count = usedImageCount();
    if (count > MAX_IMAGES) setStatus(`사진이 ${count}장 선택되어 있어요. 저장하려면 최대 ${MAX_IMAGES}장으로 줄여 주세요.`);
  });
  form.querySelectorAll('.existing-image input[name="remove_image_ids"]').forEach(input => input.addEventListener('change', () => {
    if (usedImageCount() < MAX_IMAGES) setStatus('사진을 추가할 수 있어요.');
  }));

  dialogForm?.addEventListener('submit', event => {
    event.preventDefault();
    if (!pendingInsert) return;
    let url;
    try {
      url = new URL(dialogUrl.value);
      if (url.protocol !== 'https:' || url.username || url.password) throw new Error('invalid URL');
    } catch {
      setStatus('사용자 정보가 포함되지 않은 HTTPS 주소를 입력해 주세요.');
      dialogUrl.focus();
      return;
    }
    const { instance, mode, selectedText } = pendingInsert;
    const label = dialogLabel.value.trim();
    const safeLabel = (label || selectedText || (mode === 'image' ? '게시글 사진' : url.hostname)).replace(/[\[\]]/g, '');
    const markdown = mode === 'image'
      ? `![${safeLabel}](${markdownUrl(url.href)})`
      : `[${safeLabel}](${markdownUrl(url.href)})`;
    instance.codemirror.replaceSelection(markdown);
    instance.codemirror.focus();
    pendingInsert = null;
    dialog.close();
  });
  dialog?.querySelector('[data-editor-insert-cancel]')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('close', () => { pendingInsert = null; });
})();
