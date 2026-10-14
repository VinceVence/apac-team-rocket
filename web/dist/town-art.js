// Original, code-drawn town assets. No external art, fonts or game-engine runtime.
export const WIDTH=960,HEIGHT=600;
export const PLACES=[
  {id:'m1',x:145,y:91,w:150,name:'Kape café',roof:'#ba7055',kind:'cafe',entry:{x:150,y:260}},
  {id:'m2',x:480,y:78,w:154,name:'Sari-sari',roof:'#639384',kind:'store',entry:{x:480,y:260}},
  {id:'m3',x:145,y:361,w:156,name:'Mercado',roof:'#c99053',kind:'market',entry:{x:150,y:485}},
  {id:'m4',x:820,y:88,w:162,name:'Town bank',roof:'#477a72',kind:'bank',entry:{x:820,y:260}},
  {id:'cash',x:480,y:359,w:144,name:'Cash agent',roof:'#6889a0',kind:'cash',entry:{x:480,y:485}},
  {id:'homes',x:820,y:357,w:148,name:'Riverside homes',roof:'#9e7b78',kind:'home',entry:{x:820,y:485}}
];
export const NODES=[
  [45,310],[150,310],[315,310],[405,310],[405,346],[555,346],[555,310],[690,310],[820,310],[915,310],
  [150,260],[315,260],[480,260],[690,260],[820,260],
  [315,485],[150,485],[480,485],[690,485],[820,485]
].map(([x,y])=>({x,y}));
export const EDGES=[[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[7,8],[8,9],[1,10],[10,11],[11,12],[12,13],[13,14],[14,8],[2,11],[7,13],[2,15],[7,18],[15,16],[15,17],[17,18],[18,19]];

export function paintTown(ctx){
  const r=(x,y,w,h,c)=>{ctx.fillStyle=c;ctx.fillRect(Math.round(x),Math.round(y),w,h)};
  const poly=(points,c)=>{ctx.fillStyle=c;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.closePath();ctx.fill()};
  const oval=(x,y,rx,ry,c)=>{ctx.fillStyle=c;ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);ctx.fill()};
  let seed=1937;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
  function bush(x,y,color='#557e59'){oval(x+4,y+5,17,7,'#42644b25');r(x-12,y-5,24,12,color);r(x-8,y-10,16,6,color);r(x-8,y-7,7,3,'#8cb274');r(x+6,y-2,4,3,'#759b68')}
  function pot(x,y,color='#cf895e'){r(x-5,y,10,9,color);r(x-7,y-2,14,4,'#e2a276');bush(x,y-5);r(x-2,y-13,3,3,'#e6b886')}
  function tree(x,y,variant=0){
    oval(x+13,y+44,28,11,'#3d69522c');r(x-4,y+13,10,34,'#7a6348');r(x-2,y+17,4,29,'#ac8458');
    if(variant){poly([[x,y+8],[x-38,y-2],[x-43,y+4],[x-15,y+10],[x-31,y+20],[x-25,y+25],[x,y+13],[x+17,y+34],[x+22,y+32],[x+10,y+11],[x+42,y+15],[x+38,y+6],[x+12,y+4],[x+27,y-14],[x+20,y-17]],'#467b61');poly([[x,y+7],[x-24,y-17],[x-31,y-12],[x-8,y+11],[x+5,y+4],[x+3,y-26],[x-3,y-22]],'#6b9c72');return}
    poly([[x-28,y+4],[x-20,y-12],[x-10,y-12],[x-10,y-22],[x+10,y-22],[x+10,y-13],[x+24,y-9],[x+31,y+10],[x+23,y+25],[x-20,y+25],[x-29,y+15]],'#426d55');
    poly([[x-23,y+1],[x-17,y-12],[x-4,y-17],[x+11,y-12],[x+20,y-4],[x+21,y+12],[x+7,y+19],[x-16,y+16]],'#649464');
    r(x-12,y-10,14,5,'#8caf73');r(x-19,y,9,5,'#85aa70');r(x+6,y+9,9,5,'#79a36c');
  }
  function fence(x,y,length){r(x,y+5,length,3,'#a6926a');r(x,y+17,length,3,'#a6926a');for(let p=x;p<x+length;p+=17){r(p,y,5,26,'#e2d4ad');r(p+3,y+1,2,25,'#c5b58f')}}
  function bench(x,y){r(x-18,y-9,36,5,'#9a7652');r(x-18,y-2,36,5,'#b89162');r(x-18,y+6,36,6,'#bd9666');r(x-13,y+12,4,8,'#526b58');r(x+10,y+12,4,8,'#526b58')}
  function lamp(x,y){oval(x+4,y+5,10,4,'#435e4330');r(x-2,y-33,4,38,'#577566');r(x-7,y-42,14,12,'#eee5ba');r(x-9,y-45,18,3,'#47695c');r(x-4,y-39,8,8,'#fff1bc');r(x-7,y-30,14,2,'#47695c')}
  function window(x,y,w=24){r(x-2,y-2,w+4,29,'#f9ecc8');r(x,y,w,25,'#5e8c8a');r(x+3,y+3,w-6,8,'#a1c2ad');r(x+w/2-1,y,2,25,'#f4e6bd');r(x,y+12,w,2,'#f4e6bd');r(x-3,y+26,w+6,4,'#b6a781')}
  function building(s){
    const x=s.x-s.w/2,y=s.y,w=s.w,h=115;
    poly([[x+7,y+12],[x+w+27,y+30],[x+w+27,y+h+21],[x+25,y+h+21],[x,y+h]],'#436d4528');
    r(x-8,y+h-2,w+24,12,'#b8ba91');r(x-5,y+40,w+10,70,'#d8c9a1');r(x,y+40,w,67,'#f1e1b9');r(x+w-9,y+40,9,67,'#d9c49a');r(x,y+100,w,8,'#c3b48b');
    r(x+8,y+44,w-16,5,'#c3ac83');
    for(let j=0;j<4;j++)r(x+13+j*34,y+49,2,48,'#ead5ac');
    window(x+13,y+62);window(x+w-38,y+62);
    r(s.x-14,y+63,28,45,'#638a79');r(s.x-10,y+66,20,24,'#9bb8a0');r(s.x+8,y+91,3,3,'#f3dbaa');r(s.x-18,y+108,36,6,'#eee1b9');r(s.x-22,y+114,44,5,'#d2c4a0');
    poly([[x-13,y+42],[x+8,y+1],[x+w-7,y+1],[x+w+16,y+42],[x+w+16,y+49],[x-13,y+49]],'#4d6251');
    poly([[x-10,y+39],[x+10,y],[x+w-10,y],[x+w+12,y+39]],s.roof);
    r(x+9,y-3,w-17,5,'#e1bc8a');
    for(let row=0;row<4;row++){
      const yy=y+7+row*9,left=x+7-row*4,right=x+w-6+row*4;
      r(left,yy,right-left,2,'#ffffff20');r(left,yy+3,right-left,2,'#233c3220');
      for(let xx=left+(row%2)*11;xx<right-8;xx+=22)r(xx,yy-5,2,7,'#ffffff12');
    }
    r(x-13,y+42,w+29,5,'#526454');r(x-13,y+41,w+29,2,'#e4c496');
    if(s.kind==='cafe'||s.kind==='store'||s.kind==='market'){
      const aw=s.kind==='market'?w+20:w-6;
      poly([[s.x-aw/2,y+51],[s.x+aw/2,y+51],[s.x+aw/2+5,y+68],[s.x-aw/2-5,y+68]],s.roof);
      for(let j=0;j<aw/16;j++)if(j%2===0)poly([[s.x-aw/2+j*16,y+51],[s.x-aw/2+j*16+8,y+51],[s.x-aw/2+j*16+8,y+68],[s.x-aw/2+j*16-2,y+68]],'#f4e7c6');
      r(s.x-aw/2-5,y+68,aw+10,5,'#596953');
    }
    if(s.kind==='bank'){
      for(const xx of [x+3,x+w-12]){r(xx,y+51,10,53,'#f8ebc5');r(xx-3,y+100,16,7,'#d6c49d')}
      r(s.x-16,y+8,32,24,'#e2dfb5');r(s.x-10,y+13,8,12,'#4e7e66');r(s.x+2,y+13,8,12,'#4e7e66');r(s.x-7,y+25,14,3,'#4e7e66');
      r(x+w+7,y+76,22,34,'#4c7567');r(x+w+10,y+80,16,13,'#b5d9bc');r(x+w+11,y+98,14,3,'#efe7c0');
    }
    if(s.kind==='home'){r(x+20,y-15,14,29,'#ad8f73');r(x+17,y-18,20,6,'#d6c49f')}
    // Readable small signs are part of the scenery; the UI remains DM Sans.
    const labelWidth=Math.max(78,s.name.length*7+22);
    r(s.x-labelWidth/2+2,y+49,labelWidth,21,'#49654a20');r(s.x-labelWidth/2,y+46,labelWidth,21,'#fcf0d3');
    r(s.x-labelWidth/2,y+46,labelWidth,2,'#fff9e7');ctx.fillStyle='#405b4d';ctx.font='600 12px "DM Sans",sans-serif';ctx.textAlign='center';ctx.fillText(s.name,s.x,y+61);
    pot(x-15,y+105);pot(x+w+16,y+110);
    if(['cafe','store','market'].includes(s.kind)){r(x+w-4,y+93,9,16,'#456657');r(x+w-3,y+95,7,9,'#eef3d5');r(x+w-2,y+96,2,3,'#43614f');r(x+w+1,y+100,2,2,'#43614f')}
  }
  r(0,0,WIDTH,HEIGHT,'#9cbb82');
  r(0,20,WIDTH,480,'#a9c48c');
  for(let i=0;i<2100;i++){
    const x=Math.floor(rand()*WIDTH),y=Math.floor(rand()*510);r(x,y,rand()>.7?4:2,2,i%3?'#7eaa6e30':'#dce0a74d');
  }
  // District gardens, stone paths, and a shaded plaza.
  for(const [x,y,w,h] of [[40,65,217,177],[377,52,206,183],[721,66,204,184],[43,365,219,115],[386,365,195,120],[724,359,200,125]]){
    r(x+4,y+4,w,h,'#8bab763d');r(x,y,w,h,'#b3c58d');r(x+6,y+6,w-12,h-12,'#bfd09a');
  }
  for(const x of [315,690]){r(x-25,0,50,515,'#b7b391');r(x-21,0,42,515,'#d9d1ad');r(x-15,0,30,515,'#e2d9b9')}
  r(0,273,960,70,'#b4b58d');r(0,277,960,62,'#ded6b4');r(0,284,960,48,'#ece1bf');
  r(65,250,824,24,'#d2cba7');r(67,255,820,15,'#e6dcba');
  r(0,473,960,29,'#c3bc98');r(0,477,960,23,'#e0d4b0');
  r(389,308,181,48,'#ddd2af');
  for(let i=0;i<105;i++){const x=(i*113)%950,y=285+(i%3)*17;r(x,y,12,1,'#c3b89965');r(x+7,y+3,1,5,'#c3b89950')}
  for(const x of [315,690])for(let y=15;y<470;y+=22){r(x-18,y,36,1,'#c5b89980');r(x+(y%3-1)*5,y-10,1,10,'#c5b89970')}
  // Terraced riverbank, moving water is painted separately.
  r(0,502,960,98,'#619c9a');r(0,501,960,6,'#577e64');r(0,507,960,7,'#c4cb98');r(0,514,960,4,'#8cbaad');r(0,518,960,7,'#77aba0');
  for(let i=0;i<100;i++){const x=(i*179)%960,y=532+(i*29)%66;r(x,y,15+i%5*7,2,i%2?'#bbdbbf40':'#416f7e24')}
  for(let x=30;x<960;x+=83){r(x,501,9,11,'#8b8c70');r(x-4,499,17,4,'#b9b294')}
  for(const x of [315,690]){
    r(x-35,492,70,108,'#786e52');r(x-30,492,60,108,'#ba986c');
    for(let y=494;y<600;y+=10){r(x-30,y,60,2,'#dcc194');r(x-30,y+8,60,2,'#896f51')}
    for(const side of [-39,35]){r(x+side,484,4,116,'#d9c29a');for(const y of [486,526,566]){r(x+side-2,y,8,23,'#e5cf9f');r(x+side-3,y-2,10,4,'#f3dfb4')}}
  }
  // Fountain and village square.
  oval(480,309,45,22,'#6a82622e');oval(480,300,42,25,'#8eaa8a');oval(480,296,38,23,'#e6ddba');oval(480,293,31,17,'#638f91');oval(480,292,26,13,'#91bdb0');
  r(476,265,8,28,'#d9d7b1');oval(480,266,13,6,'#f1e8c7');oval(480,263,10,4,'#6d9d9a');r(479,253,2,11,'#c4e4d1');
  bush(425,282);bush(537,283);bench(431,327);bench(531,327);
  // Tiny flowerbeds and tropical borders.
  for(const [x,y] of [[38,30],[228,38],[382,28],[584,34],[735,27],[921,39],[33,380],[244,427],[740,419],[923,417],[44,485],[585,483]]){
    bush(x,y);for(let j=0;j<3;j++)r(x-7+j*6,y-7+(j%2)*4,4,4,['#f0d888','#d59283','#e5e5bb'][j]);
  }
  for(const v of [[25,80,1],[250,112,0],[27,194,0],[905,119,1],[937,200,0],[375,185,0],[593,172,1],[257,376,1],[31,433,0],[608,408,0],[932,363,1],[934,480,0],[53,550,1]])tree(...v);
  fence(55,58,195);fence(379,45,198);fence(740,55,171);
  PLACES.forEach(building);
  // Café terrace and market baskets.
  for(const [x,y] of [[45,238],[244,247]]){oval(x+3,y+6,18,8,'#4f71502a');r(x-2,y-5,4,18,'#9a7b53');oval(x,y-6,16,9,'#d8b386');r(x-24,y-1,8,8,'#c4a073');r(x+18,y-1,8,8,'#c4a073')}
  for(let i=0;i<4;i++){const x=48+i*22;r(x,447,18,13,'#a87e51');r(x+2,446,14,7,'#c1945f');for(let j=0;j<3;j++)r(x+2+j*5,443+j%2*2,4,5,['#dca659','#96af61','#bb7555','#e8c36e'][i])}
  bench(906,266);bench(55,355);lamp(361,259);lamp(648,261);lamp(352,480);lamp(654,480);
  // Bunting anchors the central square without covering its walking lane.
  ctx.strokeStyle='#7a8d64';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(354,219);ctx.quadraticCurveTo(480,247,610,219);ctx.stroke();
  for(let i=0;i<12;i++){const x=360+i*21,y=221+Math.sin(i/11*Math.PI)*13;poly([[x,y],[x+10,y+1],[x+5,y+12]],['#e4bd6f','#ce8d6d','#78a296','#aec0a0'][i%4])}
  // Moored banca, sunlit water and lily pads.
  poly([[780,549],[843,549],[860,558],[838,568],[793,568],[773,559]],'#5a7972');poly([[785,546],[842,546],[851,554],[835,563],[796,563],[780,555]],'#d8b381');r(806,549,26,11,'#a2835e');r(790,540,2,33,'#c5a67a');r(842,540,2,33,'#c5a67a');r(775,538,82,3,'#e6cf9f');r(775,572,82,3,'#e6cf9f');
  for(const [x,y] of [[126,553],[164,571],[560,562],[896,587]]){oval(x,y,8,3,'#7baf8b');r(x,y-3,4,4,'#eac2a3')}
}

export function paintWater(ctx,time,running){
  const phase=running?time*.00065:0;ctx.fillStyle='#e6f2d280';
  for(let i=0;i<16;i++){const x=(i*127+Math.sin(phase+i)*7)%960,y=532+i*17%63;if((x>274&&x<357)||(x>648&&x<733)||(x>770&&x<864&&y<577))continue;ctx.fillRect(x,y,10+Math.sin(phase+i)*6,1);if(i%4===0)ctx.fillRect(x+5,y-2,1,5)}
  if(running){ctx.strokeStyle='#d7eee080';ctx.lineWidth=1;ctx.beginPath();ctx.ellipse(480,294,12+Math.sin(phase*3)*5,5,0,0,Math.PI*2);ctx.stroke()}
}
