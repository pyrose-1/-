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
    try: return json.loads(o).get("token")
    except: return None

# 学生 + 机头授权（沿用已有）
rows = sql("SELECT id FROM plm_users WHERE role='STUDENT' ORDER BY id").split()
stu = [int(x) for x in rows]
stu_heads = {}
for line in sql("SELECT userId,instrumentId FROM plm_polyhead_auth ORDER BY userId").splitlines():
    if not line.strip(): continue
    u, h = line.split("\t"); stu_heads.setdefault(int(u), []).append(int(h))
print("学生", len(stu), "有机头授权", len(stu_heads))

# 新需求等级 60/30/10
random.seed(42)
ids = stu[:]; random.shuffle(ids)
n = len(ids); nf = round(n * 0.6); ns = round(n * 0.3)
levels = {}
for i, uid in enumerate(ids):
    levels[uid] = 1.0 if i < nf else 0.7 if i < nf + ns else 0.4
print("等级分布:", dict(Counter(levels.values())))

def demand_of(level, uid):
    out = {}
    g = round(6 * level)
    if g > 0:
        film = g // 3; dry = g - film * 3
        out['VACUUM_OVEN'] = dict(film=film, dry=dry, block=0, grids=film*3+dry, mode='CATEGORY', ids=None, temp=None)
    b = round(2 * level)
    if b > 0: out['FURNACE'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=300)
    b = round(7 * level)
    if b > 0: out['POLY_HEAD'] = dict(film=0, dry=0, block=b, grids=b, mode='SPECIFIC', ids=stu_heads.get(uid, []), temp=None)
    b = round(4 * level)
    if b > 0:
        out['DMA'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=None)
        out['TGA'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=None)
    return out

CATS = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA']
CAP = {'VACUUM_OVEN': 17*7*4, 'FURNACE': 6*7, 'POLY_HEAD': 32*7*2, 'DMA': 28, 'TGA': 28}
adm = login("admin", "Pniaef6b526!"); AH = "-H 'Authorization: Bearer %s'" % adm
cycles = ["2026-07-20", "2026-07-27", "2026-08-03", "2026-08-10", "2026-08-17"]

def dma_scores():
    o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/priorities %s" % AH)
    d = json.loads(o); return sorted([r['scores']['DMA'] for r in d], reverse=True)
print("\n本批开始前 DMA 优先级(高→低 前5/后5):", [round(x,1) for x in dma_scores()[:5]], "...", [round(x,1) for x in dma_scores()[-5:]])

report = []
satrounds = {uid: {c: 0 for c in CATS} for uid in stu}
for wk, ck in enumerate(cycles, 6):
    vals = []
    for uid in stu:
        for cat, v in demand_of(levels[uid], uid).items():
            iv = 'NULL' if not v['ids'] else "'%s'" % json.dumps(v['ids'])
            tv = 'NULL' if v['temp'] is None else str(v['temp'])
            vals.append("(%d,'%s','%s','%s',%s,%d,%d,%d,%s,%d)" % (uid, ck, cat, v['mode'], iv, v['film'], v['dry'], v['block'], tv, v['grids']))
    sql("DELETE FROM plm_booking_demands WHERE cycleKey='%s'" % ck)
    for i in range(0, len(vals), 200):
        sql("INSERT INTO plm_booking_demands (userId,cycleKey,category,instrumentMode,instrumentIds,filmCount,dryCount,blockCount,tempCeiling,gridsTotal) VALUES %s" % ",".join(vals[i:i+200]))
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/lottery/run -H 'Content-Type: application/json' %s -d '{\"cycle\":\"%s\"}'" % (AH, ck))
    res = json.loads(o)
    granted = {}
    for line in sql("SELECT userId,category,taskType,COUNT(*) FROM plm_bookings WHERE cycleKey='%s' GROUP BY userId,category,taskType" % ck).splitlines():
        if not line.strip(): continue
        uid, cat, tt, cnt = line.split("\t"); uid = int(uid); cnt = int(cnt)
        add = cnt*3 if tt == 'FILM' else cnt
        granted[(uid, cat)] = granted.get((uid, cat), 0) + add
    cs = {}
    for cat in CATS:
        dem = grt = full = part = zero = ndem = 0
        for uid in stu:
            dm = demand_of(levels[uid], uid).get(cat)
            if not dm: continue
            ndem += 1; req = dm['grids']; got = granted.get((uid, cat), 0); dem += req; grt += got
            if got >= req: full += 1; satrounds[uid][cat] += 1
            elif got > 0: part += 1
            else: zero += 1
        cs[cat] = dict(ndem=ndem, dem=dem, cap=CAP[cat], grt=grt, full=full, part=part, zero=zero)
    report.append((wk, ck, res.get('bookings'), cs)); print("第%d轮 %s 课表%s条" % (wk, ck, res.get('bookings')))

print("\n========= 续跑 5 轮（第6~10轮）结果 · 需求 60/30/10 =========")
for wk, ck, nb, cs in report:
    print("\n【第%d轮 / %s】 课表 %s 条" % (wk, ck, nb))
    print("  类别            需求人 需求格 容量 授予格 利用率 全满足 部分 落空")
    for cat in CATS:
        s = cs[cat]; util = "%d%%" % round(100*s['grt']/s['cap']) if s['cap'] else "-"
        print("  %-13s %5d %6d %5d %6d %6s %5d %4d %4d" % (cat, s['ndem'], s['dem'], s['cap'], s['grt'], util, s['full'], s['part'], s['zero']))

print("\n===== 这 5 轮公平性：被全满足的轮数分布 =====")
for cat in CATS:
    dist = Counter(satrounds[uid][cat] for uid in stu if demand_of(levels[uid], uid).get(cat))
    print("  %-13s %s" % (cat, "  ".join("满足%d轮:%d人" % (k, dist[k]) for k in sorted(dist))))

print("\n本批结束后 DMA 优先级(高→低 前5/后5):", [round(x,1) for x in dma_scores()[:5]], "...", [round(x,1) for x in dma_scores()[-5:]])
cli.close()
print("\n=== DONE ===")
