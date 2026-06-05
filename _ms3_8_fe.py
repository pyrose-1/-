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
def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content)); print("  写", path.replace(W, ""))
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

SIGNUP = r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface Inst { id: number; name: string; category: string; filmCapable: boolean; dryCapable: boolean }
interface Demand { id: number; category: string; instrumentMode: string; instrumentIds: number[] | null; instrumentNames: string[]; filmCount: number; dryCount: number; blockCount: number; tempCeiling: number | null; gridsTotal: number }
const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i)
const sel0 = 'h-9 w-20 rounded-md border border-input bg-background px-2 text-sm'

function InstPicker({ insts, sel, setSel }: { insts: Inst[]; sel: number[]; setSel: (v: number[]) => void }) {
  const [open, setOpen] = useState(false)
  function toggle(id: number) { setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]) }
  return (
    <div className="text-xs">
      <button type="button" className="text-primary underline" onClick={() => setOpen(!open)}>{sel.length ? `已指定 ${sel.length} 台` : '默认大类内任意（可指定）'}</button>
      {open && <div className="mt-1 max-h-32 overflow-y-auto rounded border border-border p-1">
        {insts.map((i) => <label key={i.id} className="flex items-center gap-1 py-0.5"><input type="checkbox" checked={sel.includes(i.id)} onChange={() => toggle(i.id)} /><span>{i.name}</span>{i.filmCapable && <span className="rounded bg-blue-100 px-1 text-blue-700">铺</span>}</label>)}
      </div>}
    </div>
  )
}

export default function Signup() {
  const { user } = useAuth()
  const [cycle, setCycle] = useState<any>(null)
  const [mine, setMine] = useState<Demand[]>([])
  const [insts, setInsts] = useState<Inst[]>([])
  const [heads, setHeads] = useState<Inst[]>([])
  const [fc, setFc] = useState<Record<string, number> | null>(null)
  const [msg, setMsg] = useState('')

  async function loadMine() { setMine(await http.get('/instruments/booking/mine') as any) }
  useEffect(() => {
    http.get('/instruments/booking/cycle').then(setCycle)
    http.get('/instruments').then((d: any) => setInsts(d))
    http.get('/instruments/my-heads').then((d: any) => setHeads(d)).catch(() => {})
    http.get('/instruments/forecast').then((d: any) => setFc(d)).catch(() => {})
    loadMine()
  }, [])
  const dOf = (c: string) => mine.find((d) => d.category === c)
  async function save(body: any) { setMsg(''); try { await http.post('/instruments/booking', body); setMsg('✅ 已保存'); loadMine() } catch (e: any) { setMsg('✖ ' + e.message) } }
  async function del(id: number) { await http.delete('/instruments/booking/' + id); loadMine() }

  if (user?.role !== 'STUDENT') return <Card><CardContent className="py-10 text-center text-muted-foreground">仅学生参与仪器预约报名。</CardContent></Card>
  const vac = insts.filter((i) => i.category === 'VACUUM_OVEN')
  const cyc = insts.filter((i) => i.category === 'CYCLE_OVEN')

  const FcItem = ({ t, v }: { t: string; v?: number }) => <span className="whitespace-nowrap">{t} <b className="text-primary">{v ?? '—'}%</b></span>

  return (
    <div className="space-y-3">
      <Card><CardContent className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm">
        <span className="font-medium text-foreground">本轮报名 → {cycle?.start} ~ {cycle?.end}</span>
        <span className="text-muted-foreground">截止 {cycle?.deadline} 24:00，周一抽签。每类填好点保存，可改/删；选 0 即不报名。</span>
        {msg && <span className="text-accent">{msg}</span>}
      </CardContent></Card>

      {fc && <Card><CardContent className="flex flex-wrap gap-x-5 gap-y-1 py-2 text-sm">
        <span className="font-medium">中签概率预估·至少约到1次：</span>
        <FcItem t="真空铺膜" v={fc.VACUUM_FILM} /><FcItem t="真空干燥" v={fc.VACUUM_DRY} />
        <FcItem t="环化" v={fc.CYCLE_OVEN} /><FcItem t="马弗" v={fc.MUFFLE} /><FcItem t="管式" v={fc.TUBE} /><FcItem t="BET" v={fc.BET} />
        <FcItem t="机头" v={fc.POLY_HEAD} /><FcItem t="DMA" v={fc.DMA} /><FcItem t="TGA" v={fc.TGA} />
      </CardContent></Card>}

      <VacCard d={dOf('VACUUM_OVEN')} insts={vac} onSave={save} onDel={del} />

      <div className="grid gap-3 md:grid-cols-2">
        <CycleCard d={dOf('CYCLE_OVEN')} insts={cyc} onSave={save} onDel={del} />
        <PolyCard d={dOf('POLY_HEAD')} heads={heads} onSave={save} onDel={del} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <SmallCard cat="MUFFLE" label="马弗炉" unit="全天块" max={3} d={dOf('MUFFLE')} onSave={save} onDel={del} />
        <SmallCard cat="TUBE" label="管式炉" unit="全天块" max={3} d={dOf('TUBE')} onSave={save} onDel={del} />
        <SmallCard cat="BET" label="BET" unit="全天块" max={7} note="不限" d={dOf('BET')} onSave={save} onDel={del} />
        <SmallCard cat="DMA" label="DMA" unit="4h块" max={4} d={dOf('DMA')} onSave={save} onDel={del} />
        <SmallCard cat="TGA" label="TGA" unit="4h块" max={4} d={dOf('TGA')} onSave={save} onDel={del} />
      </div>
    </div>
  )
}

function VacCard({ d, insts, onSave, onDel }: any) {
  const [film, setFilm] = useState(d?.filmCount ?? 0); const [dry, setDry] = useState(d?.dryCount ?? 0)
  const [sel, setSel] = useState<number[]>(d?.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : [])
  useEffect(() => { if (d) { setFilm(d.filmCount); setDry(d.dryCount); setSel(d.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : []) } }, [d?.id])
  const grids = film * 3 + dry
  return (
    <Card><CardHeader className="pb-2"><CardTitle className="text-base">真空烘箱 <span className="text-xs font-normal text-muted-foreground">铺膜=3格/次、干燥=1格/次 · 每周上限 8 格 · 选 0 不报名</span></CardTitle></CardHeader>
      <CardContent className="flex flex-wrap items-end gap-3 py-2">
        <div><Label className="text-xs">铺膜次数</Label><select className={sel0} value={film} onChange={(e) => setFilm(+e.target.value)}>{range(0, 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><Label className="text-xs">干燥次数</Label><select className={sel0} value={dry} onChange={(e) => setDry(+e.target.value)}>{range(0, 8).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div className={'text-sm ' + (grids > 8 ? 'text-red-600' : 'text-muted-foreground')}>合计 {grids}/8</div>
        <InstPicker insts={insts} sel={sel} setSel={setSel} />
        <Button disabled={grids > 8} onClick={() => grids < 1 ? (d && onDel(d.id)) : onSave({ category: 'VACUUM_OVEN', filmCount: film, dryCount: dry, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>
      </CardContent>
    </Card>
  )
}

function CycleCard({ d, insts, onSave, onDel }: any) {
  const [block, setBlock] = useState(d?.blockCount ?? 0); const [temp, setTemp] = useState<string>(d?.tempCeiling != null ? String(d.tempCeiling) : '')
  const [sel, setSel] = useState<number[]>(d?.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : [])
  useEffect(() => { if (d) { setBlock(d.blockCount); setTemp(d.tempCeiling != null ? String(d.tempCeiling) : ''); setSel(d.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : []) } }, [d?.id])
  return (
    <Card><CardHeader className="pb-2"><CardTitle className="text-base">环化烘箱 <span className="text-xs font-normal text-muted-foreground">全天块 · 每周上限 2 · 需填温度上限</span></CardTitle></CardHeader>
      <CardContent className="flex flex-wrap items-end gap-3 py-2">
        <div><Label className="text-xs">全天块</Label><select className={sel0} value={block} onChange={(e) => setBlock(+e.target.value)}>{range(0, 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><Label className="text-xs">温度上限℃</Label><Input className="h-9 w-24" value={temp} onChange={(e) => setTemp(e.target.value)} placeholder="如 300" /></div>
        <InstPicker insts={insts} sel={sel} setSel={setSel} />
        <Button onClick={() => block < 1 ? (d && onDel(d.id)) : onSave({ category: 'CYCLE_OVEN', blockCount: block, tempCeiling: temp, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>
      </CardContent>
    </Card>
  )
}

function PolyCard({ d, heads, onSave, onDel }: any) {
  const [block, setBlock] = useState(d?.blockCount ?? 0)
  const [sel, setSel] = useState<number[]>(d?.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : [])
  useEffect(() => { if (d) { setBlock(d.blockCount); setSel(d.instrumentMode === 'SPECIFIC' ? d.instrumentIds || [] : []) } }, [d?.id])
  return (
    <Card><CardHeader className="pb-2"><CardTitle className="text-base">聚合机头 <span className="text-xs font-normal text-muted-foreground">半天块 · 每周上限 7 · 仅授权机头</span></CardTitle></CardHeader>
      <CardContent className="py-2">
        {heads.length === 0 ? <p className="text-sm text-muted-foreground">你暂无授权机头，请联系管理员。</p> : (
          <div className="flex flex-wrap items-end gap-3">
            <div><Label className="text-xs">半天块</Label><select className={sel0} value={block} onChange={(e) => setBlock(+e.target.value)}>{range(0, 7).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
            <InstPicker insts={heads} sel={sel} setSel={setSel} />
            <Button onClick={() => block < 1 ? (d && onDel(d.id)) : onSave({ category: 'POLY_HEAD', blockCount: block, instrumentMode: sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: sel })}>保存</Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function SmallCard({ cat, label, unit, max, note, d, onSave, onDel }: any) {
  const [block, setBlock] = useState(d?.blockCount ?? 0)
  useEffect(() => { if (d) setBlock(d.blockCount); else setBlock(0) }, [d?.id])
  return (
    <Card><CardContent className="space-y-2 py-3">
      <div className="text-sm font-medium text-foreground">{label}</div>
      <div className="text-xs text-muted-foreground">{note || ('上限 ' + max)} · {unit}</div>
      <div className="flex items-center gap-2">
        <select className={sel0} value={block} onChange={(e) => setBlock(+e.target.value)}>{range(0, max).map((n) => <option key={n} value={n}>{n}</option>)}</select>
        <Button className="h-8 px-2 text-xs" onClick={() => block < 1 ? (d && onDel(d.id)) : onSave({ category: cat, blockCount: block })}>保存</Button>
      </div>
      {d && <div className="text-xs text-green-700">已报 {d.blockCount} 块</div>}
    </CardContent></Card>
  )
}
"""
wfile(W + "/src/pages/Signup.tsx", SIGNUP)

# Instruments 页类别
pyedit(W + "/src/pages/Instruments.tsx", [
  ["const CAT_ORDER = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA']",
   "const CAT_ORDER = ['VACUUM_OVEN', 'CYCLE_OVEN', 'MUFFLE', 'TUBE', 'BET', 'POLY_HEAD', 'DMA', 'TGA']"],
  ["const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', FURNACE: '环化 / 马弗 / 管式 / BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他（随用随约）' }",
   "const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', CYCLE_OVEN: '环化烘箱', MUFFLE: '马弗炉', TUBE: '管式炉', BET: 'BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他（随用随约）' }"],
  ["const CAP: Record<string, string> = { VACUUM_OVEN: '每周 8 格（铺膜=3格 / 干燥=1格）', FURNACE: '每周 2 个全天块', POLY_HEAD: '每周 7 个半天块', DMA: '每周 4 个 4h 块', TGA: '每周 4 个 4h 块', OTHER: '不限、不抽签' }",
   "const CAP: Record<string, string> = { VACUUM_OVEN: '每周 8 格（铺膜=3格 / 干燥=1格）', CYCLE_OVEN: '每周 2 个全天块 · 需填温度上限', MUFFLE: '每周 3 个全天块', TUBE: '每周 3 个全天块', BET: '不限全天块', POLY_HEAD: '每周 7 个半天块', DMA: '每周 4 个 4h 块', TGA: '每周 4 个 4h 块', OTHER: '不限、不抽签' }"],
])
# Priorities 页类别
pyedit(W + "/src/pages/Priorities.tsx", [
  ["const CATS = [['VACUUM_OVEN', '真空烘箱'], ['FURNACE', '环化/马弗/管式/BET'], ['POLY_HEAD', '聚合机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]",
   "const CATS = [['VACUUM_OVEN', '真空烘箱'], ['CYCLE_OVEN', '环化'], ['MUFFLE', '马弗'], ['TUBE', '管式'], ['BET', 'BET'], ['POLY_HEAD', '机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]"],
])
# Schedule 页类别 tab
pyedit(W + "/src/pages/Schedule.tsx", [
  ["const CATORD = [['VACUUM_OVEN', '真空烘箱'], ['FURNACE', '环化/马弗/管式/BET'], ['POLY_HEAD', '聚合机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]",
   "const CATORD = [['VACUUM_OVEN', '真空烘箱'], ['CYCLE_OVEN', '环化烘箱'], ['MUFFLE', '马弗炉'], ['TUBE', '管式炉'], ['BET', 'BET'], ['POLY_HEAD', '聚合机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]"],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
