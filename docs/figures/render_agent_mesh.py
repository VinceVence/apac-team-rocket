"""Render the architecture proposal locally: uv run --locked --group figures python this_file.py."""
import base64
import math
from pathlib import Path

import pymupdf

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Rect, Circle, Ellipse, Polygon, PolyLine, String, Image
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
FONTS=ROOT/'web/dist/fonts'
for name,file in [('MintSans','dm-sans-400.ttf'),('MintSansB','dm-sans-700.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONTS/file)))

INK='#20342D';MUTED='#52665D';GREEN='#31765C';BLUE='#3D6D94';PURPLE='#76638D';LINE='#C3CFC7'

class Figure:
    def __init__(self,w,h):
        self.w,self.h=w,h;self.d=Drawing(w,h)
        self.rect(0,0,w,h,fill='#FFFFFF',stroke=None)
    def rect(self,x,y,w,h,fill='#FFFFFF',stroke=LINE,r=12,dashed=False,sw=1.8):
        a=Rect(x,self.h-y-h,w,h,rx=r,ry=r,fillColor=HexColor(fill) if fill else None,
               strokeColor=HexColor(stroke) if stroke else None,strokeWidth=sw)
        if dashed:a.strokeDashArray=[9,6]
        self.d.add(a)
    def text(self,x,y,s,size=24,bold=False,color=INK,anchor='start'):
        self.d.add(String(x,self.h-y,s,fontName='MintSansB' if bold else 'MintSans',fontSize=size,
                          fillColor=HexColor(color),textAnchor=anchor))
    def lines(self,x,y,lines,size=23,leading=31,color=MUTED,bold=False,anchor='start'):
        for n,line in enumerate(lines):self.text(x,y+n*leading,line,size,bold,color,anchor)
    def circle(self,x,y,r,fill=None,stroke=GREEN,sw=2.5):
        self.d.add(Circle(x,self.h-y,r,fillColor=HexColor(fill) if fill else None,strokeColor=HexColor(stroke) if stroke else None,strokeWidth=sw))
    def path(self,points,color=GREEN,sw=4,dashed=False,arrow=True,both=False):
        flat=[value for x,y in points for value in (x,self.h-y)]
        p=PolyLine(flat,strokeColor=HexColor(color),strokeWidth=sw,fillColor=None)
        if dashed:p.strokeDashArray=[7,5]
        self.d.add(p)
        def head(a,b):
            dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
            tip=b;length=max(12,sw*3);half=max(6,sw*1.5)
            back=(b[0]-length*ux,b[1]-length*uy)
            pts=[tip,(back[0]+half*uy,back[1]-half*ux),(back[0]-half*uy,back[1]+half*ux)]
            self.d.add(Polygon([v for x,y in pts for v in (x,self.h-y)],fillColor=HexColor(color),strokeColor=None))
        if arrow:head(points[-2],points[-1])
        if both:head(points[1],points[0])
    def icon(self,kind,x,y,size=44,color=GREEN):
        def xy(a,b):return x+a*size/48,y+b*size/48
        def p(points):self.path([xy(*v) for v in points],color,2.5,arrow=False)
        def c(a,b,r,fill=None):self.circle(*xy(a,b),r*size/48,fill,color,2.5)
        if kind=='agent':
            self.rect(*xy(7,12),34*size/48,28*size/48,fill=None,stroke=color,r=7,sw=2.5)
            p([(24,12),(24,5)]);c(24,4,2.4,color)
            c(17,25,2.2,color);c(31,25,2.2,color);p([(18,34),(30,34)])
            p([(7,22),(3,22),(3,31),(7,31)]);p([(41,22),(45,22),(45,31),(41,31)])
        elif kind=='human':
            c(24,12,8);p([(7,43),(7,35),(12,28),(36,28),(41,35),(41,43)])
            p([(14,43),(14,36)]);p([(34,43),(34,36)])
        elif kind=='database':
            self.rect(*xy(7,11),34*size/48,28*size/48,fill=None,stroke=color,r=0,sw=2.5)
            for cy in (11,25,39):
                cx,py=xy(24,cy);self.d.add(Ellipse(cx,self.h-py,17*size/48,6*size/48,
                    strokeColor=HexColor(color),fillColor=HexColor('#FFFFFF') if cy==11 else None,strokeWidth=2.5))
        elif kind=='model':
            self.rect(*xy(10,10),28*size/48,28*size/48,fill=None,stroke=color,r=4,sw=2.5)
            for a in (16,24,32):
                p([(a,5),(a,10)]);p([(a,38),(a,43)]);p([(5,a),(10,a)]);p([(38,a),(43,a)])
            for a,b in ((17,18),(30,17),(24,30)):c(a,b,2.3,color)
            p([(17,18),(24,30),(30,17)])
        elif kind=='world':
            p([(3,23),(14,12),(25,23),(25,43),(4,43),(4,23)])
            p([(24,14),(34,5),(46,16),(46,43),(28,43)])
            p([(12,43),(12,33),(18,33),(18,43)])
            p([(33,24),(38,24)]);p([(33,32),(38,32)])
        elif kind=='tool':
            p([(8,12),(0,24),(8,36)]);p([(40,12),(48,24),(40,36)]);p([(29,8),(19,40)])
        elif kind=='shield':
            p([(24,3),(42,10),(40,29),(32,40),(24,46),(16,40),(8,29),(6,10),(24,3)])
            p([(14,24),(21,31),(34,18)])
        else:
            self.rect(*xy(7,4),32*size/48,40*size/48,fill=None,stroke=color,r=3,sw=2.5)
            for yy in (15,24,33):p([(14,yy),(32,yy)])
    def card(self,x,y,w,h,title,body,kind='agent',color=GREEN,fill='#FFFFFF',title_size=29,body_size=25):
        self.rect(x,y,w,h,fill,stroke=color,r=8,sw=1.7)
        self.icon(kind,x+22,y+22,42,color)
        ascent,descent=pdfmetrics.getAscentDescent('MintSansB',title_size)
        self.text(x+80,y+43+(ascent+descent)/2,title,title_size,True)
        self.lines(x+24,y+91,body,body_size,30)
        for line in body:
            assert pdfmetrics.stringWidth(line,'MintSans',body_size)<w-43,(title,line)
        assert pdfmetrics.stringWidth(title,'MintSansB',title_size)<w-94,title
    def logo(self,x,y,size=64):
        self.rect(x,y,size,size,'#8bd5b3',stroke=None,r=size*18/64)
        for pts,color in [
            ([(11,23),(16,23),(16,17),(23,17),(23,12),(30,12),(30,18),(35,18),(35,35),(11,35)],'#234c3d'),
            ([(39,26),(44,26),(44,20),(51,20),(51,26),(54,26),(54,41),(39,41)],'#234c3d'),
            ([(14,41),(22,41),(22,47),(40,47),(40,44),(51,44),(51,52),(17,52),(17,47),(14,47)],'#234c3d'),
            ([(19,26),(24,26),(24,31),(19,31)],'#c7f3d8'),
            ([(27,23),(31,23),(31,31),(27,31)],'#c7f3d8'),
            ([(44,31),(49,31),(49,36),(44,36)],'#c7f3d8')]:
            self.d.add(Polygon([v for a,b in pts for v in (x+a*size/64,self.h-y-b*size/64)],fillColor=HexColor(color),strokeColor=None))
    def brand(self,title):
        self.logo(60,38,64)
        self.text(142,82,'Mint Town',39,True)
        self.text(390,82,title,39,True)
    def picture(self,x,y,w,h,path):
        self.d.add(Image(x,self.h-y-h,w,h,str(path)))
    def stage(self,x,y,w,label,color):
        points=[(x,y),(x+w-30,y),(x+w,y+42),(x+w-30,y+84),(x,y+84)]
        self.d.add(Polygon([v for a,b in points for v in (a,self.h-b)],fillColor=HexColor(color),strokeColor=None))
        self.text(x+32,y+54,label,31,True,'#FFFFFF')
    def save(self,stem):
        renderSVG.drawToFile(self.d,str(OUT/(stem+'.svg')))
        svg=(OUT/(stem+'.svg')).read_text()
        styles=''
        for name,file in [('MintSans','dm-sans-400.ttf'),('MintSansB','dm-sans-700.ttf')]:
            font=base64.b64encode((FONTS/file).read_bytes()).decode()
            styles+=f'@font-face{{font-family:"{name}";src:url(data:font/ttf;base64,{font}) format("truetype");}}'
        title='Mint Town — '+('case sequence' if 'sequence' in stem else 'simulation, data plane and agent plane')
        svg=svg.replace('<title>...</title>', '<title>'+title+'</title><defs><style type="text/css">'+styles+'</style></defs>',1)
        for asset in OUT.glob('*.jpg'):
            svg=svg.replace(str(asset),'data:image/jpeg;base64,'+base64.b64encode(asset.read_bytes()).decode())
        svg=svg.replace('<desc>...</desc>','<desc>Architecture proposal with original agent icons. See docs/fraud-agent-mesh.md for the review specification.</desc>',1)
        (OUT/(stem+'.svg')).write_text(svg)
        scale=1190/self.w
        self.d.scale(scale,scale);self.d.width=self.w*scale;self.d.height=self.h*scale
        pdf=OUT/(stem+'.pdf')
        renderPDF.drawToFile(self.d,str(pdf))
        with pymupdf.open(pdf) as document:
            document[0].get_pixmap(matrix=pymupdf.Matrix(self.w/1190,self.w/1190),alpha=False).save(OUT/(stem+'.png'))

def architecture():
    f=Figure(2600,1435)
    f.brand('A case becomes protection')
    for x,w,fill,label,color in [(60,740,'#F8F6F0','Simulation','#74644D'),
                                (860,540,'#F2F6FA','Data plane',BLUE),
                                (1460,1080,'#F1F7F3','Agent plane',GREEN)]:
        f.rect(x,165,w,1155,fill,stroke=None,r=0)
        f.stage(x,165,w,label,color)

    # The real application panel is the simulation, not another abstract box.
    f.picture(90,315,680,510,OUT/'mint-town-world.jpg')
    f.logo(92,265,36)
    f.text(143,292,'Live world',31,True)
    f.path([(430,825),(430,925)],GREEN,5)
    f.card(90,925,680,130,'Customer reports a scam',['Story + disputed transaction'],'document',title_size=30,body_size=27)
    f.card(90,1165,680,125,'Next payment checked',['Flag a related scam before money moves'],'shield',color=PURPLE,title_size=30,body_size=26)

    # Exactly the four tables produced by the AE, with DS models as tools.
    f.rect(890,315,480,540,'#FFFFFF',stroke=BLUE,r=8)
    f.icon('database',918,339,44,BLUE)
    f.text(982,372,'AE dataset',32,True)
    f.text(918,414,'BigQuery',26,color=BLUE)
    for i,name in enumerate(['customers','wallets','devices','wallet_transactions']):
        yy=450+i*61
        f.rect(918,yy,424,48,'#F2F6FA',stroke=None,r=5)
        f.text(938,yy+32,name,26,True,BLUE)
    f.path([(918,713),(1342,713)],'#D9E3EC',1.8,arrow=False)
    f.icon('model',920,744,42,BLUE)
    f.text(982,777,'Fraud model tools',28,True)
    f.text(918,820,'Trained by the DS team',25,color=MUTED)
    f.path([(1370,465),(1520,465)],BLUE,5,both=True)
    f.path([(890,570),(770,570)],BLUE,5)
    f.text(830,549,'Replay',23,True,BLUE,anchor='middle')
    f.text(1445,443,'Query / score',22,True,BLUE,anchor='middle')

    # The complaint has one uninterrupted route into the investigation team.
    f.path([(770,990),(1430,990),(1430,570),(1520,570)],INK,5)
    f.text(1090,969,'Complaint',25,True,INK,anchor='middle')

    # Four numbered steps, with specialization contained inside the team.
    f.rect(1520,315,920,370,'#FFFFFF',stroke=GREEN,r=8)
    f.circle(1480,358,23,GREEN,stroke=None)
    f.text(1480,367,'1',25,True,'#FFFFFF',anchor='middle')
    f.text(1544,369,'Investigate',34,True)
    f.icon('agent',1874,403,47,GREEN)
    f.text(1937,438,'Case lead',32,True)
    f.text(1980,480,'Chooses tools and specialists',25,color=MUTED,anchor='middle')
    f.path([(1980,496),(1980,515)],GREEN,arrow=False)
    f.path([(1680,515),(2280,515)],GREEN,arrow=False)
    for x,label in [(1680,'Transactions'),(1980,'Device & identity'),(2280,'Scam context')]:
        f.path([(x,515),(x,543)],GREEN,3)
        f.icon('agent',x-24,554,48,GREEN)
        f.text(x,640,label,27,True,anchor='middle')

    def step(y,n,title,body,kind,color):
        f.card(1520,y,920,125,title,[body],kind,color=color,title_size=32,body_size=27)
        f.circle(1480,y+43,23,color,stroke=None)
        f.text(1480,y+52,str(n),25,True,'#FFFFFF',anchor='middle')
    f.path([(1980,685),(1980,775)],GREEN,5)
    f.text(2000,738,'Resolution',24,color=GREEN)
    step(775,2,'Risk analyst reviews','Verify evidence and approve the case','human',PURPLE)
    f.path([(1980,900),(1980,960)],PURPLE,5)
    step(960,3,'Remember the approved case','Shared knowledge for future investigations','database',PURPLE)
    f.path([(1980,1085),(1980,1145)],PURPLE,5)
    step(1145,4,'Prevention agent learns','Propose safeguard → replay → analyst activation','agent',PURPLE)
    # Reuse stays separate from the forward investigation path.
    f.path([(2440,1022),(2505,1022),(2505,410),(2440,410)],PURPLE,3.5)
    f.text(2505,389,'Recall',22,True,PURPLE,anchor='end')
    f.path([(1980,1270),(1980,1373),(430,1373),(430,1290)],PURPLE,5)
    f.text(1230,1355,'Approved safeguard',26,True,PURPLE,anchor='middle')
    f.save('mint-town-agent-mesh')


def sequence():
    f=Figure(2400,1630)
    f.brand('From report to protected payment')
    participants=[('Customer / world','world',180),('Case lead','agent',510),('Specialist','agent',840),
                  ('Tools / gate','tool',1170),('State / knowledge','database',1500),('Risk analyst','human',1830),
                  ('Prevention','agent',2160)]
    for label,kind,x in participants:
        f.rect(x-138,205,276,126,'#F1F7F3',stroke=None,r=8)
        f.icon(kind,x-22,222,44,PURPLE if kind=='human' else GREEN)
        f.text(x,306,label,26,True,anchor='middle')
        f.path([(x,340),(x,1560)],'#C4CFC8',1.5,dashed=True,arrow=False)
    def msg(a,b,y,label,ret=False,color=INK):
        f.path([(a,y),(b,y)],color,3.5,dashed=ret)
        f.text((a+b)/2,y-16,label,24,color=color,anchor='middle')
    msg(180,510,395,'File complaint',color=GREEN)
    msg(510,1500,465,'Pin evidence + reserve budget')
    msg(510,840,535,'Delegate question',color=GREEN)
    msg(840,1170,605,'Choose tool / model',color=BLUE)
    msg(1170,840,675,'Return evidence',True,BLUE)
    msg(840,1500,745,'Save cited finding',color=GREEN)
    msg(1500,510,815,'Read shared case revision',True,GREEN)
    f.rect(105,853,1500,146,'#F2F6FA',stroke='#C2D0DC',r=0)
    f.text(122,881,'opt  Missing evidence',21,True,BLUE)
    msg(510,180,923,'Ask customer',color=BLUE)
    msg(180,510,978,'Reply + resume',True,BLUE)
    msg(510,1830,1050,'Propose resolution with evidence',color=GREEN)
    msg(1830,1500,1120,'Approve lesson',color=PURPLE)
    msg(1500,2160,1190,'Learn from approved case',color=PURPLE)
    msg(2160,1170,1260,'Propose safeguard + replay',color=PURPLE)
    msg(1170,1830,1330,'Review replay result',color=PURPLE)
    msg(1830,1500,1400,'Activate safeguard',color=PURPLE)
    msg(180,1170,1470,'Later payment → check active safeguard',color=PURPLE)
    msg(1170,180,1540,'Hold or allow before debit',True,PURPLE)
    f.save('mint-town-agent-mesh-sequence')


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    architecture()
    sequence()
    print('Rendered architecture and sequence: SVG, PDF and PNG.')
