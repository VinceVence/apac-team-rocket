"""Render the architecture proposal locally: uv run --locked --group figures python this_file.py."""
import base64
import math
from pathlib import Path

import pymupdf

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Rect, Circle, Ellipse, Polygon, PolyLine, String
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
        self.icon(kind,x+20,y+25,42,color)
        self.text(x+78,y+53,title,title_size,True)
        self.lines(x+24,y+91,body,body_size,30)
        for line in body:
            assert pdfmetrics.stringWidth(line,'MintSans',body_size)<w-43,(title,line)
        assert pdfmetrics.stringWidth(title,'MintSansB',title_size)<w-94,title
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
        svg=svg.replace('<desc>...</desc>','<desc>Architecture proposal with original agent icons. See docs/fraud-agent-mesh.md for the review specification.</desc>',1)
        (OUT/(stem+'.svg')).write_text(svg)
        scale=1190/self.w
        self.d.scale(scale,scale);self.d.width=self.w*scale;self.d.height=self.h*scale
        pdf=OUT/(stem+'.pdf')
        renderPDF.drawToFile(self.d,str(pdf))
        with pymupdf.open(pdf) as document:
            document[0].get_pixmap(matrix=pymupdf.Matrix(self.w/1190,self.w/1190),alpha=False).save(OUT/(stem+'.png'))

def architecture():
    f=Figure(2800,1510)
    f.text(60,72,'MINT TOWN',25,True,GREEN)
    f.text(60,133,'Fraud intelligence architecture',48,True)

    f.rect(60,200,460,1170,'#F8F6F0',stroke=None,r=0)
    f.rect(610,200,680,1170,'#F2F6FA',stroke=None,r=0)
    f.rect(1380,200,1360,1170,'#F1F7F3',stroke=None,r=0)
    f.stage(60,200,460,'Simulation','#74644D')
    f.stage(610,200,680,'Data plane',BLUE)
    f.stage(1380,200,1360,'Agent plane',GREEN)

    # Simulation, observed data, and complaint intake.
    f.path([(285,490),(285,570)],INK)
    f.path([(285,700),(285,840)],INK)
    f.path([(460,635),(650,635)],BLUE,6)
    f.path([(460,905),(555,905),(555,320),(1350,320),(1350,420),(1470,420)],INK)
    f.text(1010,309,'Complaint',23,True,INK,anchor='middle')
    f.path([(110,1245),(85,1245),(85,420),(110,420)],PURPLE)

    f.card(110,350,350,140,'Live world',['Customers · merchants','Payments · devices'],'world',color='#74644D')
    f.card(110,570,350,130,'Event ledger',['Customer ID + event date'],'database',color='#74644D',body_size=24)
    f.card(110,840,350,130,'Scam report',['Story + disputed transfer'],'document',color='#74644D',body_size=24)
    f.card(110,1180,350,130,'Payment gate',['Verify · hold · allow'],'shield',color=PURPLE)

    # The warehouse, model creation and versioned serving resources.
    f.path([(950,490),(950,570)],BLUE,6)
    f.path([(950,700),(950,740)],BLUE,6)
    f.path([(950,870),(950,910)],BLUE,6)
    f.path([(950,1040),(950,1100),(790,1100),(790,1160)],BLUE)
    f.path([(930,1235),(970,1235)],BLUE)
    f.path([(1250,975),(1310,975),(1310,890),(1440,890)],BLUE)
    f.path([(1250,1235),(1330,1235),(1330,930),(1440,930)],BLUE)

    f.card(650,350,600,140,'AE / SQL generation',['Synthetic history · versioned batches'],'document',color=BLUE)
    f.card(650,570,600,130,'Bronze · raw events',['Transactions · customers · devices'],'database',color=BLUE)
    f.card(650,740,600,130,'Silver · validated records',['Ownership · chronology · relationships'],'database',color=BLUE)
    f.card(650,910,600,130,'Gold · BigQuery features',['Pinned case evidence + model inputs'],'database',color=BLUE)
    f.card(650,1160,280,145,'Fraud models',['DS training','+ evaluation'],'model',color=BLUE,title_size=24,body_size=24)
    f.card(970,1160,280,145,'Model registry',['Versioned','predictors'],'model',color=BLUE,title_size=23,body_size=24)

    # A selective agent network, one tool gateway and durable case state.
    f.path([(1720,495),(1720,545)],GREEN,arrow=False)
    f.path([(1630,545),(2460,545)],GREEN,arrow=False)
    for x in (1630,2045,2460):
        f.path([(x,545),(x,620)],GREEN)
        f.path([(x,760),(x,835)],GREEN)
    f.text(2000,533,'Delegate',23,True,GREEN,anchor='middle')
    f.path([(1970,420),(2250,420)],GREEN,5)
    f.text(2110,402,'Resolution',23,True,GREEN,anchor='middle')
    f.path([(1780,965),(1780,1060)],GREEN)
    f.text(1800,1020,'Evidence + predictions',23,color=GREEN)
    f.path([(1780,1190),(1780,1240)],GREEN)
    f.path([(1440,1125),(1400,1125),(1400,470),(1470,470)],GREEN)
    f.path([(2650,420),(2705,420),(2705,1125),(2650,1125)],PURPLE)
    f.path([(2290,1125),(2120,1125)],PURPLE)
    f.path([(2470,1190),(2470,1240)],PURPLE)
    f.path([(2470,1345),(2470,1430),(555,1430),(555,1245),(460,1245)],PURPLE,5)
    f.text(1700,1414,'Safeguard → replay → analyst activation',25,True,PURPLE,anchor='middle')

    f.card(1470,350,500,145,'Case lead',['Gemini on Vertex AI · Google ADK','Route · ask · resolve'],title_size=32)
    f.card(2250,350,400,145,'Risk analyst',['Review + approve'],'human',color=PURPLE,title_size=31)
    f.card(1440,620,380,140,'Transaction agent',['Spending · recipient flows'],title_size=26,body_size=25)
    f.card(1855,620,380,140,'Device & identity',['Login · authorization'],title_size=27)
    f.card(2270,620,380,140,'Scam context',['Report · scam patterns'],title_size=28)
    f.card(1440,835,1210,130,'Evidence & model tools',['Scoped queries · registered predictors · versioned receipts'],'tool',title_size=31,body_size=27)
    f.card(1440,1060,680,130,'Shared case workspace',['Facts · findings · open questions'],'document',title_size=31,body_size=27)
    f.card(1440,1240,680,105,'Durable checkpoints',['Case revision · evidence · spend'],'database',title_size=31,body_size=25)
    f.card(2290,1060,360,130,'Shared knowledge',['Analyst-approved cases'],'database',color=PURPLE,title_size=25,body_size=24)
    f.card(2290,1240,360,105,'Prevention agent',['Learn a narrow safeguard'],color=PURPLE,title_size=25,body_size=23)
    f.save('mint-town-agent-mesh')


def sequence():
    f=Figure(2400,1630)
    f.text(60,72,'MINT TOWN',25,True,GREEN)
    f.text(60,133,'From one resolved case to the next protected payment',42,True)
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
