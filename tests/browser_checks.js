// Run against the opened generated HTML using gstack browse eval.
return await (async () => {
  const $ = id => document.getElementById(id);
  const data = JSON.parse($('handbook-data').textContent);
  document.documentElement.style.scrollBehavior='auto';
  const checks = [];
  function assert(condition, name) {if(!condition)throw new Error(name);checks.push(name);}
  const visible = () => [...document.querySelectorAll('article.entry')].filter(e=>!e.hidden);
  function select(id,value){$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}));}
  function search(value){$('search').value=value;$('search').dispatchEvent(new Event('input',{bubbles:true}));}
  function clear(){$('clear').click();}
  const pause = () => new Promise(r=>setTimeout(r,80));
  clear();
  assert(visible().length===552,'all 552 entries visible');
  assert(document.querySelectorAll('section.chapter').length===32,'all 32 chapters');
  for(const code of ['trusted','qualified','uncertain','disputed','incorrect','experience']){
    select('status-filter',code);
    assert(visible().length===data.items.filter(r=>r.status===code).length,'status '+code+' count matches data');
    assert(visible().every(e=>e.querySelector('.status').classList.contains(code)),'status '+code+' has no leakage');
    select('chapter-filter','13');
    assert(visible().length===data.items.filter(r=>r.status===code&&r.chapter===13).length,'combined chapter 13 / '+code);
    select('chapter-filter','');
  }
  clear();search('c13-i036');
  assert(visible().length===1&&visible()[0].id==='c13-i036','ID search');
  clear();search('煮沸 化学');
  assert(visible().some(e=>e.id==='c13-i036'),'multiple keywords across revised text and summary');
  clear();search('a-no-such-keyword-923468');
  assert(!visible().length&&!$('empty').hidden,'empty result message');
  location.hash='#c13-i036';await pause();
  assert(visible().length===552&&!$('c13-i036').hidden,'hidden deep link clears incompatible filters');
  assert($('c13-i036').querySelector('details').open,'deep link opens full evidence');
  clear();select('chapter-filter','32');location.hash='#chapter-01';await pause();
  assert(!document.getElementById('chapter-01').hidden&&visible().length===552,'chapter link restores hidden chapter');
  assert(document.documentElement.scrollWidth<=innerWidth,'no horizontal viewport overflow at '+innerWidth);
  assert([...document.querySelectorAll('button')].every(b=>b.type==='button'),'buttons avoid implicit form submission');
  assert([...document.querySelectorAll('a[target="_blank"]')].every(a=>a.rel.includes('noopener')),'external links isolated');
  assert(!document.querySelector('script[src],link[href]'),'no external script or stylesheet');
  const externalResources=performance.getEntriesByType('resource').filter(e=>/^https?:/.test(e.name));
  assert(externalResources.length===0,'no runtime HTTP resource requests');
  // Force the denied-clipboard path regardless of browser clipboard grants.
  const prior=Object.getOwnPropertyDescriptor(navigator,'clipboard');
  Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('permission denied'))},configurable:true});
  const button=$('c13-i036').querySelector('button');button.click();await pause();
  assert($('copy-dialog').open,'denied clipboard opens manual dialog');
  assert($('copy-text').value.includes('c13-i036')&&$('copy-text').value.includes('适用条件：')&&$('copy-text').value.includes('2026-10-07'),'manual text preserves ID, conditions and dates');
  $('close-copy').click();assert(!$('copy-dialog').open&&document.activeElement===button,'manual dialog closes and restores focus');
  if(prior)Object.defineProperty(navigator,'clipboard',prior);else delete navigator.clipboard;
  const details=[...document.querySelectorAll('.entry-details')];
  search('c13-i036');
  const priorOpen=details.map(d=>d.open);window.dispatchEvent(new Event('beforeprint'));
  assert(details.every(d=>d.open),'print exposes full evidence content');
  assert(visible().length===552,'print includes whole handbook despite filters');
  window.dispatchEvent(new Event('afterprint'));
  assert(details.every((d,i)=>d.open===priorOpen[i]),'afterprint restores reading state');
  assert(visible().length===1&&visible()[0].id==='c13-i036','afterprint restores filters');
  clear();location.hash='#top';await pause();window.scrollTo(0,0);
  return {passed:checks.length,viewport:[innerWidth,innerHeight],protocol:location.protocol,checks};
})();
