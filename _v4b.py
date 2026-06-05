import os,sys,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=60):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p)); return json.loads(o).get("token")
H="-H 'Authorization: Bearer %s'"%login("1225071","Plm@2026")
iid=run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT id FROM plm_instruments WHERE category='DMA' LIMIT 1\" 2>/dev/null")[0].strip()
o,_=run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/claim -H 'Content-Type: application/json' %s -d '{\"instrumentId\":%s,\"date\":\"2026-10-07\",\"startHour\":8,\"endHour\":12}'"%(H,iid))
print("点击即得(空周):",o[:120])
o,_=run("curl -s 'http://127.0.0.1:3000/api/instruments/lottery/result?cycle=2026-10-05' %s | python3 -c \"import sys,json;d=json.load(sys.stdin)['items'];[print(' ',x['date'],x['startHour'],x['instrumentName'][:18],x['userName'],x['source']) for x in d]\""%H)
print(o)
cli.close()
