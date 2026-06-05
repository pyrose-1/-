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
    if out: print(out[-2200:])
    if err: print("[stderr]", err[-1000:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(W, ""))

wfile(W + "/src/pages/Purchases.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface Bat { scope: string; ownerName: string | null; remainText: string; borrowable: boolean }
interface Matched { chemicalId: number; name: string; batches: Bat[] }
interface Precheck { hazmat: { listed: boolean; toxic: boolean; names: string[] }; matched: Matched[]; hasStock: boolean; hasBorrowable: boolean }
interface Req { id: number; name: string; cas: string | null; productNo: string | null; price: string | null; quantity: string | null; unit: string | null; reason: string | null; urgency: string; status: string; hazmatListed: boolean; hazmatToxic: boolean; dupNote: string | null; applicantName: string; tutorName: string | null; reviewerName: string | null; reviewComment: string | null; stockLocation: string | null; stockedAt: string | null; createdAt: string }
interface Tutor { id: number; name: string }

const statusMap: Record<string, { t: string; c: string }> = {
  DRAFT: { t: '待提交', c: 'bg-slate-100 text-slate-600' },
  PENDING: { t: '待审批', c: 'bg-amber-100 text-amber-800' },
  APPROVED: { t: '已通过·入库', c: 'bg-green-100 text-green-700' },
  REJECTED: { t: '已驳回', c: 'bg-red-100 text-red-700' },
}
const empty = { name: '', cas: '', productNo: '', price: '', quantity: '', unit: 'mL', reason: '', urgency: 'NORMAL' }

export default function Purchases() {
  const { user } = useAuth()
  const isReviewer = user?.role === 'ADMIN' || user?.role === 'TUTOR'
  const myTutorId = (user as any)?.tutorId as number | undefined
  const [f, setF] = useState({ ...empty })
  const [pc, setPc] = useState<Precheck | null>(null)
  const [ack, setAck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [drafts, setDrafts] = useState<Req[]>([])
  const [submitted, setSubmitted] = useState<Req[]>([])
  const [pending, setPending] = useState<Req[]>([])
  const [tutors, setTutors] = useState<Tutor[]>([])
  const [tutorId, setTutorId] = useState<number | ''>('')

  function set(k: string, v: string) { setF((s) => ({ ...s, [k]: v })) }

  async function precheck() {
    if (!f.name && !f.cas) { setPc(null); return }
    const p = new URLSearchParams()
    if (f.name) p.set('name', f.name)
    if (f.cas) p.set('cas', f.cas)
    const d: any = await http.get('/purchases/precheck?' + p.toString())
    setPc(d); setAck(false)
  }

  async function loadLists() {
    const mine: any = await http.get('/purchases?scope=mine')
    setDrafts(mine.filter((r: Req) => r.status === 'DRAFT'))
    setSubmitted(mine.filter((r: Req) => r.status !== 'DRAFT'))
    if (isReviewer) { const p: any = await http.get('/purchases?status=PENDING'); setPending(p) }
  }
  useEffect(() => {
    loadLists()
    http.get('/users/tutors').then((t: any) => { setTutors(t); if (myTutorId) setTutorId(myTutorId) })
  }, [isReviewer])

  const needAck = !!pc && (pc.hasStock || pc.hasBorrowable)

  async function addToCart() {
    setMsg('')
    if (!f.name) { setMsg('请填写药品名称'); return }
    if (needAck && !ack) { setMsg('库内已有库存或可借，请先勾选确认仍需采购'); return }
    setBusy(true)
    try {
      await http.post('/purchases', { ...f, ackDup: ack })
      setF({ ...empty }); setPc(null); setAck(false); setMsg('✅ 已加入申购清单')
      loadLists()
    } catch (e: any) {
      if (e.data?.code === 'DUP_NEEDS_ACK') { setPc(e.data.precheck); setMsg('⚠ ' + e.message) }
      else setMsg('加入失败：' + e.message)
    } finally { setBusy(false) }
  }

  async function sendToTutor() {
    if (!drafts.length) { setMsg('清单为空'); return }
    if (!tutorId) { setMsg('请选择审核导师'); return }
    setBusy(true)
    try {
      const r: any = await http.post('/purchases/submit', { tutorId })
      setMsg(`✅ 已发送 ${r.submitted} 项给${r.tutor}审核`)
      loadLists()
    } catch (e: any) { setMsg('发送失败：' + e.message) } finally { setBusy(false) }
  }

  async function delDraft(id: number) { await http.delete('/purchases/' + id); loadLists() }

  async function approve(r: Req) {
    const location = window.prompt(`通过【${r.name}】并自动入库，存放位置：`, r.stockLocation || 'B柜')
    if (location === null) return
    const comment = window.prompt('审批意见（可空）', '同意') || ''
    await http.post(`/purchases/${r.id}/approve`, { comment, location })
    loadLists()
  }
  async function reject(r: Req) {
    const comment = window.prompt('驳回理由', '')
    if (comment === null) return
    await http.post(`/purchases/${r.id}/reject`, { comment })
    loadLists()
  }

  return (
    <div className="space-y-4">
      {/* 录入 */}
      <Card>
        <CardHeader><CardTitle>申购录入（加入清单前自动查重 + 危化品识别）</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div><Label>药品名称 *</Label><Input value={f.name} onChange={(e) => set('name', e.target.value)} onBlur={precheck} placeholder="DMF / N,N-二甲基甲酰胺" /></div>
            <div><Label>CAS 号</Label><Input value={f.cas} onChange={(e) => set('cas', e.target.value)} onBlur={precheck} placeholder="68-12-2" /></div>
            <div><Label>采购货号</Label><Input value={f.productNo} onChange={(e) => set('productNo', e.target.value)} placeholder="供应商货号" /></div>
            <div><Label>价格(元)</Label><Input value={f.price} onChange={(e) => set('price', e.target.value)} placeholder="如 85.00" /></div>
            <div><Label>数量</Label><Input value={f.quantity} onChange={(e) => set('quantity', e.target.value)} placeholder="500" /></div>
            <div><Label>单位</Label>
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={f.unit} onChange={(e) => set('unit', e.target.value)}>
                {['mL', 'L', 'g', 'kg', '瓶', '个'].map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><Label>用途说明</Label><Input value={f.reason} onChange={(e) => set('reason', e.target.value)} placeholder="用于…" /></div>
            <div><Label>紧急程度</Label>
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={f.urgency} onChange={(e) => set('urgency', e.target.value)}>
                <option value="NORMAL">常规</option><option value="URGENT">紧急</option>
              </select>
            </div>
          </div>

          {pc && (
            <div className="space-y-2">
              {pc.hazmat.listed && (
                <div className={'rounded-md border p-2 text-sm ' + (pc.hazmat.toxic ? 'border-red-300 bg-red-50' : 'border-amber-300 bg-amber-50')}>
                  {pc.hazmat.toxic ? '☠ 危险化学品 · 剧毒品' : '⚠ 危险化学品'}（{pc.hazmat.names.join('、')}）— 入库领用须按危化品规程。
                </div>
              )}
              {pc.matched.length > 0 ? (
                <div className="rounded-md border border-blue-300 bg-blue-50 p-3 text-sm">
                  <div className="font-semibold">🔎 查重：库内已有，建议先借用，避免重复采购</div>
                  {pc.matched.map((m) => (
                    <div key={m.chemicalId} className="mt-1">
                      <span className="font-medium">{m.name}</span>
                      <span className="ml-2 text-muted-foreground">{m.batches.map((b) => (b.scope === 'PUBLIC' ? '公用' : b.ownerName || '个人') + b.remainText + (b.borrowable ? '【可借】' : '')).join('、') || '无库存'}</span>
                    </div>
                  ))}
                  {needAck && (
                    <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />我已确认无法借用/库存不足，仍需采购</label>
                  )}
                </div>
              ) : <div className="rounded-md border border-green-300 bg-green-50 p-2 text-sm">✓ 库内暂无同款，可正常申购。</div>}
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={precheck} type="button">查重 / 检索</Button>
            <Button onClick={addToCart} disabled={busy}>加入申购清单</Button>
            {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
          </div>
        </CardContent>
      </Card>

      {/* 我的清单（待提交） */}
      <Card>
        <CardHeader><CardTitle>我的申购清单（待提交 · {drafts.length}）</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <ReqTable rows={drafts} empty="清单为空，先在上方加入药品" actions={(r) => <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => delDraft(r.id)}>移除</Button>} />
          {drafts.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
              <Label className="m-0">发送给导师：</Label>
              <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={tutorId} onChange={(e) => setTutorId(e.target.value ? +e.target.value : '')}>
                <option value="">请选择导师</option>
                {tutors.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              <Button variant="accent" onClick={sendToTutor} disabled={busy}>发送给导师审核</Button>
            </div>
          )}
        </CardContent>
      </Card>

      {isReviewer && (
        <Card>
          <CardHeader><CardTitle>待我审批（{pending.length}）· 仅本人学生</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <ReqTable rows={pending} empty="暂无待审批" showApplicant actions={(r) => (
              <div className="flex gap-2">
                <Button className="h-7 px-2 text-xs" onClick={() => approve(r)}>通过+入库</Button>
                <Button variant="destructive" className="h-7 px-2 text-xs" onClick={() => reject(r)}>驳回</Button>
              </div>
            )} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>我的申购记录</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <ReqTable rows={submitted} empty="还没有已提交的申购" />
        </CardContent>
      </Card>
    </div>
  )

  function ReqTable({ rows, empty, actions, showApplicant }: { rows: Req[]; empty: string; actions?: (r: Req) => any; showApplicant?: boolean }) {
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 pr-3 font-medium">药品 / CAS</th>
            <th className="py-2 pr-3 font-medium">货号 / 价格</th>
            <th className="py-2 pr-3 font-medium">数量</th>
            {showApplicant && <th className="py-2 pr-3 font-medium">申请人</th>}
            <th className="py-2 pr-3 font-medium">状态</th>
            <th className="py-2 pr-3 font-medium">说明 / 入库 / 审批</th>
            {actions && <th className="py-2 pr-3 font-medium"></th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-border/60 align-top">
              <td className="py-2 pr-3">
                <div className="font-medium text-foreground">
                  {r.name}
                  {r.hazmatListed && <span className={'ml-1 rounded px-1 py-0.5 text-xs ' + (r.hazmatToxic ? 'bg-red-600 text-white' : 'bg-red-100 text-red-700')}>{r.hazmatToxic ? '剧毒' : '危化'}</span>}
                  {r.urgency === 'URGENT' && <span className="ml-1 rounded bg-orange-100 px-1 py-0.5 text-xs text-orange-700">急</span>}
                </div>
                <div className="text-xs text-muted-foreground">{r.cas || '—'}</div>
              </td>
              <td className="py-2 pr-3 text-muted-foreground">{r.productNo || '—'}<br />{r.price ? '¥' + r.price : '—'}</td>
              <td className="py-2 pr-3 text-muted-foreground">{r.quantity || '—'}{r.unit || ''}</td>
              {showApplicant && <td className="py-2 pr-3 text-muted-foreground">{r.applicantName}</td>}
              <td className="py-2 pr-3"><span className={'rounded px-2 py-0.5 text-xs ' + (statusMap[r.status]?.c || '')}>{statusMap[r.status]?.t || r.status}</span></td>
              <td className="py-2 pr-3 text-xs text-muted-foreground">
                {r.reason && <div>{r.reason}</div>}
                {r.dupNote && <div className="text-amber-700">查重: {r.dupNote}</div>}
                {r.status === 'APPROVED' && <div className="text-green-700">已入库 → {r.stockLocation || '—'} · {r.stockedAt ? r.stockedAt.slice(0, 10) : ''}（归 {r.applicantName}）</div>}
                {r.reviewerName && <div>审批: {r.reviewerName} {r.reviewComment ? '「' + r.reviewComment + '」' : ''}</div>}
                {r.status === 'PENDING' && r.tutorName && <div>待 {r.tutorName} 审核</div>}
              </td>
              {actions && <td className="py-2 pr-3">{actions(r)}</td>}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={showApplicant ? 7 : 6} className="py-6 text-center text-muted-foreground">{empty}</td></tr>}
        </tbody>
      </table>
    )
  }
}
""")

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (W, SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\\.js' | head -1")
cli.close()
print("\n=== DONE ===")
