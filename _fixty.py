import os,sys
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
APP="/www/wwwroot/plm-server"
PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=300):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
p=APP+"/src/purchases/purchases.service.ts"
o,e=run("python3 - <<'PYEOF'\n"
  "p=%r\n"
  "s=open(p,encoding='utf-8').read()\n"
  "a='async updateMyBatch(user: any, batchId: number, body: { location?: string; remainLevel?: string }) {'\n"
  "b='async updateMyBatch(user: any, batchId: number, body: { location?: string; remainLevel?: string; shareable?: boolean }) {'\n"
  "assert a in s; s=s.replace(a,b); open(p,'w',encoding='utf-8').write(s); print('ok')\n"
  "PYEOF"%p)
print(o,e[-200:])
o,e=run(PATHX+"cd %s && npm run build 2>&1 | tail -6"%APP,400)
print(o[-600:], e[-300:])
o,_=run("pm2 restart plm-api >/dev/null 2>&1; sleep 2; echo restarted; pm2 logs plm-api --lines 30 --nostream 2>&1 | grep -ciE 'error TS'")
print(o)
cli.close()
