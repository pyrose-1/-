# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
def run(cmd, t=180):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def sql(s): o,_=run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e %s 2>/dev/null"%json.dumps(s)); return o
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p)); return json.loads(o).get("token")
TA="-H 'Authorization: Bearer %s'"%login("admin","Pniaef6b526!")
def post(path, body, tok=TA):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/instruments/%s -H 'Content-Type: application/json' %s -d %s"%(path,tok,json.dumps(json.dumps(body)))); return o

print("## 1) 新建 OTHER 仪器(记录用)")
print(" ", post("admin/instrument", {"name":"测试-超声清洗机","categoryMode":"OTHER","blockType":"四块"})[:200])
print("## 2) 已有 真空 + 3+1")
print(" ", post("admin/instrument", {"name":"测试-真空烘箱-新","categoryMode":"EXISTING","categoryKey":"VACUUM_OVEN","blockType":"3+1","lottery":True})[:200])
print("## 3) 新建大类 纺丝机 (抽签, 上限3, 全天)")
r=post("admin/instrument", {"name":"测试-纺丝机1","categoryMode":"NEW","newCategoryLabel":"纺丝机","blockType":"全天","lottery":True,"weeklyCap":3})
print(" ", r[:240])
try: ck_cat=json.loads(r).get("category")
except: ck_cat=None
print("  新大类key:", ck_cat)

print("\n## categories now:")
o,_=run("curl -s http://127.0.0.1:3000/api/instruments/categories %s | python3 -c \"import sys,json;[print('  ',c['key'],c['label'],c['lottery'],'cap=',c['weeklyCap']) for c in json.load(sys.stdin)]\""%TA); print(o)

# 给一个测试周 2026-06-22 写两个学生对新大类的需求并抽签
if ck_cat:
    ids=[int(x) for x in sql("SELECT id FROM plm_users WHERE role='STUDENT' ORDER BY id LIMIT 5").split()]
    vals=",".join("(%d,'2026-06-22','%s','CATEGORY',NULL,0,0,3,NULL,3,NOW(),NOW())"%(u,ck_cat) for u in ids)
    run("mysql -uplm -ppni38AWG4xy6wEyc plm -e \"INSERT INTO plm_booking_demands (userId,cycleKey,category,instrumentMode,instrumentIds,filmCount,dryCount,blockCount,tempCeiling,gridsTotal,createdAt,updatedAt) VALUES %s\" 2>/dev/null"%vals)
    print("\n## 对 2026-06-22 抽签(含新大类)")
    print(" ", post("lottery/run", {"cycle":"2026-06-22"})[:400])
    print("## 新大类预约结果:")
    print(sql("SELECT date,startHour,endHour,COUNT(*) FROM plm_bookings WHERE cycleKey='2026-06-22' AND category='%s' GROUP BY date,startHour ORDER BY date"%ck_cat))
    print(" 总数/人数:", sql("SELECT COUNT(*),COUNT(DISTINCT userId) FROM plm_bookings WHERE cycleKey='2026-06-22' AND category='%s'"%ck_cat))

# 清理测试数据
print("\n## 清理测试数据")
run("mysql -uplm -ppni38AWG4xy6wEyc plm -e \"DELETE FROM plm_bookings WHERE cycleKey='2026-06-22'; DELETE FROM plm_lottery_runs WHERE cycleKey='2026-06-22'; DELETE FROM plm_booking_demands WHERE cycleKey='2026-06-22'; DELETE FROM plm_instruments WHERE name LIKE '测试-%%'; DELETE FROM plm_instr_categories WHERE builtin=0; DELETE FROM plm_instr_priority WHERE category LIKE 'CUSTOM_%%';\" 2>/dev/null")
print("  已删除测试仪器/大类/需求/预约")
print("  剩余非内置大类:", sql("SELECT COUNT(*) FROM plm_instr_categories WHERE builtin=0"))
print("  测试仪器残留:", sql("SELECT COUNT(*) FROM plm_instruments WHERE name LIKE '测试-%'"))
cli.close(); print("\n=== DONE ===")
