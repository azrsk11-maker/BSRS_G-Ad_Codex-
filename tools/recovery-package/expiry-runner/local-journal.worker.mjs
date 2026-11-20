// Disposable test-only child; never imported by the journal or runner.
import {createLocalJournal} from './local-journal.mjs';
const [mode,directory,journalId]=process.argv.slice(2);
const journal=createLocalJournal(directory,{journalId,enabled:true,authorization:'USE_SYNTHETIC_LOCAL_JOURNAL'});
try{
 await journal.exclusive(async tx=>{
  const state=await tx.load();
  if(mode==='read'){process.send?.({kind:'READ',lastNowMs:state.lastNowMs});return;}
  if(mode==='crash'){state.lastNowMs=1700000000000;await tx.save(state);}
  if(!['hold','crash'].includes(mode))throw Error('UNKNOWN_SYNTHETIC_WORKER_MODE');
  process.send?.({kind:mode==='crash'?'SAVED':'LOCKED'});
  await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('SYNTHETIC_WORKER_TIMEOUT')),15000);
   process.once('message',message=>{clearTimeout(timer);message?.kind==='RELEASE'?resolve():reject(Error('SYNTHETIC_WORKER_PROTOCOL'));});
  });
 });
 process.disconnect?.();
}catch{process.send?.({kind:'HELD'});process.exitCode=1;process.disconnect?.();}
