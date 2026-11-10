(function () {
  'use strict';
  const engine = globalThis.BSREPropertyTools;
  if (!engine) return;
  const money = (key, label, signed = false) => ({key, label, kind: signed ? 'signed_money' : 'money'});
  const integer = (key, label, maximum, minimum = 0) => ({key, label, kind: 'integer', maximum, minimum});
  const decimal = (key, label, maximum, kind = 'decimal') => ({key, label, kind, maximum});
  const definitions = {
    net_yield: {title: 'Gross and net rental yield', fields: [money('purchase_price', 'Purchase price'), money('acquisition_cost', 'Additional nonrefundable acquisition costs'), money('annual_rent', 'Annual rent at full occupancy'), money('annual_operating_cost', 'Annual operating costs'), decimal('vacancy_percent', 'Assumed vacancy (%)', 100)]},
    cash_needed: {title: 'Cash needed to purchase', fields: [money('purchase_price', 'Purchase price'), money('loan_amount', 'Borrowing applied to the price'), money('nonrefundable_cost', 'Nonrefundable upfront costs'), money('refundable_deposit', 'Refundable deposits'), money('cash_reserve', 'Additional cash reserve to keep')]},
    rent_buy: {title: 'Rent versus buy cash scenario', fields: [integer('months', 'Comparison horizon (months)', 600, 1), money('monthly_rent', 'Monthly rent'), money('rental_nonrefundable_cost', 'Total nonrefundable rental fees over the horizon'), money('purchase_price', 'Purchase price'), money('loan_amount', 'Initial borrowing applied to the price'), money('buy_cost', 'Nonrefundable buying costs'), money('monthly_loan_payment', 'Monthly loan payment, including principal and interest'), money('annual_owner_cost', 'Annual owner running costs'), money('expected_sale_price', 'Assumed sale price at the end of the horizon'), money('remaining_loan_balance', 'Assumed loan balance at that date'), money('sell_cost', 'Selling costs at that date')]},
    offplan_cashflow: {title: 'Off-plan payment cash flow', fields: [money('purchase_price', 'Purchase price'), money('available_cash', 'Cash available now'), money('monthly_saving', 'Cash added to savings each month'), money('upfront_cost', 'Additional costs payable now')]},
    ready_offplan: {title: 'Ready versus off-plan cash scenario', fields: [integer('months', 'Comparison horizon (months)', 600, 1), integer('handover_month', 'Assumed off-plan handover month from now', 600), money('ready_purchase_price', 'Ready property purchase price'), money('ready_acquisition_cost', 'Ready property acquisition costs'), money('ready_annual_net_rent', 'Ready property annual net rental income or loss after costs and vacancy', true), money('ready_expected_sale_price', 'Ready property assumed sale price at horizon'), money('ready_sale_cost', 'Ready property selling costs'), money('offplan_purchase_price', 'Off-plan purchase price'), money('offplan_acquisition_cost', 'Off-plan acquisition costs'), money('offplan_annual_net_rent', 'Off-plan annual net rental income or loss after costs and vacancy', true), money('offplan_expected_sale_price', 'Off-plan assumed sale price at horizon'), money('offplan_sale_cost', 'Off-plan selling costs')]},
    rental_movein: {title: 'Rental move-in cash', fields: [money('annual_rent', 'Total first-year rent'), money('first_rent_payment', 'Actual first rent payment'), money('security_deposit', 'Refundable security deposit'), money('utility_deposit', 'Refundable utility deposit'), money('nonrefundable_cost', 'Nonrefundable upfront fees'), money('moving_cost', 'Moving costs')]},
    occupancy_cost: {title: 'Commercial occupancy cost', fields: [decimal('area', 'Usable floor area (square metres)', 1000000, 'area'), integer('years', 'Years over which to spread fit-out cost', 50, 1), money('annual_rent', 'Annual rent'), money('annual_service_cost', 'Annual service charges'), money('annual_utilities', 'Annual utilities'), money('annual_insurance', 'Annual insurance'), money('annual_other_cost', 'Other annual occupancy costs'), money('fitout_cost', 'One-off fit-out cost'), money('refundable_deposit', 'Refundable deposit')]},
    office_fit: {title: 'Office space planning', fields: [integer('people', 'Number of people', 10000, 1), decimal('area_per_person', 'Desk area per person (square metres)', 1000000, 'area'), decimal('shared_area', 'Shared area before circulation (square metres)', 1000000, 'area'), decimal('circulation_percent', 'Additional circulation allowance (%)', 100), decimal('available_area', 'Available usable area (square metres)', 1000000, 'area')]},
    seller_proceeds: {title: 'Seller net proceeds', fields: [money('sale_price', 'Assumed sale price'), money('loan_payoff', 'Loan payoff at sale'), decimal('selling_fee_percent', 'Your entered percentage-based selling fee (%)', 100), money('other_selling_cost', 'Other selling costs, including any fee taxes')]},
    landlord_vacancy: {title: 'Landlord vacancy and letting scenario', fields: [money('annual_rent', 'Annual rent at full occupancy'), decimal('vacancy_months', 'Assumed vacant months in this year', 12), money('annual_fixed_cost', 'Annual fixed operating costs'), money('letting_cost', 'Letting cost incurred in this year'), money('tenant_refundable_deposit', 'Refundable tenant deposit held')]}
  };
  function element(tag, text, attributes = {}) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    return node;
  }
  const currencyFormat = new Intl.NumberFormat('en-AE', {style: 'currency', currency: 'AED', minimumFractionDigits: 2, maximumFractionDigits: 2});
  const decimalFormat = new Intl.NumberFormat('en-AE', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  function formatted(value, format) {
    if (format === 'money') return currencyFormat.format(value / 100);
    if (format === 'percent') return `${decimalFormat.format(value / 100)}%`;
    if (format === 'area') return `${decimalFormat.format(value / 100)} m²`;
    if (format === 'integer') return new Intl.NumberFormat('en-AE').format(value);
    return String(value);
  }
  function renderResult(output, answer, title) {
    output.replaceChildren();
    output.hidden = false;
    const heading = element('h3', `${title}: your scenario`, {tabindex: '-1'});
    output.append(heading);
    const list = element('dl', undefined, {class: 'bsre-tools-results'});
    for (const item of answer.rows) list.append(element('dt', item.label), element('dd', formatted(item.value, item.format)));
    output.append(list);
    if (answer.schedule) {
      const table = element('table');
      table.append(element('caption', 'Your payment milestones and funding balance'));
      const head = element('thead');
      const header = element('tr');
      for (const name of ['Elapsed month', 'Payment due', 'Cumulative price paid', 'Cash balance']) header.append(element('th', name, {scope: 'col'}));
      head.append(header);
      const body = element('tbody');
      for (const entry of answer.schedule) {
        const line = element('tr');
        line.append(element('th', String(entry.month), {scope: 'row'}));
        for (const key of ['due', 'cumulative', 'balance']) line.append(element('td', formatted(entry[key], 'money')));
        body.append(line);
      }
      table.append(head, body);
      const scroll = element('div', undefined, {class: 'bsre-tools-table', tabindex: '0', role: 'region', 'aria-label': 'Payment milestone results, scroll horizontally if needed'});
      scroll.append(table);
      output.append(scroll);
    }
    const assumptions = element('ul');
    for (const note of answer.notes) assumptions.append(element('li', note));
    output.append(element('h4', 'What this scenario assumes'), assumptions);
    heading.focus();
  }
  function mount(root) {
    const host = root.querySelector('[data-bsre-tool-mount]');
    if (!host) return;
    const prefix = root.id;
    const selected = root.getAttribute('data-tool') || '';
    if (selected && !Object.prototype.hasOwnProperty.call(definitions, selected)) return;
    host.replaceChildren();
    let selection;
    if (!selected) {
      const label = element('label', 'Choose a property tool', {for: `${prefix}-choice`});
      selection = element('select', undefined, {id: `${prefix}-choice`});
      for (const [id, definition] of Object.entries(definitions)) selection.append(element('option', definition.title, {value: id}));
      host.append(label, selection);
    }
    const content = element('div');
    host.append(content);
    function show(tool) {
      const definition = definitions[tool];
      content.replaceChildren();
      let output;
      let error;
      const inputs = new Map();
      function invalidate() {
        if (output) { output.hidden = true; output.replaceChildren(); }
        if (error) { error.hidden = true; error.textContent = ''; }
        for (const input of inputs.values()) input.removeAttribute('aria-invalid');
      }
      const heading = element('h3', definition.title);
      const hint = element('p', 'All money amounts are in AED. Enter your own figures without separators, with up to two decimal places. Enter 0 for a cost you want to exclude. No fees, returns or property facts are supplied.', {id: `${prefix}-hint`});
      const form = element('form', undefined, {autocomplete: 'off', 'aria-describedby': `${prefix}-hint`});
      const fieldset = element('fieldset');
      fieldset.append(element('legend', 'Your assumptions'));
      const grid = element('div', undefined, {class: 'bsre-tools-fields'});
      function addInput(field, container, fieldKey = field.key) {
        const id = `${prefix}-${fieldKey.replace(/\./g, '-')}`;
        const wrapper = element('div', undefined, {class: 'bsre-tools-field'});
        const label = element('label', field.label, {for: id});
        const limit = field.kind === 'signed_money' ? '-1,000,000,000 to 1,000,000,000 AED; negative means a net loss' : field.kind === 'money' ? '0 to 1,000,000,000 AED' : field.kind === 'integer' ? `${field.minimum} to ${field.maximum}, whole numbers` : `0 to ${field.maximum}, up to two decimals`;
        const input = element('input', undefined, {id, type: 'text', inputmode: field.kind === 'integer' ? 'numeric' : 'decimal', required: 'required', maxlength: '16', 'aria-describedby': `${id}-limit`, autocomplete: 'off'});
        input.addEventListener('input', () => { input.removeAttribute('aria-invalid'); invalidate(); });
        const info = element('small', limit, {id: `${id}-limit`});
        wrapper.append(label, input, info);
        container.append(wrapper);
        inputs.set(fieldKey, input);
        return input;
      }
      for (const field of definition.fields) addInput(field, grid);
      fieldset.append(grid);
      const milestones = [];
      if (tool === 'offplan_cashflow') {
        const group = element('fieldset', undefined, {class: 'bsre-tools-milestones'});
        group.append(element('legend', 'Payment milestones'), element('p', 'Add 1–24 milestones totaling 100%. Month 0 means due now. Months may be entered in any order.'));
        const rows = element('div');
        const add = element('button', 'Add a milestone', {type: 'button'});
        let sequence = 0;
        function addMilestone() {
          if (milestones.length >= 24) return;
          invalidate();
          const index = sequence++;
          const item = element('fieldset');
          const title = element('legend');
          item.append(title);
          const fields = element('div', undefined, {class: 'bsre-tools-fields'});
          const month = addInput(integer('month', 'Elapsed month', 600), fields, `milestone.${index}.month`);
          const percent = addInput(decimal('percent', 'Percentage of price (%)', 100), fields, `milestone.${index}.percent`);
          const remove = element('button', 'Remove milestone', {type: 'button'});
          const entry = {item, title, month, percent, remove};
          remove.addEventListener('click', () => {
            if (milestones.length <= 1) return;
            const at = milestones.indexOf(entry);
            milestones.splice(at, 1);
            inputs.delete(`milestone.${index}.month`);
            inputs.delete(`milestone.${index}.percent`);
            item.remove();
            invalidate();
            renumber();
            add.focus();
          });
          item.append(fields, remove);
          rows.append(item);
          milestones.push(entry);
          renumber();
          return month;
        }
        function renumber() {
          milestones.forEach((entry, index) => {
            entry.title.textContent = `Milestone ${index + 1}`;
            entry.remove.disabled = milestones.length <= 1;
            entry.remove.setAttribute('aria-label', `Remove milestone ${index + 1}`);
          });
          add.disabled = milestones.length >= 24;
        }
        add.addEventListener('click', () => { const input = addMilestone(); if (input) input.focus(); });
        addMilestone();
        addMilestone();
        group.append(rows, add);
        fieldset.append(group);
      }
      error = element('p', undefined, {class: 'bsre-tools-error', role: 'alert', tabindex: '-1'});
      error.hidden = true;
      const submit = element('button', 'Calculate my scenario', {type: 'submit'});
      const reset = element('button', 'Clear my figures', {type: 'button'});
      const actions = element('div', undefined, {class: 'bsre-tools-actions'});
      actions.append(submit, reset);
      output = element('section', undefined, {'aria-label': 'Scenario results', class: 'bsre-tools-output'});
      output.hidden = true;
      form.append(fieldset, error, actions);
      reset.addEventListener('click', () => { show(tool); content.querySelector('input').focus(); });
      form.addEventListener('invalid', invalidate, true);
      form.addEventListener('submit', event => {
        event.preventDefault();
        invalidate();
        error.hidden = true;
        for (const input of inputs.values()) input.removeAttribute('aria-invalid');
        const data = {};
        for (const field of definition.fields) data[field.key] = inputs.get(field.key).value.trim();
        if (tool === 'offplan_cashflow') data.payments = milestones.map(entry => ({month: entry.month.value.trim(), percent: entry.percent.value.trim()}));
        try {
          renderResult(output, engine.calculate(tool, data), definition.title);
        } catch (exception) {
          output.hidden = true;
          output.replaceChildren();
          error.hidden = false;
          error.textContent = exception instanceof engine.InputError ? exception.message : 'This scenario could not be calculated. Check your figures and try again.';
          let target = inputs.get(exception.field);
          const milestoneMatch = /^payments\.(\d+)\.(month|percent)$/.exec(exception.field || '');
          if (milestoneMatch) target = milestones[Number(milestoneMatch[1])]?.[milestoneMatch[2]];
          if (target) { target.setAttribute('aria-invalid', 'true'); target.focus(); }
          else error.focus();
        }
      });
      content.append(heading, hint, form, output);
    }
    if (selection) selection.addEventListener('change', () => show(selection.value));
    show(selected || engine.toolIds[0]);
  }
  for (const root of document.querySelectorAll('[data-bsre-property-tools]')) mount(root);
})();
