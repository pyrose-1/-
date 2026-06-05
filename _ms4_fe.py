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
def run(cmd, t=420):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def step(t, c, to=420):
    o, e = run(c, to); print("\n#### %s"%t); print(o[-1600:])
    if e: print("[stderr]", e[-600:])
def wfile(path, content):
    b = base64.b64encode(content.encode()).decode()
    o,e=run("mkdir -p $(dirname %s) && python3 - <<'PY'\nimport base64\nopen(%r,'w',encoding='utf-8').write(base64.b64decode('%s').decode())\nprint('w ok')\nPY"%(path,path,b))
    print("  写", path.replace(W,""), o.strip(), e[-150:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:70])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit", path.split('/')[-1], o.strip(), e[-200:])

# 恢复验证时改动的学生真实资料
step("恢复学生1225071资料", "mysql -uplm -ppni38AWG4xy6wEyc plm -e \"UPDATE plm_users SET phone='17864296227', tutorId=10, email=NULL WHERE username='1225071'\" 2>/dev/null; echo done")

# ---- MyProfile.tsx ----
wfile(W + "/src/pages/MyProfile.tsx", """import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

export default function MyProfile() {
  const { fetchMe } = useAuth()
  const [me, setMe] = useState<any>(null)
  const [tutors, setTutors] = useState<{ id: number; name: string }[]>([])
  const [f, setF] = useState({ name: '', phone: '', email: '', tutorId: '' })
  const [msg, setMsg] = useState('')
  async function load() {
    const m: any = await http.get('/users/me'); setMe(m)
    setF({ name: m.name || '', phone: m.phone || '', email: m.email || '', tutorId: m.tutorId ? String(m.tutorId) : '' })
    const ts: any = await http.get('/users/tutors'); setTutors(ts)
  }
  useEffect(() => { load() }, [])
  async function save() {
    setMsg('')
    try { await http.post('/users/me', { name: f.name, phone: f.phone, email: f.email, tutorId: f.tutorId || null }); setMsg('\\u2705 \\u5df2\\u4fdd\\u5b58'); fetchMe().catch(() => {}); load() }
    catch (e: any) { setMsg('\\u2716 ' + e.message) }
  }
  if (!me) return <Card><CardContent className="py-10 text-center text-muted-foreground">\\u52a0\\u8f7d\\u4e2d\\u2026</CardContent></Card>
  return (
    <Card className="max-w-lg">
      <CardHeader><CardTitle>\\u6211\\u7684\\u4fe1\\u606f</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div><Label className="text-xs text-muted-foreground">\\u8d26\\u53f7\\uff08\\u5b66\\u53f7/\\u624b\\u673a\\uff0c\\u4e0d\\u53ef\\u6539\\uff09</Label><Input disabled value={me.username} className="h-9" /></div>
        <div><Label className="text-xs">\\u59d3\\u540d</Label><Input className="h-9" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div><Label className="text-xs">\\u624b\\u673a\\u53f7</Label><Input className="h-9" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="\\u7528\\u4e8e\\u8054\\u7cfb" /></div>
        <div><Label className="text-xs">\\u90ae\\u7bb1</Label><Input className="h-9" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="\\u7528\\u4e8e\\u63a5\\u6536\\u6bcf\\u5468\\u4eea\\u5668\\u6392\\u73ed\\u4e0e\\u65e5\\u7a0b\\u63d0\\u9192" /></div>
        <div>
          <Label className="text-xs">\\u5bfc\\u5e08</Label>
          <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={f.tutorId} onChange={(e) => setF({ ...f, tutorId: e.target.value })}>
            <option value="">\\u8bf7\\u9009\\u62e9\\u5bfc\\u5e08</option>
            {tutors.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-3"><Button onClick={save}>\\u4fdd\\u5b58</Button>{msg && <span className="text-sm text-accent">{msg}</span>}</div>
      </CardContent>
    </Card>
  )
}
""")

# ---- Overview.tsx ----
wfile(W + "/src/pages/Overview.tsx", """import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function barColor(r: number) { return r >= 90 ? 'bg-red-500' : r >= 70 ? 'bg-amber-500' : 'bg-emerald-500' }
export default function Overview() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { http.get('/instruments/overview').then((x: any) => setD(x)) }, [])
  if (!d) return <Card><CardContent className="py-10 text-center text-muted-foreground">\\u52a0\\u8f7d\\u4e2d\\u2026</CardContent></Card>
  const t = d.tightness
  const lvColor = t.score >= 6 ? 'bg-red-100 text-red-700' : t.score >= 4 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700'
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">\\u672c\\u5468\\uff08{d.cycleKey} \\u8d77\\uff09\\u5b9e\\u9a8c\\u5ba4\\u8fd0\\u884c\\u603b\\u89c8</p>
      <Card>
        <CardHeader className="pb-2"><CardTitle>\\u672c\\u5468\\u4eea\\u5668\\u9884\\u7ea6\\u7387</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {d.util.map((u: any) => (
            <div key={u.key}>
              <div className="mb-1 flex justify-between text-sm"><span className="text-foreground">{u.label}</span><span className="text-muted-foreground">{u.rate}% <span className="opacity-70">({u.used}/{u.cap})</span></span></div>
              <div className="h-2 w-full rounded bg-muted"><div className={'h-2 rounded ' + barColor(u.rate)} style={{ width: Math.min(u.rate, 100) + '%' }} /></div>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2"><CardTitle>\\u4e0a\\u5468\\u836f\\u54c1\\u7533\\u8d2d\\u603b\\u91d1\\u989d</CardTitle></CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-primary">\\u00a5{Number(d.lastWeekPurchase.amount).toLocaleString()}</div>
          <div className="mt-1 text-sm text-muted-foreground">{d.lastWeekPurchase.from} ~ {d.lastWeekPurchase.to} \\u00b7 \\u5ba1\\u6279\\u901a\\u8fc7 {d.lastWeekPurchase.count} \\u5355</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2"><CardTitle>\\u672c\\u5468\\u4eea\\u5668\\u7d27\\u4fcf\\u7a0b\\u5ea6</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-bold text-foreground">{t.score}</span><span className="text-lg text-muted-foreground">/ 10</span>
            <span className={'rounded px-2 py-0.5 text-sm ' + lvColor}>{t.level}</span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">\\u7d27\\u4fcf\\u5ea6 = \\u672c\\u5468\\u603b\\u9700\\u6c42\\u683c\\u5b50\\u6570 {t.totalDemand} \\u00f7 \\u53ef\\u7ea6\\u683c\\u5b50\\u6570 {t.totalCap}\\uff0c\\u6309\\u5404\\u4eea\\u5668\\u6298\\u7b97\\uff080~10\\u5206\\uff0c\\u8d8a\\u9ad8\\u8d8a\\u7d27\\u5f20\\uff09\\u3002</p>
          <div className="mt-3 space-y-1">
            {t.cats.map((c: any) => (
              <div key={c.key} className="flex items-center justify-between text-sm">
                <span className="text-foreground">{c.label}</span>
                <span className="text-muted-foreground">\\u9700\\u6c42 {c.demand} / \\u53ef\\u7ea6 {c.cap} \\u00b7 \\u7d27\\u4fcf\\u6bd4 <b className={c.ratio >= 1 ? 'text-red-600' : c.ratio >= 0.7 ? 'text-amber-600' : 'text-emerald-600'}>{Math.round(c.ratio * 100)}%</b></span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
""")

# ---- App.tsx routes ----
pyedit(W + "/src/App.tsx", [
  ["import MyInstruments from './pages/MyInstruments'",
   "import MyInstruments from './pages/MyInstruments'\nimport MyProfile from './pages/MyProfile'\nimport Overview from './pages/Overview'"],
  ["        <Route path=\"my-instruments\" element={<MyInstruments />} />",
   "        <Route path=\"my-instruments\" element={<MyInstruments />} />\n        <Route path=\"my-profile\" element={<MyProfile />} />\n        <Route path=\"overview\" element={<Overview />} />"],
])

# ---- MainLayout nav ----
pyedit(W + "/src/layouts/MainLayout.tsx", [
  ["            <NavLink to=\"/\" end className={linkCls}>工作台</NavLink>",
   "            <NavLink to=\"/\" end className={linkCls}>我的日程</NavLink>\n            <NavLink to=\"/overview\" className={linkCls}>实验室总览</NavLink>"],
  ["            {user?.role === 'STUDENT' && <NavLink to=\"/my-instruments\" className={linkCls}>我的仪器</NavLink>}",
   "            {user?.role === 'STUDENT' && <NavLink to=\"/my-instruments\" className={linkCls}>我的仪器</NavLink>}\n            {user?.role === 'STUDENT' && <NavLink to=\"/my-profile\" className={linkCls}>我的信息</NavLink>}"],
])

# ---- Instruments.tsx: 已预约/空闲中 ----
pyedit(W + "/src/pages/Instruments.tsx", [
  ["interface Inst { id: number; name: string; category: string; blockType: string; filmCapable: boolean; dryCapable: boolean; piggyback: boolean; lottery: boolean; authRequired: boolean; note: string | null; status: string }",
   "interface Inst { id: number; name: string; category: string; blockType: string; filmCapable: boolean; dryCapable: boolean; piggyback: boolean; lottery: boolean; authRequired: boolean; note: string | null; status: string; occupied?: boolean }"],
  ["                      <td className=\"py-2 pr-3 text-muted-foreground\">{x.status}</td>",
   "                      <td className=\"py-2 pr-3\"><span className={'rounded px-1.5 py-0.5 text-xs ' + (x.occupied ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700')}>{x.occupied ? '已预约' : '空闲中'}</span></td>"],
])

# ---- MyInstruments.tsx: 转赠自/蹭自 区分 ----
pyedit(W + "/src/pages/MyInstruments.tsx", [
  ["<span className={'rounded px-1.5 py-0.5 text-xs ' + (b.fromName ? 'bg-purple-100 text-purple-700' : b.source === 'CLAIM' ? 'bg-green-100 text-green-700' : 'bg-primary/10 text-primary')}>{b.fromName ? '来自' + b.fromName : b.source === 'CLAIM' ? '点击即得' : '抽签'}</span>",
   "<span className={'rounded px-1.5 py-0.5 text-xs ' + (b.fromName ? 'bg-amber-100 text-amber-800' : b.source === 'CLAIM' ? 'bg-green-100 text-green-700' : 'bg-primary/10 text-primary')}>{b.fromName ? '转赠自' + b.fromName : b.source === 'CLAIM' ? '点击即得' : '抽签'}</span>"],
  ["                  <td className=\"py-2 pr-3 text-muted-foreground\">{p.ownerName}</td>",
   "                  <td className=\"py-2 pr-3\"><span className=\"rounded bg-violet-100 px-1.5 py-0.5 text-xs text-violet-700\">蹭自{p.ownerName}</span></td>"],
  ["<td className=\"py-2 pr-3 text-muted-foreground\">{b.fromName ? '来自' + b.fromName : b.source === 'CLAIM' ? '点击即得' : '抽签'}</td>",
   "<td className=\"py-2 pr-3 text-muted-foreground\">{b.fromName ? '转赠自' + b.fromName : b.source === 'CLAIM' ? '点击即得' : '抽签'}</td>"],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8"%W, 480)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1"%(SITE,SITE,W,SITE,SITE))
cli.close(); print("\n=== DONE ===")
