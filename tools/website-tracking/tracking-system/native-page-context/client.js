/* Private candidate: context projection only. No storage, SDK, network, provider events or consent authority. */
(function () {
  'use strict';
  const PAGE_FIELDS = ['campaign_key','landing_page_id','page_version','page_family','property_destination','property_segment','transaction_intent','language','property_id','project_id'];
  const ROLES = ['off_plan','resale','tenant','seller','landlord','unknown'];
  const TYPES = ['ordinary','phone','whatsapp','email','brochure','floorplan','calculator','comparison','property','viewing','main_site'];
  const POSITIONS = ['header','hero','form','footer','sticky','other'];
  const CODE = /^[A-Za-z][A-Za-z0-9_-]{0,79}$/;
  const COMPONENT = /^BSRE-[A-Z][A-Z0-9_-]{0,110}$/;
  const PATH = /^\/(?:[a-z][a-z0-9-]{0,60}\/)+$/;
  const EVENT_ID = /^[A-Za-z0-9._:-]{1,150}$/;
  // Legacy canonical names remain unchanged. There is one mapping per representation, never a second emit.
  const EVENTS = Object.freeze({
    page_view: ['page_view','page_view','browser'], cta_click: ['cta_click','cta_click','browser'],
    telephone_click: ['phone_click','phone_click','browser'], phone_click: ['phone_click','phone_click','browser'],
    whatsapp_click: ['whatsapp_click','whatsapp_click','browser'], email_click: ['email_click','email_click','browser'],
    form_start: ['form_start','form_start','browser'], form_error: ['form_error','form_error','browser'],
    form_submit: ['form_accepted','generate_lead','server_confirmed','durable_receipt'], form_accepted: ['form_accepted','generate_lead','server_confirmed','durable_receipt'],
    brochure_download: ['brochure_download','brochure_download','browser_or_response'], floorplan_view: ['floorplan_view','floorplan_view','browser'],
    calculator_complete: ['calculator_complete','calculator_complete','browser','validated_result'], comparison_complete: ['comparison_complete','comparison_complete','browser','validated_result'],
    property_view: ['property_view','property_view','browser'], viewing_request: ['viewing_request','viewing_request','server_confirmed'],
    viewing_booked: ['viewing_booked','viewing_booked','booking_or_authorized_ledger'], viewing_attended: ['viewing_attended','viewing_attended','authorized_ledger'],
    lp_to_main_site: ['lp_to_main_site','lp_to_main_site','browser'], conversation_verified: ['conversation_verified',null,'provider_or_authorized_ledger'],
    qualified_lead: ['qualified_lead',null,'authorized_ledger'], mandate_signed: ['mandate_signed',null,'authorized_ledger'],
    offer_submitted: ['offer_submitted',null,'authorized_ledger'], transaction_closed: ['transaction_closed',null,'authorized_ledger'],
    commission_collected: ['commission_collected',null,'finance_ledger']
  });
  const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const exact = (value, fields) => plain(value) && Object.keys(value).length === fields.length && fields.every(key => Object.hasOwn(value,key));
  function frozen(value) { if (value && typeof value === 'object') { Object.values(value).forEach(frozen); Object.freeze(value); } return value; }
  function pageField(key,value) {
    if (typeof value !== 'string') return false;
    if (key === 'campaign_key') return /^BSRE-C[0-9]{4}$/.test(value);
    if (key === 'landing_page_id') return /^BSRE-LP[0-9]{4}$/.test(value);
    if (key === 'language') return /^[a-z]{2}(?:-[A-Z]{2})?$/.test(value);
    if (key === 'page_version' && /^[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}$/.test(value)) return true;
    return CODE.test(value);
  }
  function current() {
    // Config is emitted by the native PHP port. URL/search, DOM text and dataset metadata are never merged.
    // As with any browser global this is not cryptographic authority; backend joins re-resolve the native registry.
    const value = window.BSRENativePageContextConfig;
    if (!exact(value,['schema','registry_revision','company','page_path','role','page_context','forms','ctas'])
        || value.schema !== 1 || typeof value.registry_revision !== 'string' || !CODE.test(value.registry_revision) || value.company !== 'BlackSwan Real Estate'
        || typeof value.page_path !== 'string' || value.page_path.length > 240 || !(value.page_path === '/' || PATH.test(value.page_path))
        || !window.location || window.location.protocol !== 'https:' || value.page_path !== window.location.pathname
        || !ROLES.includes(value.role) || !plain(value.page_context) || !Array.isArray(value.forms) || !Array.isArray(value.ctas)
        || value.forms.length > 100 || value.ctas.length > 100 || !value.forms.every(id => typeof id === 'string' && COMPONENT.test(id))
        || new Set(value.forms).size !== value.forms.length) return null;
    for (const [key,item] of Object.entries(value.page_context)) if (!PAGE_FIELDS.includes(key) || !pageField(key,item)) return null;
    if (Object.hasOwn(value.page_context,'campaign_key') !== Object.hasOwn(value.page_context,'landing_page_id')) return null;
    const seen = new Set();
    for (const cta of value.ctas) {
      if (!exact(cta,['cta_id','cta_type','cta_position','destination_key']) || typeof cta.cta_id !== 'string' || !COMPONENT.test(cta.cta_id)
          || seen.has(cta.cta_id) || !TYPES.includes(cta.cta_type) || !POSITIONS.includes(cta.cta_position) || typeof cta.destination_key !== 'string' || !CODE.test(cta.destination_key)) return null;
      seen.add(cta.cta_id);
    }
    return frozen(JSON.parse(JSON.stringify(value)));
  }
  function matches(path,role) { const context=current(); return !!context && context.page_path === path && context.role === role; }
  function mapping(name) {
    if (typeof name !== 'string' || !Object.hasOwn(EVENTS,name)) return null;
    const [operational_event,ga4_event,evidence_source,prerequisite] = EVENTS[name];
    return frozen({operational_event,ga4_event,evidence_source,...(prerequisite?{prerequisite}:{})});
  }
  function mapLegacy(event) {
    // Only called by the existing canonical mapper, after its occurrence/receipt checks. This function does not emit.
    if (!plain(event) || !['form_submit','form_start','whatsapp_click','telephone_click'].includes(event.event)
        || typeof event.event_id !== 'string' || !EVENT_ID.test(event.event_id) || !ROLES.includes(event.role)
        || typeof event.page_path !== 'string' || !(/^\/enquire\/(?:(?:off-plan|resale|rent|sell|let)\/)?$/.test(event.page_path) || matches(event.page_path,event.role))) return null;
    const parameters = {schema_version:'1.0.0',site_scope:'BSRE_REAL_ESTATE',page_path:event.page_path,role:event.role};
    if (event.cta_location) parameters.cta_location = POSITIONS.includes(event.cta_location) ? event.cta_location : 'other';
    const context=current();
    if (context && context.page_path === event.page_path && context.role === event.role) Object.assign(parameters,{company:context.company},context.page_context);
    // Neither event_id, Lead ID, receipt, consent revision, attribution, raw URL nor input text is copied.
    return frozen({event_name:EVENTS[event.event][1],parameters});
  }
  function component(kind,id) {
    const context=current(); if (!context || typeof id !== 'string') return null;
    if (kind === 'form') return context.forms.includes(id) ? frozen({form_id:id}) : null;
    if (kind === 'cta') return context.ctas.find(cta => cta.cta_id === id) || null;
    return null;
  }
  function clickMapping(id) {
    const cta=component('cta',id); if (!cta) return null;
    const name = {ordinary:'cta_click',phone:'phone_click',whatsapp:'whatsapp_click',email:'email_click',brochure:'brochure_download',floorplan:'floorplan_view',property:'property_view',main_site:'lp_to_main_site'}[cta.cta_type];
    // Calculator/comparison completion and viewing requests cannot be established by a click.
    return name ? frozen({event:name,cta}) : null;
  }
  function continuation(permittedHistories) {
    // Pure current-page join. Histories belong to the existing purpose reducer and remain private, separate and unchanged.
    // Caller must supply the reducer's currently permitted result; this port does not grant/reconstruct/persist history.
    // No UTMs are added and no touch/page_view is produced. Null source remains null.
    return Object.freeze({current_page:current(),permitted_histories:permittedHistories === undefined ? null : permittedHistories});
  }
  window.BSRENativePageContext = Object.freeze({version:'1.0.0',current,matches,mapping,mapLegacy,component,clickMapping,continuation});
}());
