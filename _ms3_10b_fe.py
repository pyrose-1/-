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
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def step(t, c, to=420):
    o, e = run(c, to); print("\n#### %s" % t); print(o[-1500:])
    if e: print("[stderr]", e[-700:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

MS = W + "/src/pages/MyStudents.tsx"
pyedit(MS, [
  # helpers
  ["import { Button } from '@/components/ui/button'",
   """import { Button } from '@/components/ui/button'
const WDX = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const TASKL: Record<string, string> = { FILM: '铺膜', DRY: '干燥', FULL_DAY: '全天', HALF_DAY: '半天', BLOCK: '' }
function addD(iso: string, n: number) { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function curMon() { const d = new Date(); d.setHours(0, 0, 0, 0); const wd = d.getDay(); d.setDate(d.getDate() + (wd === 0 ? -6 : 1 - wd)); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function locD(iso: string) { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }
function hmX(iso: string) { const d = new Date(iso); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0') }"""],
  # state
  ["  const [detail, setDetail] = useState<{ totalAmount: number; count: number; items: Item[] } | null>(null)",
   "  const [detail, setDetail] = useState<{ totalAmount: number; count: number; items: Item[] } | null>(null)\n  const [sched, setSched] = useState<any>(null)"],
  # open
  ["  async function open(s: Stu) { setSel(s); const d: any = await http.get('/inventory/student/' + s.id); setDetail(d) }",
   "  async function open(s: Stu) { setSel(s); const d: any = await http.get('/inventory/student/' + s.id); setDetail(d); http.get('/instruments/student-schedule/' + s.id + '?week=' + curMon()).then((x: any) => setSched(x)).catch(() => setSched(null)) }"],
  # back button reset
  ["onClick={() => { setSel(null); setDetail(null) }}",
   "onClick={() => { setSel(null); setDetail(null); setSched(null) }}"],
  # 替换占位卡
  ["""          <CardHeader><CardTitle>近期仪器预约记录</CardTitle></CardHeader>
          <CardContent className="py-6 text-sm text-muted-foreground">仪器预约模块开发中，稍后接入。</CardContent>""",
   """          <CardHeader className="pb-2"><CardTitle>{sel.name} 本周日程（{curMon()} 起 · 仪器预约 + 个人日程）</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            {!sched ? <p className="text-sm text-muted-foreground">加载中…</p> : (
              <div className="grid min-w-[840px] grid-cols-7 gap-1">
                {Array.from({ length: 7 }, (_, i) => {
                  const day = addD(curMon(), i)
                  const its: any[] = []
                  ;(sched.bookings || []).filter((b: any) => b.date === day).forEach((b: any) => its.push({ sort: b.startHour * 60, time: `${b.startHour}:00–${b.endHour}:00`, text: `${b.instrumentName} ${TASKL[b.taskType] || ''}`, k: 'bk' }))
                  ;(sched.events || []).filter((e: any) => locD(e.startAt) === day).forEach((e: any) => its.push({ sort: new Date(e.startAt).getHours() * 60, time: `${hmX(e.startAt)}–${hmX(e.endAt)}`, text: e.title + (e.location ? ` @${e.location}` : ''), k: 'ev' }))
                  its.sort((a, b) => a.sort - b.sort)
                  return <div key={day} className="min-h-20 rounded border border-border p-1"><div className="mb-1 text-xs font-medium text-muted-foreground">{WDX[i]} {day.slice(5)}</div>{its.map((x, j) => <div key={j} className={'mb-0.5 rounded px-1 py-0.5 text-xs ' + (x.k === 'bk' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}><span className="text-[10px] opacity-70">{x.time}</span> {x.text}</div>)}</div>
                })}
              </div>
            )}"""],
])
step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -6" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1" % (SITE, SITE, W, SITE, SITE))
cli.close(); print("\n=== DONE ===")
