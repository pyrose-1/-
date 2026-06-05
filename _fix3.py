import os,sys,json,base64
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
APP="/www/wwwroot/plm-server"; PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=300):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
reps=[
  ["await this.inst.save(rows.map((r) => this.inst.create(r)));","await this.inst.save(rows as any);"],
  ["if (add.length) { await this.prio.save(add.map((a) => this.prio.create(a))); console.log('[seed] priorities', add.length); }",
   "if (add.length) { await this.prio.save(add as any); console.log('[seed] priorities', add.length); }"],
  ["if (add.length) { await this.auth.save(add.map((a) => this.auth.create(a))); console.log('[seed] polyhead auth', add.length); }",
   "if (add.length) { await this.auth.save(add as any); console.log('[seed] polyhead auth', add.length); }"],
]
b=base64.b64encode(json.dumps(reps,ensure_ascii=False).encode()).decode()
o,e=run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/instruments/instruments.service.ts'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:40])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(APP,b))
print(o,e[-200:])
o,e=run(PATHX+"cd %s && npm run build 2>&1 | tail -5"%APP,400)
print(o[-400:], e[-200:])
o,_=run("pm2 restart plm-api >/dev/null 2>&1; sleep 2; echo restarted")
print(o)
cli.close()
