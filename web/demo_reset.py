"""Fresh synthetic scenes with durable spend, admission counters and private archives."""
import gzip
import uuid
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from lab import LabError, now, AS_OF
from cloud_data import MAX_STATE_BYTES


def initialize(lab):
    lab.db.executescript('''
    CREATE TABLE IF NOT EXISTS model_usage_archive(
      id TEXT PRIMARY KEY,provider TEXT NOT NULL,report_id TEXT,role TEXT NOT NULL,
      created_at TEXT NOT NULL,amount_microusd INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS demo_usage_archive(
      day TEXT PRIMARY KEY,publications INTEGER NOT NULL DEFAULT 0,
      queries INTEGER NOT NULL DEFAULT 0,model_builds INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS demo_scene(id INTEGER PRIMARY KEY CHECK(id=1),scene_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS demo_scene_archives(scene_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,location TEXT NOT NULL);
    ''')
    with lab.db:lab.db.execute('INSERT OR IGNORE INTO demo_scene VALUES(1,?)',('DEMO-'+uuid.uuid4().hex[:10],))


class DemoReset:
    def __init__(self,lab,world,runner,cloud,baseline):
        self.lab,self.world,self.runner,self.cloud,self.baseline=lab,world,runner,cloud,baseline
        initialize(lab)

    def reset(self,new_run_id):
        with self.lab.lock:
            if self.runner.pending or self.lab.db.execute("SELECT 1 FROM fraud_agent_turns WHERE status IN ('reserved','responded')").fetchone():
                raise LabError('An agent is still working. Finish or stop that investigation before starting a fresh demo.',409)
            if self.lab.db.in_transaction:raise RuntimeError('Fresh scenes require a committed checkpoint.')
            previous=self.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0]
            data=self.lab.db.serialize()
            if len(data)>MAX_STATE_BYTES:raise LabError('The scene exceeds the archive size limit.',507)
            archive=gzip.compress(data,compresslevel=1,mtime=0)
            location='archives/'+previous+'-'+uuid.uuid4().hex[:8]+'.sqlite3.gz'
            if self.cloud:
                # Archive once before replacing the canonical state. An uncertain upload
                # stops the reset; never overwrite or repeat an ambiguous object write.
                self.cloud.upload(location,archive,'0')
            else:
                database=self.lab.db.execute('PRAGMA database_list').fetchone()['file']
                target=(Path(database).parent if database else Path(__file__).resolve().parent/'data')/location
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as f:f.write(archive)
            tables={r['name'] for r in self.lab.rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            charges=self.lab.rows('SELECT * FROM model_usage_archive')
            for table in ('agent_runs','macro_decisions','science_reviews','mesh_turns','fraud_agent_turns'):
                if table not in tables:continue
                if table=='fraud_agent_turns':
                    rows=self.lab.rows('SELECT id,provider,report_id,role,created_at,coalesce(cost_microusd,reserved_microusd) AS amount FROM fraud_agent_turns')
                else:
                    rows=self.lab.rows("SELECT id,provider,NULL AS report_id,'legacy' AS role,created_at,coalesce(cost_usd,reserved_usd,0) AS amount FROM "+table+" WHERE provider='gemini'")
                    for row in rows:row['amount']=int((Decimal(str(row['amount']))*1000000).to_integral_value(rounding=ROUND_CEILING))
                for row in rows:charges.append({'id':previous+':'+table+':'+row['id'],'provider':row['provider'],
                    'report_id':row['report_id'],'role':row['role'],'created_at':row['created_at'],'amount_microusd':row['amount']})
            usage={r['day']:r for r in self.lab.rows('SELECT * FROM demo_usage_archive')}
            for table,column,where in [('cloud_exports','publications','WHERE row_count>0'),('warehouse_snapshots','publications',''),('warehouse_queries','queries',''),('behavior_models','model_builds','')]:
                if table not in tables:continue
                for row in self.lab.rows('SELECT substr(created_at,1,10) AS day,count(*) AS n FROM '+table+' '+where+' GROUP BY day'):
                    entry=usage.setdefault(row['day'],{'day':row['day'],'publications':0,'queries':0,'model_builds':0});entry[column]+=row['n']
            admissions=self.lab.rows('SELECT * FROM demo_daily_usage') if 'demo_daily_usage' in tables else []
            control=dict(self.lab.db.execute('SELECT * FROM fraud_live_control WHERE id=1').fetchone())
            archives=self.lab.rows('SELECT * FROM demo_scene_archives ORDER BY created_at DESC LIMIT 49')
            archives.append({'scene_id':previous,'created_at':now(),'location':location})
            script=self.baseline()
            drop='\n'.join('DROP TABLE "'+name.replace('"','""')+'";' for name in tables)
            try:
                self.lab.db.executescript('PRAGMA foreign_keys=OFF; BEGIN IMMEDIATE;\n'+drop+'\n'+script)
                self.lab.db.executemany('INSERT OR IGNORE INTO model_usage_archive VALUES(:id,:provider,:report_id,:role,:created_at,:amount_microusd)',charges)
                self.lab.db.executemany('INSERT OR REPLACE INTO demo_usage_archive VALUES(:day,:publications,:queries,:model_builds)',usage.values())
                self.lab.db.executemany('INSERT OR REPLACE INTO demo_scene_archives VALUES(:scene_id,:created_at,:location)',archives)
                for row in admissions:
                    columns=list(row);self.lab.db.execute('INSERT OR REPLACE INTO demo_daily_usage('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',tuple(row[k] for k in columns))
                self.lab.db.execute('UPDATE fraud_live_control SET next_call_at=?,blocked_reason=? WHERE id=1',(control['next_call_at'],control['blocked_reason']))
                self.lab.db.execute('UPDATE demo_scene SET scene_id=? WHERE id=1',('DEMO-'+uuid.uuid4().hex[:10],))
                self.lab.db.execute('UPDATE world_demo_state SET run_id=?,guided=1,event_start=(SELECT coalesce(max(rowid),0) FROM financial_events) WHERE id=1',(new_run_id,))
                self.lab.db.commit()
            except Exception:
                self.lab.db.rollback();raise
            finally:self.lab.db.execute('PRAGMA foreign_keys=ON')
            self.lab.clock_day=AS_OF
            if self.lab.db.execute('PRAGMA foreign_key_check').fetchone():raise RuntimeError('Fresh scene failed referential integrity.')
            if not self.lab.integrity():raise RuntimeError('Fresh scene ledger is not balanced.')
            if self.cloud:self.cloud.save(self.lab)
