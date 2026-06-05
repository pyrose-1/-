# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"; W = "/www/wwwroot/plm-web"; SITE = "/www/wwwroot/lab.dhupi.cn"
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

# 后端：批量保存
B = r"""
  async saveDemandBatch(user: any, items: any[]) {
    let error: string | null = null;
    for (const it of items || []) {
      try { await this.saveDemand(user, it); }
      catch (e: any) { if (!error) error = (e && e.message) ? e.message : '保存失败'; }
    }
    return { demands: await this.myDemands(user.sub), error };
  }
"""
b64 = base64.b64encode(B.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s/src/instruments/instruments.service.ts'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('batch inserted')\nPYEOF" % (APP, b64))
print(" ", o.strip(), e[-150:])
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Post('booking') saveDemand(@CurrentUser() u: any, @Body() b: any) { return this.svc.saveDemand(u, b); }",
   "  @Post('booking') saveDemand(@CurrentUser() u: any, @Body() b: any) { return this.svc.saveDemand(u, b); }\n  @Post('booking/batch') saveBatch(@CurrentUser() u: any, @Body() b: any) { return this.svc.saveDemandBatch(u, b?.items || []); }"],
])
step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -5 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")

# 前端：重写 Signup（单一保存 + 查看报名 + 分格规则）
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
const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', CYCLE_OVEN: '环化烘箱', MUFFLE: '马弗炉', TUBE: '管式炉', BET: 'BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA' }

function InstPicker({ insts, sel, setSel }: { insts: Inst[]; sel: number[]; setSel: (v: number[]) => void }) {
  const [open, setOpen] = useState(false)
  const toggle = (id: number) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id])
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
  const [busy, setBusy] = useState(false)
  const [showSum, setShowSum] = useState(false)
  // 表单
  const [vac, setVac] = useState({ film: 0, dry: 0, sel: [] as number[] })
  const [cyc, setCyc] = useState({ block: 0, temp: '', sel: [] as number[] })
  const [poly, setPoly] = useState({ block: 0, sel: [] as number[] })
  const [sm, setSm] = useState<Record<string, number>>({ MUFFLE: 0, TUBE: 0, BET: 0, DMA: 0, TGA: 0 })

  async function loadMine() { setMine(await http.get('/instruments/booking/mine') as any) }
  useEffect(() => {
    http.get('/instruments/booking/cycle').then(setCycle)
    http.get('/instruments').then((d: any) => setInsts(d))
    http.get('/instruments/my-heads').then((d: any) => setHeads(d)).catch(() => {})
    http.get('/instruments/forecast').then((d: any) => setFc(d)).catch(() => {})
    loadMine()
  }, [])
  useEffect(() => {
    const g = (c: string) => mine.find((d) => d.category === c)
    const v = g('VACUUM_OVEN'); setVac({ film: v?.filmCount || 0, dry: v?.dryCount || 0, sel: v?.instrumentMode === 'SPECIFIC' ? v.instrumentIds || [] : [] })
    const c2 = g('CYCLE_OVEN'); setCyc({ block: c2?.blockCount || 0, temp: c2?.tempCeiling != null ? String(c2.tempCeiling) : '', sel: c2?.instrumentMode === 'SPECIFIC' ? c2.instrumentIds || [] : [] })
    const p = g('POLY_HEAD'); setPoly({ block: p?.blockCount || 0, sel: p?.instrumentMode === 'SPECIFIC' ? p.instrumentIds || [] : [] })
    setSm({ MUFFLE: g('MUFFLE')?.blockCount || 0, TUBE: g('TUBE')?.blockCount || 0, BET: g('BET')?.blockCount || 0, DMA: g('DMA')?.blockCount || 0, TGA: g('TGA')?.blockCount || 0 })
  }, [mine])

  async function saveAll() {
    setBusy(true); setMsg('')
    const items = [
      { category: 'VACUUM_OVEN', filmCount: vac.film, dryCount: vac.dry, instrumentMode: vac.sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: vac.sel },
      { category: 'CYCLE_OVEN', blockCount: cyc.block, tempCeiling: cyc.temp, instrumentMode: cyc.sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: cyc.sel },
      { category: 'POLY_HEAD', blockCount: poly.block, instrumentMode: poly.sel.length ? 'SPECIFIC' : 'CATEGORY', instrumentIds: poly.sel },
      { category: 'MUFFLE', blockCount: sm.MUFFLE }, { category: 'TUBE', blockCount: sm.TUBE }, { category: 'BET', blockCount: sm.BET },
      { category: 'DMA', blockCount: sm.DMA }, { category: 'TGA', blockCount: sm.TGA },
    ]
    try { const r: any = await http.post('/instruments/booking/batch', { items }); setMine(r.demands); setMsg(r.error ? ('⚠ 部分未保存：' + r.error) : '✅ 全部已保存') }
    catch (e: any) { setMsg('✖ ' + e.message) } finally { setBusy(false) }
  }

  if (user?.role !== 'STUDENT') return <Card><CardContent className="py-10 text-center text-muted-foreground">仅学生参与仪器预约报名。</CardContent></Card>
  const vacI = insts.filter((i) => i.category === 'VACUUM_OVEN')
  const cycI = insts.filter((i) => i.category === 'CYCLE_OVEN')
  const FcItem = ({ t, v }: { t: string; v?: number }) => <span className="whitespace-nowrap">{t} <b className="text-primary">{v ?? '—'}%</b></span>
  function demText(d: Demand) {
    if (d.category === 'VACUUM_OVEN') return `铺膜${d.filmCount} + 干燥${d.dryCount}（${d.gridsTotal}格）`
    if (d.category === 'CYCLE_OVEN') return `${d.blockCount} 个全天块 · ${d.tempCeiling || '?'}℃`
    if (d.category === 'POLY_HEAD') return `${d.blockCount} 个半天块`
    return `${d.blockCount} 块`
  }

  return (
    <div className="space-y-3">
      {/* 分格规则 */}
      <Card><CardContent className="py-3 text-sm">
        <div className="font-medium text-foreground">分格规则</div>
        <div className="mt-1 text-muted-foreground">每天 8:00–24:00 分为 <b>4 个 4h 格</b>：① 8–12 ② 12–16 ③ 16–20 ④ 20–24。<b>半天块</b>=上午 8–16 / 下午 16–24；<b>全天块</b>=整天独占。</div>
        <div className="mt-1 text-muted-foreground">每人每周可约：真空 <b>8 格</b>（铺膜占3格/次、干燥占1格/次）· 环化 <b>2 全天</b> · 马弗 <b>3 全天</b> · 管式 <b>3 全天</b> · BET <b>不限</b> · 机头 <b>7 半天</b> · DMA <b>4 格</b> · TGA <b>4 格</b>。</div>
      </CardContent></Card>

      <Card><CardContent className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm">
        <span className="font-medium text-foreground">本轮报名 → {cycle?.start} ~ {cycle?.end}</span>
        <span className="text-muted-foreground">截止 {cycle?.deadline} 24:00，周一抽签。各项选 0 即不报名。</span>
      </CardContent></Card>

      {fc && <Card><CardContent className="flex flex-wrap gap-x-5 gap-y-1 py-2 text-sm">
        <span className="font-medium">中签概率预估·至少约到1次：</span>
        <FcItem t="真空铺膜" v={fc.VACUUM_FILM} /><FcItem t="真空干燥" v={fc.VACUUM_DRY} />
        <FcItem t="环化" v={fc.CYCLE_OVEN} /><FcItem t="马弗" v={fc.MUFFLE} /><FcItem t="管式" v={fc.TUBE} /><FcItem t="BET" v={fc.BET} />
        <FcItem t="机头" v={fc.POLY_HEAD} /><FcItem t="DMA" v={fc.DMA} /><FcItem t="TGA" v={fc.TGA} />
      </CardContent></Card>}

      {/* 真空 */}
      <Card><CardHeader className="pb-2"><CardTitle className="text-base">真空烘箱 <span className="text-xs font-normal text-muted-foreground">铺膜=3格/次、干燥=1格/次 · 上限 8 格</span></CardTitle></CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3 py-2">
          <div><Label className="text-xs">铺膜次数</Label><select className={sel0} value={vac.film} onChange={(e) => setVac({ ...vac, film: +e.target.value })}>{range(0, 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
          <div><Label className="text-xs">干燥次数</Label><select className={sel0} value={vac.dry} onChange={(e) => setVac({ ...vac, dry: +e.target.value })}>{range(0, 8).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
          <div className={'text-sm ' + (vac.film * 3 + vac.dry > 8 ? 'text-red-600' : 'text-muted-foreground')}>合计 {vac.film * 3 + vac.dry}/8</div>
          <InstPicker insts={vacI} sel={vac.sel} setSel={(s) => setVac({ ...vac, sel: s })} />
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2">
        <Card><CardHeader className="pb-2"><CardTitle className="text-base">环化烘箱 <span className="text-xs font-normal text-muted-foreground">全天块 · 上限 2 · 需填温度</span></CardTitle></CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3 py-2">
            <div><Label className="text-xs">全天块</Label><select className={sel0} value={cyc.block} onChange={(e) => setCyc({ ...cyc, block: +e.target.value })}>{range(0, 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
            <div><Label className="text-xs">温度上限℃</Label><Input className="h-9 w-24" value={cyc.temp} onChange={(e) => setCyc({ ...cyc, temp: e.target.value })} placeholder="如 300" /></div>
            <InstPicker insts={cycI} sel={cyc.sel} setSel={(s) => setCyc({ ...cyc, sel: s })} />
          </CardContent>
        </Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-base">聚合机头 <span className="text-xs font-normal text-muted-foreground">半天块 · 上限 7 · 仅授权机头</span></CardTitle></CardHeader>
          <CardContent className="py-2">
            {heads.length === 0 ? <p className="text-sm text-muted-foreground">你暂无授权机头，请联系管理员。</p> : (
              <div className="flex flex-wrap items-end gap-3">
                <div><Label className="text-xs">半天块</Label><select className={sel0} value={poly.block} onChange={(e) => setPoly({ ...poly, block: +e.target.value })}>{range(0, 7).map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
                <InstPicker insts={heads} sel={poly.sel} setSel={(s) => setPoly({ ...poly, sel: s })} />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[['MUFFLE', '马弗炉', '全天块', 3, '上限 3'], ['TUBE', '管式炉', '全天块', 3, '上限 3'], ['BET', 'BET', '全天块', 7, '不限'], ['DMA', 'DMA', '4h块', 4, '上限 4'], ['TGA', 'TGA', '4h块', 4, '上限 4']].map(([cat, label, unit, max, note]: any) => (
          <Card key={cat}><CardContent className="space-y-1 py-3">
            <div className="text-sm font-medium text-foreground">{label}</div>
            <div className="text-xs text-muted-foreground">{note} · {unit}</div>
            <select className={sel0} value={sm[cat]} onChange={(e) => setSm({ ...sm, [cat]: +e.target.value })}>{range(0, max).map((n: number) => <option key={n} value={n}>{n}</option>)}</select>
          </CardContent></Card>
        ))}
      </div>

      {/* 总保存 + 查看 */}
      <Card><CardContent className="flex flex-wrap items-center gap-3 py-3">
        <Button variant="accent" disabled={busy} onClick={saveAll}>保存全部报名</Button>
        <Button variant="outline" onClick={() => { loadMine(); setShowSum(!showSum) }}>{showSum ? '收起报名情况' : '查看报名情况'}</Button>
        {msg && <span className="text-sm text-accent">{msg}</span>}
      </CardContent></Card>

      {showSum && (
        <Card><CardHeader className="pb-2"><CardTitle className="text-base">我的本轮报名（{mine.length} 项）</CardTitle></CardHeader>
          <CardContent className="py-2">
            {mine.length === 0 ? <p className="text-sm text-muted-foreground">尚未报名任何项目。</p> : (
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border text-left text-muted-foreground"><th className="py-1 pr-3 font-medium">类别</th><th className="py-1 pr-3 font-medium">内容</th><th className="py-1 pr-3 font-medium">指定仪器</th></tr></thead>
                <tbody>
                  {mine.map((d) => <tr key={d.id} className="border-b border-border/60"><td className="py-1 pr-3 font-medium">{CAT_LABEL[d.category] || d.category}</td><td className="py-1 pr-3">{demText(d)}</td><td className="py-1 pr-3 text-xs text-muted-foreground">{d.instrumentMode === 'SPECIFIC' ? d.instrumentNames.join('、') : '大类任意'}</td></tr>)}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
"""
wfile(W + "/src/pages/Signup.tsx", SIGNUP)

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -6" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
