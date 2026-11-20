'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const engine = require('./engine.js');
const source = fs.readFileSync(path.join(__dirname, 'ui.js'), 'utf8');

// Event/DOM double exercises real UI handlers; it does not claim browser/layout acceptance.
class Element {
  constructor(tag, document) { this.tagName = tag; this.document = document; this.attributes = new Map(); this.children = []; this.listeners = new Map(); this.hidden = false; this.disabled = false; this._text = ''; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  get id() { return this.getAttribute('id') || ''; }
  get value() { return this._value ?? (this.tagName === 'select' ? this.children[0]?.getAttribute('value') || '' : ''); }
  set value(value) { this._value = String(value); }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set textContent(text) { this._text = String(text); this.replaceChildren(); }
  append(...nodes) { for (const node of nodes) { node.parent = this; this.children.push(node); } }
  replaceChildren(...nodes) { for (const child of this.children) child.parent = null; this.children = []; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; }
  matches(selector) {
    const attribute = /^\[([^=\]]+)(?:="([^"]*)")?\]$/.exec(selector);
    if (attribute) return this.attributes.has(attribute[1]) && (attribute[2] === undefined || this.getAttribute(attribute[1]) === attribute[2]);
    return this.tagName === selector;
  }
  querySelectorAll(selector) { const out = []; for (const child of this.children) { if (child.matches(selector)) out.push(child); out.push(...child.querySelectorAll(selector)); } return out; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  addEventListener(type, handler, capture = false) { if (!this.listeners.has(type)) this.listeners.set(type, []); this.listeners.get(type).push({handler, capture}); }
  dispatch(type, bubbles = true) {
    const event = {type, target: this, prevented: false, preventDefault() { this.prevented = true; }};
    const ancestors = []; for (let node = this.parent; node; node = node.parent) ancestors.push(node);
    const invoke = (node, capture) => { for (const listener of node.listeners.get(type) || []) if (listener.capture === capture) listener.handler(event); };
    for (const node of [...ancestors].reverse()) invoke(node, true);
    invoke(this, true); invoke(this, false);
    if (bubbles) for (const node of ancestors) invoke(node, false);
    return event;
  }
  requestSubmit() {
    let valid = true;
    for (const input of this.querySelectorAll('input')) if (input.getAttribute('required') !== null && input.value === '') { valid = false; input.dispatch('invalid', false); }
    return valid ? this.dispatch('submit') : null;
  }
  focus() { this.document.activeElement = this; }
}
function setup(tool = '') {
  const document = {activeElement: null, createElement(tag) { return new Element(tag, this); }};
  const root = document.createElement('section');
  root.setAttribute('id', 'synthetic-tool-1'); root.setAttribute('data-bsre-property-tools', ''); root.setAttribute('data-tool', tool);
  const mount = document.createElement('div'); mount.setAttribute('data-bsre-tool-mount', ''); root.append(mount);
  document.querySelectorAll = selector => root.matches(selector) ? [root] : [];
  const calls = [];
  const forbidden = name => () => { calls.push(name); throw new Error('UNEXPECTED_SIDE_EFFECT'); };
  const sandbox = {document, BSREPropertyTools: engine, Intl, fetch: forbidden('fetch'), XMLHttpRequest: forbidden('xhr'), navigator: {sendBeacon: forbidden('beacon')}, localStorage: new Proxy({}, {get: forbidden('localStorage')}), sessionStorage: new Proxy({}, {get: forbidden('sessionStorage')}), dataLayer: new Proxy([], {get: forbidden('dataLayer')})};
  vm.runInNewContext(source, sandbox);
  const input = key => root.querySelectorAll('input').find(node => node.id.endsWith(`-${key}`));
  const fill = values => { for (const [key, value] of Object.entries(values)) { const node = input(key); assert.ok(node, `Missing input ${key}`); node.value = value; node.dispatch('input'); } };
  const output = () => root.querySelector('[aria-label="Scenario results"]');
  return {document, root, input, fill, output, calls};
}
const yieldInputs = {purchase_price: '1000000', acquisition_cost: '50000', annual_rent: '100000', annual_operating_cost: '20000', vacancy_percent: '10'};

test('the UI offers all ten tools with labelled required inputs and no submission names', () => {
  const {root} = setup();
  assert.equal(root.querySelectorAll('option').length, 10);
  const ids = root.querySelectorAll('input').map(node => node.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const node of root.querySelectorAll('input')) {
    assert.ok(root.querySelectorAll('label').some(label => label.getAttribute('for') === node.id));
    assert.equal(node.getAttribute('required'), 'required');
    assert.equal(node.getAttribute('name'), null);
  }
  assert.equal(root.querySelector('form').getAttribute('action'), null);
});
test('a valid scenario produces visible results, assumptions and keyboard focus without transmission', () => {
  const page = setup('net_yield'); page.fill(yieldInputs);
  const event = page.root.querySelector('form').requestSubmit();
  assert.equal(event.prevented, true);
  assert.equal(page.output().hidden, false);
  assert.match(page.output().textContent, /6.67%/);
  assert.match(page.output().textContent, /Financing, tax/);
  assert.equal(page.document.activeElement.tagName, 'h3');
  assert.deepEqual(page.calls, []);
});
test('editing or clearing an input invalidates all previous results before native required validation', () => {
  const page = setup('net_yield'); page.fill(yieldInputs); page.root.querySelector('form').requestSubmit();
  page.input('annual_rent').value = ''; page.input('annual_rent').dispatch('input');
  assert.equal(page.output().hidden, true); assert.equal(page.output().textContent, '');
  assert.equal(page.root.querySelector('form').requestSubmit(), null);
  assert.equal(page.output().hidden, true); assert.equal(page.output().textContent, '');
});
test('capture-phase native invalid handling clears results even without an input event', () => {
  const page = setup('net_yield'); page.fill(yieldInputs); page.root.querySelector('form').requestSubmit();
  page.input('annual_rent').value = '';
  assert.equal(page.root.querySelector('form').requestSubmit(), null);
  assert.equal(page.output().hidden, true); assert.equal(page.output().textContent, '');
});
test('bad numeric input is explained and focused without injecting markup, and editing clears old errors', () => {
  const page = setup('net_yield'); page.fill({...yieldInputs, purchase_price: '<img src=x onerror=alert(1)>'});
  page.root.querySelector('form').requestSubmit();
  const error = page.root.querySelector('[role="alert"]');
  assert.equal(error.hidden, false); assert.match(error.textContent, /non-negative number/);
  assert.equal(page.document.activeElement, page.input('purchase_price'));
  assert.equal(page.input('purchase_price').getAttribute('aria-invalid'), 'true');
  page.input('purchase_price').value = '1000000'; page.input('purchase_price').dispatch('input');
  assert.equal(error.hidden, true); assert.equal(page.input('purchase_price').getAttribute('aria-invalid'), null);
});
test('editing a related field clears the entire cross-field validation state', () => {
  const page = setup('cash_needed'); page.fill({purchase_price: '100', loan_amount: '200', nonrefundable_cost: '0', refundable_deposit: '0', cash_reserve: '0'});
  page.root.querySelector('form').requestSubmit();
  assert.equal(page.input('loan_amount').getAttribute('aria-invalid'), 'true');
  page.input('purchase_price').value = '300'; page.input('purchase_price').dispatch('input');
  assert.equal(page.root.querySelector('[role="alert"]').hidden, true);
  assert.ok(page.root.querySelectorAll('input').every(input => input.getAttribute('aria-invalid') === null));
});
test('off-plan add/remove invalidates old results and table exposes row and column headers', () => {
  const page = setup('offplan_cashflow'); page.fill({purchase_price: '1000', available_cash: '1000', monthly_saving: '0', upfront_cost: '0'});
  const inputs = page.root.querySelectorAll('input').filter(node => node.id.includes('-milestone-'));
  for (let index = 0; index < inputs.length; index++) inputs[index].value = index % 2 ? '50' : String(index / 2);
  page.root.querySelector('form').requestSubmit();
  assert.equal(page.output().hidden, false);
  assert.equal(page.output().querySelectorAll('th').filter(node => node.getAttribute('scope') === 'col').length, 4);
  const add = page.root.querySelectorAll('button').find(node => node.textContent === 'Add a milestone');
  add.dispatch('click'); assert.equal(page.output().hidden, true); assert.equal(page.output().textContent, '');
  const remove = page.root.querySelectorAll('button').filter(node => node.textContent === 'Remove milestone');
  remove.at(-1).dispatch('click'); assert.equal(page.output().hidden, true);
});
test('tool selection and explicit clear discard entered figures and computed results', () => {
  const page = setup(); page.fill(yieldInputs); page.root.querySelector('form').requestSubmit();
  const selection = page.root.querySelector('select'); selection.value = 'seller_proceeds'; selection.dispatch('change');
  assert.equal(page.output().hidden, true); assert.ok(page.root.querySelectorAll('input').every(node => node.value === ''));
  page.fill({sale_price: '1000000', loan_payoff: '600000', selling_fee_percent: '2', other_selling_cost: '5000'}); page.root.querySelector('form').requestSubmit();
  page.root.querySelectorAll('button').find(node => node.textContent === 'Clear my figures').dispatch('click');
  assert.equal(page.output().hidden, true); assert.ok(page.root.querySelectorAll('input').every(node => node.value === ''));
  assert.equal(page.document.activeElement, page.root.querySelector('input')); assert.deepEqual(page.calls, []);
});
test('sources contain no network, persistence, analytics, HTML injection or execution interfaces', () => {
  for (const file of ['engine.js', 'ui.js']) {
    const content = fs.readFileSync(path.join(__dirname, file), 'utf8');
    assert.doesNotMatch(content, /\b(?:fetch|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|dataLayer|gtag|eval)\b|\.cookie\b|\.innerHTML\b|\.outerHTML\b|new\s+Function\b/);
  }
});
