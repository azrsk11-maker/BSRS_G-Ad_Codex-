import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash, createHmac, randomUUID} from 'node:crypto';
import vm from 'node:vm';
const source=readFileSync(new URL('./fixtures/receiver-v2/Code.gs',import.meta.url));
assert.equal(createHash('sha256').update(source).digest('hex'),'6669cb28e5267a49e061427b736cdbdbad87bee6cbb946e99483d9439f61fa38');
// Capability-only VM: no require, fetch, network, files, real Google or mail APIs.
export function lab(providedSource){
  const evaluatedSource=providedSource===undefined?source:providedSource;
  if(!Buffer.isBuffer(evaluatedSource))throw new TypeError('Receiver source must be a Buffer');
  const rows=[],mail=[], properties={LEAD_SHEET_ID:'SYNTHETIC_WORKBOOK_NOT_REAL',HMAC_SECRET:'synthetic-secret-never-production-0000',ROUTING_ENABLED:'true',MAIL_ENABLED:'true'};
  let busy=false,flushFault=false,sendFault=false,quota=100;
  const sheet={getLastRow:()=>rows.length,appendRow:r=>rows.push([...r]),setFrozenRows(){},getRange:(r,c,h=1,w=1)=>({getValues:()=>Array.from({length:h},(_,i)=>Array.from({length:w},(_,j)=>rows[r-1+i]?.[c-1+j]??'')),setValues:values=>values.forEach((row,i)=>row.forEach((value,j)=>{rows[r-1+i]??=[];rows[r-1+i][c-1+j]=value;}))})};
  const context=vm.createContext({PropertiesService:{getScriptProperties:()=>({getProperties:()=>({...properties})})},SpreadsheetApp:{openById:id=>{assert.equal(id,properties.LEAD_SHEET_ID);return {getSheetByName:()=>sheet,insertSheet:()=>sheet};},flush:()=>{if(flushFault){flushFault=false;throw Error('synthetic flush fault');}}},LockService:{getScriptLock:()=>({tryLock:()=>!busy,waitLock:()=>{if(busy)throw Error('busy');},releaseLock(){}})},Utilities:{Charset:{UTF_8:'utf8'},DigestAlgorithm:{SHA_256:'sha256'},getUuid:randomUUID,computeDigest:(_,s)=>Array.from(createHash('sha256').update(s).digest(),b=>b>127?b-256:b),computeHmacSha256Signature:(s,key)=>Array.from(createHmac('sha256',key).update(s).digest(),b=>b>127?b-256:b)},ContentService:{MimeType:{JSON:'json'},createTextOutput:text=>({text,setMimeType(){return this;}})},MailApp:{getRemainingDailyQuota:()=>quota,sendEmail:message=>{mail.push(message);if(sendFault)throw Error('synthetic ambiguous send');}}});
  vm.runInContext(evaluatedSource.toString(),context,{timeout:1000});
  context.initializeLeadRouting();
  const payload=()=>({request_id:randomUUID(),role:'tenant',name:'TEST synthetic',phone:'+971500000000',email:'fixture@example.invalid',country:'UAE',area:'Synthetic',budget:'To discuss',timeline:'Immediate / move now',funding:'To discuss',property_type:'Apartment',property_details:'',authority:'',contact_consent:true,marketing_consent:false,campaign:'SYNTHETIC',landing_page:'https://blackswanrealestate.ae/enquire/rent/',website:'',started_at:Date.now()-5000});
  const post=(p,changes={})=>{const body=JSON.stringify(p),timestamp=String(Date.now());const env={version:1,body,timestamp,signature:createHmac('sha256',properties.HMAC_SECRET).update(`v1\n${timestamp}\n${body}`).digest('hex'),...changes};if(!Object.hasOwn(changes,'signature'))env.signature=createHmac('sha256',properties.HMAC_SECRET).update(`v1\n${env.timestamp}\n${env.body}`).digest('hex');return JSON.parse(context.doPost({postData:{contents:JSON.stringify(env)}}).text);};
  return {rows,mail,properties,context,payload,post,postWire:raw=>JSON.parse(context.doPost({postData:{contents:raw}}).text),setBusy:v=>busy=v,failFlush:()=>flushFault=true,setSendFault:v=>sendFault=v,setQuota:v=>quota=v};
}
