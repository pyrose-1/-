# -*- coding: utf-8 -*-
import os, sys, json, glob, re, random, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import docx, bcrypt, paramiko
from collections import Counter

HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
DBP = "pni38AWG4xy6wEyc"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=20, look_for_keys=False, allow_agent=False)

def run(c, t=300):
    i, o, e = cli.exec_command(c, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def sql(q, t=120):
    out, _ = run("mysql -uplm -p%s plm -N -e \"%s\" 2>/dev/null" % (DBP, q), t)
    return out

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    try:
        return json.loads(o).get("token")
    except Exception:
        return None

# ---- 解析名单 ----
fn = [f for f in glob.glob("*.docx") if "课题" in f][0]
doc = docx.Document(fn); tbl = doc.tables[0]
teachers = []; students = []
for r in tbl.rows:
    c = [x.text.strip() for x in r.cells]
    role = c[0]; name = re.sub(r"\s+", "", c[1]); phone = c[2].strip(); email = c[3].strip(); sid = c[4].strip()
    if not name:
        continue
    if role == "教师" and phone:
        teachers.append((phone, name, phone))
    elif sid:
        students.append((sid, name, phone))
print("教师", len(teachers), "学生", len(students))

H = bcrypt.hashpw(b"Plm@2026", bcrypt.gensalt(10)).decode()

# ---- 清理旧数据 ----
for q in ["DELETE FROM plm_instr_priority", "DELETE FROM plm_polyhead_auth", "DELETE FROM plm_booking_demands",
          "DELETE FROM plm_bookings", "DELETE FROM plm_lottery_runs",
          "DELETE FROM plm_instruments WHERE name LIKE '聚合机头-%（测试）'",
          "DELETE FROM plm_users WHERE username IN ('stu_xm','stu_xg','stu_xh')"]:
    sql(q)
print("旧数据已清")

def esc(s):
    return s.replace("'", "''")

vals = []
for (un, nm, ph) in teachers:
    vals.append("('%s','%s','%s','TUTOR','%s','ACTIVE')" % (esc(un), H, esc(nm), esc(ph)))
for (un, nm, ph) in students:
    vals.append("('%s','%s','%s','STUDENT','%s','ACTIVE')" % (esc(un), H, esc(nm), esc(ph)))
sql("INSERT IGNORE INTO plm_users (username,passwordHash,name,role,phone,status) VALUES %s" % ",".join(vals))
print("账号建好, 当前用户数:", sql("SELECT COUNT(*) FROM plm_users"))

heads_vals = ",".join("('聚合机头-%d#','POLY_HEAD','HALF_DAY',0,0,0,1,1,'正常',1)" % i for i in range(1, 33))
sql("INSERT INTO plm_instruments (name,category,blockType,filmCapable,dryCapable,piggyback,lottery,authRequired,status,active) VALUES %s" % heads_vals)
print("机头数:", sql("SELECT COUNT(*) FROM plm_instruments WHERE category='POLY_HEAD'"))

run("export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; pm2 restart plm-api >/dev/null 2>&1")
time.sleep(6)
print("已重启, 优先级行数:", sql("SELECT COUNT(*) FROM plm_instr_priority"))

rows = sql("SELECT id,username FROM plm_users WHERE role='STUDENT' ORDER BY id").splitlines()
stu = [(int(r.split('\t')[0]), r.split('\t')[1]) for r in rows if r.strip()]
heads = [int(x) for x in sql("SELECT id FROM plm_instruments WHERE category='POLY_HEAD' ORDER BY id").split()]
print("真实学生", len(stu), "机头", len(heads))

auth_vals = []; stu_heads = {}
for gi in range(0, len(stu), 4):
    grp = stu[gi:gi + 4]; hpair = heads[(gi // 4) * 2:(gi // 4) * 2 + 2]
    if len(hpair) < 2:
        hpair = heads[-2:]
    for (uid, un) in grp:
        stu_heads[uid] = hpair
        for hid in hpair:
            auth_vals.append("(%d,%d)" % (uid, hid))
sql("INSERT INTO plm_polyhead_auth (userId,instrumentId) VALUES %s" % ",".join(auth_vals))
print("授权数:", sql("SELECT COUNT(*) FROM plm_polyhead_auth"))

random.seed(42)
ids = [uid for uid, _ in stu]; random.shuffle(ids)
n = len(ids); n3 = round(n * 0.3)
levels = {}
for i, uid in enumerate(ids):
    levels[uid] = 1.0 if i < n3 else 0.7 if i < 2 * n3 else 0.4 if i < 3 * n3 else 0.1
print("等级分布:", dict(Counter(levels.values())))

def demand_of(level, uid):
    out = {}
    g = round(6 * level)
    if g > 0:
        film = g // 3; dry = g - film * 3
        out['VACUUM_OVEN'] = dict(film=film, dry=dry, block=0, grids=film * 3 + dry, mode='CATEGORY', ids=None, temp=None)
    b = round(2 * level)
    if b > 0:
        out['FURNACE'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=300)
    b = round(7 * level)
    if b > 0:
        out['POLY_HEAD'] = dict(film=0, dry=0, block=b, grids=b, mode='SPECIFIC', ids=stu_heads[uid], temp=None)
    b = round(4 * level)
    if b > 0:
        out['DMA'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=None)
        out['TGA'] = dict(film=0, dry=0, block=b, grids=b, mode='CATEGORY', ids=None, temp=None)
    return out

CATS = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA']
CAP = {'VACUUM_OVEN': 17 * 7 * 4, 'FURNACE': 6 * 7, 'POLY_HEAD': 32 * 7 * 2, 'DMA': 28, 'TGA': 28}
adm = login("admin", "Pniaef6b526!"); AH = "-H 'Authorization: Bearer %s'" % adm
cycles = ["2026-06-15", "2026-06-22", "2026-06-29", "2026-07-06", "2026-07-13"]

report = []
satrounds = {uid: {c: 0 for c in CATS} for uid, _ in stu}
for wk, ck in enumerate(cycles, 1):
    vals = []
    for uid, _ in stu:
        dm = demand_of(levels[uid], uid)
        for cat, v in dm.items():
            iv = 'NULL' if not v['ids'] else "'%s'" % json.dumps(v['ids'])
            tv = 'NULL' if v['temp'] is None else str(v['temp'])
            vals.append("(%d,'%s','%s','%s',%s,%d,%d,%d,%s,%d)" % (uid, ck, cat, v['mode'], iv, v['film'], v['dry'], v['block'], tv, v['grids']))
    sql("DELETE FROM plm_booking_demands WHERE cycleKey='%s'" % ck)
    for i in range(0, len(vals), 200):
        sql("INSERT INTO plm_booking_demands (userId,cycleKey,category,instrumentMode,instrumentIds,filmCount,dryCount,blockCount,tempCeiling,gridsTotal) VALUES %s" % ",".join(vals[i:i + 200]))
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/lottery/run -H 'Content-Type: application/json' %s -d '{\"cycle\":\"%s\"}'" % (AH, ck))
    res = json.loads(o)
    bk = sql("SELECT userId,category,taskType,COUNT(*) FROM plm_bookings WHERE cycleKey='%s' GROUP BY userId,category,taskType" % ck).splitlines()
    granted = {}
    for line in bk:
        if not line.strip():
            continue
        uid, cat, tt, cnt = line.split('\t'); uid = int(uid); cnt = int(cnt)
        w = 3 if tt == 'FILM' else 1
        add = cnt * w if cat == 'VACUUM_OVEN' else cnt
        granted[(uid, cat)] = granted.get((uid, cat), 0) + add
    catstat = {}
    for cat in CATS:
        dem = grt = full = part = zero = ndem = 0
        for uid, _ in stu:
            dm = demand_of(levels[uid], uid).get(cat)
            if not dm:
                continue
            ndem += 1; req = dm['grids']; got = granted.get((uid, cat), 0)
            dem += req; grt += got
            if got >= req:
                full += 1; satrounds[uid][cat] += 1
            elif got > 0:
                part += 1
            else:
                zero += 1
        catstat[cat] = dict(ndem=ndem, dem=dem, cap=CAP[cat], grt=grt, full=full, part=part, zero=zero)
    report.append((wk, ck, res.get('bookings'), catstat))
    print("第%d轮 %s 课表%s条" % (wk, ck, res.get('bookings')))

print("\n================= 5 轮抽签结果 =================")
for wk, ck, nb, cs in report:
    print("\n【第%d轮 / %s】 课表 %s 条" % (wk, ck, nb))
    print("  类别            需求人 需求格 容量 授予格 利用率 全满足 部分 落空")
    for cat in CATS:
        s = cs[cat]
        util = "%d%%" % round(100 * s['grt'] / s['cap']) if s['cap'] else "-"
        print("  %-13s %5d %6d %5d %6d %6s %5d %4d %4d" % (cat, s['ndem'], s['dem'], s['cap'], s['grt'], util, s['full'], s['part'], s['zero']))

print("\n========== 5 轮公平性：被全满足的轮数分布 ==========")
for cat in CATS:
    dist = Counter(satrounds[uid][cat] for uid, _ in stu if demand_of(levels[uid], uid).get(cat))
    line = "  ".join("满足%d轮:%d人" % (k, dist[k]) for k in sorted(dist))
    print("  %-13s %s" % (cat, line))

print("\n最终优先级抽样(前8名学生):")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/priorities %s | python3 -c \"import sys,json;[print('  ',r['name'],{k:round(v,2) for k,v in r['scores'].items()}) for r in json.load(sys.stdin)[:8]]\"" % AH)
print(o)
cli.close()
print("\n=== DONE ===")
