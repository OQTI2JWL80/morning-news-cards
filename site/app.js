const $ = (selector) => document.querySelector(selector);
const news = $('#news');
const dateSelect = $('#edition-date');
let currentEdition;
let requestNumber = 0;
let currentController;
let toastTimer;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function kstDate(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Seoul', year:'numeric', month:'2-digit', day:'2-digit'}).format(date);
}

function expectedEdition(date = new Date()) {
  // Subtract seven hours before taking the Korea calendar date.
  return kstDate(new Date(date.getTime() - 7 * 60 * 60 * 1000));
}

function timeLabel(value) {
  return new Intl.DateTimeFormat('ko-KR', {timeZone:'Asia/Seoul', hour:'2-digit', minute:'2-digit', hour12:false}).format(new Date(value));
}

function safeUrl(value) {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}

function icon(type) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('fill','none'); svg.setAttribute('stroke','currentColor');
  svg.setAttribute('stroke-width','1.7'); svg.setAttribute('aria-hidden','true');
  const path = document.createElementNS(svg.namespaceURI,'path');
  path.setAttribute('d', type === 'save' ? 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5' : 'M14 3h7v7m0-7L10 14M11 4H4v16h16v-7');
  svg.append(path); return svg;
}

function summaryReason(article) {
  const reasons = {
    quota_exceeded:'오늘의 무료 요약 한도에 도달했습니다.', key_missing:'AI 요약 연결을 준비하고 있습니다.',
    free_tier_unconfirmed:'무료 요약 설정을 확인하고 있습니다.', updated_after_cutoff:'07시 이후 수정된 본문은 요약에서 제외했습니다.',
    restricted:'이 기사는 원문에서 직접 확인해 주세요.', model_unavailable:'오늘은 AI 요약을 사용할 수 없습니다.',
    summary_unverified:'본문에 근거한 요약을 충분히 확인하지 못했습니다.', invalid_response:'요약 결과를 충분히 확인하지 못했습니다.',
    key_invalid:'AI 요약 연결을 확인하고 있습니다.', request_limit:'오늘의 요약 처리량에 도달했습니다.',
  };
  return reasons[article.summaryStatus] || '기사 본문을 충분히 확인하지 못했습니다.';
}

function makeCard(article, index, section) {
  const card = el('article','news-card'); card.dataset.articleId = article.id;
  const top = el('div','card-topline');
  top.append(el('span','',article.city || section.name), el('span','card-rank',String(index + 1).padStart(2,'0')));
  card.append(top, el('h3','',article.title));
  if (article.summaryStatus === 'summarized' && article.bullets.length === 3) {
    const list = el('ul','summary');
    article.bullets.forEach(text => list.append(el('li','',text)));
    card.append(list);
  } else {
    const missing = el('p','summary-missing');
    missing.append(el('strong','','본문 요약 없음'), document.createTextNode(`${summaryReason(article)} 원문에서 내용을 확인할 수 있습니다.`));
    card.append(missing);
  }
  const bottom = el('div','card-bottom');
  const source = article.sources[0];
  const line = el('div','source-line');
  const time = el('time','',new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(article.publishedAt)));
  time.dateTime = article.publishedAt;
  line.append(el('span','source-name',source.name),time);
  const actions = el('div','card-actions');
  const link = el('a','source-link','원문 읽기');
  const url = safeUrl(source.url);
  if (url) {link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';}
  const external = icon('external'); external.classList.add('external-icon'); link.append(external);
  const save = el('button','save-button'); save.type = 'button';
  save.setAttribute('aria-label',`${article.title} 이미지 저장`);
  save.append(icon('save'),document.createTextNode('이미지 저장'));
  save.addEventListener('click', () => downloadCard(article, section, index, save));
  actions.append(link,save); bottom.append(line,actions);
  if (article.sources.length > 1) {
    const related = el('p','related','함께 보도 ');
    article.sources.slice(1).forEach(source => {
      const href = safeUrl(source.url); if (!href) return;
      const link = el('a','',source.name); link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer'; related.append(link);
    });
    bottom.append(related);
  }
  card.append(bottom); return card;
}

function updateNotice(edition) {
  const notice = $('#edition-status');
  const expected = expectedEdition();
  const isArchive = edition.date !== dateSelect.options[0]?.value;
  const stale = !isArchive && edition.date < expected;
  notice.className = `notice${stale ? ' stale' : ''}`;
  const parts = [];
  if (isArchive) parts.push(`${edition.date} 보관판을 보고 있습니다.`);
  else if (stale) parts.push(`오늘자 갱신 지연 · 마지막으로 준비된 ${edition.date} 브리핑입니다.`);
  if (edition.articles.length < 33) parts.push(`확인된 기사 ${edition.articles.length}개를 담았습니다. 부족한 분야는 아래에 표시합니다.`);
  if (edition.summaryCount < edition.articles.length) parts.push('일부 기사는 본문 요약 없이 제공됩니다.');
  if (edition.collection.feedsOk < edition.collection.feedsTotal) parts.push('일부 뉴스 출처에 연결하지 못했습니다.');
  notice.textContent = parts.join(' '); notice.hidden = !parts.length;
}

function render(edition) {
  currentEdition = edition;
  const date = new Date(edition.cutoffAt);
  $('#edition-label').textContent = new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',weekday:'long',year:'numeric',month:'short',day:'numeric'}).format(date).toUpperCase();
  $('#edition-description').textContent = `${edition.date.replaceAll('-','.')} · 한국시간 07:00 기준 · ${kstDate(new Date(edition.generatedAt)).replaceAll('-','.')} ${timeLabel(edition.generatedAt)} 갱신`;
  $('#story-count').textContent = edition.articles.length;
  $('#summary-count').textContent = `${edition.summaryCount}개 본문 요약`;
  $('#reading-bar').hidden = false;
  const nav = $('#sections-nav'); nav.replaceChildren(); nav.hidden = false;
  news.replaceChildren(); news.setAttribute('aria-busy','false');
  edition.sections.forEach((section, position) => {
    const articles = edition.articles.filter(a => a.section === section.id);
    const jump = el('a','',section.name.replace('·비즈니스','')); jump.href = `#section-${section.id}`; jump.append(el('span','',String(articles.length))); nav.append(jump);
    const block = el('section',`news-section${section.id === 'top' ? ' top-section' : ''}`); block.id = `section-${section.id}`;
    const heading = el('div','section-heading');
    const left = el('div','section-title'); const title = el('h2','',section.name); title.id = `title-${section.id}`;
    block.setAttribute('aria-labelledby', title.id);
    left.append(el('span','section-number',String(position + 1).padStart(2,'0')),title,el('span','section-label',section.label));
    heading.append(left,el('span','section-count',`${articles.length} / ${section.count}`)); block.append(heading);
    if (articles.length) {
      const grid = el('div','card-grid'); articles.forEach((a,i) => grid.append(makeCard(a,i,section))); block.append(grid);
      if (articles.length < section.count) {
        const missingCities = section.id === 'local' ? ['서울시','고양시','파주시'].filter(city => !articles.some(a => a.city === city)) : [];
        block.append(el('p','section-gap',missingCities.length ? `${missingCities.join('·')} · 집계 시간 안에 확인된 지역 기사가 없습니다.` : `집계 시간 안에 확인된 서로 다른 기사 ${articles.length}개만 제공합니다.`));
      }
    } else block.append(el('div','empty-section','집계 시간 안에 이 분야의 기사를 충분히 확인하지 못했습니다.'));
    news.append(block);
  });
  updateNotice(edition);
}

function checkEdition(data, date) {
  if (data.schemaVersion !== 1 || data.date !== date || !Array.isArray(data.articles) || !Array.isArray(data.sections) || data.articles.length > 33) throw new Error('잘못된 브리핑 자료');
  for (const article of data.articles) {
    if (typeof article.title !== 'string' || !Array.isArray(article.sources) || !article.sources.length || !Array.isArray(article.bullets) || !safeUrl(article.sources[0].url)) throw new Error('잘못된 기사 자료');
  }
  return data;
}

async function loadEdition(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
  const number = ++requestNumber;
  currentController?.abort(); currentController = new AbortController();
  news.setAttribute('aria-busy','true');
  try {
    const response = await fetch(`./data/${date}.json`,{cache:'no-store',signal:currentController.signal});
    if (!response.ok) throw new Error('자료를 찾을 수 없습니다.');
    const data = checkEdition(await response.json(),date);
    if (number !== requestNumber) return;
    render(data);
    const location = new URL(window.location.href); location.searchParams.set('date',date); history.replaceState(null,'',location);
  } catch (error) {
    if (error.name === 'AbortError' || number !== requestNumber) return;
    if (currentEdition) { dateSelect.value = currentEdition.date; news.setAttribute('aria-busy','false'); toast('선택한 날짜를 불러오지 못했습니다. 이전 화면을 유지합니다.'); }
    else showError();
  }
}

function showError() {
  news.setAttribute('aria-busy','false'); news.replaceChildren();
  const box = el('div','load-error'); box.append(el('h2','','브리핑을 불러오지 못했습니다.'),el('p','','아직 첫 브리핑을 준비 중이거나 연결이 원활하지 않습니다. 잠시 후 다시 확인해 주세요.'));
  const retry = el('button','retry-button','다시 불러오기'); retry.addEventListener('click',init); box.append(retry); news.append(box);
}

async function init() {
  try {
    const response = await fetch('./data/index.json',{cache:'no-store'});
    if (!response.ok) throw new Error('No index');
    const index = await response.json();
    const days = [...new Set(index.editions.map(e => e.date).filter(date => /^\d{4}-\d{2}-\d{2}$/.test(date)))].sort().reverse().slice(0,30);
    if (!days.length) throw new Error('Empty index');
    dateSelect.replaceChildren(...days.map(date => {const option = el('option','',date.replaceAll('-','.')); option.value = date; return option;}));
    const requested = new URLSearchParams(window.location.search).get('date');
    dateSelect.value = days.includes(requested) ? requested : days[0]; dateSelect.disabled = false;
    await loadEdition(dateSelect.value);
  } catch { showError(); }
}

function toast(message) { clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').hidden = false; toastTimer = setTimeout(() => $('#toast').hidden = true,5000); }

function wrap(context,text,width) {
  const lines = []; let line = '';
  for (const character of Array.from(text)) {
    if (character === '\n') {lines.push(line);line='';continue;}
    if (context.measureText(line + character).width > width && line) {lines.push(line.trim());line=character;} else line += character;
  }
  if (line) lines.push(line.trim()); return lines;
}

async function downloadCard(article,section,index,button) {
  button.disabled = true;
  try {
    const {makeImage} = await import('./card-image.js');
    const blob = await makeImage(article,section,currentEdition,wrap,index);
    const url = URL.createObjectURL(blob); const anchor = el('a'); anchor.href = url; anchor.download = `morning-${currentEdition.date}-${article.id}.${blob.type === 'image/webp' ? 'webp' : 'png'}`;
    document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url),30000);
    toast(`이미지 저장을 요청했습니다 · ${Math.ceil(blob.size/1024)}KB`);
  } catch { toast('이미지를 저장하지 못했습니다. 브라우저의 화면 캡처를 이용해 주세요.'); }
  finally {button.disabled=false;}
}

dateSelect.addEventListener('change',() => loadEdition(dateSelect.value));
document.addEventListener('visibilitychange',() => {if (!document.hidden && currentEdition) updateNotice(currentEdition);});
setInterval(() => {if (currentEdition) updateNotice(currentEdition);},60000);
init();
