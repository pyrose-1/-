import os,sys,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=60):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"Pniaef6b526!\"}'")
tok=json.loads(o)["token"]
o,_=run("curl -s 'http://127.0.0.1:3000/api/instruments/lottery/result' -H 'Authorization: Bearer %s'"%tok)
d=json.loads(o)["items"]
print("共",len(d),"条，按时段抽样：")
for x in d:
    if x["taskType"] in ("FILM","DRY"):
        print("  %s %d:00-%d:00 %s [%s] %s"%(x["date"],x["startHour"],x["endHour"],x["instrumentName"][:20],x["taskType"],x["userName"]))
print("  --- 环化/机头/4h ---")
for x in d:
    if x["taskType"] in ("FULL_DAY","HALF_DAY"):
        print("  %s %d-%d %s [%s] %s 温%s"%(x["date"],x["startHour"],x["endHour"],x["instrumentName"][:16],x["taskType"],x["userName"],x.get("tempCeiling")))
cli.close()
