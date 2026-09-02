from pathlib import Path
from dbase2py import DBase2Table, Field, DBaseEngine

def test_native_dbf_roundtrip(tmp_path):
    p=tmp_path/'PEOPLE.DBF'
    t=DBase2Table.create(p,[Field('NAME','C',20),Field('AGE','N',3),Field('ACTIVE','L',1)])
    t.append({'NAME':'ALICE','AGE':30,'ACTIVE':True})
    t.append({'NAME':'BOB','AGE':41,'ACTIVE':False})
    t.save()
    raw=p.read_bytes()
    assert raw[0]==2
    assert len(raw)>=521
    u=DBase2Table(p)
    assert u.count==2 and u.records[0]['NAME']=='ALICE' and u.records[1]['AGE']==41

def test_engine_commands(tmp_path):
    t=DBase2Table.create(tmp_path/'T.DBF',[Field('NAME','C',10),Field('N','N',5)])
    for name,n in [('A',1),('B',2),('C',3)]: t.append({'NAME':name,'N':n})
    t.save()
    e=DBaseEngine(tmp_path)
    e.execute('USE T')
    assert e.execute('COUNT ALL')==3
    e.execute('REPLACE ALL N WITH N*10 FOR N >= 2')
    assert DBase2Table(tmp_path/'T.DBF').records[2]['N']==30
    e.execute("DELETE ALL FOR NAME = 'B'")
    assert DBase2Table(tmp_path/'T.DBF').deleted[1]
    e.execute('PACK')
    assert DBase2Table(tmp_path/'T.DBF').count==2
    e.execute('INDEX ON NAME TO TNAME')
    assert e.execute('FIND C')==2
    e.execute('STORE 123 TO X')
    e.execute('SAVE TO VARS')
    e.execute('RELEASE ALL')
    e.execute('RESTORE FROM VARS')
    assert e.mem['X']==123

def test_cmd_control_flow(tmp_path):
    e=DBaseEngine(tmp_path)
    script=tmp_path/'TEST.CMD'
    script.write_text("""STORE 1 TO X
IF X = 1
 STORE 10 TO Y
ELSE
 STORE 20 TO Y
ENDIF
DO CASE
 CASE Y = 10
  STORE 'OK' TO RESULT
 OTHERWISE
  STORE 'BAD' TO RESULT
ENDCASE
""")
    e.run_cmd(script)
    assert e.mem['RESULT']=='OK'
