// Shared actual-client VM fixture. DOM, storage and provider delivery are doubles.
import {randomUUID} from 'node:crypto';
import {runInNewContext} from 'node:vm';

export function createClientPage({client, origin, request, slug, role, timeline, csrf, store,
  blank = false, loseAcknowledgement = false, name = 'TEST synthetic client ' + slug,
  analytics = false, advertising = false, eligible = false, snapshot = null,
  formPresent = true, locationPath = '/enquire/' + slug + '/', referrer = ''}) {
  const handlers = new Map();
  const button = {dataset: {}, textContent: 'Submit'};
  const status = {dataset: {}};
  const requests = [];
  const measurement = [];
  const events = [];
  let acceptedResponse;
  const values = blank ? {} : {
    name, phone: '+971500000000', email: 'fixture@example.invalid', country: 'UAE',
    area: 'Synthetic fixture', budget: 'To discuss', timeline, funding: 'To discuss',
    property_type: 'Apartment', property_details: 'SYNTHETIC NOT INVENTORY',
    authority: ['seller', 'landlord'].includes(role) ? 'owner' : '',
  };
  const form = {
    dataset: {role, landingPath: '/enquire/' + slug + '/', campaign: 'SYNTHETIC_LAB_ONLY'},
    elements: {namedItem(key) {
      if (key === 'contact_consent') return {checked: !blank};
      if (key === 'marketing_consent') return {checked: false};
      return {value: values[key] || ''};
    }},
    querySelector: selector => selector === '[data-bsre-status]' ? status : button,
    reportValidity: () => !blank,
    addEventListener: (type, listener) => handlers.set(type, listener),
  };
  const window = {
    location: new URL(origin + locationPath), crypto: {randomUUID},
    BSRELeadConfig: {endpoint: origin + '/wp-json/bsre/v1/lead', csrfToken: csrf, measurementEligible: eligible},
    BSREConsentBridge: {
      permissions: () => ({analytics, advertising}),
      measurementEligible: () => eligible,
      getSnapshot: () => snapshot,
      normalizeSnapshot: value => value,
    },
    sessionStorage: {
      getItem: key => store.get(key) ?? null,
      setItem: (key, value) => store.set(key, value),
      removeItem: key => store.delete(key),
    },
    setTimeout, clearTimeout, addEventListener() {},
    dispatchEvent: event => events.push(event),
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    async fetch(url, options) {
      requests.push({url, request: options});
      const result = await request({url, method: options.method, credentials: options.credentials,
        headers: options.headers, body: options.body});
      if (url.endsWith('/lead')) acceptedResponse = result;
      if (url.endsWith('/lead') && loseAcknowledgement) {
        loseAcknowledgement = false;
        throw new Error('synthetic_browser_acknowledgement_loss');
      }
      return {ok: result.status >= 200 && result.status < 300, status: result.status,
        json: async () => result.body};
    },
  };
  const document = {readyState: 'complete', referrer, querySelector: () => formPresent ? form : null,
    querySelectorAll: selector => formPresent && selector === 'form[data-bsre-form]' ? [form] : []};
  runInNewContext(client, {window, document, URL, AbortController});
  window.BSREMeasurement.connect('ads', payload => measurement.push({destination: 'ads', payload}));
  window.BSREMeasurement.connect('ga4', payload => measurement.push({destination: 'ga4', payload}));
  return {submit: () => handlers.get('submit')({preventDefault() {}}), requests, measurement, events,
    status, button, get acceptedResponse() { return acceptedResponse; }};
}
