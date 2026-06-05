# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"; SITE = "/www/wwwroot/lab.dhupi.cn"; APP="/www/wwwroot/plm-server"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=480):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def step(t, c, to=480):
    o, e = run(c, to); print("\n#### %s"%t); print(o[-1200:])
    if e: print("[stderr]", e[-500:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:80])\n  s=s.replace(a,b,1)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit", path.split('/')[-1], o.strip(), e[-200:])

SC = W + "/src/pages/Schedule.tsx"
pyedit(SC, [
  # tabs: no italic, no ·记录
  ["className={'rounded-md px-3 py-1 text-sm ' + (cat === c.key ? 'bg-primary text-primary-foreground' : 'bg-card border border-border text-foreground') + (c.lottery ? '' : ' italic')}>{c.label}{c.lottery ? '' : '·记录'}</button>",
   "className={'rounded-md px-3 py-1 text-sm ' + (cat === c.key ? 'bg-primary text-primary-foreground' : 'bg-card border border-border text-foreground')}>{c.label}</button>"],
  # legend
  ["蓝=抽签 · 绿=点击即得 · 灰=使用记录", "蓝=抽签 · 绿=点击即得 · 灰=非抽签"],
  # title hint remove
  ["（{catInsts.length} 台）{recordMode && <span className=\"ml-2 text-sm font-normal text-muted-foreground\">使用记录表：点击「登记」记录使用情况</span>}</CardTitle>",
   "（{catInsts.length} 台）</CardTitle>"],
  # RECORD display: drop '使用'
  ["{b.startHour}–{b.endHour} {isRec ? '使用' : (TASK[b.taskType] || '')}·{b.userName}",
   "{b.startHour}–{b.endHour} {isRec ? '' : (TASK[b.taskType] || '')}·{b.userName}"],
  # non-lottery slot: past=登记 future=预约
  ["""      if (recordMode) {
        if (!user) return null
        any = true
        return <button key={s} onClick={() => claim(inst, date, s, e)} className="mb-0.5 block w-full rounded border border-dashed border-slate-400 px-1 text-left text-xs text-slate-600 hover:bg-slate-100">登记 {s}–{e}</button>
      }""",
   """      if (recordMode) {
        if (!user) return null
        any = true
        const rpast = new Date(date + 'T' + String(s).padStart(2, '0') + ':00:00').getTime() < Date.now()
        return <button key={s} onClick={() => claim(inst, date, s, e)} className="mb-0.5 block w-full rounded border border-dashed border-slate-400 px-1 text-left text-xs text-slate-600 hover:bg-slate-100">{rpast ? '登记' : '预约'} {s}–{e}</button>
      }"""],
])
step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -5"%W, 520)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1"%(SITE,SITE,W,SITE,SITE))

# ===== dump for import =====
step("plm_hazmat schema", "mysql -uplm -ppni38AWG4xy6wEyc plm -e 'DESCRIBE plm_hazmat' 2>/dev/null")
step("plm_hazmat sample", "mysql -uplm -ppni38AWG4xy6wEyc plm -e 'SELECT * FROM plm_hazmat LIMIT 3' 2>/dev/null")
step("users name->id,tutor", "mysql -uplm -ppni38AWG4xy6wEyc plm -e \"SELECT id,name,tutorId,role FROM plm_users\" 2>/dev/null")
step("chem counts", "mysql -uplm -ppni38AWG4xy6wEyc plm -e \"SELECT COUNT(*) chems FROM plm_chemicals; SELECT COUNT(*) reqs FROM plm_purchase_requests\" 2>/dev/null")
cli.close(); print("\n=== DONE ===")
