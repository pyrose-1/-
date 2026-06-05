# -*- coding: utf-8 -*-
import os, sys, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd, paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
def run(cmd, t=240):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace"), e.read().decode("utf-8","replace")
def sql(s): o,_=run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e %r 2>/dev/null"%s); return o

try:
    import pypinyin
    def py_full(s):
        return ''.join(pypinyin.lazy_pinyin(s))
    def py_init(s):
        return ''.join(x[0] for x in pypinyin.lazy_pinyin(s) if x)
    print("pypinyin OK")
except Exception:
    def py_full(s): return ''
    def py_init(s): return ''
    print("no pypinyin -> 拼音留空")

# 读 xls（无表头，按列位）
df = pd.read_excel("申购历史记录.xls", header=None)
COL = {'name':0,'no':1,'cas':2,'brand':3,'spec':4,'qty':5,'unit':6,'who':7,'unit_price':8,'total':9,'topic':10,'supplier':11,'time':12,'invoice':13,'note':14}
rows = df.iloc[3:]  # 0,1空 2表头

# 维度表
um = {}
for ln in sql("SELECT id,name,tutorId FROM plm_users").strip().splitlines():
    p = ln.split('\t');
    if len(p) >= 2: um[p[1].strip()] = (int(p[0]), (int(p[2]) if len(p)>2 and p[2] not in ('NULL','') else None))
chem_cas = {}
for ln in sql("SELECT id,cas FROM plm_chemicals WHERE cas IS NOT NULL").strip().splitlines():
    p = ln.split('\t');
    if len(p)==2 and p[1] not in ('NULL',''): chem_cas[p[1].strip()] = int(p[0])
haz_toxic = {}
for ln in sql("SELECT cas,toxic FROM plm_hazmat").strip().splitlines():
    p = ln.split('\t')
    if len(p)==2: haz_toxic[p[0].strip()] = (p[1]=='1')
print("users=%d  既有化学品(含cas)=%d  危化条目=%d"%(len(um),len(chem_cas),len(haz_toxic)))

def esc(v):
    if v is None: return ''
    s = str(v).replace('\\','').replace("'","''").replace('\n',' ').replace('\r',' ').replace('\t',' ').strip()
    return s
def cell(r,k):
    v = r.iloc[COL[k]]
    if pd.isna(v): return None
    return v
def fmt_time(v):
    if v is None: return '2026-01-01 00:00:00'
    try: return pd.to_datetime(v).strftime('%Y-%m-%d %H:%M:%S')
    except Exception: return '2026-01-01 00:00:00'
def fmt_qty(v):
    if v is None: return None
    try:
        f=float(v);
        return str(int(f)) if f==int(f) else str(f)
    except Exception: return esc(v)

stmts=[]
new_chem={}  # cas -> (name,unit,listed,toxic)
imported=0; skip_nocas=0; unmatched={}
bidx=0
data_rows=[]
for _,r in rows.iterrows():
    name=cell(r,'name'); cas=cell(r,'cas'); who=cell(r,'who')
    if name is None and cas is None and who is None: continue
    if cas is None or str(cas).strip()=='':
        skip_nocas+=1; continue
    cas=str(cas).strip(); nm=esc(name) or '未命名'
    whon=str(who).strip() if who is not None else ''
    if whon not in um:
        unmatched[whon]=unmatched.get(whon,0)+1; continue
    uid,tid=um[whon]
    listed = cas in haz_toxic
    toxic = haz_toxic.get(cas,False)
    if cas not in chem_cas and cas not in new_chem:
        unit=esc(cell(r,'unit')) or 'mL'
        new_chem[cas]=(nm,unit,listed,toxic)
    data_rows.append(dict(uid=uid,tid=tid,name=nm,cas=cas,no=esc(cell(r,'no')),
        price=cell(r,'total') if cell(r,'total') is not None else cell(r,'unit_price'),
        qty=fmt_qty(cell(r,'qty')), unit=esc(cell(r,'unit')),
        reason=esc(' '.join(filter(None,[
            ('品牌:'+esc(cell(r,'brand'))) if cell(r,'brand') is not None else '',
            ('规格:'+esc(cell(r,'spec'))) if cell(r,'spec') is not None else '',
            ('供应商:'+esc(cell(r,'supplier'))) if cell(r,'supplier') is not None else '',
            ('课题:'+esc(cell(r,'topic'))) if cell(r,'topic') is not None else '',
            ('备注:'+esc(cell(r,'note'))) if cell(r,'note') is not None else '',
        ]))),
        listed=listed, toxic=toxic, time=fmt_time(cell(r,'time'))))

# 1) 新化学品
for cas,(nm,unit,listed,toxic) in new_chem.items():
    hz = 'CONTROLLED' if toxic else ('HIGH' if listed else 'MODERATE')
    pf=py_full(nm); pi=py_init(nm)
    stmts.append("INSERT INTO plm_chemicals (name,aliases,pinyin,pinyinInitials,cas,hazardLevel,unit,safetyStock,active) SELECT '%s','[]','%s','%s','%s','%s','%s',0,1 FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM plm_chemicals WHERE cas='%s');"%(nm,esc(pf),esc(pi),cas,hz,esc(unit) or 'mL',cas))

# 2) 批次 + 申购单
for d in data_rows:
    bidx+=1
    bn='HIS%05d-%d'%(bidx,d['uid'])
    stmts.append("INSERT INTO plm_chemical_batches (chemicalId,batchNo,scope,ownerId,shareable,remainLevel,receivedAt) SELECT id,'%s','PERSONAL',%d,1,'FULL','%s' FROM plm_chemicals WHERE cas='%s' LIMIT 1;"%(bn,d['uid'],d['time'],d['cas']))
    price = 'NULL'
    if d['price'] is not None:
        try: price='%.2f'%float(d['price'])
        except Exception: price='NULL'
    tid = str(d['tid']) if d['tid'] else 'NULL'
    revid = str(d['tid']) if d['tid'] else 'NULL'
    revat = "'%s'"%d['time'] if d['tid'] else 'NULL'
    qty = "'%s'"%d['qty'] if d['qty'] else 'NULL'
    unit = "'%s'"%d['unit'] if d['unit'] else 'NULL'
    no = "'%s'"%d['no'] if d['no'] else 'NULL'
    reason = "'%s'"%d['reason'] if d['reason'] else 'NULL'
    stmts.append(
      "INSERT INTO plm_purchase_requests (applicantId,tutorId,chemicalId,name,cas,productNo,price,quantity,unit,reason,urgency,status,hazmatListed,hazmatToxic,reviewerId,reviewedAt,batchId,stockedAt,submittedAt,createdAt) "
      "SELECT {uid},{tid},(SELECT id FROM plm_chemicals WHERE cas='{cas}' LIMIT 1),'{name}','{cas}',{no},{price},{qty},{unit},{reason},'NORMAL','APPROVED',{listed},{toxic},{revid},{revat},(SELECT id FROM plm_chemical_batches WHERE batchNo='{bn}'),'{time}','{time}','{time}';".format(
        uid=d['uid'], tid=tid, cas=d['cas'], name=d['name'], no=no, price=price, qty=qty, unit=unit,
        reason=reason, listed=1 if d['listed'] else 0, toxic=1 if d['toxic'] else 0, revid=revid, revat=revat, bn=bn, time=d['time']))

print("将导入: 申购单 %d 条 · 新建化学品 %d 种 · 跳过(无CAS) %d · 未匹配姓名 %d 人次"%(len(data_rows),len(new_chem),skip_nocas,sum(unmatched.values())))
if unmatched: print("  未匹配:", dict(unmatched))

# 写入服务器并执行
script = "\n".join(stmts)
b=base64.b64encode(script.encode()).decode()
# 分块写避免命令过长
run("rm -f /tmp/imp.sql")
CH=60000
for i in range(0,len(b),CH):
    run("python3 -c \"import base64,sys;open('/tmp/imp.sql','ab').write(base64.b64decode(sys.argv[1]))\" %s"%b[i:i+CH])
o,e=run("mysql -uplm -ppni38AWG4xy6wEyc plm < /tmp/imp.sql 2>&1", 600)
print("执行:", (o or '(ok)')[-400:], e[-300:])
print("\n== 结果校验 ==")
print("化学品总数:", sql("SELECT COUNT(*) FROM plm_chemicals").strip())
print("申购单(APPROVED):", sql("SELECT COUNT(*) FROM plm_purchase_requests WHERE status='APPROVED'").strip())
print("批次总数:", sql("SELECT COUNT(*) FROM plm_chemical_batches").strip())
print("按申购人前10:")
print(sql("SELECT u.name,COUNT(*) cnt,ROUND(SUM(p.price),1) amt FROM plm_purchase_requests p JOIN plm_users u ON u.id=p.applicantId WHERE p.status='APPROVED' GROUP BY p.applicantId ORDER BY cnt DESC LIMIT 10"))
print("危化标记数:", sql("SELECT COUNT(*) FROM plm_purchase_requests WHERE hazmatListed=1 AND status='APPROVED'").strip())
cli.close(); print("\n=== DONE ===")
