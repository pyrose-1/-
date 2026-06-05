# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
def run(cmd, t=120):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def login(u, p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p))
    try: return json.loads(o).get("token")
    except: print("login fail", o[:200]); return None
TA="-H 'Authorization: Bearer %s'"%login("admin","Pniaef6b526!")
print("## 总览 overview")
o,_=run("curl -s 'http://127.0.0.1:3000/api/instruments/overview' %s | python3 -m json.tool"%TA); print(o[:1600])
print("\n## 发送测试邮件到 gmail (可能耗时)")
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/instruments/mail/test -H 'Content-Type: application/json' %s -d '{}'"%TA, 90); print("  ", o[:400])
# 学生资料更新
ts=login("1225071","Plm@2026"); TS="-H 'Authorization: Bearer %s'"%ts
print("\n## 学生 me（更新前）")
o,_=run("curl -s http://127.0.0.1:3000/api/users/me %s"%TS); print("  ", o[:300])
# 找一个导师id
tid,_=run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT id FROM plm_users WHERE role='TUTOR' LIMIT 1\" 2>/dev/null"); tid=tid.strip()
print("\n## 更新资料 phone/email/tutor=%s"%tid)
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/users/me -H 'Content-Type: application/json' %s -d '{\"phone\":\"13800001111\",\"email\":\"stu_test@example.com\",\"tutorId\":%s}'"%(TS,tid)); print("  ", o[:300])
print("\n## 仪器 live status 抽样")
o,_=run("curl -s http://127.0.0.1:3000/api/instruments %s | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(' ',x['name'][:20],x.get('occupied'),x.get('status')) for x in d[:5]]\""%TS); print(o)
cli.close()
