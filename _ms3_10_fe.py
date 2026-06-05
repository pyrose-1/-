# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"; SITE = "/www/wwwroot/lab.dhupi.cn"; DBP = "pni38AWG4xy6wEyc"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def sql(q): out, _ = run("mysql -uplm -p%s plm -N -e \"%s\" 2>/dev/null" % (DBP, q)); return out
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t); print(o[-1800:])
    if e: print("[stderr]", e[-700:])
def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content)); print("  写", path.replace(W, ""))
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

# 师生关系：学生轮流分给7位老师
tea = [int(x) for x in sql("SELECT id FROM plm_users WHERE role='TUTOR' AND username REGEXP '^[0-9]+$' ORDER BY id").split()]
stu = [int(x) for x in sql("SELECT id FROM plm_users WHERE role='STUDENT' ORDER BY id").split()]
if tea and stu:
    buckets = {t: [] for t in tea}
    for i, s in enumerate(stu): buckets[tea[i % len(tea)]].append(s)
    for t, ids in buckets.items():
        if ids: sql("UPDATE plm_users SET tutorId=%d WHERE id IN (%s)" % (t, ",".join(map(str, ids))))
    print("已分配师生：%d 师 / %d 生" % (len(tea), len(stu)))

# ---- Schedule：过期灰显 + 蹭确认 ----
pyedit(W + "/src/pages/Schedule.tsx", [
  ["""  async function piggyback(bookingId: number) {""",
   """  const [piggConfirm, setPiggConfirm] = useState<number | null>(null)
  async function piggyback(bookingId: number) {"""],
  ["""      if (canClaim) { any = true; return <button key={s} onClick={() => claim(inst, date, s, e)} className="mb-0.5 block w-full rounded border border-dashed border-accent/60 px-1 text-left text-xs text-accent hover:bg-accent/10">可约 {s}–{e}</button> }""",
   """      if (canClaim) {
        any = true
        const past = new Date(date + 'T' + String(s).padStart(2, '0') + ':00:00').getTime() < Date.now()
        return past
          ? <div key={s} className="mb-0.5 px-1 text-xs text-muted-foreground/70">已过期 {s}–{e}</div>
          : <button key={s} onClick={() => claim(inst, date, s, e)} className="mb-0.5 block w-full rounded border border-dashed border-accent/60 px-1 text-left text-xs text-accent hover:bg-accent/10">可约 {s}–{e}</button>
      }"""],
  ["""            {inst.piggyback && isStudent && b.userId !== myId && <button onClick={() => piggyback(b.id)} className="ml-1 rounded bg-amber-200 px-1 text-amber-900">蹭</button>}""",
   """            {inst.piggyback && isStudent && b.userId !== myId && (piggConfirm === b.id
              ? <span className="ml-1 whitespace-nowrap"><button onClick={() => { piggyback(b.id); setPiggConfirm(null) }} className="rounded bg-green-600 px-1 text-white">确定</button><button onClick={() => setPiggConfirm(null)} className="ml-0.5 rounded bg-slate-300 px-1">取消</button></span>
              : <button onClick={() => setPiggConfirm(b.id)} className="ml-1 rounded bg-amber-200 px-1 text-amber-900">蹭</button>)}"""],
])

# ---- MyInstruments：我蹭到的 加 取消 ----
pyedit(W + "/src/pages/MyInstruments.tsx", [
  ["""  async function decide(p: Pg, ok: boolean) {""",
   """  async function cancelPigg(p: Pg) { if (!window.confirm('取消该蹭一下？')) return; try { await http.post(`/instruments/piggyback/${p.id}/cancel`, {}); load() } catch (e: any) { setMsg('✖ ' + e.message) } }
  async function decide(p: Pg, ok: boolean) {"""],
  ["""            <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2 pr-3 font-medium">仪器/时段</th><th className="py-2 pr-3 font-medium">原预约人</th><th className="py-2 pr-3 font-medium">状态</th></tr></thead>
            <tbody>
              {mine.map((p) => (
                <tr key={p.id} className="border-b border-border/60">
                  <td className="py-2 pr-3">{p.instrumentName}<div className="text-xs text-muted-foreground">{p.date} {p.startHour}–{p.endHour}</div></td>
                  <td className="py-2 pr-3 text-muted-foreground">{p.ownerName}</td>
                  <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (sc[p.status] || '')}>{p.statusText}</span></td>
                </tr>
              ))}
              {mine.length === 0 && <tr><td colSpan={3} className="py-4 text-center text-muted-foreground">还没有蹭一下申请（在排班表点别人预约上的「蹭」发起）</td></tr>}""",
   """            <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2 pr-3 font-medium">仪器/时段</th><th className="py-2 pr-3 font-medium">原预约人</th><th className="py-2 pr-3 font-medium">状态</th><th className="py-2 pr-3 font-medium">操作</th></tr></thead>
            <tbody>
              {mine.map((p) => (
                <tr key={p.id} className="border-b border-border/60">
                  <td className="py-2 pr-3">{p.instrumentName}<div className="text-xs text-muted-foreground">{p.date} {p.startHour}–{p.endHour}</div></td>
                  <td className="py-2 pr-3 text-muted-foreground">{p.ownerName}</td>
                  <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (sc[p.status] || '')}>{p.statusText}</span></td>
                  <td className="py-2 pr-3">{(p.status === 'PENDING' || p.status === 'APPROVED') ? <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => cancelPigg(p)}>取消</Button> : <span className="text-xs text-muted-foreground">—</span>}</td>
                </tr>
              ))}
              {mine.length === 0 && <tr><td colSpan={4} className="py-4 text-center text-muted-foreground">还没有蹭一下申请（在排班表点别人预约上的「蹭」发起）</td></tr>"""],
])
# sc 颜色加 CANCELLED
pyedit(W + "/src/pages/MyInstruments.tsx", [
  ["const sc: Record<string, string> = { PENDING: 'bg-amber-100 text-amber-800', APPROVED: 'bg-green-100 text-green-700', REJECTED: 'bg-red-100 text-red-700' }",
   "const sc: Record<string, string> = { PENDING: 'bg-amber-100 text-amber-800', APPROVED: 'bg-green-100 text-green-700', REJECTED: 'bg-red-100 text-red-700', CANCELLED: 'bg-slate-100 text-slate-500' }"],
])

# ---- Dashboard 重写：学生日历 ----
DASH = r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

const WD = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const TASK: Record<string, string> = { FILM: '铺膜', DRY: '干燥', FULL_DAY: '全天', HALF_DAY: '半天', BLOCK: '' }
function addDays(iso: string, n: number) { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function curMonday() { const d = new Date(); d.setHours(0, 0, 0, 0); const wd = d.getDay(); d.setDate(d.getDate() + (wd === 0 ? -6 : 1 - wd)); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function localDate(iso: string) { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function hm(iso: string) { const d = new Date(iso); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') }

interface Item { date: string; sort: number; time: string; text: string; kind: 'bk' | 'ev'; id?: number }

export default function Dashboard() {
  const { user } = useAuth()
  if (user?.role !== 'STUDENT') {
    return <Card><CardHeader><CardTitle>工作台</CardTitle></CardHeader><CardContent className="py-6 text-sm text-muted-foreground">欢迎，{user?.name}（{user?.role === 'ADMIN' ? '管理员' : '导师'}）。请使用左侧功能。导师可在「我的学生」查看学生库存与本周日程。</CardContent></Card>
  }
  const mon0 = curMonday(); const mon1 = addDays(mon0, 7)
  const [items, setItems] = useState<Item[]>([])
  const [showForm, setShowForm] = useState(false)
  const [f, setF] = useState({ title: '', location: '', startAt: '', endAt: '' })
  const [msg, setMsg] = useState('')

  async function load() {
    const out: Item[] = []
    for (const wk of [mon0, mon1]) {
      const bks: any = await http.get('/instruments/my-bookings?cycle=' + wk)
      for (const b of bks) out.push({ date: b.date, sort: b.startHour * 60, time: `${b.startHour}:00–${b.endHour}:00`, text: `${b.instrumentName} ${TASK[b.taskType] || ''}`, kind: 'bk' })
    }
    const evs: any = await http.get('/instruments/events?from=' + mon0 + '&to=' + addDays(mon1, 6))
    for (const e of evs) out.push({ date: localDate(e.startAt), sort: new Date(e.startAt).getHours() * 60 + new Date(e.startAt).getMinutes(), time: `${hm(e.startAt)}–${hm(e.endAt)}`, text: e.title + (e.location ? ` @${e.location}` : ''), kind: 'ev', id: e.id })
    setItems(out)
  }
  useEffect(() => { load() }, [])

  async function addEvent() {
    setMsg('')
    if (!f.title || !f.startAt) { setMsg('请填写事项与开始时间'); return }
    try { await http.post('/instruments/events', f); setShowForm(false); setF({ title: '', location: '', startAt: '', endAt: '' }); load() }
    catch (e: any) { setMsg('✖ ' + e.message) }
  }
  async function delEvent(id?: number) { if (!id) return; if (!window.confirm('删除该日程？')) return; await http.delete('/instruments/events/' + id); load() }

  function Week({ mon, label }: { mon: string; label: string }) {
    const days = Array.from({ length: 7 }, (_, i) => addDays(mon, i))
    return (
      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-base">{label}（{mon} ~ {addDays(mon, 6)}）</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <div className="grid min-w-[840px] grid-cols-7 gap-1">
            {days.map((d, i) => {
              const its = items.filter((x) => x.date === d).sort((a, b) => a.sort - b.sort)
              const isToday = d === curMonday() ? false : false
              return (
                <div key={d} className="min-h-24 rounded border border-border p-1">
                  <div className="mb-1 text-xs font-medium text-muted-foreground">{WD[i]} {d.slice(5)}</div>
                  {its.map((x, k) => (
                    <div key={k} className={'mb-0.5 rounded px-1 py-0.5 text-xs ' + (x.kind === 'bk' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>
                      <span className="text-[10px] opacity-70">{x.time}</span> {x.text}
                      {x.kind === 'ev' && <button onClick={() => delEvent(x.id)} className="ml-1 text-red-500">✖</button>}
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card><CardContent className="flex flex-wrap items-center gap-3 py-3 text-sm">
        <span className="font-medium text-foreground">我的日历 · 本周与下周</span>
        <span className="text-muted-foreground">蓝=仪器预约（来自抽签/点击即得）· 橙=个人日程（仅你与导师可见）</span>
        <Button variant="accent" className="h-8" onClick={() => setShowForm(!showForm)}>{showForm ? '收起' : '添加日程'}</Button>
        {msg && <span className="text-accent">{msg}</span>}
      </CardContent></Card>

      {showForm && (
        <Card><CardContent className="flex flex-wrap items-end gap-3 py-3">
          <div><Label className="text-xs">事项 *</Label><Input className="h-9 w-40" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="如 组会 / 测样" /></div>
          <div><Label className="text-xs">地点</Label><Input className="h-9 w-32" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} placeholder="如 A301" /></div>
          <div><Label className="text-xs">开始时间 *</Label><Input type="datetime-local" className="h-9 w-52" value={f.startAt} onChange={(e) => setF({ ...f, startAt: e.target.value, endAt: f.endAt || (e.target.value ? e.target.value.slice(0, 11) + String(Math.min(23, +e.target.value.slice(11, 13) + 1)).padStart(2, '0') + e.target.value.slice(13) : '') })} /></div>
          <div><Label className="text-xs">结束时间（默认+1h）</Label><Input type="datetime-local" className="h-9 w-52" value={f.endAt} onChange={(e) => setF({ ...f, endAt: e.target.value })} /></div>
          <Button onClick={addEvent}>确认添加</Button>
        </CardContent></Card>
      )}

      <Week mon={mon0} label="本周" />
      <Week mon={mon1} label="下周" />
    </div>
  )
}
"""
wfile(W + "/src/pages/Dashboard.tsx", DASH)

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
