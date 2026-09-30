export async function makeImage(article,section,edition,wrap,index) {
  const canvas = document.createElement('canvas'); canvas.width=720; canvas.height=900;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas unavailable');
  const font = 'system-ui, "Malgun Gothic", sans-serif';
  const texts = article.summaryStatus === 'summarized' ? article.bullets : ['본문 요약 없음. 원문에서 자세한 내용을 확인해 주세요.'];
  let titleSize=36, bodySize=25, titleLines, bodyLines;
  let fits=false;
  for (let attempt=0; attempt<10; attempt++) {
    ctx.font=`750 ${titleSize}px ${font}`; titleLines=wrap(ctx,article.title,600);
    ctx.font=`400 ${bodySize}px ${font}`; bodyLines=texts.map(text => wrap(ctx,text,576));
    const total=titleLines.length*titleSize*1.4+35+bodyLines.reduce((sum,lines)=>sum+lines.length*bodySize*1.6+18,0);
    if (total<=590) {fits=true;break;}
    titleSize-=1;bodySize-=1;
  }
  if (!fits || titleSize<27 || bodySize<17) throw new Error('Text does not fit legibly');
  ctx.fillStyle='#f4f6f8';ctx.fillRect(0,0,720,900);
  ctx.fillStyle='#132f4c';ctx.fillRect(0,0,720,104);
  ctx.fillStyle='#e19a36';ctx.fillRect(0,104,720,5);
  ctx.fillStyle='#fff';ctx.font=`750 30px ${font}`;ctx.fillText('아침 일곱 시',48,61);
  ctx.font=`400 16px ${font}`;ctx.textAlign='right';ctx.fillText(`${edition.date} · 07:00 기준`,672,59);ctx.textAlign='left';
  ctx.fillStyle='#fff';ctx.fillRect(28,133,664,663);
  ctx.fillStyle='#225da4';ctx.font=`650 18px ${font}`;ctx.fillText(article.city || section.name,60,174);
  ctx.textAlign='right';ctx.fillStyle='#8195a8';ctx.font='italic 27px Georgia';ctx.fillText(String(index+1).padStart(2,'0'),660,174);ctx.textAlign='left';
  let y=212;ctx.textBaseline='top';ctx.fillStyle='#152d44';ctx.font=`750 ${titleSize}px ${font}`;
  for (const line of titleLines) {ctx.fillText(line,60,y);y+=titleSize*1.4;}
  y+=25;ctx.font=`400 ${bodySize}px ${font}`;ctx.fillStyle='#405365';
  for (const lines of bodyLines) {
    ctx.fillStyle='#225da4';ctx.fillRect(60,y+bodySize*.75,4,4);ctx.fillStyle='#405365';
    for (const line of lines) {ctx.fillText(line,78,y);y+=bodySize*1.6;}
    y+=18;
  }
  ctx.textBaseline='alphabetic';ctx.fillStyle='#607084';ctx.font=`500 17px ${font}`;
  const sourceWidth=article.summaryStatus === 'summarized' ? 260 : 590;
  let publisher=article.sources[0].name;while(ctx.measureText(publisher).width>sourceWidth) publisher=publisher.slice(0,-2)+'…';
  ctx.fillText(publisher,48,832);
  if (article.summaryStatus === 'summarized') {
    ctx.textAlign='right';ctx.font=`400 14px ${font}`;
    ctx.fillText(`AI 요약 · ${article.summaryModel || edition.ai?.model || '모델 기록 없음'}`,672,832);
    ctx.textAlign='left';
  }
  ctx.font=`400 14px ${font}`;ctx.fillText('Google 뉴스 기반 · AI 요약은 원문과 함께 확인하세요.',48,865);
  let result;
  for (const quality of [.88,.8,.7,.6]) {
    result = await new Promise(resolve => canvas.toBlob(resolve,'image/webp',quality));
    if (!result) throw new Error('Encoding failed');
    if (result.size<=150*1024) return result;
  }
  // Never reduce font size to meet the byte target. Preserve legibility instead.
  return result;
}
