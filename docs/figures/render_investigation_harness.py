"""Draw the design proposal locally; no inference or cloud calls."""
from render_agent_mesh import Figure, GREEN, BLUE, PURPLE, INK, MUTED


def harness():
    f = Figure(2600,1360)
    f.brand('Inside the investigation harness')
    f.rect(570,205,1230,715,'#F1F7F3',stroke=None,r=12)
    f.text(60,262,'Case intake',31,True,GREEN)
    f.text(610,262,'Google ADK harness',31,True,GREEN)
    f.text(1880,262,'Data and model tools',31,True,BLUE)

    # The clockwise execution loop; the role may change, the controls do not.
    f.path([(460,395),(610,395)],INK,5)
    f.path([(1160,395),(1260,395)],GREEN,5)
    f.path([(1760,395),(1880,395)],GREEN,5)
    f.path([(2210,630),(2210,785),(1760,785)],BLUE,5)
    f.text(2230,713,'Tool result',25,True,BLUE)
    f.path([(1260,785),(1160,785)],GREEN,5)
    f.path([(885,710),(885,470)],GREEN,5)
    f.text(905,600,'Observe → decide',25,True,GREEN)

    f.card(60,320,400,260,'Case evidence',[
        'Report + disputed payments',
        'Customer + event cutoff',
        'Pinned AE records',
    ],'document',title_size=29,body_size=24)
    f.card(610,320,550,150,'Choose next step',[
        'Gemini · lead or selected specialist',
    ],'agent',title_size=31,body_size=25)
    f.card(1260,320,500,150,'Validate request',[
        'Schema · scope · budget',
    ],'shield',title_size=31,body_size=27)
    f.card(1260,710,500,150,'Record the result',[
        'Evidence receipt · model version',
        'Checkpoint + spend',
    ],'document',title_size=31,body_size=24)
    f.card(610,710,550,150,'Build next context',[
        'Facts · predictions · open questions',
        'Relevant reviewed lessons',
    ],'database',title_size=31,body_size=25)

    f.rect(1880,320,660,310,'#F2F6FA',stroke=BLUE,r=8)
    for y,kind,title,sub in [
        (348,'database','Read case evidence','AE customers, wallets, devices, transactions'),
        (441,'model','Call an eligible model','DS predictor + versioned model card'),
        (534,'database','Retrieve reviewed knowledge','Scoped lessons and counterexamples'),
    ]:
        f.icon(kind,1905,y,42,BLUE)
        f.text(1965,y+32,title,29,True)
        f.text(1965,y+65,sub,23,color=MUTED)

    # Human review publishes lessons; activation is a separate safeguard gate.
    f.path([(610,835),(550,835),(550,1115),(610,1115)],INK,4)
    f.text(532,1000,'Saved proposal',24,True,INK,anchor='end')
    f.path([(1060,1115),(1180,1115)],PURPLE,5)
    f.text(1120,1094,'Approve',23,True,PURPLE,anchor='middle')
    f.path([(1660,1115),(1780,1115)],PURPLE,5)
    f.text(1720,1094,'Learn',23,True,PURPLE,anchor='middle')
    f.path([(1420,1040),(1420,975),(885,975),(885,860)],PURPLE,4)
    f.text(1130,957,'Applicable lessons',24,True,PURPLE,anchor='middle')
    f.path([(2125,1190),(2125,1280),(260,1280),(260,1190)],PURPLE,5)
    f.text(1270,1260,'Active safeguard',26,True,PURPLE,anchor='middle')

    f.card(610,1040,450,150,'Risk analyst',[
        'Verify resolution + evidence',
    ],'human',color=PURPLE,title_size=31,body_size=25)
    f.card(1180,1040,480,150,'Approved knowledge',[
        'Scope · provenance · expiry',
    ],'database',color=PURPLE,title_size=29,body_size=25)
    f.card(1780,1040,690,150,'Prevention learner',[
        'Propose · replay · analyst activation',
    ],'agent',color=PURPLE,title_size=31,body_size=27)
    f.card(60,1040,400,150,'Payment gate',[
        'Hold for verification or allow',
        'No Gemini per payment',
    ],'shield',color=PURPLE,title_size=29,body_size=24)
    f.save('mint-town-investigation-harness',title='Mint Town — investigation harness')


if __name__ == '__main__':
    harness()
    print('Rendered investigation harness: SVG, PDF and PNG.')
