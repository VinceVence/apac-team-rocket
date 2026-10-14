// Original Mint Town pixel art, with directional residents and payment interactions.
import {drawResident,appearance} from './resident-sprites.js';
export function createTown(canvas) {
  let ctx=canvas.getContext('2d');
  function rect(x,y,w,h,c){ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y),w,h)}
  function tree(x,y){rect(x+12,y+26,8,18,'#80684c');rect(x+3,y+12,29,23,'#54775b');rect(x+7,y+4,21,29,'#658c61');rect(x+12,y,12,28,'#779968');rect(x+6,y+12,9,8,'#88a876')}

  function house(s){var x=s.x,y=s.y;rect(x-42,y+8,105,69,'#91a281');rect(x-49,y-13,106,75,'#e9dcba');rect(x-49,y+30,106,9,'#d8c89f');rect(x-57,y-29,122,39,s.roof);rect(x-50,y-36,108,10,s.roof);rect(x-44,y-43,96,8,s.roof);rect(x-57,y+3,122,7,'#685d4b');for(var q=0;q<4;q++){rect(x-45+q*28,y-26,21,3,'#ffffff22');rect(x-48+q*28,y-13,21,3,'#00000016')}rect(x-10,y+23,23,39,'#786b51');rect(x-5,y+28,13,18,'#9bb5a3');rect(x-37,y+21,17,20,'#7faaa7');rect(x+24,y+21,19,20,'#7faaa7');rect(x-36,y+30,17,3,'#e4d7b5');rect(x+25,y+30,19,3,'#e4d7b5');rect(x-12,y+62,28,6,'#ded0af');if(s.kind===1){for(var j=0;j<6;j++)rect(x-48+j*17,y+9,17,10,j%2?'#efe7cf':s.roof)}if(s.kind===3){rect(x-4,y-25,8,21,'#e5e9ce');rect(x-10,y-19,20,8,'#e5e9ce')}if(s.kind===4){rect(x-10,y-27,23,18,'#cad8af');rect(x-5,y-22,5,9,'#426249');rect(x+4,y-22,5,9,'#426249')}}
  function label(text,x,y,w){rect(x-w/2,y,w,19,'#fff6de');ctx.fillStyle='#455546';ctx.font='600 11px "DM Sans",sans-serif';ctx.textAlign='center';ctx.fillText(text,x,y+13)}

  const shops=[
    {x:90,y:100,name:'KAPE CAFÉ',roof:'#bf7459',kind:0},
    {x:350,y:78,name:'SARI-SARI',roof:'#647c9a',kind:1},
    {x:99,y:334,name:'MERCADO',roof:'#9b6985',kind:1},
    {x:570,y:100,name:'TOWN BANK',roof:'#528875',kind:4},
    {x:350,y:350,name:'CASH AGENT',roof:'#6c8b6c',kind:4},
    {x:563,y:335,name:'FAMILY HOMES',roof:'#849293',kind:0}
  ];

  let customers=[],population=[],recent=[],selected=null,kind='world',running=false,speed=1,raf=0,last=0,background=null,market=null;
  const actors=new Map();let alerts=new Map();const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  function makeBackground(){
    background=document.createElement('canvas');background.width=768;background.height=480;
    const live=ctx;ctx=background.getContext('2d');
    ctx.imageSmoothingEnabled=false;
    rect(0,0,768,480,'#b1c894');
    for(let i=0;i<145;i++)rect((i*71+9)%764,(i*47+13)%476,3,3,i%3?'#a5bd8933':'#d8dfa555');
    rect(0,209,768,65,'#d8cda9');rect(250,0,50,480,'#d8cda9');rect(469,0,50,480,'#d8cda9');
    rect(0,222,768,37,'#e8ddbb');rect(261,0,28,480,'#e8ddbb');rect(480,0,28,480,'#e8ddbb');
    rect(0,450,768,30,'#81b4ac');rect(0,455,768,3,'#a5cabc');
    for(const x of [274,494]){rect(x-34,448,68,32,'#9a7c53');for(let i=0;i<7;i++)rect(x-32+i*10,448,2,32,'#c6a272')}
    rect(323,157,125,43,'#8ba777');rect(369,162,35,25,'#80b7af');rect(377,166,19,16,'#c8dbc3');
    [[18,12],[203,24],[707,15],[711,83],[196,343],[20,367],[674,364],[703,407],[335,283],[407,287],[620,20],[39,190],[666,187]].forEach(v=>tree(...v));
    shops.forEach(s=>{house(s);label(s.name,s.x,s.y+78,Math.max(90,s.name.length*7))});

    // Cash point, payment terminals and market produce are original pixel assets.
    rect(623,130,19,32,'#3c6857');rect(626,134,13,12,'#b8ddc9');rect(628,137,9,6,'#6f9f91');rect(627,153,11,3,'#e2d8b5');
    for(const [x,y] of [[130,153],[366,132],[141,386]]){rect(x,y,8,13,'#40564c');rect(x+1,y+1,6,8,'#e7efd6');rect(x+2,y+2,2,2,'#40564c');rect(x+5,y+5,1,2,'#40564c')}
    for(let i=0;i<3;i++){rect(144+i*14,364,12,12,'#aa8153');rect(146+i*14,361,8,7,['#dbab54','#97ac62','#bc6c50'][i]);}
    rect(40,295,30,7,'#8f7958');rect(43,302,3,8,'#6a634d');rect(64,302,3,8,'#6a634d');
    ctx=live;
  }
  function paint(time=performance.now()){
    if(!background)makeBackground();ctx.imageSmoothingEnabled=false;ctx.drawImage(background,0,0);
    if(market)market.goods.forEach((good,i)=>{const shop=shops[i];label(good.status==='open'?'₱'+(good.price_minor/100).toFixed(2):'CLOSED',shop.x,shop.y+100,78)});
    if(kind==='macro'){ctx.strokeStyle='#e2f1ba';ctx.lineWidth=3;ctx.strokeRect(shops[3].x-61,shops[3].y-48,130,122)}
    for(const p of [...customers].sort((a,b)=>(actors.get(a.id)?.y||0)-(actors.get(b.id)?.y||0))){
      const a=actors.get(p.id);if(!a)continue;
      if(p.id===selected){ctx.strokeStyle=kind==='fraud'?'#ad6242':'#315d43';ctx.lineWidth=3;ctx.strokeRect(a.x-14,a.y-12,29,44)}
      drawResident(ctx,a.x,a.y,p.id,a.direction||'down',!reduced&&running&&a.path.length?Math.floor(time/125)%4:0,a.bubble&&a.until>time);
      const alert=alerts.get(p.id);
      if(alert){ctx.beginPath();ctx.arc(a.x,a.y-23,14,0,Math.PI*2);ctx.fillStyle=alert==='!'?'#b65131':'#33684c';ctx.fill();ctx.strokeStyle='#fff9e9';ctx.lineWidth=2;ctx.stroke();ctx.fillStyle='white';ctx.textAlign='center';ctx.font='700 21px "DM Sans",sans-serif';ctx.fillText(alert,a.x,a.y-16)}
      else if(a.bubble&&a.until>time)label(a.bubble,a.x,a.y-35,Math.max(54,a.bubble.length*7));
    }
  }
  function frame(time){
    raf=0;if(!running)return;
    const distance=Math.min((time-(last||time))/1000,.06)*65*speed;last=time;
    if(!reduced)for(const [i,p] of customers.entries()){
      const a=actors.get(p.id);
      if(!a.path.length&&time>a.until){
        const lane=236+(i%3-1)*7;
        if(a.home){if(Math.hypot(a.x-a.home.x,a.y-a.home.y)>3)a.path=[{x:a.x,y:lane},{x:a.home.x,y:lane},{...a.home}]}
        else a.path=[{x:a.x,y:lane},{x:45+(i*97+Math.floor(time/3000)*43)%650,y:lane}];
      }
      const target=a.path[0];if(!target)continue;
      const dx=target.x-a.x,dy=target.y-a.y,d=Math.hypot(dx,dy);
      a.direction=Math.abs(dx)>Math.abs(dy)?(dx<0?'left':'right'):(dy<0?'up':'down');
      if(d<=distance){a.x=target.x;a.y=target.y;a.path.shift();if(!a.path.length){a.until=time+1700;if(a.pending){a.bubble=a.pending;a.pending=null}}}
      else{a.x+=dx/d*distance;a.y+=dy/d*distance}
    }
    paint(time);raf=requestAnimationFrame(frame);
  }
  function draw(people,focus,role){
    population=people.slice(0,100);selected=focus;kind=role;
    const ids=[...new Set([...alerts.keys(),focus,...recent,...population.filter(p=>appearance(p.id).role!=='resident').map(p=>p.id),...population.map(p=>p.id)].filter(Boolean))].slice(0,24);
    customers=ids.map(id=>population.find(p=>p.id===id)).filter(Boolean);
    customers.forEach((p,i)=>{if(!actors.has(p.id)){
      const role=appearance(p.id).role,shop=role==='merchant'?shops[100-Number(p.id.slice(1))]:role==='cashier'?shops[4]:null;
      const home=shop?{x:shop.x+(role==='cashier'?80:75),y:shop.y+(role==='cashier'?60:45)}:null;
      actors.set(p.id,{x:home?.x??(i%3===0?274:i%3===1?494:45+(i*73)%650),y:home?.y??(i%3<2?40+(i*53)%365:236),home,direction:'down',path:[],bubble:null,until:0});
    }});paint();
  }
  draw.motion=function(events){
    recent=[...new Set([...events.flatMap(e=>[e.customer_id,e.receiver_customer_id]),...recent].filter(Boolean))].slice(0,12);
    draw(population,selected,kind);
    for(const e of events){
      const a=actors.get(e.customer_id);if(!a)continue;
      const receiver=actors.get(e.receiver_customer_id);
      const shop=e.transaction_type?.startsWith('CASH_')?shops[4]:(shops[Number(String(e.merchant).slice(1))-1]||shops[3]);
      const target=e.transaction_type==='P2P_TRANSFER'&&receiver?{x:receiver.x-20,y:receiver.y}:{x:shop.x,y:shop.y+91};
      a.path=[{x:a.x,y:236},{x:target.x,y:236},target];
      const action={P2P_TRANSFER:'SEND',MERCHANT_QR:'QR',CASH_IN_AGENT:'CASH IN',CASH_OUT_AGENT:'CASH OUT'}[e.transaction_type]||'';
      a.pending=e.status==='blocked'?'HELD':e.status==='declined'?'DECLINED':(action? action+' ':'')+'₱'+Math.round(e.amount_minor/100);a.until=0;
    }
    paint();
  };
  draw.setRunning=function(on){running=on;last=0;cancelAnimationFrame(raf);if(on&&!reduced)raf=requestAnimationFrame(frame);else{raf=0;paint()}};
  draw.setSpeed=value=>{speed=value};
  draw.setMarket=value=>{market=value};
  draw.setAlerts=value=>{alerts=new Map(value.map(v=>[v.customer_id,v.mark]));draw(population,selected,kind)};
  draw.reset=()=>{actors.clear();alerts.clear();recent=[];selected=null;last=0;paint()};
  document.fonts.ready.then(()=>{background=null;paint()});
  return draw;
}
