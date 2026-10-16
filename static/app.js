document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('scan-form');
  const input = document.getElementById('payload');
  if (form && input) {
    input.focus();
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        form.submit();
      }
    });
  }
  const mode = document.getElementById('create_mode');
  const range = document.getElementById('range-fields');
  const single = document.getElementById('single-field');
  if (mode && range && single) {
    const update = () => { const isRange = mode.value === 'range'; range.hidden = !isRange; single.hidden = isRange; };
    mode.addEventListener('change', update); update();
  }
});

