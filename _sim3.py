# -*- coding: utf-8 -*-
import os, sys, json, random
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
DBP = "pni38AWG4xy6wEyc"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=20, look_for_keys=False, allow_agent=False)
def run(c, t=180):
    i, o, e = cli.exec_command(c, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def sql(q, t=120):
    out, _ = run("mysql -uplm -p%s plm -N -e \"%s\" 2>/dev/null" % (DBP, q), t); return out
def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o).get("token")

stu = [int(x) for x in sql("SELECT id FROM plm_users WHERE role='STUDENT' ORDER BY id").split()]
stu_heads = {}
for line in sql("SELECT userId,instrumentId FROM plm_polyhead_auth ORDER BY userId").splitlines():
    if line.strip():
        u, h = line.split("\t"); stu_heads.setdefault(int(u), []).append(int(h))

# ===== 旧算法基线：读已存在的第6-10轮(07-20..08-17) DMA =====
old_cycles = ["2026-07-20", "2026-07-27", "2026-08-03", "2026-08-10", "2026-08-17"]
print("===== 旧算法（一次性灌满）基线 · DMA =====")
old_distinct = []
for ck in old_cycles:
    d = sql("SELECT COUNT(DISTINCT userId) FROM plm_bookings WHERE category='DMA' AND cycleKey='%s'" % ck)
    old_distinct.append(int(d or 0))
ever_old = int(sql("SELECT COUNT(DISTINCT userId) FROM plm_bookings WHERE category='DMA' AND cycleKey IN ('%s')" % "','".join(old_cycles)) or 0)
print("  每轮被服务人数:", old_distinct, " 5轮内共服务到:", ever_old, "人 / 需求65人 → 一次没轮到:", 65 - ever_old, "人")

# ===== 新算法：重置 DMA/TGA 优先级为新随机，跑 5 轮 =====
sql("UPDATE plm_instr_priority SET score=ROUND(RAND(),3) WHERE category IN ('DMA','TGA')")
random.seed(42)
ids = stu[:]; random.shuffle(ids)
n = len(ids); nf = round(n*0.6); ns = round(n*0.3)
levels = {uid: (1.0 if i < nf else 0.7 if i < nf+ns else 0.4) for i, uid in enumerate(ids)}

def demand_of(level, uid):
    out = {}
    g = round(6*level)
    if g > 0:
        film = g//3; out['VACUUM_OVEN'] = dict(film=film, dry=g-film*3, block=0, grids=g, mode='CATEGORY', ids=None, temp=None)
    b = round(2*level)
    if b > 0: out['FURNACE'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=300)
    b = round(7*level)
    if b > 0: out['POLY_HEAD'] = dict(film=0, dry=0, block=b, grids=b, mode='SPECIFIC', ids=stu_heads.get(uid, []), temp=None)
    b = round(4*level)
    if b > 0:
        out['DMA'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=None)
        out['TGA'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=None)
    return out

adm = login("admin", "Pniaef6b526!"); AH = "-H 'Authorization: Bearer %s'" % adm
new_cycles = ["2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21"]
new_distinct = []
gotrounds = Counter()  # uid -> #rounds got any DMA
for ck in new_cycles:
    vals = []
    for uid in stu:
        for cat, v in demand_of(levels[uid], uid).items():
            iv = 'NULL' if not v['ids'] else "'%s'" % json.dumps(v['ids'])
            tv = 'NULL' if v['temp'] is None else str(v['temp'])
            vals.append("(%d,'%s','%s','%s',%s,%d,%d,%d,%s,%d)" % (uid, ck, cat, v['mode'], iv, v['film'], v['dry'], v['block'], tv, v['grids']))
    sql("DELETE FROM plm_booking_demands WHERE cycleKey='%s'" % ck)
    for i in range(0, len(vals), 200):
        sql("INSERT INTO plm_booking_demands (userId,cycleKey,category,instrumentMode,instrumentIds,filmCount,dryCount,blockCount,tempCeiling,gridsTotal) VALUES %s" % ",".join(vals[i:i+200]))
    run("curl -s -X POST http://127.0.0.1:3000/api/instruments/lottery/run -H 'Content-Type: application/json' %s -d '{\"cycle\":\"%s\"}'" % (AH, ck))
    d = int(sql("SELECT COUNT(DISTINCT userId) FROM plm_bookings WHERE category='DMA' AND cycleKey='%s'" % ck) or 0)
    new_distinct.append(d)
    for line in sql("SELECT DISTINCT userId FROM plm_bookings WHERE category='DMA' AND cycleKey='%s'" % ck).split():
        gotrounds[int(line)] += 1

ever_new = len(gotrounds)
print("\n===== 新算法（每2格轮换）· DMA =====")
print("  每轮被服务人数:", new_distinct, " 5轮内共服务到:", ever_new, "人 / 需求65人 → 一次没轮到:", 65 - ever_new, "人")
dist = Counter(gotrounds.get(uid, 0) for uid in stu)
print("  被服务轮数分布:", "  ".join("%d轮:%d人" % (k, dist[k]) for k in sorted(dist)))

print("\n===== 对比小结 (DMA, 1台/周28格, 65人争) =====")
print("  每轮服务人数:  旧 %.1f  →  新 %.1f" % (sum(old_distinct)/5, sum(new_distinct)/5))
print("  5轮一次没轮到: 旧 %d 人  →  新 %d 人" % (65-ever_old, 65-ever_new))
cli.close()
print("\n=== DONE ===")
