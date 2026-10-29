// Keep subcategory choices and the compact summary aligned with the selected board.
document.querySelectorAll('[data-editor]').forEach(form => {
  const board = form.elements.category;
  const region = form.elements.region;
  const subcategory = form.elements.board_category;
  if (!board || !subcategory) return;
  const heading = document.querySelector('[data-board-heading]');
  const summary = form.querySelector('[data-classification-summary]');
  const titleSuffix = form.dataset.titleSuffix || '';
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
  board.addEventListener('change', sync);
  form.addEventListener('draft:restored', sync);
  region?.addEventListener('change', updateSummary);
  subcategory.addEventListener('change', updateSummary);
  sync();
});
// A list's categories are specific to its original board; reload the filter
// without a stale subcategory when the board changes.
const listBoard = document.querySelector('.filters select[name="category"]');
const listSubcategory = document.querySelector('.filters select[name="board_category"]');
if (listBoard && listSubcategory) listBoard.addEventListener('change', () => { listSubcategory.value = ''; });
