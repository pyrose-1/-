# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=180):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def sql(s, t=180):
    o,e = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e %s 2>/dev/null" % json.dumps(s), t); return o
ck0 = "2026-06-01"
# 清掉上次跑到 2026-06-15 的空抽签记录与任何零散预约
run("mysql -uplm -ppni38AWG4xy6wEyc plm -e \"DELETE FROM plm_lottery_runs; DELETE FROM plm_bookings;\" 2>/dev/null")
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p)); return json.loads(o).get("token")
TA="-H 'Authorization: Bearer %s'"%login("admin","Pniaef6b526!")
# 正确字段名是 cycle
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/instruments/lottery/run -H 'Content-Type: application/json' %s -d '{\"cycle\":\"%s\"}'"%(TA,ck0), 180)
print("抽签结果(本周 %s):"%ck0, o[:500])

print("\n===== 本周(%s)抽签预约分布 ====="%ck0)
print(sql("SELECT category, taskType, COUNT(*) cnt FROM plm_bookings WHERE cycleKey='%s' GROUP BY category, taskType ORDER BY category"%ck0))
print("\n总格子数 / 有预约人数:", sql("SELECT COUNT(*), COUNT(DISTINCT userId) FROM plm_bookings WHERE cycleKey='%s'"%ck0))
print("\n各类别『至少抽到1次』的人数 / 65:")
print(sql("SELECT category, COUNT(DISTINCT userId) FROM plm_bookings WHERE cycleKey='%s' GROUP BY category ORDER BY category"%ck0))
print("\n按天分布(格子数):")
print(sql("SELECT date, COUNT(*) FROM plm_bookings WHERE cycleKey='%s' GROUP BY date ORDER BY date"%ck0))
print("\n下周(2026-06-08)报名需求仍在(60%):")
print(sql("SELECT category, SUM(filmCount) f, SUM(blockCount) b, COUNT(*) ppl FROM plm_booking_demands WHERE cycleKey='2026-06-08' GROUP BY category ORDER BY category"))
cli.close(); print("\n=== DONE ===")
