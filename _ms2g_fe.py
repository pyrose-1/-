# -*- coding: utf-8 -*-
import os, sys, json, base64
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

def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:50])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.replace(W, ""), o.strip(), e[-200:])

# ---------- Borrow.tsx 重写：公用借用 USING + 前两借用人 + 借用完毕弹窗 ----------
wfile(W + "/src/pages/Borrow.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface BR { id: number; status: string; statusText: string; chemicalName: string; cas: string | null; scope: string | null; remainText: string | null; remainLevel: string | null; location: string | null; ownerName: string; borrowerName: string; prevBorrowers: string[]; createdAt: string }
const sc: Record<string, string> = { PENDING: 'bg-amber-100 text-amber-800', LENT: 'bg-green-100 text-green-700', USING: 'bg-green-100 text-green-700', TRANSFERRED: 'bg-blue-100 text-blue-700', DONE: 'bg-slate-100 text-slate-500', REJECTED: 'bg-red-100 text-red-700', CANCELLED: 'bg-slate-100 text-slate-500' }
const LEVELS = [['FULL', '满'], ['ALMOST_FULL', '几乎满'], ['HALF', '半瓶'], ['LOW', '快没了'], ['LITTLE', '一点点'], ['EMPTY', '空']]

export default function Borrow() {
  const [mine, setMine] = useState<BR[]>([])
  const [toMe, setToMe] = useState<BR[]>([])
  const [msg, setMsg] = useState('')
  // 借用完毕弹窗
  const [fin, setFin] = useState<BR | null>(null)
  const [fLv, setFLv] = useState('HALF')
  const [fLoc, setFLoc] = useState('')
  const [fFull, setFFull] = useState(false)

  async function load() { setMine(await http.get('/borrow/mine') as any); setToMe(await http.get('/borrow/to-me') as any) }
  useEffect(() => { load() }, [])

  async function act(r: BR, kind: 'reject' | 'lend' | 'transfer') {
    if (kind === 'transfer' && !window.confirm(`确认把【${r.chemicalName}】所有权完全转让给 ${r.borrowerName}？转让后归对方所有（金额仍计最初采购人）。`)) return
    try { await http.post(`/borrow/${r.id}/${kind}`, {}); setMsg('✅ 已处理'); load() } catch (e: any) { setMsg('操作失败：' + e.message) }
  }
  async function cancel(r: BR) { if (!window.confirm('取消该借用申请？')) return; await http.post(`/borrow/${r.id}/cancel`, {}); load() }

  function openFinish(r: BR) { setFin(r); setFLv(r.remainLevel || 'HALF'); setFLoc(r.location || ''); setFFull(false) }
  async function submitFinish() {
    if (!fin) return
    try { await http.post(`/borrow/${fin.id}/finish`, { remainLevel: fLv, location: fLoc, fullyTaken: fFull }); setFin(null); setMsg('✅ 已登记借用完毕'); load() }
    catch (e: any) { setMsg('登记失败：' + e.message) }
  }

  return (
    <div className="space-y-4">
      {msg && <div className="text-sm text-muted-foreground">{msg}</div>}

      <Card>
        <CardHeader><CardTitle>我的借用（{mine.length}）· 我借/取用的药品</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">药品</th><th className="py-2 pr-3 font-medium">拥有人</th>
              <th className="py-2 pr-3 font-medium">余量 / 位置</th><th className="py-2 pr-3 font-medium">前两个借用人</th>
              <th className="py-2 pr-3 font-medium">状态</th><th className="py-2 pr-3 font-medium">操作</th>
            </tr></thead>
            <tbody>
              {mine.map((r) => (
                <tr key={r.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3">{r.chemicalName}{r.scope === 'PUBLIC' && <span className="ml-1 rounded bg-primary/10 px-1 py-0.5 text-xs text-primary">公用</span>}<div className="text-xs text-muted-foreground">{r.cas}</div></td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.ownerName}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.remainText || '—'} / {r.location || '—'}</td>
                  <td className="py-2 pr-3 text-xs text-muted-foreground">{r.prevBorrowers?.length ? r.prevBorrowers.join('、') : '—'}</td>
                  <td className="py-2 pr-3"><span className={'rounded px-2 py-0.5 text-xs ' + (sc[r.status] || '')}>{r.statusText}</span>{r.status === 'LENT' && <div className="text-xs text-muted-foreground">请联系持有人确认</div>}</td>
                  <td className="py-2 pr-3">
                    {r.status === 'USING' && <Button variant="accent" className="h-7 px-2 text-xs" onClick={() => openFinish(r)}>借用完毕</Button>}
                    {r.status === 'PENDING' && <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => cancel(r)}>取消</Button>}
                  </td>
                </tr>
              ))}
              {mine.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">还没有借用记录（在「申购」页查重命中可借药品时可发起；公用药品可直接取用）</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>我的借出（{toMe.length}）· 别人想借我的药品</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">借用人</th><th className="py-2 pr-3 font-medium">药品</th>
              <th className="py-2 pr-3 font-medium">余量/位置</th><th className="py-2 pr-3 font-medium">状态</th><th className="py-2 pr-3 font-medium">操作</th>
            </tr></thead>
            <tbody>
              {toMe.map((r) => (
                <tr key={r.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3 font-medium text-foreground">{r.borrowerName}</td>
                  <td className="py-2 pr-3">{r.chemicalName}{r.scope === 'PUBLIC' && <span className="ml-1 rounded bg-primary/10 px-1 py-0.5 text-xs text-primary">公用</span>}<div className="text-xs text-muted-foreground">{r.cas}</div></td>
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

      {fin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setFin(null)}>
          <div className="w-full max-w-md rounded-lg bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-3 text-base font-semibold text-foreground">借用完毕 · {fin.chemicalName}</h3>
            <div className="space-y-3">
              <div><Label>当前余量</Label>
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={fLv} onChange={(e) => setFLv(e.target.value)}>
                  {LEVELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              </div>
              <div><Label>存放位置</Label><Input value={fLoc} onChange={(e) => setFLoc(e.target.value)} placeholder="放回处 / 你的工位" /></div>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={fFull} onChange={(e) => setFFull(e.target.checked)} />全部领用（剩余整瓶归我，划入我的药品）</label>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setFin(null)}>取消</Button>
                <Button variant="accent" onClick={submitFinish}>确认登记</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
""")

# ---------- Purchases：公用借用提示语 ----------
pyedit(W + "/src/pages/Purchases.tsx", [
  ["""    try { await http.post('/borrow', { batchId: b.batchId }); setMsg(`✅ 已发起借用申请（对方：${b.sharedBy || b.ownerName || '持有人'}），请联系持有人确认药品情况；进度见「借用申请」`) }""",
   """    try {
      await http.post('/borrow', { batchId: b.batchId })
      if (b.scope === 'PUBLIC') setMsg('✅ 公用药品可直接取用，用完后到「借用申请」点『借用完毕』登记余量/位置')
      else setMsg(`✅ 已发起借用申请（对方：${b.sharedBy || b.ownerName || '持有人'}），请联系持有人确认药品情况；进度见「借用申请」`)
    }"""],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (W, SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\\.js' | head -1")
cli.close()
print("\n=== DONE ===")
