# -*- coding: utf-8 -*-
import os, sys
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

SCHED = r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface Inst { id: number; name: string; category: string; blockType: string }
interface Bk { id: number; instrumentId: number; userId: number; userName: string; date: string; startHour: number; endHour: number; taskType: string; tempCeiling: number | null; source: string }
const CATORD = [['VACUUM_OVEN', '真空烘箱'], ['FURNACE', '环化/马弗/管式/BET'], ['POLY_HEAD', '聚合机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]
const WD = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const TASK: Record<string, string> = { FILM: '铺膜', DRY: '干燥', FULL_DAY: '全天', HALF_DAY: '半天', BLOCK: '占用' }
const LAYOUT: Record<string, number[][]> = { FOUR_HOUR: [[8, 12], [12, 16], [16, 20], [20, 24]], HALF_DAY: [[8, 16], [16, 24]], FULL_DAY: [[8, 24]] }
function addDays(iso: string, n: number) { const d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10) }
function curMonday() { const d = new Date(); const wd = d.getDay(); d.setDate(d.getDate() + (wd === 0 ? -6 : 1 - wd)); return d.toISOString().slice(0, 10) }

export default function Schedule() {
  const { user } = useAuth()
  const isStudent = user?.role === 'STUDENT'
  const isAdmin = user?.role === 'ADMIN'
  const myId = (user as any)?.id as number
  const today0 = curMonday()
  const maxStu = addDays(today0, 7)

  const [insts, setInsts] = useState<Inst[]>([])
  const [myHeads, setMyHeads] = useState<number[]>([])
  const [week, setWeek] = useState('')
  const [cat, setCat] = useState('VACUUM_OVEN')
  const [bks, setBks] = useState<Bk[]>([])
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    http.get('/instruments').then((d: any) => setInsts(d))
    http.get('/instruments/my-heads').then((d: any) => setMyHeads(d.map((x: Inst) => x.id))).catch(() => {})
    if (isStudent) setWeek(today0)
    else http.get('/instruments/booking/cycle').then((c: any) => setWeek(c.cycleKey || today0))
  }, [])
  async function loadBks(wk: string) { if (!wk) return; const d: any = await http.get('/instruments/lottery/result?cycle=' + wk); setBks(d.items || []) }
  useEffect(() => { loadBks(week) }, [week])

  const prevDisabled = isStudent && week <= today0
  const nextDisabled = isStudent && week >= maxStu
  function go(delta: number) { const w = addDays(week, delta); if (isStudent && (w < today0 || w > maxStu)) return; setWeek(w); setMsg('') }

  async function runLottery() {
    if (!window.confirm('对本周(' + week + ')运行抽签分配？')) return
    setBusy(true)
    try { const r: any = await http.post('/instruments/lottery/run', { cycle: week }); setMsg('✅ 抽签完成，生成 ' + r.bookings + ' 条' + (r.settled ? '（已结算优先级）' : '（重排）')); loadBks(week) }
    catch (e: any) { setMsg('✖ ' + e.message) } finally { setBusy(false) }
  }
  async function claim(inst: Inst, date: string, s: number, e: number) {
    setMsg('')
    try { await http.post('/instruments/booking/claim', { instrumentId: inst.id, date, startHour: s, endHour: e }); loadBks(week) }
    catch (err: any) { setMsg('✖ ' + err.message) }
  }
  async function release(b: Bk) {
    if (!window.confirm('取消你这条预约？')) return
    try { await http.delete('/instruments/booking/claim/' + b.id); loadBks(week) } catch (e: any) { setMsg('✖ ' + e.message) }
  }

  const days = week ? Array.from({ length: 7 }, (_, i) => addDays(week, i)) : []
  const catInsts = insts.filter((i) => i.category === cat)

  function Cell({ inst, date }: { inst: Inst; date: string }) {
    const dayBks = bks.filter((b) => b.instrumentId === inst.id && b.date === date)
    const lay = LAYOUT[inst.blockType] || LAYOUT.FOUR_HOUR
    const canClaim = isStudent && (inst.category !== 'POLY_HEAD' || myHeads.includes(inst.id))
    let any = false
    const rows = lay.map(([s, e]) => {
      const b = dayBks.find((x) => x.startHour === s)
      if (b) {
        any = true
        return (
          <div key={s} className={'mb-0.5 rounded px-1 py-0.5 text-xs ' + (b.source === 'CLAIM' ? 'bg-green-100 text-green-800' : 'bg-primary/10 text-primary')}>
            {b.startHour}–{b.endHour} {TASK[b.taskType] || ''}·{b.userName}{b.tempCeiling ? `(${b.tempCeiling}℃)` : ''}
            {b.source === 'CLAIM' && b.userId === myId && <button onClick={() => release(b)} className="ml-1 text-red-500">✖</button>}
          </div>
        )
      }
      const covered = dayBks.some((x) => x.startHour < e && s < x.endHour)
      if (covered) return null
      if (canClaim) { any = true; return <button key={s} onClick={() => claim(inst, date, s, e)} className="mb-0.5 block w-full rounded border border-dashed border-accent/60 px-1 text-left text-xs text-accent hover:bg-accent/10">可约 {s}–{e}</button> }
      return null
    })
    return <td className="border border-border p-1 align-top">{rows}{!any && <span className="text-xs text-muted-foreground">—</span>}</td>
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 py-3 text-sm">
          <Button variant="outline" className="h-8 px-2" disabled={prevDisabled} onClick={() => go(-7)}>← 上一周</Button>
          <span className="font-medium text-foreground">{week} ~ {week && addDays(week, 6)}{week === today0 ? '（本周）' : week === maxStu ? '（下周）' : ''}</span>
          <Button variant="outline" className="h-8 px-2" disabled={nextDisabled} onClick={() => go(7)}>下一周 →</Button>
          <Button variant="outline" className="h-8 px-2" onClick={() => { setWeek(today0); setMsg('') }}>回到本周</Button>
          {isAdmin && <Button variant="accent" className="h-8" disabled={busy} onClick={runLottery}>对本周运行抽签</Button>}
          <span className="text-muted-foreground">蓝=抽签 · 绿=点击即得</span>
          {isStudent && <span className="text-muted-foreground">（学生仅可查看本周与下周）</span>}
          {msg && <span className="text-accent">{msg}</span>}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        {CATORD.map(([k, t]) => (
          <button key={k} onClick={() => setCat(k)} className={'rounded-md px-3 py-1 text-sm ' + (cat === k ? 'bg-primary text-primary-foreground' : 'bg-card border border-border text-foreground')}>{t}</button>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>仪器排班表 · {CATORD.find((c) => c[0] === cat)?.[1]}（{catInsts.length} 台）</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          {isStudent && cat === 'POLY_HEAD' && <p className="mb-2 text-xs text-muted-foreground">只能预约你被授权的机头（其余仅可查看）。</p>}
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border border-border bg-primary px-2 py-1 text-left text-primary-foreground">仪器</th>
                {days.map((d, i) => <th key={d} className="border border-border bg-primary px-2 py-1 text-left text-primary-foreground">{WD[i]}<br />{d.slice(5)}</th>)}
              </tr>
            </thead>
            <tbody>
              {catInsts.map((inst) => (
                <tr key={inst.id}>
                  <td className="border border-border bg-primary/5 px-2 py-1 align-top text-xs font-medium text-primary">{inst.name}</td>
                  {days.map((d) => <Cell key={d} inst={inst} date={d} />)}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
"""
wfile(W + "/src/pages/Schedule.tsx", SCHED)
step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
