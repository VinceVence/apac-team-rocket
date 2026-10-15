// Original Mint Town characters. One shared pixel grid and foot anchor for every frame.
const SKIN=['#e8bb91','#c98e64','#a96f4e','#8c563d','#f1ceb0'];
const HAIR=['#37332c','#624533','#392e2a','#79736a','#a36b43'];
const SHIRTS=['#528e7c','#c27655','#698ba9','#a584ae','#d0a34f','#597c9e','#c5808a','#78976b'];
const hash=text=>{let n=2166136261;for(const c of text)n=Math.imul(n^c.charCodeAt(0),16777619);return n>>>0};
export const residentLabel=id=>'Resident '+Number(String(id).replace(/^C/,''));
export function alarmMotion(elapsed,reduced=false){
  const active=elapsed>=0&&elapsed<8000;
  return {active,jump:active&&!reduced?Math.max(0,Math.sin(elapsed/160))*15:0};
}
export function protectionMotion(elapsed,reduced=false){
  const active=elapsed>=0&&elapsed<6500;
  return {active,lift:active&&!reduced?4+Math.sin(elapsed/230)*3:0};
}
export function residentAlerts(demo){
  const reports=(demo.incidents||[]).filter(i=>i.report_id&&i.report_status!=='resolved').map(i=>({...i,mark:'!'}));
  const held=(demo.protection?.recent||[]).map(i=>({...i,mark:'✓'}));
  const legacy=(demo.incidents||[]).filter(i=>i.status==='blocked').map(i=>({...i,mark:'✓'}));
  const alerts=new Map();
  for(const i of [...reports,...held,...legacy].sort((a,b)=>(b.created_at||'').localeCompare(a.created_at||'')))if(!alerts.has(i.customer_id))alerts.set(i.customer_id,{customer_id:i.customer_id,mark:i.mark,id:i.id});
  return [...alerts.values()];
}

export function appearance(id){
  const n=hash(id),role=Number(id.slice(1))>=98?'merchant':id==='C097'?'cashier':'resident';
  return {skin:SKIN[n%SKIN.length],hair:HAIR[(n>>>3)%HAIR.length],shirt:SHIRTS[(n>>>6)%SHIRTS.length],
    cut:(n>>>10)%4,accessory:(n>>>12)%5,role};
}

export function drawResident(ctx,x,y,id,direction='down',frame=0,paying=false,alarmed=false){
  const a=appearance(id),stride=[0,2,0,-2][frame%4],back=direction==='up',side=direction==='left'||direction==='right';
  const facing=direction==='left'?-1:1;
  const r=(px,py,w,h,color)=>{ctx.fillStyle=color;ctx.fillRect(Math.round(x+px),Math.round(y+py),w,h)};
  // Feet share an anchor at y + 25. Movement changes limbs, never overall scale.
  if(!alarmed)r(-9,24,18,3,'#637a5f55');r(-5,16,5,7+stride,'#42545b');r(1,16,5,7-stride,'#42545b');
  r(-6,22+stride,6,3,'#343d3c');r(1,22-stride,6,3,'#343d3c');
  r(-7,5,14,13,a.shirt);r(-7,5,14,2,'#ffffff2d');r(-5,17,10,2,'#00000020');
  r(-10,alarmed?-5:7-stride,3,9,a.skin);r(7,alarmed?-5:7+stride,3,9,a.skin);
  if(a.role==='merchant'){r(-5,9,10,9,'#e9ddbc');r(-5,7,2,3,'#e9ddbc');r(3,7,2,3,'#e9ddbc');r(-2,12,5,3,'#b7ac8e')}
  else if(a.role==='cashier'){r(-2,7,4,10,'#ecebda');r(0,7,1,7,'#31534b')}
  else if(a.accessory===0){r(back?-5:4,7,5,10,'#8c694e');r(-4,7,1,9,'#614c3c')}
  r(-5,-5,11,10,a.skin);r(-6,-8,13,6,a.hair);r(-7,-5,3,8,a.hair);
  if(a.cut===1)r(5,-4,3,10,a.hair);
  if(a.cut===2){r(-8,-10,16,4,'#c29b54');r(-10,-6,20,3,'#ddba73')}
  if(a.cut===3){r(-4,-9,9,3,a.hair);r(5,-5,3,4,a.hair)}
  if(back){r(-5,-3,11,7,a.hair);r(-3,4,7,2,a.skin)}
  else if(side){r(facing===-1?-5:4,-1,2,2,'#29342f');r(facing===-1?-7:6,1,2,3,a.skin)}
  else{r(-3,-1,2,2,'#29342f');r(3,-1,2,2,'#29342f');r(0,3,3,1,'#a56d55')}
  if(alarmed){r(-2,-2,2,2,'#29342f');r(3,-2,2,2,'#29342f');r(0,2,3,3,'#783e32')}
  if(!back&&a.accessory===1){r(-4,-2,4,3,'#58635a');r(2,-2,4,3,'#58635a');r(0,-1,2,1,'#58635a')}
  if(paying){r(6,8,4,5,a.skin);r(8,3,6,10,'#304c44');r(9,4,4,6,'#b8e3cc');r(10,11,2,1,'#f0ebd7')}
}
