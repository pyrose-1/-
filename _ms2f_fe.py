# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"
SITE = "/www/wwwroot/lab.dhupi.cn"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=300):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2000:])
    if err: print("[stderr]", err[-800:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(W, ""))

# 顺手把个人批次默认设为可借出（历史遗留）
step("个人批次默认可借", "mysql -uplm -ppni38AWG4xy6wEyc plm -e \"UPDATE plm_chemical_batches SET shareable=1 WHERE scope='PERSONAL';\" 2>/dev/null; echo ok")

# ---------- MyChemicals：处置标签 + 共享 + 只读 ----------
wfile(W + "/src/pages/MyChemicals.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface Item { batchId: number; batchNo: string; name: string; cas: string | null; hazmat?: { listed: boolean; toxic: boolean }; price: string | null; productNo: string | null; quantity: string | null; unit: string | null; purchaseDate: string | null; location: string | null; remainLevel: string; shareable: boolean; scope: string | null; sharedBy: string | null; ownPrice: boolean; editable: boolean; dispState: string; dispText: string }
const LEVELS = [['FULL', '满'], ['ALMOST_FULL', '几乎满'], ['HALF', '半瓶'], ['LOW', '快没了'], ['LITTLE', '一点点'], ['EMPTY', '空']]
const levelMap: Record<string, string> = Object.fromEntries(LEVELS)
const dispColor: Record<string, string> = { HELD: 'bg-slate-100 text-slate-600', SHARED: 'bg-blue-100 text-blue-700', LENT: 'bg-amber-100 text-amber-800', TRANSFERRED: 'bg-purple-100 text-purple-700', NONE: 'bg-slate-100 text-slate-400' }

function Row({ it, onSaved }: { it: Item; onSaved: () => void }) {
  const [loc, setLoc] = useState(it.location || '')
  const [lv, setLv] = useState(it.remainLevel || 'FULL')
  const [share, setShare] = useState(it.shareable)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const dirty = loc !== (it.location || '') || lv !== it.remainLevel || share !== it.shareable
  const isShared = it.dispState === 'SHARED'
  const badge = <span className={'rounded px-2 py-0.5 text-xs ' + (dispColor[it.dispState] || '')}>{it.dispText}</span>

  async function save() {
    setSaving(true)
    try { await http.put('/inventory/batches/' + it.batchId, { location: loc, remainLevel: lv, shareable: share }); setDone(true); setTimeout(() => setDone(false), 1500); onSaved() }
    finally { setSaving(false) }
  }
  async function toPublic() {
    if (!window.confirm(`把【${it.name}】设为公用？设为公用后全实验室可见可借（仍计在你的采购金额内）。`)) return
    await http.post(`/inventory/batches/${it.batchId}/share`, { remainLevel: lv, location: loc }); onSaved()
  }

  return (
    <tr className="border-b border-border/60 align-middle">
      <td className="py-2 pr-3">
        <div className="font-medium text-foreground">{it.name}
          {it.hazmat?.listed && <span className={'ml-1 rounded px-1 py-0.5 text-xs ' + (it.hazmat.toxic ? 'bg-red-600 text-white' : 'bg-red-100 text-red-700')}>{it.hazmat.toxic ? '剧毒' : '危化'}</span>}
        </div>
        <div className="text-xs text-muted-foreground">{it.cas || '—'} · {it.batchNo}</div>
      </td>
      <td className="py-2 pr-3 text-muted-foreground">{it.productNo || '—'}</td>
      <td className="py-2 pr-3 text-foreground">{it.ownPrice ? (it.price ? '¥' + it.price : '—') : <span className="text-xs text-muted-foreground">他人采购</span>}</td>
      <td className="py-2 pr-3 text-muted-foreground">{it.purchaseDate ? String(it.purchaseDate).slice(0, 10) : '—'}</td>
      {it.editable ? (
        <>
          <td className="py-2 pr-3"><Input className="h-8 w-28" value={loc} onChange={(e) => setLoc(e.target.value)} placeholder="B柜/工位" /></td>
          <td className="py-2 pr-3">
            <select className="h-8 rounded-md border border-input bg-background px-2 text-sm" value={lv} onChange={(e) => setLv(e.target.value)}>
              {LEVELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </td>
          <td className="py-2 pr-3">{isShared ? <span className="text-xs text-blue-700">公用</span> : <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />可借出</label>}</td>
          <td className="py-2 pr-3">{badge}</td>
          <td className="py-2 pr-3">
            <div className="flex gap-1">
              <Button className="h-7 px-2 text-xs" disabled={!dirty || saving} onClick={save}>{saving ? '…' : done ? '已存' : '保存'}</Button>
              {!isShared && <Button variant="outline" className="h-7 px-2 text-xs" onClick={toPublic}>设为公用</Button>}
            </div>
          </td>
        </>
      ) : (
        <>
          <td className="py-2 pr-3 text-muted-foreground">{it.location || '—'}</td>
          <td className="py-2 pr-3 text-muted-foreground">{levelMap[it.remainLevel] || it.remainLevel || '—'}</td>
          <td className="py-2 pr-3 text-xs text-muted-foreground">—</td>
          <td className="py-2 pr-3">{badge}</td>
          <td className="py-2 pr-3 text-xs text-muted-foreground">不在你手上</td>
        </>
      )}
    </tr>
  )
}

export default function MyChemicals() {
  const [data, setData] = useState<{ totalAmount: number; count: number; items: Item[] }>({ totalAmount: 0, count: 0, items: [] })
  async function load() { const d: any = await http.get('/inventory/mine'); setData(d) }
  useEffect(() => { load() }, [])
  return (
    <Card>
      <CardHeader><CardTitle>我的药品（共 {data.count} 项 · 我的累计采购金额 ¥{data.totalAmount?.toFixed?.(2) ?? data.totalAmount}）</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <p className="mb-2 text-xs text-muted-foreground">说明：金额始终计在最初采购人名下；借出/共享/转让后仅在状态列标注去向。可勾「可借出」让同组借用，或「设为公用」同步到公共药品。</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">药品 / CAS / 批次</th>
              <th className="py-2 pr-3 font-medium">货号</th>
              <th className="py-2 pr-3 font-medium">价格</th>
              <th className="py-2 pr-3 font-medium">申购日期</th>
              <th className="py-2 pr-3 font-medium">存放地点</th>
              <th className="py-2 pr-3 font-medium">剩余情况</th>
              <th className="py-2 pr-3 font-medium">可借出</th>
              <th className="py-2 pr-3 font-medium">状态</th>
              <th className="py-2 pr-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((it) => <Row key={it.batchId} it={it} onSaved={load} />)}
            {data.items.length === 0 && <tr><td colSpan={9} className="py-8 text-center text-muted-foreground">还没有药品（申购通过后会自动归到这里）</td></tr>}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
""")

# ---------- Borrow：去留言 ----------
pyfix = r'''import os,sys
'''
wfile(W + "/src/pages/Borrow.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface BR { id: number; status: string; statusText: string; chemicalName: string; cas: string | null; remainText: string | null; location: string | null; ownerName: string; borrowerName: string; createdAt: string }
const sc: Record<string, string> = { PENDING: 'bg-amber-100 text-amber-800', LENT: 'bg-green-100 text-green-700', TRANSFERRED: 'bg-blue-100 text-blue-700', REJECTED: 'bg-red-100 text-red-700', CANCELLED: 'bg-slate-100 text-slate-500' }

export default function Borrow() {
  const [mine, setMine] = useState<BR[]>([])
  const [toMe, setToMe] = useState<BR[]>([])
  const [msg, setMsg] = useState('')
  async function load() { setMine(await http.get('/borrow/mine') as any); setToMe(await http.get('/borrow/to-me') as any) }
  useEffect(() => { load() }, [])

  async function act(r: BR, kind: 'reject' | 'lend' | 'transfer') {
    if (kind === 'transfer' && !window.confirm(`确认把【${r.chemicalName}】所有权完全转让给 ${r.borrowerName}？转让后该药品归对方所有（金额仍计在最初采购人）。`)) return
    try { await http.post(`/borrow/${r.id}/${kind}`, {}); setMsg('✅ 已处理'); load() } catch (e: any) { setMsg('操作失败：' + e.message) }
  }
  async function cancel(r: BR) { if (!window.confirm('取消该借用申请？')) return; await http.post(`/borrow/${r.id}/cancel`, {}); load() }

  return (
    <div className="space-y-4">
      {msg && <div className="text-sm text-muted-foreground">{msg}</div>}
      <Card>
        <CardHeader><CardTitle>我的借出（{toMe.length}）· 别人想借我的药品</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">借用人</th><th className="py-2 pr-3 font-medium">药品</th><th className="py-2 pr-3 font-medium">余量/位置</th>
              <th className="py-2 pr-3 font-medium">状态</th><th className="py-2 pr-3 font-medium">操作</th>
            </tr></thead>
            <tbody>
              {toMe.map((r) => (
                <tr key={r.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3 font-medium text-foreground">{r.borrowerName}</td>
                  <td className="py-2 pr-3">{r.chemicalName}<div className="text-xs text-muted-foreground">{r.cas}</div></td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.remainText || '—'} / {r.location || '—'}</td>
                  <td className="py-2 pr-3"><span className={'rounded px-2 py-0.5 text-xs ' + (sc[r.status] || '')}>{r.statusText}</span></td>
                  <td className="py-2 pr-3">
                    {r.status === 'PENDING' ? (
                      <div className="flex flex-wrap gap-1">
                        <Button className="h-7 px-2 text-xs" onClick={() => act(r, 'lend')}>借一点</Button>
                        <Button variant="outline" className="h-7 px-2 text-xs" onClick={() => act(r, 'transfer')}>转让</Button>
                        <Button variant="destructive" className="h-7 px-2 text-xs" onClick={() => act(r, 'reject')}>拒绝</Button>
                      </div>
                    ) : <span className="text-xs text-muted-foreground">—</span>}
                  </td>
                </tr>
              ))}
              {toMe.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-muted-foreground">暂无借用申请</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>我的借用（{mine.length}）· 我向别人借的</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">药品</th><th className="py-2 pr-3 font-medium">拥有人</th><th className="py-2 pr-3 font-medium">余量/位置</th>
              <th className="py-2 pr-3 font-medium">状态</th><th className="py-2 pr-3 font-medium">操作</th>
            </tr></thead>
            <tbody>
              {mine.map((r) => (
                <tr key={r.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3">{r.chemicalName}<div className="text-xs text-muted-foreground">{r.cas}</div></td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.ownerName}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.remainText || '—'} / {r.location || '—'}</td>
                  <td className="py-2 pr-3"><span className={'rounded px-2 py-0.5 text-xs ' + (sc[r.status] || '')}>{r.statusText}</span>{r.status === 'LENT' && <div className="text-xs text-muted-foreground">请联系持有人确认药品情况</div>}</td>
                  <td className="py-2 pr-3">{r.status === 'PENDING' && <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => cancel(r)}>取消</Button>}</td>
                </tr>
              ))}
              {mine.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-muted-foreground">还没有借用申请（在「申购」页查重命中可借药品时可发起）</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
""")

# ---------- Purchases：借用提示语 + 公开自 标签 ----------
def pyedit(path, reps):
    import base64, json
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:50])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.replace(W, ""), o.strip(), e[-200:])

pyedit(W + "/src/pages/Purchases.tsx", [
  ["interface Bat { batchId: number; scope: string; ownerId: number | null; ownerName: string | null; remainText: string; shareable: boolean; borrowable: boolean }",
   "interface Bat { batchId: number; scope: string; ownerId: number | null; ownerName: string | null; sharedBy: string | null; remainText: string; shareable: boolean; borrowable: boolean }"],
  ["""    try { await http.post('/borrow', { batchId: b.batchId }); setMsg(`✅ 已向 ${b.ownerName} 发起借用申请，可在「借用申请」中查看进度`) }""",
   """    try { await http.post('/borrow', { batchId: b.batchId }); setMsg(`✅ 已发起借用申请（对方：${b.sharedBy || b.ownerName || '持有人'}），请联系持有人确认药品情况；进度见「借用申请」`) }"""],
  ["""                            <span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>{b.scope === 'PUBLIC' ? '公用' : (b.ownerName || '个人')}</span>""",
   """                            <span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>{b.scope === 'PUBLIC' ? (b.sharedBy ? '公开自' + b.sharedBy : '公用') : (b.ownerName || '个人')}</span>"""],
])

# ---------- Chemicals：公开自 标签 ----------
pyedit(W + "/src/pages/Chemicals.tsx", [
  ["interface Batch { id: number; batchNo: string; scope: string; ownerName: string | null; shareable: boolean; remainLevel: string }",
   "interface Batch { id: number; batchNo: string; scope: string; ownerName: string | null; sharedBy: string | null; shareable: boolean; remainLevel: string }"],
  ["""<span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>{b.scope === 'PUBLIC' ? '公用' : (b.ownerName || '个人')}</span>""",
   """<span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>{b.scope === 'PUBLIC' ? (b.sharedBy ? '公开自' + b.sharedBy : '公用') : (b.ownerName || '个人')}</span>"""],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (W, SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\\.js' | head -1")
cli.close()
print("\n=== DONE ===")
