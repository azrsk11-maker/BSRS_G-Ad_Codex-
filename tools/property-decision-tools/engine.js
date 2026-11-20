/* Black Swan property scenario arithmetic. No storage, network, tracking or business defaults. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else Object.defineProperty(root, 'BSREPropertyTools', {value: api, configurable: true});
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const MAX_AMOUNT = 100000000000n; // AED 1 billion, expressed in cents, per input.
  const MAX_SAFE = BigInt(Number.MAX_SAFE_INTEGER);
  class InputError extends Error {
    constructor(field, message) { super(message); this.name = 'InputError'; this.field = field; }
  }
  function fail(field, message) { throw new InputError(field, message); }
  function decimal(raw, field, maximum, positive = false) {
    if (typeof raw !== 'string' || !/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(raw) || raw.length > 16)
      fail(field, 'Enter a non-negative number with up to two decimal places; omit separators.');
    const [whole, fraction = ''] = raw.split('.');
    const value = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
    if (value > maximum || (positive && value === 0n)) fail(field, positive ? 'Enter a positive value within the stated limit.' : 'Value exceeds the stated limit.');
    return value;
  }
  const amount = (data, key, positive = false) => decimal(data[key], key, MAX_AMOUNT, positive);
  function signedAmount(data, key) {
    const value = data[key];
    return typeof value === 'string' && value.startsWith('-') ? -decimal(value.slice(1), key, MAX_AMOUNT) : amount(data, key);
  }
  const rate = (data, key) => decimal(data[key], key, 10000n);
  const area = (data, key, positive = false) => decimal(data[key], key, 100000000n, positive);
  function integer(raw, field, min, max) {
    if (typeof raw !== 'string' || !/^(?:0|[1-9]\d*)$/.test(raw) || raw.length > 8) fail(field, 'Enter a whole number.');
    const value = Number(raw);
    if (!Number.isSafeInteger(value) || value < min || value > max) fail(field, `Enter a whole number from ${min} to ${max}.`);
    return BigInt(value);
  }
  const count = (data, key, min, max) => integer(data[key], key, min, max);
  function rounded(numerator, denominator) {
    if (denominator <= 0n) throw new Error('INTERNAL_DENOMINATOR');
    const sign = numerator < 0n ? -1n : 1n;
    const absolute = numerator < 0n ? -numerator : numerator;
    return sign * ((absolute + denominator / 2n) / denominator);
  }
  function number(value) {
    if (value > MAX_SAFE || value < -MAX_SAFE) throw new Error('RESULT_OUT_OF_RANGE');
    return Number(value);
  }
  const row = (label, value, format = 'money') => ({label, value: typeof value === 'bigint' ? number(value) : value, format});
  const result = (rows, notes = [], schedule = undefined) => ({rows, notes, ...(schedule ? {schedule} : {})});
  const max = (a, b) => a > b ? a : b;
  function borrowing(data, price) {
    const loan = amount(data, 'loan_amount');
    if (loan > price) fail('loan_amount', 'Borrowing cannot exceed the entered property price in this model.');
    return loan;
  }
  const calculators = {
    net_yield(data) {
      const price = amount(data, 'purchase_price', true);
      const rent = amount(data, 'annual_rent');
      const costs = amount(data, 'annual_operating_cost');
      const vacancy = rate(data, 'vacancy_percent');
      const basis = price + amount(data, 'acquisition_cost');
      const collectedRent = rounded(rent * (10000n - vacancy), 10000n);
      const net = collectedRent - costs;
      return result([
        row('Scheduled annual rent', rent), row('Rent after assumed vacancy', collectedRent),
        row('Net annual income before financing and tax', net), row('All-in acquisition cost', basis),
        row('Gross yield on purchase price', rounded(rent * 10000n, price), 'percent'),
        row('Net yield on all-in acquisition cost', rounded(net * 10000n, basis), 'percent')
      ], ['Vacancy reduces rent, while entered annual operating costs remain payable. Financing, tax, capital growth and sale costs are excluded.']);
    },
    cash_needed(data) {
      const price = amount(data, 'purchase_price', true);
      const loan = borrowing(data, price);
      const fees = amount(data, 'nonrefundable_cost');
      const deposits = amount(data, 'refundable_deposit');
      const reserve = amount(data, 'cash_reserve');
      const equity = price - loan;
      return result([
        row('Price funded from your cash', equity), row('Nonrefundable acquisition costs', fees),
        row('Refundable deposits tied up', deposits), row('Cash needed to complete', equity + fees + deposits),
        row('Additional reserve retained', reserve), row('Total cash to have available', equity + fees + deposits + reserve)
      ], ['Borrowing is an entered scenario, not financing approval. Refundable deposits are cash tied up rather than expenses. The reserve is not spent by this model.']);
    },
    rent_buy(data) {
      const months = count(data, 'months', 1, 600);
      const price = amount(data, 'purchase_price', true);
      const loan = borrowing(data, price);
      const payment = amount(data, 'monthly_loan_payment');
      const balance = amount(data, 'remaining_loan_balance');
      if (loan === 0n && (payment !== 0n || balance !== 0n)) fail('loan_amount', 'With zero initial borrowing, enter zero loan payments and zero remaining loan balance.');
      const initial = price - loan + amount(data, 'buy_cost');
      const running = rounded(amount(data, 'annual_owner_cost') * months, 12n);
      const saleEquity = amount(data, 'expected_sale_price') - balance - amount(data, 'sell_cost');
      const ownership = initial + payment * months + running - saleEquity;
      const renting = amount(data, 'monthly_rent') * months + amount(data, 'rental_nonrefundable_cost');
      return result([
        row('Initial buyer cash', initial), row('Owner running costs over horizon', running),
        row('Loan payments over horizon', payment * months), row('Expected equity returned at sale', saleEquity),
        row('Modeled net ownership cash cost', ownership), row('Modeled renting cash cost', renting),
        row('Ownership minus renting cash cost', ownership - renting),
        row('Scenario comparison', ownership > renting ? 'Renting has the lower modeled cash cost.' : ownership < renting ? 'Buying has the lower modeled cash cost.' : 'Modeled cash costs are equal.', 'text')
      ], ['Sale value and loan balance are your scenario inputs, not forecasts or realized returns. Loan payments include principal and interest; the remaining balance is deducted only at sale.', 'No discounting, opportunity return, rent escalation, refundable deposits, tax or unentered costs are modeled. A negative ownership cost represents a hypothetical net gain.']);
    },
    offplan_cashflow(data) {
      const price = amount(data, 'purchase_price', true);
      const initial = amount(data, 'available_cash');
      const saving = amount(data, 'monthly_saving');
      const extras = amount(data, 'upfront_cost');
      if (!Array.isArray(data.payments) || data.payments.length < 1 || data.payments.length > 24) fail('payments', 'Enter between one and 24 payment milestones.');
      const payments = data.payments.map((payment, index) => {
        if (!payment || typeof payment !== 'object') fail('payments', 'Enter a month and percentage for every milestone.');
        const month = integer(payment.month, `payments.${index}.month`, 0, 600);
        const percent = decimal(payment.percent, `payments.${index}.percent`, 10000n, true);
        return {month, percent, index};
      }).sort((a, b) => Number(a.month - b.month) || a.index - b.index);
      if (payments.reduce((sum, payment) => sum + payment.percent, 0n) !== 10000n) fail('payments', 'Payment percentages must total exactly 100%.');
      let paid = 0n;
      let cumulativePercent = 0n;
      let shortfall = max(0n, extras - initial);
      const schedule = payments.map(payment => {
        cumulativePercent += payment.percent;
        const cumulativeDue = rounded(price * cumulativePercent, 10000n);
        const due = cumulativeDue - paid;
        paid = cumulativeDue;
        const balance = initial + saving * payment.month - extras - paid;
        shortfall = max(shortfall, -balance);
        return {month: number(payment.month), due: number(due), cumulative: number(paid), balance: number(balance)};
      });
      const finalMonth = payments[payments.length - 1].month;
      return result([
        row('Scheduled property payments', paid), row('Entered upfront costs', extras),
        row('Additional starting cash needed to avoid a shortfall', shortfall),
        row('Cash balance after final milestone', initial + saving * finalMonth - extras - paid)
      ], ['Percentages are your contract scenario. Months are elapsed months from today; month 0 is due now. Monthly saving is available before that month’s milestones.', 'All entered extra costs are due at month 0. Savings earn no return. Interest, delays, income and fees not entered are excluded.'], schedule);
    },
    ready_offplan(data) {
      const months = count(data, 'months', 1, 600);
      const handover = count(data, 'handover_month', 0, 600);
      const readyPrice = amount(data, 'ready_purchase_price', true);
      const offplanPrice = amount(data, 'offplan_purchase_price', true);
      const readyCost = amount(data, 'ready_acquisition_cost') + amount(data, 'ready_sale_cost');
      const offplanCost = amount(data, 'offplan_acquisition_cost') + amount(data, 'offplan_sale_cost');
      const readyRent = rounded(signedAmount(data, 'ready_annual_net_rent') * months, 12n);
      const offplanMonths = max(0n, months - handover);
      const offplanRent = rounded(signedAmount(data, 'offplan_annual_net_rent') * offplanMonths, 12n);
      const readyGain = amount(data, 'ready_expected_sale_price') - readyPrice - readyCost + readyRent;
      const offplanGain = amount(data, 'offplan_expected_sale_price') - offplanPrice - offplanCost + offplanRent;
      return result([
        row('Ready: modeled net rental income', readyRent), row('Ready: hypothetical net gain or loss', readyGain),
        row('Off-plan: income-producing months', offplanMonths, 'integer'), row('Off-plan: modeled net rental income', offplanRent),
        row('Off-plan: hypothetical net gain or loss', offplanGain), row('Off-plan minus ready hypothetical result', offplanGain - readyGain),
        row('Minimum off-plan sale value to match or exceed the ready result', max(0n, offplanPrice + offplanCost - offplanRent + readyGain))
      ], ['This is an unlevered, undiscounted cash scenario. Annual net rent must already deduct vacancy and operating costs. Both scenarios assume sale at the entered horizon, including a possible pre-handover off-plan exit.', 'Expected sale values and handover are assumptions, not verified availability, assignment permission, guaranteed delivery or realized returns. Payment timing, financing, tax and unentered costs are excluded.']);
    },
    rental_movein(data) {
      const rent = amount(data, 'annual_rent');
      const first = amount(data, 'first_rent_payment');
      if (first > rent) fail('first_rent_payment', 'The first rent payment cannot exceed the entered annual rent.');
      const deposits = amount(data, 'security_deposit') + amount(data, 'utility_deposit');
      const fees = amount(data, 'nonrefundable_cost');
      const moving = amount(data, 'moving_cost');
      return result([
        row('First rent payment', first), row('Refundable deposits tied up', deposits),
        row('Nonrefundable fees and moving costs', fees + moving), row('Immediate move-in cash', first + deposits + fees + moving),
        row('Rent still payable in the first year', rent - first), row('First-year rent, fees and moving costs', rent + fees + moving)
      ], ['Enter your actual first payment; no cheque schedule or required deposit rate is assumed. Refundable deposits are excluded from first-year expense totals. Recurring utilities and other costs not entered are excluded.']);
    },
    occupancy_cost(data) {
      const years = count(data, 'years', 1, 50);
      const size = area(data, 'area', true);
      const recurring = amount(data, 'annual_rent') + amount(data, 'annual_service_cost') + amount(data, 'annual_utilities') + amount(data, 'annual_insurance') + amount(data, 'annual_other_cost');
      const fitout = amount(data, 'fitout_cost');
      const deposit = amount(data, 'refundable_deposit');
      const horizon = recurring * years + fitout;
      return result([
        row('Recurring annual occupancy cost', recurring), row('Refundable deposit tied up', deposit),
        row('First-year cash including fit-out and deposit', recurring + fitout + deposit),
        row('Total nonrefundable cost over entered years', horizon),
        row('Effective annual cost including spread fit-out', rounded(horizon, years)),
        row('Effective annual cost per square metre', rounded(horizon * 100n, years * size))
      ], ['All area inputs are square metres. Fit-out cost is spread evenly across the entered years without residual value, depreciation rules, inflation or discounting. Refundable deposits affect initial cash only. Unentered tax and exit/reinstatement costs are excluded.']);
    },
    office_fit(data) {
      const people = count(data, 'people', 1, 10000);
      const perDesk = area(data, 'area_per_person', true);
      const shared = area(data, 'shared_area');
      const circulation = rate(data, 'circulation_percent');
      const available = area(data, 'available_area');
      const base = people * perDesk + shared;
      const required = (base * (10000n + circulation) + 9999n) / 10000n;
      const usableForDesks = max(0n, available * 10000n - shared * (10000n + circulation));
      const capacity = usableForDesks / (perDesk * (10000n + circulation));
      return result([
        row('Desk and shared area before circulation', base, 'area'), row('Planning area including circulation allowance', required, 'area'),
        row('Available area minus planning requirement', available - required, 'area'),
        row('Planning desk capacity at entered assumptions', capacity, 'integer')
      ], ['Use square metres and comparable usable floor areas throughout. Circulation is an added percentage of desk plus shared area. This is a space-planning scenario, not a fire, access, zoning or legal occupancy assessment.']);
    },
    seller_proceeds(data) {
      const price = amount(data, 'sale_price', true);
      const payoff = amount(data, 'loan_payoff');
      const fee = rounded(price * rate(data, 'selling_fee_percent'), 10000n);
      const other = amount(data, 'other_selling_cost');
      return result([
        row('Modeled sale price', price), row('Entered percentage-based selling fee', fee),
        row('Loan payoff and other selling costs', payoff + other), row('Net seller proceeds before unentered costs', price - payoff - fee - other)
      ], ['The fee percentage is supplied by you; it is not a stated brokerage tariff. Negative proceeds mean additional cash is needed. Sale proceeds are neither investment profit nor Black Swan’s collected commission. Tax, purchase basis and other unentered costs are excluded.']);
    },
    landlord_vacancy(data) {
      const rent = amount(data, 'annual_rent');
      const vacancy = decimal(data.vacancy_months, 'vacancy_months', 1200n);
      const fixed = amount(data, 'annual_fixed_cost');
      const letting = amount(data, 'letting_cost');
      const deposit = amount(data, 'tenant_refundable_deposit');
      const received = rounded(rent * (1200n - vacancy), 1200n);
      const net = received - fixed - letting;
      return result([
        row('Rent lost under vacancy assumption', rent - received), row('Modeled annual rent received', received),
        row('Annual costs including letting', fixed + letting), row('Net annual cash before financing and tax', net),
        row('Net monthly equivalent', rounded(net, 12n)), row('Refundable tenant deposit held, excluded from income', deposit)
      ], ['Annual rent assumes a full occupied year, reduced proportionally by the entered vacant months. Fixed costs remain payable; letting cost occurs once in this year. Refundable tenant deposits are liabilities, not rent or profit. Financing, tax, arrears and unentered costs are excluded.']);
    }
  };
  function calculate(tool, data) {
    if (!Object.prototype.hasOwnProperty.call(calculators, tool)) fail('tool', 'Choose a supported property tool.');
    if (!data || typeof data !== 'object' || Array.isArray(data)) fail('inputs', 'Enter the required scenario inputs.');
    return calculators[tool](data);
  }
  return Object.freeze({calculate, InputError, toolIds: Object.freeze(Object.keys(calculators))});
});
