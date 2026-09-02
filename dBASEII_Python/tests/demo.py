from pathlib import Path
from tempfile import TemporaryDirectory
from dbase2py import DBase2Table, Field, DBaseEngine

with TemporaryDirectory() as d:
    root=Path(d)
    t=DBase2Table.create(root/'CUSTOMER.DBF',[Field('NAME','C',20),Field('BALANCE','N',10,2),Field('ACTIVE','L',1)])
    t.append({'NAME':'ALICE','BALANCE':100.50,'ACTIVE':True})
    t.append({'NAME':'BOB','BALANCE':250,'ACTIVE':True})
    t.append({'NAME':'CAROL','BALANCE':75,'ACTIVE':False})
    t.save()
    e=DBaseEngine(root)
    for cmd in ['USE CUSTOMER','LIST ALL',"REPLACE ALL BALANCE WITH BALANCE*1.10 FOR ACTIVE = .T.",'SUM BALANCE ALL TO TOTAL','STORE TOTAL TO GRANDTOTAL','INDEX ON NAME TO CUSTOMER_NAME','FIND BOB','DISPLAY']:
        print('. '+cmd); e.execute(cmd)
