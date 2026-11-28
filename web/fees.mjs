const field = id => document.getElementById(id);
const format = new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' });

function calculate() {
  const choice = field('registry').selectedOptions[0];
  const named = field('kind').value === 'word';
  const quoted = named && choice.dataset.name === '';
  let total = Number(choice.dataset.filing) + (named ? Number(choice.dataset.name) : 0);
  field('quote-label').hidden = !quoted;
  const quote = field('quote').value.trim();
  if (quoted && !quote) {
    field('fee-answer').textContent = format.format(total / 100) + ' filing fee, plus your supplier’s name search quote.';
    return;
  }
  if (quoted) {
    if (!/^\d{1,7}(\.\d{1,2})?$/.test(quote)) {
      field('fee-answer').textContent = 'Enter the quoted amount in dollars with up to two decimal places.';
      return;
    }
    const [whole, fraction = ''] = quote.split('.');
    total += Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  }
  field('fee-answer').textContent = format.format(total / 100) + ' for the basic filing and any selected name search.';
}
for (const id of ['registry', 'kind', 'quote']) field(id).addEventListener('input', calculate);
calculate();
