// Static full-book checks, run with gstack browse eval.
return await (async () => {
  const $=id=>document.getElementById(id);
  const data=JSON.parse($('handbook-data').textContent);
  const checks=[];
  function assert(ok,name){if(!ok)throw new Error(name);checks.push(name);}
  const pause=()=>new Promise(r=>setTimeout(r,100));
  document.documentElement.style.scrollBehavior='auto';
  const articles=[...document.querySelectorAll('article.entry')];
  assert(articles.length===552,'all 552 entries present');
  assert(document.querySelectorAll('section.chapter').length===32,'all 32 chapters present');
  assert(articles.every(a=>!a.hidden&&getComputedStyle(a).display!=='none'),'all entries visible without search');
  assert(!document.querySelector('#search,#chapter-filter,#status-filter'),'no search or filter barrier');
  assert(!document.querySelector('details.entry-details'),'no collapsed entry bodies');
  assert(articles.every(a=>a.querySelector('.detail-body').getBoundingClientRect().height>0),'all evidence and original text directly visible');
  for(const code of ['trusted','qualified','uncertain','disputed','incorrect','experience'])assert(document.querySelectorAll('.status.'+code).length===data.items.filter(r=>r.status===code).length,'status '+code+' count matches data');
  assert(document.querySelectorAll('#desktop-toc a').length===32&&document.querySelectorAll('#mobile-toc a').length===32,'both complete chapter directories');
  assert(data.items.every(r=>$(r.id).textContent.includes(r.original_title)&&$(r.id).textContent.includes(r.summary)),'all original suggestions and summaries preserved');
  location.hash='#c13-i036';await pause();
  assert($('c13-i036').getBoundingClientRect().top<100,'native entry anchor navigation');
  if(innerWidth<720){document.querySelector('.mobile-toc').open=true;document.querySelector('#mobile-toc a').click();await pause();assert(!document.querySelector('.mobile-toc').open,'mobile directory closes after chapter navigation');}
  assert(document.documentElement.scrollWidth<=innerWidth,'no horizontal overflow');
  assert([...document.querySelectorAll('a[target="_blank"]')].every(a=>a.rel.includes('noopener')),'external links isolated');
  assert(!document.querySelector('script[src],link[href]'),'no external script or stylesheet');
  assert(!performance.getEntriesByType('resource').some(e=>/^https?:/.test(e.name)),'no runtime HTTP requests');
  const prior=Object.getOwnPropertyDescriptor(navigator,'clipboard');
  Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('denied'))},configurable:true});
  const button=$('c13-i036').querySelector('button');button.click();await pause();
  assert($('copy-dialog').open,'manual copy fallback opens');
  assert($('copy-text').value.includes('c13-i036')&&$('copy-text').value.includes('适用条件：'),'copy retains stable ID and conditions');
  $('close-copy').click();assert(!$('copy-dialog').open&&document.activeElement===button,'copy dialog restores focus');
  if(prior)Object.defineProperty(navigator,'clipboard',prior);else delete navigator.clipboard;
  window.dispatchEvent(new Event('beforeprint'));window.dispatchEvent(new Event('afterprint'));
  assert(articles.every(a=>!a.hidden),'printing preserves full-book reading');
  location.hash='#top';await pause();window.scrollTo(0,0);
  return {passed:checks.length,viewport:[innerWidth,innerHeight],checks};
})();
