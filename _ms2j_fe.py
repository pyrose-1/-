# -*- coding: utf-8 -*-
import os,sys,json,base64
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W="/www/wwwroot/plm-web"; SITE="/www/wwwroot/lab.dhupi.cn"
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
print("=== SSH OK ===")
def run(c,t=300):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace").rstrip(),e.read().decode("utf-8","replace").rstrip()
def step(t,c,to=300):
    o,e=run(c,to); print("\n#### %s"%t); print(o[-1800:])
    if e: print("[stderr]",e[-700:])
def pyedit(path,reps):
    b=base64.b64encode(json.dumps(reps,ensure_ascii=False).encode()).decode()
    o,e=run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:70])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit",path.replace(W,""),o.strip(),e[-200:])

pyedit(W+"/src/pages/Borrow.tsx",[
  ["""<div><Label>存放位置</Label><Input value={fLoc} onChange={(e) => setFLoc(e.target.value)} placeholder="放回处 / 你的工位" /></div>""",
   """<div><Label>存放位置</Label><Input value={fLoc} onChange={(e) => setFLoc(e.target.value)} placeholder="你找到它的地方或填没找到" /></div>"""],
])
step("构建前端",PATHX+"cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -6"%W,420)
step("部署","rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed"%(SITE,SITE,W,SITE,SITE))
step("自检 首页JS","curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
