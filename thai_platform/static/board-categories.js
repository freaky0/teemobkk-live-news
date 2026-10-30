// Keep subcategory choices and the compact summary aligned with the selected board.
document.querySelectorAll('[data-editor]').forEach(form => {
  const board = form.elements.category;
  const region = form.elements.region;
  const subcategory = form.elements.board_category;
  if (!board || !subcategory) return;
  const heading = document.querySelector('[data-board-heading]');
  const summary = form.querySelector('[data-classification-summary]');
  const titleSuffix = form.dataset.titleSuffix || '';
  const guideScript = form.querySelector('#board-guides-data');
  let guides = {};
  try { guides = guideScript ? JSON.parse(guideScript.textContent) : {}; } catch (_) { guides = {}; }
  const guideTitle = form.querySelector('[data-editor-guide-title]');
  const guideDescription = form.querySelector('[data-editor-guide-description]');
  const guideTips = form.querySelector('[data-editor-guide-tips]');
  const updateGuide = () => {
    const guide = guides[board.value] || guides.questions;
    if (!guide) return;
    if (guideTitle) guideTitle.textContent = guide.title;
    if (guideDescription) guideDescription.textContent = guide.description;
    if (guideTips) {
      guideTips.replaceChildren(...(guide.tips || []).map(text => {
        const item = document.createElement('li');
        item.textContent = text;
        return item;
      }));
    }
  };
  const updateSummary = () => {
    const boardLabel = board.value
      ? board.selectedOptions[0]?.textContent.trim() || '게시판'
      : heading?.textContent.trim() || '게시판';
    const regionLabel = region?.selectedOptions[0]?.textContent.trim() || '지역 선택';
    const subcategoryLabel = subcategory.value
      ? subcategory.selectedOptions[0]?.textContent.trim()
      : '세부 분류 없음';
    if (heading) heading.textContent = boardLabel;
    document.title = `${boardLabel}${titleSuffix}`;
    if (summary) summary.textContent = `${boardLabel} · ${regionLabel} · ${subcategoryLabel}`;
  };
  const sync = () => {
    const current = ['housing', 'banking'].includes(board.value) ? 'living' : board.value;
    for (const group of subcategory.querySelectorAll('optgroup')) {
      group.hidden = group.label !== current;
      group.disabled = group.hidden;
    }
    const selected = subcategory.selectedOptions[0];
    if (selected && selected.parentElement.disabled) subcategory.value = '';
    updateSummary();
  };
  board.addEventListener('change', () => { sync(); updateGuide(); });
  form.addEventListener('draft:restored', () => { sync(); updateGuide(); });
  region?.addEventListener('change', updateSummary);
  subcategory.addEventListener('change', updateSummary);
  sync();
  updateGuide();
});
// A list's categories are specific to its original board; reload the filter
// without a stale subcategory when the board changes.
const listBoard = document.querySelector('.filters select[name="category"]');
const listSubcategory = document.querySelector('.filters select[name="board_category"]');
if (listBoard && listSubcategory) listBoard.addEventListener('change', () => { listSubcategory.value = ''; });
