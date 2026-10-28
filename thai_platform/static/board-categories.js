// Keep subcategory choices aligned with the selected board in the editor.
document.querySelectorAll('[data-editor]').forEach(form => {
  const board = form.elements.category;
  const subcategory = form.elements.board_category;
  if (!board || !subcategory) return;
  const sync = () => {
    const current = ['housing', 'banking'].includes(board.value) ? 'living' : board.value;
    for (const group of subcategory.querySelectorAll('optgroup')) {
      group.hidden = group.label !== current;
      group.disabled = group.hidden;
    }
    const selected = subcategory.selectedOptions[0];
    if (selected && selected.parentElement.disabled) subcategory.value = '';
  };
  board.addEventListener('change', sync);
  sync();
});
// A list's categories are specific to its original board; reload the filter
// without a stale subcategory when the board changes.
const listBoard = document.querySelector('.filters select[name="category"]');
const listSubcategory = document.querySelector('.filters select[name="board_category"]');
if (listBoard && listSubcategory) listBoard.addEventListener('change', () => { listSubcategory.value = ''; });
