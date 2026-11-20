/** Read-only, bounded HTTP inventory. Never executes page JavaScript or submits forms. */
import https from 'node:https';
import { writeFileSync, existsSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export const ORIGIN = 'https://blackswanrealestate.ae';
export const PATHS = Object.freeze(['/', '/enquire/', '/enquire/off-plan/', '/enquire/resale/',
  '/enquire/rent/', '/enquire/sell/', '/enquire/let/', '/robots.txt', '/sitemap_index.xml']);
const HOSTS = new Set(['blackswanrealestate.ae', 'www.blackswanrealestate.ae']);
// Observed 7 November: sitemap_index.xml redirects to this same-origin sitemap.
const ALLOWED_PATHS = new Set([...PATHS, '/sitemap.xml']);
const MAX_BYTES = 2 * 1024 * 1024;
const MAX_REDIRECTS = 3;

export function safeTarget(value, base = ORIGIN) {
  const url = new URL(value, base);
  if (url.protocol !== 'https:' || !HOSTS.has(url.hostname) || url.username || url.password ||
      (url.port && url.port !== '443') || url.search || url.hash || !ALLOWED_PATHS.has(url.pathname)) {
    throw new Error('OUTSIDE_EXPLICIT_AUDIT_SCOPE');
  }
  return url;
}

function attrs(tag) {
  const result = {};
  const pattern = /([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
  let match;
  while ((match = pattern.exec(tag))) result[match[1].toLowerCase()] = match[2] ?? match[3] ?? match[4];
  return result;
}

function publicPath(value, base) {
  try {
    const url = new URL(value, base);
    if (!HOSTS.has(url.hostname) || url.protocol !== 'https:') return null;
    // Only explicitly inspected routes and fixed platform identifiers enter the artifact.
    return PATHS.includes(url.pathname) ? url.origin + url.pathname : null;
  } catch { return null; }
}

function unique(values) { return [...new Set(values)].sort(); }
function robotsTokens(value = '') {
  return unique((value.toLowerCase().match(/\b(?:noindex|nofollow|index|follow|noarchive|nosnippet|none|all)\b/g) || []));
}

export function inspectHtml(body, base = ORIGIN) {
  const meta = [...body.matchAll(/<meta\b[^>]*>/gi)].map(m => attrs(m[0]));
  const links = [...body.matchAll(/<link\b[^>]*>/gi)].map(m => attrs(m[0]));
  const scripts = [...body.matchAll(/<script\b[^>]*>/gi)].map(m => attrs(m[0]));
  const externalScriptOrigins = [];
  for (const script of scripts) {
    if (!script.src) continue;
    try {
      const url = new URL(script.src.replaceAll('&amp;', '&'), base);
      if (url.protocol === 'https:' && !HOSTS.has(url.hostname)) externalScriptOrigins.push(url.origin);
    } catch { /* malformed script URL is not copied */ }
  }
  const assets = [...body.matchAll(/\/wp-content\/(themes|plugins)\/([a-zA-Z0-9_-]+)\//g)];
  const pluginVersions = [];
  for (const script of scripts) {
    if (!script.src?.includes('/wp-content/plugins/bsre-enquiries/')) continue;
    try {
      const value = new URL(script.src.replaceAll('&amp;', '&'), base).searchParams.get('ver');
      if (/^\d+\.\d+\.\d+$/.test(value || '')) pluginVersions.push(value);
    } catch { /* no raw URLs */ }
  }
  const generators = meta.filter(m => m.name?.toLowerCase() === 'generator')
    .map(m => m.content?.match(/^(WordPress|Elementor|Site Kit by Google|WooCommerce)(?:\s+([\d.]+))?/i))
    .filter(Boolean).map(m => ({name: m[1], version: m[2] || null}));
  const ctaNames = [...body.matchAll(/\bdata-(?:bsre-)?(?:cta|form|campaign|page)[a-z-]*\s*=/gi)]
    .map(m => m[0].replace(/\s*=$/, '').toLowerCase());
  return {
    wordpress_asset_evidence: assets.length > 0,
    generators,
    themes: unique(assets.filter(a => a[1] === 'themes').map(a => a[2])),
    plugins: unique(assets.filter(a => a[1] === 'plugins').map(a => a[2])),
    bsre_public_asset_versions: unique(pluginVersions),
    meta_robots: unique(meta.filter(m => ['robots','googlebot'].includes(m.name?.toLowerCase()))
      .flatMap(m => robotsTokens(m.content))),
    canonical: links.filter(l => l.rel?.toLowerCase() === 'canonical').map(l => publicPath(l.href, base)).filter(Boolean),
    public_google_ids: unique(body.match(/\b(?:GTM-[A-Z0-9]{5,15}|G-[A-Z0-9]{8,15}|AW-\d{6,15})\b/g) || []),
    external_script_origins: unique(externalScriptOrigins),
    form_count: (body.match(/<form\b/gi) || []).length,
    bsre_form_count: [...body.matchAll(/<form\b[^>]*>/gi)].filter(m => /bsre/i.test(m[0])).length,
    h1_count: (body.match(/<h1\b/gi) || []).length,
    stable_context_attribute_names: unique(ctaNames),
    inline_google_tag_markers: {
      gtag: /\bgtag\s*\(/.test(body),
      googletagmanager: /googletagmanager\.com/.test(body),
      google_analytics: /google-analytics\.com/.test(body),
      data_layer: /\bdataLayer\b/.test(body)
    },
    claims_not_established: ['tag_execution','consent_behavior','event_payload_privacy','conversion_deduplication',
      'account_ownership','cms_permissions','deployment_version','form_delivery','mobile_or_keyboard_acceptance']
  };
}

function headerSummary(headers) {
  const csp = String(headers['content-security-policy'] || '');
  return {
    content_type: String(headers['content-type'] || '').split(';')[0],
    server: /^[a-zA-Z0-9 ._-]{1,80}$/.test(headers.server || '') ? headers.server : null,
    x_robots_tag: robotsTokens(String(headers['x-robots-tag'] || '')),
    csp_present: Boolean(csp),
    csp_directive_names: unique(csp.split(';').map(x => x.trim().split(/\s/)[0])
      .filter(x => /^[a-z-]{3,40}$/.test(x))),
    cache_control_directives: unique(String(headers['cache-control'] || '').toLowerCase()
      .match(/\b(?:no-store|no-cache|private|public|must-revalidate|immutable)\b/g) || []),
    hostinger_header_evidence: ['x-hcdn-cache-status', 'x-hcdn-request-id', 'x-hcdn-upstream-rt']
      .filter(name => headers[name] !== undefined)
  };
}

function getOnce(url) {
  return new Promise((resolve, reject) => {
    const started = performance.now();
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true; clearTimeout(deadline);
      if (error) reject(error); else resolve(value);
    };
    const deadline = setTimeout(() => { request.destroy(); finish(new Error('TIMEOUT')); }, 15000);
    const request = https.get(url, {headers: {
      'User-Agent': 'BSRE-ReadOnly-Phase0-Audit/1.0', Accept: 'text/html,application/xml,text/plain',
      'Accept-Encoding': 'identity'
    }}, response => {
      const chunks = []; let count = 0;
      response.on('data', chunk => {
        count += chunk.length;
        if (count > MAX_BYTES) { response.destroy(); finish(new Error('BODY_LIMIT_EXCEEDED')); }
        else chunks.push(chunk);
      });
      response.on('error', () => finish(new Error('RESPONSE_STREAM_ERROR')));
      response.on('end', () => finish(null,{status: response.statusCode, headers: response.headers,
        body: Buffer.concat(chunks).toString('utf8'), bytes: count,
        elapsed_ms: Math.round(performance.now() - started)}));
    });
    request.setTimeout(15000, () => { request.destroy(); finish(new Error('TIMEOUT')); });
    request.on('error', error => finish(new Error(['ENOTFOUND','ECONNRESET','ECONNREFUSED',
      'CERT_HAS_EXPIRED','UNABLE_TO_VERIFY_LEAF_SIGNATURE'].includes(error.code) ? error.code : 'REQUEST_FAILED')));
  });
}

export async function auditRoute(path, transport = getOnce) {
  let url = safeTarget(path); const redirects = []; let calls = 0; let result;
  try {
    for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
      calls++; result = await transport(url);
      if ([301,302,303,307,308].includes(result.status)) {
        if (hop === MAX_REDIRECTS) throw new Error('REDIRECT_LIMIT_EXCEEDED');
        const next = safeTarget(result.headers.location, url.href);
        redirects.push({status: result.status, from: url.href, to: next.href}); url = next; continue;
      }
      const base = {requested_path: path, final_url: url.href, status: result.status, redirects,
        http_calls: calls, response_bytes: result.bytes, final_request_elapsed_ms: result.elapsed_ms,
        headers: headerSummary(result.headers)};
      if (path === '/robots.txt') return {...base, robots: {
        adsbot_named: /AdsBot-Google/i.test(result.body),
        disallow_all_present: /^Disallow:\s*\/\s*$/mi.test(result.body),
        enquire_disallow_present: /^Disallow:\s*[^\r\n]*enquire/mi.test(result.body),
        wp_admin_rule_present: /^Disallow:\s*\/wp-admin\//mi.test(result.body),
        sitemap_declared: /^Sitemap:\s*https:\/\//mi.test(result.body)
      }};
      if (path === '/sitemap_index.xml') return {...base, sitemap: {
        sitemap_index_present: /<sitemapindex\b/i.test(result.body),
        urlset_present: /<urlset\b/i.test(result.body),
        child_sitemap_count: (result.body.match(/<sitemap>/gi) || []).length,
        enquire_url_seen_in_this_response: /<loc>[^<]*\/enquire\//i.test(result.body),
        children_not_fetched: true
      }};
      return {...base, html: inspectHtml(result.body, url.href)};
    }
  } catch (error) {
    return {requested_path: path, http_calls: calls, redirects,
      error: /^[A-Z_]{3,80}$/.test(error.message) ? error.message : 'AUDIT_FAILED'};
  }
}

export async function runAudit() {
  const started = performance.now(); const routes = [];
  // Two independent requests at once; fixed allowlist and no recursive crawling.
  for (let i=0; i<PATHS.length; i+=2) routes.push(...await Promise.all(PATHS.slice(i,i+2).map(p => auditRoute(p))));
  return {schema_version: 1, observed_at_utc: new Date().toISOString(), site: ORIGIN,
    method: 'UNAUTHENTICATED_HTTP_GET_ONLY_NO_JS_NO_FORM_SUBMISSION',
    limits: {allowed_paths: PATHS.length, redirects_per_path: MAX_REDIRECTS, max_bytes_per_response: MAX_BYTES,
      socket_timeout_ms: 15000, absolute_request_timeout_ms: 15000, concurrency: 2},
    elapsed_ms: Math.round(performance.now() - started),
    total_http_calls: routes.reduce((sum, r) => sum + r.http_calls, 0),
    privacy: 'No response bodies, cookies, nonces, contact details, query strings or raw CSP retained.', routes};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const output = process.argv[2];
  if (!output?.endsWith('.json')) throw new Error('Usage: node public_audit.mjs output.json');
  if (existsSync(output)) throw new Error('OUTPUT_ALREADY_EXISTS_USE_A_NEW_ARTIFACT_NAME');
  const result = await runAudit(); writeFileSync(output, JSON.stringify(result, null, 2) + '\n', {flag:'wx'});
  console.log(JSON.stringify({artifact: output, http_calls: result.total_http_calls, elapsed_ms: result.elapsed_ms,
    routes: result.routes.map(r => ({path:r.requested_path,status:r.status,error:r.error}))}));
}
