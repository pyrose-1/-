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
    o, e = run(c, to); print("\n#### %s" % t); print(o[-2000:])
    if e: print("[stderr]", e[-800:])
def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content)); print("  写", path.replace(W, ""))
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.replace(W, ""), o.strip(), e[-150:])

MYINST = r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface Bk { id: number; instrumentId: number; instrumentName: string; category: string; date: string; startHour: number; endHour: number; taskType: string; tempCeiling: number | null; source: string }
interface Pg { id: number; status: string; statusText: string; requesterName: string; ownerName: string; instrumentName: string; date: string | null; startHour: number | null; endHour: number | null; taskType: string | null }
const TASK: Record<string, string> = { FILM: '铺膜', DRY: '干燥', FULL_DAY: '全天', HALF_DAY: '半天', BLOCK: '占用' }
const sc: Record<string, string> = { PENDING: 'bg-amber-100 text-amber-800', APPROVED: 'bg-green-100 text-green-700', REJECTED: 'bg-red-100 text-red-700' }
function addDays(iso: string, n: number) { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10) }
function curMonday() { const d = new Date(); const wd = d.getDay(); d.setDate(d.getDate() + (wd === 0 ? -6 : 1 - wd)); return d.toISOString().slice(0, 10) }

function BkRow({ b, onCancel, onTransfer }: { b: Bk; onCancel: (b: Bk) => void; onTransfer: (b: Bk) => void }) {
  return (
    <tr className="border-b border-border/60">
      <td className="py-2 pr-3">{b.date} <span className="text-muted-foreground">{b.startHour}–{b.endHour}</span></td>
      <td className="py-2 pr-3">{b.instrumentName}</td>
      <td className="py-2 pr-3 text-muted-foreground">{TASK[b.taskType] || ''}{b.tempCeiling ? `·${b.tempCeiling}℃` : ''}</td>
      <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (b.source === 'CLAIM' ? 'bg-green-100 text-green-700' : 'bg-primary/10 text-primary')}>{b.source === 'CLAIM' ? '点击即得' : '抽签'}</span></td>
      <td className="py-2 pr-3">
        <div className="flex gap-1">
          <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => onCancel(b)}>取消</Button>
          <Button variant="outline" className="h-7 px-2 text-xs" onClick={() => onTransfer(b)}>转赠</Button>
        </div>
      </td>
    </tr>
  )
}
function BkTable({ rows, onCancel, onTransfer, empty }: any) {
  return (
    <table className="w-full text-sm">
      <thead><tr className="border-b border-border text-left text-muted-foreground">
        <th className="py-2 pr-3 font-medium">日期/时段</th><th className="py-2 pr-3 font-medium">仪器</th><th className="py-2 pr-3 font-medium">任务</th><th className="py-2 pr-3 font-medium">来源</th><th className="py-2 pr-3 font-medium">操作</th>
      </tr></thead>
      <tbody>
        {rows.map((b: Bk) => <BkRow key={b.id} b={b} onCancel={onCancel} onTransfer={onTransfer} />)}
        {rows.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-muted-foreground">{empty}</td></tr>}
      </tbody>
    </table>
  )
}

export default function MyInstruments() {
  const { user } = useAuth()
  const isStudent = user?.role === 'STUDENT'
  const mon0 = curMonday(); const mon1 = addDays(mon0, 7)
  const [wk0, setWk0] = useState<Bk[]>([]); const [wk1, setWk1] = useState<Bk[]>([])
  const [incoming, setIncoming] = useState<Pg[]>([]); const [mine, setMine] = useState<Pg[]>([])
  const [msg, setMsg] = useState('')
  // 过往查询
  const [showPast, setShowPast] = useState(false)
  const [pastWk, setPastWk] = useState(addDays(mon0, -7)); const [past, setPast] = useState<Bk[]>([])

  async function load() {
    setWk0(await http.get('/instruments/my-bookings?cycle=' + mon0) as any)
    setWk1(await http.get('/instruments/my-bookings?cycle=' + mon1) as any)
    setIncoming(await http.get('/instruments/piggyback/incoming') as any)
    setMine(await http.get('/instruments/piggyback/mine') as any)
  }
  useEffect(() => { load() }, [])
  async function loadPast(wk: string) { setPast(await http.get('/instruments/my-bookings?cycle=' + wk) as any) }
  useEffect(() => { if (showPast) loadPast(pastWk) }, [showPast, pastWk])

  async function cancel(b: Bk) {
    if (!window.confirm(`取消 ${b.date} ${b.startHour}–${b.endHour} 的 ${b.instrumentName}？提前72h取消可+1优先级。`)) return
    try { const r: any = await http.post('/instruments/booking/cancel/' + b.id, {}); setMsg(r.earlyBonus ? '✅ 已取消（提前取消，+1 优先级）' : '✅ 已取消'); load(); if (showPast) loadPast(pastWk) }
    catch (e: any) { setMsg('✖ ' + e.message) }
  }
  async function transfer(b: Bk) {
    const t = window.prompt(`把 ${b.date} ${b.startHour}–${b.endHour} 的 ${b.instrumentName} 转赠给（输入对方姓名或学号）：`, '')
    if (!t) return
    try { const r: any = await http.post('/instruments/booking/transfer/' + b.id, { target: t }); setMsg('✅ 已转赠给 ' + r.to); load() }
    catch (e: any) { setMsg('✖ ' + e.message) }
  }
  async function decide(p: Pg, ok: boolean) {
    try { await http.post(`/instruments/piggyback/${p.id}/${ok ? 'approve' : 'reject'}`, {}); load() }
    catch (e: any) { setMsg('✖ ' + e.message) }
  }

  if (!isStudent) return <Card><CardContent className="py-10 text-center text-muted-foreground">仅学生有个人仪器预约。</CardContent></Card>

  return (
    <div className="space-y-4">
      {msg && <div className="text-sm text-accent">{msg}</div>}

      <Card>
        <CardHeader><CardTitle>本周我的预约（{mon0} ~ {addDays(mon0, 6)}）</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto"><BkTable rows={wk0} onCancel={cancel} onTransfer={transfer} empty="本周无预约" /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>下周我的预约（{mon1} ~ {addDays(mon1, 6)}）</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto"><BkTable rows={wk1} onCancel={cancel} onTransfer={transfer} empty="下周无预约" /></CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>蹭一蹭申请（别人想蹭我的预约 · {incoming.filter((p) => p.status === 'PENDING').length} 待处理）</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2 pr-3 font-medium">申请人</th><th className="py-2 pr-3 font-medium">仪器/时段</th><th className="py-2 pr-3 font-medium">状态</th><th className="py-2 pr-3 font-medium">操作</th></tr></thead>
            <tbody>
              {incoming.map((p) => (
                <tr key={p.id} className="border-b border-border/60">
                  <td className="py-2 pr-3 font-medium text-foreground">{p.requesterName}</td>
                  <td className="py-2 pr-3">{p.instrumentName}<div className="text-xs text-muted-foreground">{p.date} {p.startHour}–{p.endHour}</div></td>
                  <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (sc[p.status] || '')}>{p.statusText}</span></td>
                  <td className="py-2 pr-3">{p.status === 'PENDING' ? <div className="flex gap-1"><Button className="h-7 px-2 text-xs" onClick={() => decide(p, true)}>通过</Button><Button variant="destructive" className="h-7 px-2 text-xs" onClick={() => decide(p, false)}>拒绝</Button></div> : <span className="text-xs text-muted-foreground">—</span>}</td>
                </tr>
              ))}
              {incoming.length === 0 && <tr><td colSpan={4} className="py-4 text-center text-muted-foreground">暂无</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>我蹭到的（{mine.filter((p) => p.status === 'APPROVED').length} 已同意）</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2 pr-3 font-medium">仪器/时段</th><th className="py-2 pr-3 font-medium">原预约人</th><th className="py-2 pr-3 font-medium">状态</th></tr></thead>
            <tbody>
              {mine.map((p) => (
                <tr key={p.id} className="border-b border-border/60">
                  <td className="py-2 pr-3">{p.instrumentName}<div className="text-xs text-muted-foreground">{p.date} {p.startHour}–{p.endHour}</div></td>
                  <td className="py-2 pr-3 text-muted-foreground">{p.ownerName}</td>
                  <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (sc[p.status] || '')}>{p.statusText}</span></td>
                </tr>
              ))}
              {mine.length === 0 && <tr><td colSpan={3} className="py-4 text-center text-muted-foreground">还没有蹭一下申请（在排班表点别人预约上的「蹭」发起）</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle><button className="text-primary" onClick={() => setShowPast(!showPast)}>{showPast ? '▾' : '▸'} 过往预约查询</button></CardTitle></CardHeader>
        {showPast && (
          <CardContent className="overflow-x-auto">
            <div className="mb-2 flex items-center gap-2 text-sm">
              <Button variant="outline" className="h-8 px-2" onClick={() => setPastWk(addDays(pastWk, -7))}>← 上一周</Button>
              <span className="font-medium">{pastWk} ~ {addDays(pastWk, 6)}</span>
              <Button variant="outline" className="h-8 px-2" onClick={() => setPastWk(addDays(pastWk, 7))}>下一周 →</Button>
            </div>
            <table className="w-full text-sm">
              <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-2 pr-3 font-medium">日期/时段</th><th className="py-2 pr-3 font-medium">仪器</th><th className="py-2 pr-3 font-medium">任务</th><th className="py-2 pr-3 font-medium">来源</th></tr></thead>
              <tbody>
                {past.map((b) => <tr key={b.id} className="border-b border-border/60"><td className="py-2 pr-3">{b.date} {b.startHour}–{b.endHour}</td><td className="py-2 pr-3">{b.instrumentName}</td><td className="py-2 pr-3 text-muted-foreground">{TASK[b.taskType] || ''}</td><td className="py-2 pr-3 text-muted-foreground">{b.source === 'CLAIM' ? '点击即得' : '抽签'}</td></tr>)}
                {past.length === 0 && <tr><td colSpan={4} className="py-4 text-center text-muted-foreground">该周无预约</td></tr>}
              </tbody>
            </table>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
"""
wfile(W + "/src/pages/MyInstruments.tsx", MYINST)

# 排班表加 蹭 按钮
pyedit(W + "/src/pages/Schedule.tsx", [
  ["interface Inst { id: number; name: string; category: string; blockType: string }",
   "interface Inst { id: number; name: string; category: string; blockType: string; piggyback?: boolean }"],
  ["""  async function release(b: Bk) {
    if (!window.confirm('取消你这条预约？')) return
    try { await http.delete('/instruments/booking/claim/' + b.id); loadBks(week) } catch (e: any) { setMsg('✖ ' + e.message) }
  }""",
   """  async function release(b: Bk) {
    if (!window.confirm('取消你这条预约？')) return
    try { await http.delete('/instruments/booking/claim/' + b.id); loadBks(week) } catch (e: any) { setMsg('✖ ' + e.message) }
  }
  async function piggyback(bookingId: number) {
    setMsg('')
    try { await http.post('/instruments/piggyback', { bookingId }); setMsg('✅ 已申请蹭一下，等对方在「我的仪器」通过') } catch (e: any) { setMsg('✖ ' + e.message) }
  }"""],
  ["""            {b.source === 'CLAIM' && b.userId === myId && <button onClick={() => release(b)} className="ml-1 text-red-500">✖</button>}
          </div>""",
   """            {b.source === 'CLAIM' && b.userId === myId && <button onClick={() => release(b)} className="ml-1 text-red-500">✖</button>}
            {inst.piggyback && isStudent && b.userId !== myId && <button onClick={() => piggyback(b.id)} className="ml-1 rounded bg-amber-200 px-1 text-amber-900">蹭</button>}
          </div>"""],
])

# 路由 + 导航
pyedit(W + "/src/App.tsx", [
  ["import Schedule from './pages/Schedule'",
   "import Schedule from './pages/Schedule'\nimport MyInstruments from './pages/MyInstruments'"],
  ["""        <Route path=\"schedule\" element={<Schedule />} />""",
   """        <Route path=\"schedule\" element={<Schedule />} />
        <Route path=\"my-instruments\" element={<MyInstruments />} />"""],
])
pyedit(W + "/src/layouts/MainLayout.tsx", [
  ["""            <NavLink to=\"/schedule\" className={linkCls}>仪器排班表</NavLink>""",
   """            <NavLink to=\"/schedule\" className={linkCls}>仪器排班表</NavLink>
            {user?.role === 'STUDENT' && <NavLink to=\"/my-instruments\" className={linkCls}>我的仪器</NavLink>}"""],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
