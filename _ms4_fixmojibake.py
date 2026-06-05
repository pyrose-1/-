# -*- coding: utf-8 -*-
import os, sys, base64
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
    try { await http.post('/users/me', { name: f.name, phone: f.phone, email: f.email, tutorId: f.tutorId || null }); setMsg('✅ 已保存'); fetchMe().catch(() => {}); load() }
    catch (e: any) { setMsg('✖ ' + e.message) }
  }
  if (!me) return <Card><CardContent className="py-10 text-center text-muted-foreground">加载中…</CardContent></Card>
  return (
    <Card className="max-w-lg">
      <CardHeader><CardTitle>我的信息</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div><Label className="text-xs text-muted-foreground">账号（学号/手机，不可改）</Label><Input disabled value={me.username} className="h-9" /></div>
        <div><Label className="text-xs">姓名</Label><Input className="h-9" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div><Label className="text-xs">手机号</Label><Input className="h-9" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="用于联系" /></div>
        <div><Label className="text-xs">邮箱</Label><Input className="h-9" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="用于接收每周仪器排班与日程提醒" /></div>
        <div>
          <Label className="text-xs">导师</Label>
          <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={f.tutorId} onChange={(e) => setF({ ...f, tutorId: e.target.value })}>
            <option value="">请选择导师</option>
            {tutors.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-3"><Button onClick={save}>保存</Button>{msg && <span className="text-sm text-accent">{msg}</span>}</div>
      </CardContent>
    </Card>
  )
}
""")

wfile(W + "/src/pages/Overview.tsx", """import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function barColor(r: number) { return r >= 90 ? 'bg-red-500' : r >= 70 ? 'bg-amber-500' : 'bg-emerald-500' }
export default function Overview() {
  const [d, setD] = useState<any>(null)
  useEffect(() => { http.get('/instruments/overview').then((x: any) => setD(x)) }, [])
  if (!d) return <Card><CardContent className="py-10 text-center text-muted-foreground">加载中…</CardContent></Card>
  const t = d.tightness
  const lvColor = t.score >= 6 ? 'bg-red-100 text-red-700' : t.score >= 4 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700'
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">本周（{d.cycleKey} 起）实验室运行总览</p>
      <Card>
        <CardHeader className="pb-2"><CardTitle>本周仪器预约率</CardTitle></CardHeader>
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
        <CardHeader className="pb-2"><CardTitle>上周药品申购总金额</CardTitle></CardHeader>
        <CardContent>
          <div className="text-3xl font-bold text-primary">¥{Number(d.lastWeekPurchase.amount).toLocaleString()}</div>
          <div className="mt-1 text-sm text-muted-foreground">{d.lastWeekPurchase.from} ~ {d.lastWeekPurchase.to} · 审批通过 {d.lastWeekPurchase.count} 单</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2"><CardTitle>本周仪器紧俏程度</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-bold text-foreground">{t.score}</span><span className="text-lg text-muted-foreground">/ 10</span>
            <span className={'rounded px-2 py-0.5 text-sm ' + lvColor}>{t.level}</span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">紧俏度 = 本周总需求格子数 {t.totalDemand} ÷ 可约格子数 {t.totalCap}，按各仪器折算（0~10 分，越高越紧张）。</p>
          <div className="mt-3 space-y-1">
            {t.cats.map((c: any) => (
              <div key={c.key} className="flex items-center justify-between text-sm">
                <span className="text-foreground">{c.label}</span>
                <span className="text-muted-foreground">需求 {c.demand} / 可约 {c.cap} · 紧俏比 <b className={c.ratio >= 1 ? 'text-red-600' : c.ratio >= 0.7 ? 'text-amber-600' : 'text-emerald-600'}>{Math.round(c.ratio * 100)}%</b></span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
""")

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -6"%W, 480)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1"%(SITE,SITE,W,SITE,SITE))
cli.close(); print("\n=== DONE ===")
