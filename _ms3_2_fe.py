# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"; SITE = "/www/wwwroot/lab.dhupi.cn"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=300):
    out, err = run(cmd, t); print("\n#### %s" % title); print(out[-2000:])
    if err: print("[stderr]", err[-800:])

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(W, ""))

def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.replace(W, ""), o.strip(), e[-200:])

wfile(W + "/src/pages/Signup.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface Inst { id: number; name: string; category: string; filmCapable: boolean; dryCapable: boolean }
interface Demand { id: number; category: string; instrumentMode: string; instrumentIds: number[] | null; instrumentNames: string[]; filmCount: number; dryCount: number; blockCount: number; tempCeiling: number | null; gridsTotal: number }
const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i)

function InstPicker({ insts, sel, setSel }: { insts: Inst[]; sel: number[]; setSel: (v: number[]) => void }) {
  const [open, setOpen] = useState(false)
  function toggle(id: number) { setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]) }
  return (
    <div className="text-sm">
      <button type="button" className="text-primary underline" onClick={() => setOpen(!open)}>
        {sel.length ? `已指定 ${sel.length} 台（点开调整）` : '默认大类内任意（点开可指定具体仪器）'}
      </button>
      {open && (
        <div className="mt-1 max-h-40 overflow-y-auto rounded border border-border p-2">
          {insts.map((i) => (
            <label key={i.id} className="flex items-center gap-2 py-0.5">
              <input type="checkbox" checked={sel.includes(i.id)} onChange={() => toggle(i.id)} />
              <span>{i.name}</span>
              {i.filmCapable && <span className="rounded bg-blue-100 px-1 text-xs text-blue-700">铺膜</span>}
              {i.dryCapable && <span className="rounded bg-slate-100 px-1 text-xs text-slate-600">干燥</span>}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Signup() {
  const { user } = useAuth()
  const [cycle, setCycle] = useState<any>(null)
  const [mine, setMine] = useState<Demand[]>([])
  const [insts, setInsts] = useState<Inst[]>([])
  const [heads, setHeads] = useState<Inst[]>([])
  const [msg, setMsg] = useState('')

  async function loadMine() { setMine(await http.get('/instruments/booking/mine') as any) }
  useEffect(() => {
    http.get('/instruments/booking/cycle').then(setCycle)
    http.get('/instruments').then((d: any) => setInsts(d))
    http.get('/instruments/my-heads').then((d: any) => setHeads(d)).catch(() => {})
    loadMine()
  }, [])

  const dOf = (c: string) => mine.find((d) => d.category === c)
  async function save(body: any) {
    setMsg('')
    try { await http.post('/instruments/booking', body); setMsg('✅ 已保存报名'); loadMine() }
    catch (e: any) { setMsg('✖ ' + e.message) }
  }
  async function del(id: number) { await http.delete('/instruments/booking/' + id); loadMine() }

  if (user?.role !== 'STUDENT') return <Card><CardContent className="py-10 text-center text-muted-foreground">仅学生参与仪器预约报名。</CardContent></Card>

  const vac = insts.filter((i) => i.category === 'VACUUM_OVEN')
  const fur = insts.filter((i) => i.category === 'FURNACE')

  return (
    <div className="space-y-4">
      <Card><CardContent className="py-3 text-sm">
        <span className="font-medium text-foreground">本轮报名 → {cycle?.start} ~ {cycle?.end} 那周</span>
        <span className="ml-3 text-muted-foreground">报名截止 {cycle?.deadline} 24:00，周一闭站抽签。每类填写后点保存；可随时修改/删除。</span>
        {msg && <span className="ml-3 text-accent">{msg}</span>}
      </CardContent></Card>

      <VacCard d={dOf('VACUUM_OVEN')} insts={vac} onSave={save} onDel={del} />
      <FurCard d={dOf('FURNACE')} insts={fur} onSave={save} onDel={del} />
      <PolyCard d={dOf('POLY_HEAD')} heads={heads} onSave={save} onDel={del} />
      <BlockCard cat="DMA" label="DMA（4h 块，每周上限 4）" max={4} d={dOf('DMA')} onSave={save} onDel={del} />
      <BlockCard cat="TGA" label="TGA（4h 块，每周上限 4）" max={4} d={dOf('TGA')} onSave={save} onDel={del} />
    </div>
  )
}

function VacCard({ d, insts, onSave, onDel }: any) {
  const [film, setFilm] = useState(d?.filmCount ?? 0)
  const [dry, setDry] = useState(d?.dryCount ?? 0)
  const [sel, setSel] = useState<number[]>(d?.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : [])
  useEffect(() => { if (d) { setFilm(d.filmCount); setDry(d.dryCount); setSel(d.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : []) } }, [d?.id])
  const grids = film * 3 + dry
  return (
    <Card>
      <CardHeader><CardTitle>真空烘箱 <span className="text-sm font-normal text-muted-foreground">· 铺膜=3格/次、干燥=1格/次 · 每周上限 6 格</span></CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-4">
          <div><Label>铺膜次数</Label><select className="h-9 w-24 rounded-md border border-input bg-background px-2 text-sm" value={film} onChange={(e) => setFilm(+e.target.value)}>{range(0, 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
          <div><Label>干燥次数</Label><select className="h-9 w-24 rounded-md border border-input bg-background px-2 text-sm" value={dry} onChange={(e) => setDry(+e.target.value)}>{range(0, 6).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
          <div className={'text-sm ' + (grids > 6 ? 'text-red-600' : 'text-muted-foreground')}>合计 {grids} / 6 格</div>
        </div>
        <InstPicker insts={insts} sel={sel} setSel={setSel} />
        <div className="flex gap-2">
          <Button disabled={grids < 1 || grids > 6} onClick={() => onSave({ category: 'VACUUM_OVEN', filmCount: film, dryCount: dry, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>
          {d && <Button variant="ghost" onClick={() => onDel(d.id)}>删除该项</Button>}
        </div>
      </CardContent>
    </Card>
  )
}

function FurCard({ d, insts, onSave, onDel }: any) {
  const [block, setBlock] = useState(d?.blockCount || 1)
  const [temp, setTemp] = useState<string>(d?.tempCeiling != null ? String(d.tempCeiling) : '')
  const [sel, setSel] = useState<number[]>(d?.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : [])
  useEffect(() => { if (d) { setBlock(d.blockCount); setTemp(d.tempCeiling != null ? String(d.tempCeiling) : ''); setSel(d.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : []) } }, [d?.id])
  return (
    <Card>
      <CardHeader><CardTitle>环化 / 马弗 / 管式 / BET <span className="text-sm font-normal text-muted-foreground">· 全天块 · 每周上限 2 · 需填升温温度上限</span></CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-4">
          <div><Label>全天块数</Label><select className="h-9 w-24 rounded-md border border-input bg-background px-2 text-sm" value={block} onChange={(e) => setBlock(+e.target.value)}>{range(1, 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
          <div><Label>升温温度上限(℃)</Label><Input className="w-32" value={temp} onChange={(e) => setTemp(e.target.value)} placeholder="如 300" /></div>
        </div>
        <InstPicker insts={insts} sel={sel} setSel={setSel} />
        <div className="flex gap-2">
          <Button disabled={!temp} onClick={() => onSave({ category: 'FURNACE', blockCount: block, tempCeiling: temp, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>
          {d && <Button variant="ghost" onClick={() => onDel(d.id)}>删除该项</Button>}
        </div>
      </CardContent>
    </Card>
  )
}

function PolyCard({ d, heads, onSave, onDel }: any) {
  const [block, setBlock] = useState(d?.blockCount || 1)
  const [sel, setSel] = useState<number[]>(d?.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : [])
  useEffect(() => { if (d) { setBlock(d.blockCount); setSel(d.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : []) } }, [d?.id])
  return (
    <Card>
      <CardHeader><CardTitle>聚合机头 <span className="text-sm font-normal text-muted-foreground">· 半天块 · 每周上限 7 · 仅限你被授权的机头</span></CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {heads.length === 0 ? <p className="text-sm text-muted-foreground">你暂无授权的机头，请联系管理员。</p> : (
          <>
            <div className="flex flex-wrap items-end gap-4">
              <div><Label>半天块数</Label><select className="h-9 w-24 rounded-md border border-input bg-background px-2 text-sm" value={block} onChange={(e) => setBlock(+e.target.value)}>{range(1, 7).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
              <div className="text-sm text-muted-foreground">你的授权机头：{heads.map((h: Inst) => h.name).join('、')}</div>
            </div>
            <InstPicker insts={heads} sel={sel} setSel={setSel} />
            <div className="flex gap-2">
              <Button onClick={() => onSave({ category: 'POLY_HEAD', blockCount: block, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>
              {d && <Button variant="ghost" onClick={() => onDel(d.id)}>删除该项</Button>}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function BlockCard({ cat, label, max, d, onSave, onDel }: any) {
  const [block, setBlock] = useState(d?.blockCount || 1)
  useEffect(() => { if (d) setBlock(d.blockCount) }, [d?.id])
  return (
    <Card>
      <CardHeader><CardTitle>{label}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div><Label>块数</Label><select className="h-9 w-24 rounded-md border border-input bg-background px-2 text-sm" value={block} onChange={(e) => setBlock(+e.target.value)}>{range(1, max).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div className="flex gap-2">
          <Button onClick={() => onSave({ category: cat, blockCount: block })}>保存</Button>
          {d && <Button variant="ghost" onClick={() => onDel(d.id)}>删除该项</Button>}
        </div>
      </CardContent>
    </Card>
  )
}
""")

# 路由 + 导航
pyedit(W + "/src/App.tsx", [
  ["import Priorities from './pages/Priorities'",
   "import Priorities from './pages/Priorities'\nimport Signup from './pages/Signup'"],
  ["""        <Route path=\"instruments\" element={<Instruments />} />""",
   """        <Route path=\"instruments\" element={<Instruments />} />
        <Route path=\"signup\" element={<Signup />} />"""],
])
pyedit(W + "/src/layouts/MainLayout.tsx", [
  ["""            <NavLink to=\"/instruments\" className={linkCls}>仪器</NavLink>""",
   """            <NavLink to=\"/instruments\" className={linkCls}>仪器</NavLink>
            {user?.role === 'STUDENT' && <NavLink to=\"/signup\" className={linkCls}>仪器报名</NavLink>}"""],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close()
print("\n=== DONE ===")
