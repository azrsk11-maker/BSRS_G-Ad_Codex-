'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const tools = require('./engine.js');

const fixtures = {
  net_yield: {purchase_price: '1000000', acquisition_cost: '50000', annual_rent: '100000', annual_operating_cost: '20000', vacancy_percent: '10'},
  cash_needed: {purchase_price: '1000000', loan_amount: '700000', nonrefundable_cost: '30000', refundable_deposit: '10000', cash_reserve: '50000'},
  rent_buy: {months: '24', monthly_rent: '5000', rental_nonrefundable_cost: '5000', purchase_price: '1000000', loan_amount: '600000', buy_cost: '50000', monthly_loan_payment: '5000', annual_owner_cost: '12000', expected_sale_price: '1100000', remaining_loan_balance: '550000', sell_cost: '25000'},
  offplan_cashflow: {purchase_price: '1000.01', available_cash: '200', monthly_saving: '100', upfront_cost: '10', payments: [{month: '0', percent: '33.33'}, {month: '1', percent: '33.33'}, {month: '2', percent: '33.34'}]},
  ready_offplan: {months: '24', handover_month: '12', ready_purchase_price: '1000000', ready_acquisition_cost: '50000', ready_annual_net_rent: '60000', ready_expected_sale_price: '1100000', ready_sale_cost: '20000', offplan_purchase_price: '900000', offplan_acquisition_cost: '30000', offplan_annual_net_rent: '72000', offplan_expected_sale_price: '1100000', offplan_sale_cost: '20000'},
  rental_movein: {annual_rent: '120000', first_rent_payment: '30000', security_deposit: '6000', utility_deposit: '2000', nonrefundable_cost: '5000', moving_cost: '1000'},
  occupancy_cost: {area: '100', years: '2', annual_rent: '100000', annual_service_cost: '10000', annual_utilities: '6000', annual_insurance: '1000', annual_other_cost: '3000', fitout_cost: '40000', refundable_deposit: '10000'},
  office_fit: {people: '10', area_per_person: '6', shared_area: '20', circulation_percent: '25', available_area: '100'},
  seller_proceeds: {sale_price: '1000000', loan_payoff: '600000', selling_fee_percent: '2', other_selling_cost: '5000'},
  landlord_vacancy: {annual_rent: '120000', vacancy_months: '1.5', annual_fixed_cost: '20000', letting_cost: '5000', tenant_refundable_deposit: '6000'}
};
const calculate = (tool, changes = {}) => tools.calculate(tool, {...fixtures[tool], ...changes});
const values = output => output.rows.map(row => row.value);

test('net yield uses scheduled gross rent and vacancy-adjusted income with distinct denominators', () => {
  assert.deepEqual(values(calculate('net_yield')), [10000000, 9000000, 7000000, 105000000, 1000, 667]);
  assert.equal(calculate('net_yield', {vacancy_percent: '100'}).rows[2].value, -2000000);
});
test('cash required separates reserve, borrowing and refundable deposits', () => {
  assert.deepEqual(values(calculate('cash_needed')), [30000000, 3000000, 1000000, 34000000, 5000000, 39000000]);
});
test('rent versus buy deducts remaining debt from exit equity without counting principal twice', () => {
  const answer = values(calculate('rent_buy'));
  assert.deepEqual(answer.slice(0, 7), [45000000, 2400000, 12000000, 52500000, 6900000, 12500000, -5600000]);
  assert.match(answer[7], /Buying/);
});
test('constant-price all-cash ownership has only entered running and transaction costs', () => {
  const answer = calculate('rent_buy', {loan_amount: '0', monthly_loan_payment: '0', remaining_loan_balance: '0', expected_sale_price: '1000000'});
  assert.equal(answer.rows[4].value, 9900000);
});
test('off-plan cumulative rounding conserves the exact price and identifies peak funding shortfall', () => {
  const answer = calculate('offplan_cashflow');
  assert.deepEqual(answer.schedule.map(row => row.due), [33330, 33331, 33340]);
  assert.deepEqual(answer.schedule.map(row => row.balance), [-14330, -37661, -61001]);
  assert.deepEqual(values(answer), [100001, 1000, 61001, -61001]);
});
test('milestones are sorted without mutating input, and same-month payments share only that month savings', () => {
  const input = {...fixtures.offplan_cashflow, payments: [{month: '2', percent: '40'}, {month: '0', percent: '20'}, {month: '2', percent: '40'}]};
  const before = structuredClone(input);
  const answer = tools.calculate('offplan_cashflow', input);
  assert.deepEqual(input, before);
  assert.deepEqual(answer.schedule.map(row => row.month), [0, 2, 2]);
  assert.equal(answer.schedule[2].balance, -61001);
});
test('off-plan funds must also cover costs at month zero even if all property payments are later', () => {
  const answer = calculate('offplan_cashflow', {purchase_price: '100', available_cash: '0', monthly_saving: '100', upfront_cost: '50', payments: [{month: '1', percent: '100'}]});
  assert.equal(answer.rows[2].value, 5000);
});
test('ready and off-plan scenarios distinguish handover income delay and hypothetical sale value', () => {
  assert.deepEqual(values(calculate('ready_offplan')), [12000000, 15000000, 12, 7200000, 22200000, 7200000, 102800000]);
  const late = calculate('ready_offplan', {handover_month: '30'});
  assert.equal(late.rows[2].value, 0);
  assert.equal(late.rows[3].value, 0);
  assert.match(late.notes.join(' '), /pre-handover/);
});
test('ready/off-plan net rental losses are supported and a non-negative break-even sale floor is explicit', () => {
  const loss = calculate('ready_offplan', {ready_annual_net_rent: '-60000', offplan_annual_net_rent: '-72000'});
  assert.equal(loss.rows[0].value, -12000000);
  assert.equal(loss.rows[3].value, -7200000);
  const floor = calculate('ready_offplan', {ready_expected_sale_price: '0', ready_annual_net_rent: '0'});
  assert.equal(floor.rows[6].value, 0);
});
test('move-in cash includes refundable deposits while first-year expenses exclude them', () => {
  assert.deepEqual(values(calculate('rental_movein')), [3000000, 800000, 600000, 4400000, 9000000, 12600000]);
});
test('commercial occupancy separates deposit from amortized fit-out and per-area cost', () => {
  assert.deepEqual(values(calculate('occupancy_cost')), [12000000, 1000000, 17000000, 28000000, 14000000, 140000]);
});
test('office fit applies circulation once and floors desk capacity conservatively', () => {
  assert.deepEqual(values(calculate('office_fit')), [8000, 10000, 0, 10]);
  assert.equal(calculate('office_fit', {available_area: '99.99'}).rows[3].value, 9);
  assert.equal(calculate('office_fit', {available_area: '5'}).rows[3].value, 0);
  assert.equal(calculate('office_fit', {people: '1', area_per_person: '1', shared_area: '0', circulation_percent: '0.01'}).rows[1].value, 101);
});
test('seller proceeds account for entered fee and preserve cash-shortfall results', () => {
  assert.deepEqual(values(calculate('seller_proceeds')), [100000000, 2000000, 60500000, 37500000]);
  assert.equal(calculate('seller_proceeds', {loan_payoff: '1000000'}).rows[3].value, -2500000);
});
test('landlord vacancy is proportional, with tenant deposit excluded from all income', () => {
  assert.deepEqual(values(calculate('landlord_vacancy')), [1500000, 10500000, 2500000, 8000000, 666667, 600000]);
  assert.equal(calculate('landlord_vacancy', {vacancy_months: '12'}).rows[3].value, -2500000);
});
test('refundable deposits never inflate expense or rent yields', () => {
  const rental = calculate('rental_movein', {security_deposit: '1000000'});
  assert.equal(rental.rows[5].value, calculate('rental_movein').rows[5].value);
  const landlord = calculate('landlord_vacancy', {tenant_refundable_deposit: '1000000'});
  assert.equal(landlord.rows[3].value, calculate('landlord_vacancy').rows[3].value);
  const office = calculate('occupancy_cost', {refundable_deposit: '1000000'});
  assert.equal(office.rows[4].value, calculate('occupancy_cost').rows[4].value);
});
test('zero, full vacancy and cent-level inputs use deterministic half-up currency rounding', () => {
  const answer = calculate('net_yield', {purchase_price: '1', acquisition_cost: '0', annual_rent: '0.01', annual_operating_cost: '0', vacancy_percent: '50'});
  assert.equal(answer.rows[1].value, 1);
  const negative = calculate('net_yield', {purchase_price: '2', acquisition_cost: '0', annual_rent: '0', annual_operating_cost: '0.01', vacancy_percent: '0'});
  assert.equal(negative.rows[5].value, -50);
});
test('payment allocations conserve cents across varied prices and uneven percentage schedules', () => {
  for (let cents = 1; cents <= 300; cents += 7) {
    const price = `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
    const answer = calculate('offplan_cashflow', {purchase_price: price});
    assert.equal(answer.schedule.reduce((total, row) => total + row.due, 0), cents);
    assert.equal(answer.schedule.at(-1).cumulative, cents);
    assert.ok(answer.schedule.every(row => row.due >= 0));
  }
});
test('all tools are pure and return safe numeric output at stated maximum bounds', () => {
  assert.equal(tools.toolIds.length, 10);
  for (const id of tools.toolIds) {
    const original = structuredClone(fixtures[id]);
    assert.deepEqual(calculate(id), calculate(id));
    assert.deepEqual(fixtures[id], original);
  }
  const answer = calculate('rent_buy', {months: '600', monthly_rent: '1000000000', annual_owner_cost: '1000000000', monthly_loan_payment: '1000000000'});
  assert.ok(answer.rows.filter(row => typeof row.value === 'number').every(row => Number.isSafeInteger(row.value)));
});
test('invalid or ambiguous number syntax is rejected instead of silently coerced', () => {
  for (const value of ['', ' ', '-1', '+1', '1e6', '1,000', '1.234', 'NaN', 'Infinity', '0x10', '.5', '01', 100, null, '1000000000.01', '<script>']) {
    assert.throws(() => calculate('seller_proceeds', {sale_price: value}), tools.InputError, String(value));
  }
});
test('positive denominators, bounded rates and whole-number time inputs are enforced', () => {
  for (const [id, changes] of [['net_yield', {purchase_price: '0'}], ['occupancy_cost', {area: '0'}], ['office_fit', {area_per_person: '0'}], ['net_yield', {vacancy_percent: '100.01'}], ['landlord_vacancy', {vacancy_months: '12.01'}], ['rent_buy', {months: '1.5'}], ['rent_buy', {months: '601'}]]) {
    assert.throws(() => calculate(id, changes), tools.InputError);
  }
});
test('inconsistent loan, rent and payment schedule inputs fail with field-specific errors', () => {
  for (const [id, changes, field] of [
    ['cash_needed', {loan_amount: '1000001'}, 'loan_amount'],
    ['rent_buy', {loan_amount: '0'}, 'loan_amount'],
    ['rental_movein', {first_rent_payment: '120001'}, 'first_rent_payment'],
    ['offplan_cashflow', {payments: [{month: '0', percent: '99.99'}]}, 'payments'],
    ['offplan_cashflow', {payments: []}, 'payments'],
    ['offplan_cashflow', {payments: Array(25).fill({month: '0', percent: '4'})}, 'payments'],
    ['offplan_cashflow', {payments: [{month: '0', percent: '0'}, {month: '1', percent: '100'}]}, 'payments.0.percent'],
    ['offplan_cashflow', {payments: [{month: '601', percent: '100'}]}, 'payments.0.month']
  ]) assert.throws(() => calculate(id, changes), error => error instanceof tools.InputError && error.field === field);
});
test('unknown tool and invalid input shape cannot select inherited methods', () => {
  for (const id of ['constructor', '__proto__', 'toString', 'unknown']) assert.throws(() => tools.calculate(id, {}), tools.InputError);
  for (const input of [null, [], 'inputs']) assert.throws(() => tools.calculate('net_yield', input), tools.InputError);
});

