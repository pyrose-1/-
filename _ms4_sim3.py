# -*- coding: utf-8 -*-
import os, sys, json, random, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=180):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def sql(s, t=180):
    o,_ = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e %s 2>/dev/null" % json.dumps(s), t); return o
def sqlx(s, t=180):
    b=base64.b64encode(s.encode()).decode()
    return run("python3 -c \"import base64;open('/tmp/q.sql','w').write(base64.b64decode('%s').decode())\"; mysql -uplm -ppni38AWG4xy6wEyc plm < /tmp/q.sql 2>&1"%b, t)

ck = "2026-06-15"
# 满额(100%)基准
FULL = {'film':2, 'cycle':2, 'dma':4, 'tga':4}

ids = [int(x) for x in sql("SELECT id FROM plm_users WHERE role='STUDENT' ORDER BY id").split()]
print("学生数:", len(ids))

# 清掉该周旧报名
sqlx("DELETE FROM plm_booking_demands WHERE cycleKey='%s';" % ck)

rows = []
rsum = 0.0
sums = {'film':0,'cycle':0,'dma':0,'tga':0}
for uid in ids:
    r = random.uniform(0.5, 1.0)   # 50%~100%，均值75%
    rsum += r
    film = round(FULL['film']*r); cycle = round(FULL['cycle']*r)
    dma = round(FULL['dma']*r); tga = round(FULL['tga']*r)
    sums['film']+=film; sums['cycle']+=cycle; sums['dma']+=dma; sums['tga']+=tga
    rows.append((uid, ck, 'VACUUM_OVEN', 'CATEGORY', 'NULL', film, 0, 0, 'NULL', film*3))
    rows.append((uid, ck, 'CYCLE_OVEN', 'CATEGORY', 'NULL', 0, 0, cycle, 200, cycle))
    rows.append((uid, ck, 'DMA', 'CATEGORY', 'NULL', 0, 0, dma, 'NULL', dma))
    rows.append((uid, ck, 'TGA', 'CATEGORY', 'NULL', 0, 0, tga, 'NULL', tga))
vals = ",".join("(%d,'%s','%s','%s',%s,%d,%d,%d,%s,%d,NOW(),NOW())" % x for x in rows)
o,e = sqlx("INSERT INTO plm_booking_demands (userId,cycleKey,category,instrumentMode,instrumentIds,filmCount,dryCount,blockCount,tempCeiling,gridsTotal,createdAt,updatedAt) VALUES " + vals + ";")
print("插入 %s 报名:" % ck, o[-150:] or "ok", e[-150:])

print("\n平均需求比例: %.1f%% (目标75%%, 范围50-100%%)" % (rsum/len(ids)*100))
print("各类总需求: 铺膜 %d (满额%d) · 环化 %d (满额%d) · DMA %d (满额%d) · TGA %d (满额%d)" % (
    sums['film'], FULL['film']*len(ids), sums['cycle'], FULL['cycle']*len(ids), sums['dma'], FULL['dma']*len(ids), sums['tga'], FULL['tga']*len(ids)))
print("\n=== 入库校验 ===")
print(sql("SELECT category, SUM(filmCount) film, SUM(blockCount) blk, COUNT(*) ppl, ROUND(AVG(filmCount+blockCount),2) avgEach FROM plm_booking_demands WHERE cycleKey='%s' GROUP BY category ORDER BY category"%ck))
cli.close(); print("\n=== DONE ===")
