import os,sys,base64,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
W="/www/wwwroot/plm-web"; SITE="/www/wwwroot/lab.dhupi.cn"; PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=420):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
reps=[["还没有蹭一下申请（在排班表点别人预约上的「蹭」发起）</td></tr>\n            </tbody>",
       "还没有蹭一下申请（在排班表点别人预约上的「蹭」发起）</td></tr>}\n            </tbody>"]]
b=base64.b64encode(json.dumps(reps,ensure_ascii=False).encode()).decode()
o,e=run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/pages/MyInstruments.tsx'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,'MISS'\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('fixed')\nPYEOF"%(W,b))
print(o,e[-150:])
o,e=run(PATHX+"cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -5"%W,420); print(o[-300:],e[-150:])
o,_=run("rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1"%(SITE,SITE,W,SITE,SITE))
print("JS:",o)
cli.close()
