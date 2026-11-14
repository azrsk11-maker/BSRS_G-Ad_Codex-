/** Execute the pinned local business audit. No network, Google source, or writes. */
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {constants} from 'node:fs';
import {lstat,open,readFile,realpath} from 'node:fs/promises';
import {isAbsolute,join,relative,sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const HISTORY=fileURLToPath(new URL('../../qualification-history/',import.meta.url));
const ROOT=fileURLToPath(new URL('../../../',import.meta.url));
// Exact reviewed producer bytes, including its preserved schema/classifier.
export const HISTORY_COMPONENTS=Object.freeze({
  'audit_history.py':'6df11cba881fb23328aa7e0a3ea20cd8c0c38cca45741346a6358fd2b28fff6a',
  'qualification_core.py':'ff1bf64d1f76e9ce8c209feac98ea182b81f57693d618a78529416f88a261ded',
  'qualification_sources.py':'678d50f2b622d8bb16a5a3d10f03ce419d0558d8790d893b4b275bdca248fbcd',
  'schema/outcome-register-schema.json':'bf477cc0cc4a161775abd702777898c6046d5dfcf0f2ae0e86fe078a3a63d9df',
});
const receipts=new WeakSet(),MAX_OUTPUT=2*1024*1024;
const require=(condition,code)=>{if(!condition)throw new Error(code);};
const exact=(value,keys)=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&Object.keys(value).every(key=>keys.includes(key));
const count=value=>Number.isSafeInteger(value)&&value>=0&&value<=10000;
const hash=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
const clockValue=value=>typeof value==='string'&&
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+]00:00)$/.test(value)&&Number.isFinite(Date.parse(value));
const sameClock=(left,right)=>clockValue(left)&&clockValue(right)&&Date.parse(left)===Date.parse(right)&&
  ((/\.(\d+)/.exec(left)?.[1]??'').slice(3).replace(/0+$/,''))===
  ((/\.(\d+)/.exec(right)?.[1]??'').slice(3).replace(/0+$/,''));
const day=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&
  Number.isFinite(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
const freeze=value=>{if(value&&typeof value==='object'){for(const item of Object.values(value))freeze(item);Object.freeze(value);}return value;};

async function pinnedComponents(){
  for(const [name,expected] of Object.entries(HISTORY_COMPONENTS)){
    const path=join(HISTORY,name),info=await lstat(path);
    require(info.isFile()&&!info.isSymbolicLink(),'QUALIFICATION_PRODUCER_TYPE_INVALID');
    const actual=createHash('sha256').update(await readFile(path)).digest('hex');
    require(actual===expected,'QUALIFICATION_PRODUCER_BYTES_NOT_REVIEWED');
  }
}

async function privateInput(value){
  require(typeof value==='string'&&isAbsolute(value),'EXPLICIT_PRIVATE_HISTORY_PATH_REQUIRED');
  const info=await lstat(value);
  require(info.isFile()&&!info.isSymbolicLink()&&info.size<=10*1024*1024,'PRIVATE_HISTORY_FILE_INVALID');
  const resolved=await realpath(value),root=await realpath(ROOT),child=relative(root,resolved);
  require(child==='..'||child.startsWith('..'+sep)||isAbsolute(child),'PRIVATE_HISTORY_OUTSIDE_CHECKOUT_REQUIRED');
  const source=await open(resolved,constants.O_RDONLY|(constants.O_NOFOLLOW??0));
  try{
    const before=await source.stat();
    require(before.isFile()&&before.size<=10*1024*1024&&info.dev===before.dev&&info.ino===before.ino,
      'PRIVATE_HISTORY_CHANGED_DURING_READ');
    const bytes=Buffer.alloc(10*1024*1024+1);let used=0;
    while(used<bytes.length){const result=await source.read(bytes,used,bytes.length-used,null);if(result.bytesRead===0)break;used+=result.bytesRead;}
    const after=await source.stat();
    require(used<=10*1024*1024&&used===before.size&&before.size===after.size&&before.mtimeMs===after.mtimeMs&&
      before.dev===after.dev&&before.ino===after.ino,'PRIVATE_HISTORY_CHANGED_DURING_READ');
    return {path:resolved,sha256:createHash('sha256').update(bytes.subarray(0,used)).digest('hex')};
  }finally{await source.close();}
}

function execute(python,args){
  return new Promise((resolve,reject)=>{
    let child;
    try{child=spawn(python,args,{shell:false,windowsHide:true,stdio:['ignore','pipe','pipe'],cwd:HISTORY});}
    catch{reject(new Error('QUALIFICATION_AUDIT_PROCESS_UNAVAILABLE'));return;}
    const chunks=[];let size=0,failed=false;
    const stop=code=>{if(!failed){failed=true;child.kill();reject(new Error(code));}};
    const timeout=setTimeout(()=>stop('QUALIFICATION_AUDIT_TIME_LIMIT'),30000);timeout.unref();
    child.stdout.on('data',bytes=>{size+=bytes.length;if(size>MAX_OUTPUT)stop('QUALIFICATION_AUDIT_OUTPUT_LIMIT');else chunks.push(bytes);});
    child.stderr.on('data',bytes=>{size+=bytes.length;if(size>MAX_OUTPUT)stop('QUALIFICATION_AUDIT_OUTPUT_LIMIT');});
    child.on('error',()=>{clearTimeout(timeout);stop('QUALIFICATION_AUDIT_PROCESS_UNAVAILABLE');});
    child.on('close',code=>{clearTimeout(timeout);if(failed)return;
      if(code!==0){reject(new Error('QUALIFICATION_AUDIT_INPUT_REJECTED'));return;}
      try{resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')));}catch{reject(new Error('QUALIFICATION_AUDIT_RESPONSE_INVALID'));}
    });
  });
}

function validateAggregate(a,fromDay,toDay,now){
  require(exact(a,['schema','scope','UPLOAD_PROHIBITED','fixture_only','evaluated_at_utc','selection_window',
    'holds','source_truth_independently_verified','review','provenance','source_counts','by_day_and_source',
    'ads_by_day_and_native_campaign','source_hold_counts','contains_record_identifiers_or_click_data']),
    'QUALIFICATION_AGGREGATE_FIELDS_INVALID');
  require(a.schema==='bsre-commercial-qualification-aggregate-v1'&&a.scope==='PRIVATE_BUSINESS_AGGREGATE_REVIEW_ONLY'&&
    a.UPLOAD_PROHIBITED===true&&typeof a.fixture_only==='boolean'&&a.source_truth_independently_verified===false&&
    a.contains_record_identifiers_or_click_data===false,'QUALIFICATION_AGGREGATE_SCOPE_INVALID');
  require(sameClock(a.evaluated_at_utc,now)&&exact(a.selection_window,['from_day','to_day','end_inclusive','timezone'])&&
    a.selection_window.from_day===fromDay&&a.selection_window.to_day===toDay&&
    a.selection_window.end_inclusive===true&&a.selection_window.timezone==='Asia/Dubai','QUALIFICATION_AGGREGATE_WINDOW_INVALID');
  require(Array.isArray(a.holds)&&a.holds.every(code=>typeof code==='string'&&/^[A-Z_]+$/.test(code)),
    'QUALIFICATION_AGGREGATE_HOLDS_INVALID');
  require(exact(a.provenance,['ledger_sha256','source_review_sha256','business_review_sha256','validator_components_sha256'])&&
    hash(a.provenance.ledger_sha256)&&(a.provenance.source_review_sha256===null||hash(a.provenance.source_review_sha256))&&
    hash(a.provenance.business_review_sha256)&&exact(a.provenance.validator_components_sha256,Object.keys(HISTORY_COMPONENTS))&&
    Object.entries(HISTORY_COMPONENTS).every(([key,value])=>a.provenance.validator_components_sha256[key]===value),
    'QUALIFICATION_AGGREGATE_PROVENANCE_INVALID');
  require(exact(a.review,['observed_at_utc','valid_until_utc','input_bytes_bound','author_independently_verified'])&&
    a.review.input_bytes_bound===true&&a.review.author_independently_verified===false&&
    Number.isFinite(Date.parse(a.review.observed_at_utc))&&Number.isFinite(Date.parse(a.review.valid_until_utc)),
    'QUALIFICATION_AGGREGATE_REVIEW_INVALID');
  require(exact(a.source_counts,['intake_rows_supplied','outcome_rows_supplied','selected_first_qualified_people'])&&
    Object.values(a.source_counts).every(count),'QUALIFICATION_AGGREGATE_COUNTS_INVALID');
  const groups=['ADS_ATTRIBUTED','OTHER_SOURCE','UNKNOWN_SOURCE'];let total=0;
  for(const [date,counts] of Object.entries(a.by_day_and_source)){
    require(day(date)&&date>=fromDay&&date<=toDay&&exact(counts,groups)&&Object.values(counts).every(count),
      'QUALIFICATION_AGGREGATE_DAY_INVALID');
    total+=Object.values(counts).reduce((sum,value)=>sum+value,0);
  }
  require(total===a.source_counts.selected_first_qualified_people&&count(total),'QUALIFICATION_AGGREGATE_TOTAL_MISMATCH');
  for(const [date,counts] of Object.entries(a.ads_by_day_and_native_campaign)){
    require(Object.hasOwn(a.by_day_and_source,date)&&counts&&typeof counts==='object'&&!Array.isArray(counts)&&
      Object.entries(counts).every(([campaign,value])=>/^\d{1,20}$/.test(campaign)&&count(value))&&
      Object.values(counts).reduce((sum,value)=>sum+value,0)===a.by_day_and_source[date].ADS_ATTRIBUTED,
      'QUALIFICATION_NATIVE_CAMPAIGN_AGGREGATE_INVALID');
  }
  require(Object.entries(a.by_day_and_source).every(([date,counts])=>counts.ADS_ATTRIBUTED===0||
    Object.hasOwn(a.ads_by_day_and_native_campaign,date)),'QUALIFICATION_NATIVE_CAMPAIGN_AGGREGATE_INCOMPLETE');
}

/** Receipt identity is local execution provenance, never source authentication. */
export function isExecutedHistoryAudit(value){return receipts.has(value);}

export async function readQualificationHistory(options,{fromDay,toDay}){
  require(exact(options,['python','ledger_path','source_review_path','business_review_path','now_utc']),
    'QUALIFICATION_AUDIT_OPTIONS_INVALID');
  require(typeof options.python==='string'&&options.python.length>0&&typeof options.now_utc==='string'&&
    clockValue(options.now_utc),
    'QUALIFICATION_AUDIT_CLOCK_AND_EXECUTABLE_REQUIRED');
  require(day(fromDay)&&day(toDay)&&fromDay<=toDay,'QUALIFICATION_AUDIT_DAYS_INVALID');
  let paths;
  try{paths=await Promise.all([privateInput(options.ledger_path),privateInput(options.business_review_path),
    options.source_review_path===null?null:privateInput(options.source_review_path)]);await pinnedComponents();}
  catch(error){if(error?.code)throw new Error('PRIVATE_HISTORY_INPUT_UNAVAILABLE');throw error;}
  // -I ignores user PYTHONPATH/site customization. The fixed launcher restores
  // only this reviewed module directory, then invokes the pinned audit CLI.
  const launcher="import runpy,sys;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name='__main__')";
  const args=['-I','-B','-c',launcher,HISTORY,join(HISTORY,'audit_history.py'),'--ledger',paths[0].path,
    '--business-review',paths[1].path,'--now',options.now_utc,'--from-day',fromDay,'--to-day',toDay];
  if(paths[2]!==null)args.push('--source-review',paths[2].path);
  const result=await execute(options.python,args);
  try{await pinnedComponents();}catch{throw new Error('QUALIFICATION_PRODUCER_CHANGED_DURING_AUDIT');}
  const aggregate=result?.commercial_qualification_aggregate;
  validateAggregate(aggregate,fromDay,toDay,options.now_utc);
  require(aggregate.provenance.ledger_sha256===paths[0].sha256&&
    aggregate.provenance.business_review_sha256===paths[1].sha256&&
    aggregate.provenance.source_review_sha256===(paths[2]?.sha256??null),'QUALIFICATION_AUDIT_INPUT_BYTES_MISMATCH');
  let current;
  try{current=await Promise.all(paths.map(value=>value===null?null:privateInput(value.path)));}
  catch{throw new Error('PRIVATE_HISTORY_CHANGED_DURING_AUDIT');}
  require(current.every((value,index)=>value===null||value.sha256===paths[index].sha256),
    'PRIVATE_HISTORY_CHANGED_DURING_AUDIT');
  freeze(aggregate);receipts.add(aggregate);return aggregate;
}
