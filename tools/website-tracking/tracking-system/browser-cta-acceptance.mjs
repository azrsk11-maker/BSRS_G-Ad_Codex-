// Opt-in Chromium check using actual client code and synthetic HTTPS endpoints only.
// Set BSRE_BROWSER_PATH to a Chromium executable. Set BSRE_PYTHON if python3 is unavailable.
// Requires Node 24 and Python cryptography. Run: node tools/website-tracking/tracking-system/browser-cta-acceptance.mjs
import {execFileSync,spawn} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import https from 'node:https';
import assert from 'node:assert/strict';
import {buildAttributionClientCandidate} from './build-attribution-client-candidate.mjs';

const browser=process.env.BSRE_BROWSER_PATH;
if(!browser)throw new Error('Set BSRE_BROWSER_PATH to a Chromium browser executable');
const python=process.env.BSRE_PYTHON || 'python3';
const fixture=filename=>fs.readFile(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/'+filename,import.meta.url));
const client=buildAttributionClientCandidate(await fixture('lead.js'));
const routes={'off-plan':'off_plan',resale:'resale',sell:'seller',let:'landlord'};
const generated=execFileSync(python,['-c',`
import datetime,ipaddress,json
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
key=ec.generate_private_key(ec.SECP256R1())
name=x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME,'Loopback synthetic fixture')])
now=datetime.datetime.now(datetime.timezone.utc)
cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(hours=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256())
import hashlib,base64
spki=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
print(json.dumps({'key':key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode(),'cert':cert.public_bytes(serialization.Encoding.PEM).decode(),'pin':base64.b64encode(hashlib.sha256(spki).digest()).decode()}))
`],{encoding:'utf8'});
const {pin,...tls}=JSON.parse(generated);
const bridgeSource=await fixture('consent-bridge.js');
let mode="analytics";
const submissions=[];
const token='cc1|1794200000|'+'a'.repeat(64);
function snapshot(){return {known:true,acknowledged:true,measurement_eligible:true,preferences:{analytics:["analytics","both"].includes(mode),ad_measurement:["advertising","both"].includes(mode),personalization:false},decision_version:'synthetic-'+mode,notice_version:'synthetic-notice',preference_days:180,preference_expires_at:Math.floor(Date.now()/1000)+3600};}
const server=https.createServer(tls,async(req,res)=>{
  const url=new URL(req.url,'https://127.0.0.1');
  if(req.method==='POST'&&url.pathname==='/consent-context'){res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify({...snapshot(),csrf_token:token,expires_in:7200}));return}
  if(req.method==='POST'&&url.pathname==='/synthetic-receipt'){
    const chunks=[];for await(const c of req)chunks.push(c);
    const body=JSON.parse(Buffer.concat(chunks));
    submissions.push({body,decision:req.headers['x-bsre-consent-decision']});
    res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify({accepted:true,lead_id:'SYNTHETIC_LEAD_'+submissions.length,event_id:'SYNTHETIC_EVENT_'+submissions.length}));
    return;
  }
  if(req.method!=='GET'){res.writeHead(405).end();return}
  if(url.pathname==='/lead.js'){res.writeHead(200,{'Content-Type':'text/javascript'}).end(client);return}
  if(url.pathname==='/bridge.js'){res.writeHead(200,{'Content-Type':'text/javascript'}).end(bridgeSource);return}
  const entry=url.pathname.startsWith('/synthetic-entry/');
  const slug=url.pathname.split('/').filter(Boolean).at(-1);
  if(!entry&&!Object.hasOwn(routes,slug)){res.writeHead(404).end();return}
  const bridge="window.BSRETrackingConfig={cmpProviderId:'bsre_first_party_v1',consentContextEndpoint:location.origin+'/consent-context',consentUpdateEndpoint:location.origin+'/consent-update'};window.BSRELeadConfig={measurementEligible:true,endpoint:location.origin+'/synthetic-receipt'};";
  const body=entry?Object.keys(routes).map(key=>`<a id="${key}" href="/enquire/${key}/">${key}</a>`).join(''):`<form data-bsre-form data-role="${routes[slug]}" data-landing-path="/enquire/${slug}/"><input name="name" value="Isolated Fixture"><input name="phone" value="+971500000000"><input name="country" value="UAE"><input name="area" value="Synthetic area"><input name="budget" value="To discuss"><input name="timeline" value="Immediate"><input name="property_type" value="Apartment"><input name="contact_consent" type="checkbox" checked><button type="submit" disabled>Submit</button><p data-bsre-status hidden></p></form>`;
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; script-src 'self' 'unsafe-inline'; connect-src 'self'; form-action 'none'"}).end(`<!doctype html><body>${body}<script>${bridge}</script><script src="/bridge.js"></script><script src="/lead.js"></script></body>`);
});
server.listen(0,'127.0.0.1'); await once(server,'listening');
const origin='https://127.0.0.1:'+server.address().port;
const profile=await fs.mkdtemp(path.join(os.tmpdir(),'bsre-handoff-'));
const chrome=spawn(browser,['--headless','--disable-background-networking','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--ignore-certificate-errors-spki-list='+pin,'--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let ws;
try{
  let port;
  for(let i=0;i<40&&!port;i++){try{port=(await fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split(/\r?\n/)[0]}catch{await new Promise(r=>setTimeout(r,150))}}
  assert.ok(port);
  const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  ws=new WebSocket(tabs.find(x=>x.type==='page').webSocketDebuggerUrl);await once(ws,'open');
  let seq=0;
  const send=(method,params={})=>new Promise((resolve,reject)=>{
    const id=++seq;
    const timer=setTimeout(()=>{ws.removeEventListener('message',listener);reject(new Error(method+' timed out'))},5000);
    function listener(event){const x=JSON.parse(event.data);if(x.id!==id)return;clearTimeout(timer);ws.removeEventListener('message',listener);x.error?reject(new Error(x.error.message)):resolve(x.result)}
    ws.addEventListener('message',listener);ws.send(JSON.stringify({id,method,params}));
  });
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});assert.ok(!r.exceptionDetails,r.exceptionDetails?.exception?.description);return r.result.value};
  await send('Page.enable');
  const go=async action=>{
    let listener;
    const loaded=new Promise(resolve=>{listener=e=>{if(JSON.parse(e.data).method==='Page.loadEventFired')resolve()};ws.addEventListener('message',listener)});
    let timer;
    try{await action();await Promise.race([loaded,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Navigation timed out')),5000)})])}
    finally{clearTimeout(timer);ws.removeEventListener('message',listener)}
  };
  for(const [slug,role] of Object.entries(routes)){
    const entry=origin+'/synthetic-entry/'+slug+'/';
    mode='analytics';
    await go(()=>send('Page.navigate',{url:entry}));
    await evaluate('sessionStorage.clear()');
    for(const choice of ['analytics','advertising','both','refused']){
      mode=choice;
      await go(()=>send('Page.navigate',{url:entry+'?utm_source=synthetic_source&gclid=synthetic_gclid_123'}));
      assert.equal(await evaluate('window.BSREConsentBridge.refresh()'),true);

      await go(()=>evaluate(`document.getElementById('${slug}').click()`));
      assert.equal(await evaluate('window.BSREConsentBridge.refresh()'),true);
      const state=await evaluate(`({path:location.pathname,query:location.search,referrer:document.referrer,role:document.querySelector('form').dataset.role,analytics:JSON.parse(sessionStorage.getItem('BSRE_ATTRIBUTION_V1')),advertising:JSON.parse(sessionStorage.getItem('BSRE_AD_ATTRIBUTION_V1'))})`);
      assert.equal(state.path,'/enquire/'+slug+'/');assert.equal(state.query,'');assert.equal(state.referrer,'');assert.equal(state.role,role);
      const analytics=['analytics','both'].includes(choice);
      const advertising=['advertising','both'].includes(choice);
      if(analytics){assert.equal(state.analytics.last.landing_page,entry);assert.equal(state.analytics.last.parameters.utm_source,'synthetic_source')}
      else assert.equal(state.analytics,null);
      if(advertising){assert.equal(state.advertising.last.landing_page,entry);assert.equal(state.advertising.last.parameters.gclid,'synthetic_gclid_123')}
      else assert.equal(state.advertising,null);
      const previous=submissions.length;
      await evaluate("document.querySelector('form').requestSubmit()");
      for(let i=0;i<30;i++){
        if(await evaluate("document.querySelector('[data-bsre-status]').textContent.includes('SYNTHETIC_LEAD_')"))break;
        await new Promise(r=>setTimeout(r,100));
      }
      assert.equal(submissions.length,previous+1);
      const {body,decision}=submissions.at(-1);
      assert.equal(body.role,role);assert.equal(body.landing_page,origin+'/enquire/'+slug+'/');
      assert.equal(decision,'synthetic-'+choice);
      if(analytics||advertising){
        assert.equal(body.attribution.last.landing_page,entry);
        const parameters={};
        if(analytics)parameters.utm_source='synthetic_source';
        if(advertising)parameters.gclid='synthetic_gclid_123';
        assert.deepEqual(body.attribution.last.parameters,parameters);
      }else assert.deepEqual(body.attribution,{first:null,last:null});
      assert.equal(await evaluate("document.querySelector('[data-bsre-status]').textContent.includes('SYNTHETIC_LEAD_')"),true);
      await evaluate("document.querySelector('form').requestSubmit()");
      await new Promise(r=>setTimeout(r,70));assert.equal(submissions.length,previous+1);
      console.log(JSON.stringify({slug,consent:choice,clean_navigation:true,payload_assertion:true,synthetic_receipt:true,duplicate_submit_suppressed:true}));
    }
  }
  assert.equal(submissions.length,16);
}finally{
  ws?.close();
  const exited=once(chrome,'exit');chrome.kill();await Promise.race([exited,new Promise(r=>setTimeout(r,1500))]);
  server.close();await fs.rm(profile,{recursive:true,force:true,maxRetries:3,retryDelay:150});
}

