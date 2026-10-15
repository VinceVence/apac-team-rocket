"""DM Sans architecture using the established Mint Town icons and arrow system."""
from pathlib import Path
import base64
import render_agent_mesh as shared
from render_agent_mesh import Figure,GREEN,BLUE,PURPLE,INK,MUTED

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ace-mle';OUT.mkdir(parents=True,exist_ok=True);shared.OUT=OUT
photo=ROOT/'docs/figures/mint-town-world-current.png'

def render():
    f=Figure(2600,1620);f.brand('Two learning loops, one reviewed case')
    for x,w,label,color,fill in [(45,590,'Simulation',GREEN,'#F3F8EF'),(680,600,'Data plane',BLUE,'#F2F6FA'),(1320,1235,'Agent plane',PURPLE,'#F8F6FA')]:
        f.rect(x,145,w,1350,fill,stroke=None,r=14);f.stage(x,145,w,label,color)
    f.text(83,282,'100 residents · live payments',29,True)
    f.picture(80,315,520,325,photo)
    f.card(80,735,520,165,'Customer report',['Story + disputed payment','Observed prepayment context'],'document',title_size=28,body_size=24)
    f.path([(340,640),(340,735)],GREEN,4)
    f.card(80,1210,520,170,'Payment gateway',['Local check before debit','Hold or settle the payment'],'shield',title_size=28,body_size=25)

    f.card(720,275,520,245,'AE tables',['customers · wallets','devices · wallet_transactions','100 customers, scoped rows'],'database',BLUE,title_size=29,body_size=25)
    f.card(720,610,520,175,'Pinned case evidence',['Customer + event cutoff','BigQuery job + feature values'],'document',BLUE,title_size=28,body_size=24)
    f.path([(980,520),(980,610)],BLUE,4)
    f.card(720,810,520,140,'Training corpus',['Payment-request benchmark','100 synthetic customers'],'document',BLUE,title_size=28,body_size=23)
    f.card(720,970,520,175,'Model tools',['Versioned JSON artifacts','Read-only, scoped predictions'],'model',BLUE,title_size=30,body_size=25)
    f.card(720,1260,520,165,'Case checkpoints',['Tool receipts + reservations','SQLite + Cloud Storage'],'database',BLUE,title_size=28,body_size=24)
    f.path([(600,815),(650,815),(650,405),(720,405)],GREEN,4)
    f.text(651,789,'Data',20,True,GREEN,anchor='middle')

    f.card(1370,280,480,185,'Resolution agent',['Chooses evidence and models','Asks focused follow-ups'],'agent',GREEN,title_size=28,body_size=24)
    f.card(1930,280,570,185,'Fraud Analyst',['Reviews the cited proposal','Approves a lesson or asks for more'],'human',GREEN,title_size=29,body_size=24)
    f.path([(1240,696),(1275,696),(1275,362),(1370,362)],BLUE,4)
    f.path([(1850,372),(1930,372)],GREEN,4);f.text(1890,350,'Draft',20,True,GREEN,anchor='middle')
    f.path([(1240,1058),(1300,1058),(1300,410),(1370,410)],BLUE,4)
    f.path([(2215,465),(2215,595),(1640,595),(1640,615)],GREEN,4)

    f.rect(1360,535,1155,360,'#EAF4E6',stroke=None,r=14)
    f.text(1390,580,'ACE · reviewed case memory',30,True,GREEN)
    f.card(1390,615,500,165,'Prevention / Reflector',['Proposes a reusable strategy','Tests scams and counterexamples'],'agent',GREEN,title_size=25,body_size=23)
    f.card(1960,615,520,165,'Replay & human review',['Curates a scoped, versioned delta','Activates only tested safeguards'],'human',GREEN,title_size=25,body_size=23)
    f.path([(1890,695),(1960,695)],GREEN,4)
    f.rect(1390,815,1090,60,'#D7EAD5',stroke=None,r=8)
    f.text(1420,854,'Playbook: strategy · model hints · question · counterexample',25,True,GREEN)
    f.path([(2215,780),(2215,815)],GREEN,4)
    f.path([(1390,846),(1340,846),(1340,491),(1600,491),(1600,465)],GREEN,4)
    f.text(1510,515,'Retrieve the reviewed entry',21,True,GREEN)
    f.path([(2480,695),(2572,695),(2572,1544),(340,1544),(340,1380)],GREEN,4)
    f.text(1840,1523,'Approved safeguard · no LLM per payment',25,True,GREEN,anchor='middle')

    f.rect(1360,975,1155,350,'#EEEAF5',stroke=None,r=14)
    f.text(1390,1020,'MLE-STAR · bounded model improvement',30,True,PURPLE)
    f.card(1390,1060,325,185,'Scientist',['Search vetted recipes','Fit CPU candidates'],'agent',PURPLE,title_size=26,body_size=22)
    f.card(1765,1060,325,185,'Refiner',['Validation ablation','One targeted change'],'agent',PURPLE,title_size=26,body_size=22)
    f.card(2140,1060,340,185,'Validator',['Sealed final test','Recommend or reject'],'agent',PURPLE,title_size=26,body_size=22)
    f.path([(1715,1150),(1765,1150)],PURPLE,4);f.path([(2090,1150),(2140,1150)],PURPLE,4)
    f.path([(1240,880),(1290,880),(1290,1100),(1390,1100)],BLUE,4)
    f.path([(1630,875),(1630,940),(1350,940),(1350,1150),(1390,1150)],PURPLE,4)
    f.text(1740,936,'Reviewed lessons suggest hypotheses',23,True,PURPLE)
    f.text(1390,1295,'Training / validation first. Final test cannot choose the next experiment.',23,color=PURPLE)
    f.card(1610,1370,870,120,'Operator reviews an advisory tool',['Register for investigation; payment release remains separate.'],'human',PURPLE,title_size=26,body_size=23)
    f.path([(2310,1245),(2527,1245),(2527,1430),(2480,1430)],PURPLE,4)
    f.path([(1610,1430),(1270,1430),(1270,1130),(1240,1130)],PURPLE,4)
    f.path([(1370,445),(1310,445),(1310,1345),(1240,1345)],MUTED,2.5)
    f.save('learning-architecture','Mint Town — ACE playbooks and MLE-STAR refinement')
    svg=(OUT/'learning-architecture.svg').read_text().replace(str(photo),'data:image/png;base64,'+base64.b64encode(photo.read_bytes()).decode())
    (OUT/'learning-architecture.svg').write_text(svg)
    (ROOT/'web/dist/learning-architecture.svg').write_text(svg)

if __name__=='__main__':render()
