# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"; SITE = "/www/wwwroot/lab.dhupi.cn"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t); print(o[-1800:])
    if e: print("[stderr]", e[-700:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

# Signup: 真空上限8 + 概率卡
pyedit(W + "/src/pages/Signup.tsx", [
  ["""  const [msg, setMsg] = useState('')""",
   """  const [msg, setMsg] = useState('')
  const [fc, setFc] = useState<Record<string, number> | null>(null)"""],
  ["""    http.get('/instruments/my-heads').then((d: any) => setHeads(d)).catch(() => {})
    loadMine()
  }, [])""",
   """    http.get('/instruments/my-heads').then((d: any) => setHeads(d)).catch(() => {})
    http.get('/instruments/forecast').then((d: any) => setFc(d)).catch(() => {})
    loadMine()
  }, [])"""],
  ["""      <VacCard d={dOf('VACUUM_OVEN')} insts={vac} onSave={save} onDel={del} />""",
   """      {fc && (
        <Card>
          <CardHeader><CardTitle>中签概率预估 · 至少约到 1 次（按当前优先级与已报名情况估算）</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span>真空·铺膜 <b className="text-primary">{fc.VACUUM_FILM}%</b></span>
            <span>真空·干燥 <b className="text-primary">{fc.VACUUM_DRY}%</b></span>
            <span>环化类 <b className="text-primary">{fc.FURNACE}%</b></span>
            <span>聚合机头 <b className="text-primary">{fc.POLY_HEAD}%</b></span>
            <span>DMA <b className="text-primary">{fc.DMA}%</b></span>
            <span>TGA <b className="text-primary">{fc.TGA}%</b></span>
          </CardContent>
        </Card>
      )}
      <VacCard d={dOf('VACUUM_OVEN')} insts={vac} onSave={save} onDel={del} />"""],
  ["<CardHeader><CardTitle>真空烘箱 <span className=\"text-sm font-normal text-muted-foreground\">· 铺膜=3格/次、干燥=1格/次 · 每周上限 6 格</span></CardTitle></CardHeader>",
   "<CardHeader><CardTitle>真空烘箱 <span className=\"text-sm font-normal text-muted-foreground\">· 铺膜=3格/次、干燥=1格/次 · 每周上限 8 格</span></CardTitle></CardHeader>"],
  ["onChange={(e) => setDry(+e.target.value)}>{range(0, 6).map((n) => <option key={n} value={n}>{n}</option>)}",
   "onChange={(e) => setDry(+e.target.value)}>{range(0, 8).map((n) => <option key={n} value={n}>{n}</option>)}"],
  ["<div className={'text-sm ' + (grids > 6 ? 'text-red-600' : 'text-muted-foreground')}>合计 {grids} / 6 格</div>",
   "<div className={'text-sm ' + (grids > 8 ? 'text-red-600' : 'text-muted-foreground')}>合计 {grids} / 8 格</div>"],
  ["<Button disabled={grids < 1 || grids > 6} onClick={() => onSave({ category: 'VACUUM_OVEN', filmCount: film, dryCount: dry, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>",
   "<Button disabled={grids < 1 || grids > 8} onClick={() => onSave({ category: 'VACUUM_OVEN', filmCount: film, dryCount: dry, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>"],
])

# Instruments 页 上限文案
pyedit(W + "/src/pages/Instruments.tsx", [
  ["VACUUM_OVEN: '每周 6 格（铺膜=3格 / 干燥=1格）'",
   "VACUUM_OVEN: '每周 8 格（铺膜=3格 / 干燥=1格）'"],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -6" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
