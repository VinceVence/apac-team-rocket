"""Small, shared limits for the private single-instance hosted demo."""
import time
from collections import deque

from lab import LabError, now
from settings import DAILY_REPORTS, DAILY_WRITES, DAILY_WORLD_STEPS, READS_PER_MINUTE, WRITES_PER_MINUTE

POST_PATHS = frozenset(('/api/world/step','/api/world/start','/api/world/stop','/api/cloud/export','/api/fraud-desk/demo',
    '/api/fraud-desk/report','/api/fraud-desk/reply','/api/fraud-desk/review',
    '/api/fraud-agent/start','/api/fraud-agent/recheck','/api/fraud-agent/handoff'))
GET_PATHS = frozenset(('/api/state','/api/cloud','/api/fraud-desk'))


class DemoGuard:
    def __init__(self, lab, checkpoint, clock=now, monotonic=time.monotonic, live_enabled=False):
        self.lab,self.checkpoint,self.clock,self.monotonic=lab,checkpoint,clock,monotonic
        self.recent={'GET':deque(),'POST':deque()}
        self.live_enabled=live_enabled
        with lab.lock,lab.db:
            lab.db.execute('''CREATE TABLE IF NOT EXISTS demo_daily_usage(
                day TEXT PRIMARY KEY, writes INTEGER NOT NULL DEFAULT 0,
                world_steps INTEGER NOT NULL DEFAULT 0, reports INTEGER NOT NULL DEFAULT 0)''')
            day=clock()[:10]
            reports=lab.db.execute('SELECT count(*) FROM fraud_reports WHERE substr(created_at,1,10)=?',(day,)).fetchone()[0]
            lab.db.execute('INSERT OR IGNORE INTO demo_daily_usage(day,reports) VALUES(?,?)',(day,reports))
            lab.db.execute('UPDATE demo_daily_usage SET reports=max(reports,?) WHERE day=?',(reports,day))

    def allow(self, method, path, body=None, checkpoint=True):
        # Global limits are intentional: rotating client IDs must not create new allowances.
        if method=='GET':
            allowed=path in GET_PATHS or path.startswith('/api/fraud-desk/reports/')
        else:allowed=path in POST_PATHS
        if not allowed:raise LabError('This endpoint is disabled on the hosted demo.',403)
        with self.lab.lock:
            stamp=self.monotonic();recent=self.recent[method]
            while recent and stamp-recent[0]>=60:recent.popleft()
            if len(recent)>=(READS_PER_MINUTE if method=='GET' else WRITES_PER_MINUTE):
                raise LabError('Hosted request rate limit reached. Wait one minute; no work was queued.',429)
            recent.append(stamp)
            if method=='GET':return
            if path=='/api/fraud-agent/start' and (body.get('mode','fake') not in (('fake','gemini') if self.live_enabled else ('fake',)) or body.get('automatic',True) is not True):
                raise LabError('Use the approved automatic investigation mode.',409)
            day=self.clock()[:10]
            is_report=path in ('/api/fraud-desk/demo','/api/fraud-desk/report')
            if is_report and isinstance(body.get('request_id'),str):
                is_report=not self.lab.db.execute('SELECT 1 FROM fraud_reports WHERE request_id=?',(body['request_id'],)).fetchone()
            is_step=path=='/api/world/step'
            with self.lab.db:
                self.lab.db.execute('INSERT OR IGNORE INTO demo_daily_usage(day) VALUES(?)',(day,))
                usage=self.lab.db.execute('SELECT * FROM demo_daily_usage WHERE day=?',(day,)).fetchone()
                for label,used,added,limit in (('write',usage['writes'],1,DAILY_WRITES),
                    ('world-step',usage['world_steps'],int(is_step),DAILY_WORLD_STEPS),
                    ('new-report',usage['reports'],int(is_report),DAILY_REPORTS)):
                    if used+added>limit:raise LabError('Daily hosted '+label+' limit reached. No work was queued.',429)
                self.lab.db.execute('UPDATE demo_daily_usage SET writes=writes+1,world_steps=world_steps+?,reports=reports+? WHERE day=?',
                                    (int(is_step),int(is_report),day))
            if checkpoint:self.checkpoint()  # External work is admitted durably before it begins.

    def status(self):
        with self.lab.lock:
            row=self.lab.db.execute('SELECT * FROM demo_daily_usage WHERE day=?',(self.clock()[:10],)).fetchone()
        return {'day_utc':self.clock()[:10], 'used':dict(row) if row else {'writes':0,'world_steps':0,'reports':0},
                'limits':{'writes_per_day':DAILY_WRITES,'world_steps_per_day':DAILY_WORLD_STEPS,
                          'new_reports_per_day':DAILY_REPORTS,'reads_per_minute':READS_PER_MINUTE,'writes_per_minute':WRITES_PER_MINUTE}}
