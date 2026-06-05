# -*- coding: utf-8 -*-
import os, sys, json
from datetime import date, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=180):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def sql(s, t=180):
    o,e = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e %s 2>/dev/null" % json.dumps(s), t); return o, e
def sqlx(s, t=180):
    # multi-statement via stdin
    import base64
    b=base64.b64encode(s.encode()).decode()
    return run("python3 -c \"import base64;open('/tmp/q.sql','w').write(base64.b64decode('%s').decode())\"; mysql -uplm -ppni38AWG4xy6wEyc plm < /tmp/q.sql 2>&1"%b, t)

# 周一
today = date(2026,6,5)
mon0 = today - timedelta(days=today.weekday())   # 本周一 2026-06-01
mon1 = mon0 + timedelta(days=7)                   # 下周一 2026-06-08
ck0 = mon0.isoformat(); ck1 = mon1.isoformat()
print("本周一=", ck0, " 下周一=", ck1)

# 1) 清空所有预约信息 + 重置随机优先级
o,e = sqlx("DELETE FROM plm_bookings; DELETE FROM plm_booking_demands; DELETE FROM plm_lottery_runs; DELETE FROM plm_piggyback; UPDATE plm_instr_priority SET score = ROUND(RAND(),3);")
print("清空+重置优先级:", o[-200:] or "ok", e[-150:])

# 学生
ids_o,_ = sql("SELECT id FROM plm_users WHERE role='STUDENT' ORDER BY id")
sids = [int(x) for x in ids_o.split()] if ids_o else []
print("学生数:", len(sids))

def build_demands(ck, film, cycle, dma, tga):
    rows = []
    for uid in sids:
        rows.append((uid, ck, 'VACUUM_OVEN', 'CATEGORY', 'NULL', film, 0, 0, 'NULL', film*3))
        rows.append((uid, ck, 'CYCLE_OVEN', 'CATEGORY', 'NULL', 0, 0, cycle, 200, cycle))
        rows.append((uid, ck, 'DMA', 'CATEGORY', 'NULL', 0, 0, dma, 'NULL', dma))
        rows.append((uid, ck, 'TGA', 'CATEGORY', 'NULL', 0, 0, tga, 'NULL', tga))
    vals = ",".join("(%d,'%s','%s','%s',%s,%d,%d,%d,%s,%d,NOW(),NOW())" % r for r in rows)
    return "INSERT INTO plm_booking_demands (userId,cycleKey,category,instrumentMode,instrumentIds,filmCount,dryCount,blockCount,tempCeiling,gridsTotal,createdAt,updatedAt) VALUES " + vals + ";"

# 2) 上一周报名(=本周目标周) 90%: 铺膜2 环化2 DMA4 TGA4
o,e = sqlx(build_demands(ck0, 2, 2, 4, 4))
print("插入本周(90%)报名:", o[-150:] or "ok", e[-150:])

# 3) 抽签更新本周
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p))
    return json.loads(o).get("token")
TA="-H 'Authorization: Bearer %s'"%login("admin","Pniaef6b526!")
o,_=run("curl -s -X POST 'http://127.0.0.1:3000/api/instruments/lottery/run?cycleKey=%s' -H 'Content-Type: application/json' %s -d '{\"cycleKey\":\"%s\"}'"%(ck0,TA,ck0), 180)
print("抽签结果(本周):", o[:400])

# 4) 这一周报名(=下周目标周) 60%: 铺膜1 环化1 DMA2 TGA2
o,e = sqlx(build_demands(ck1, 1, 1, 2, 2))
print("插入下周(60%)报名:", o[-150:] or "ok", e[-150:])

# 5) 汇总
print("\n===== 本周(%s)抽签预约分布 ====="%ck0)
o,_=sql("SELECT category, taskType, COUNT(*) FROM plm_bookings WHERE cycleKey='%s' GROUP BY category, taskType ORDER BY category"%ck0)
print(o)
o,_=sql("SELECT COUNT(*) total, COUNT(DISTINCT userId) served FROM plm_bookings WHERE cycleKey='%s'"%ck0)
print("本周 预约格子总数 / 有预约的人数:", o)
print("\n===== 报名(需求)统计 =====")
o,_=sql("SELECT cycleKey, category, SUM(filmCount) film, SUM(dryCount) dry, SUM(blockCount) blk, COUNT(*) people FROM plm_booking_demands GROUP BY cycleKey, category ORDER BY cycleKey, category")
print(o)
cli.close(); print("\n=== DONE ===")
