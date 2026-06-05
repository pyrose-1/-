# -*- coding: utf-8 -*-
import os, sys, json
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

# ---- api.ts：错误带上原始 data ----
wfile(W + "/src/lib/api.ts", """import axios from 'axios'
const http = axios.create({ baseURL: '/api', timeout: 15000 })
http.interceptors.request.use((c) => { const t = localStorage.getItem('plm_token'); if (t) c.headers.Authorization = 'Bearer ' + t; return c })
http.interceptors.response.use(
  (r) => r.data,
  (e) => {
    if (e.response?.status === 401) { localStorage.removeItem('plm_token'); if (location.pathname !== '/login') location.href = '/login' }
    let m = e.response?.data?.message || e.message || '请求失败'
    if (Array.isArray(m)) m = m.join('; ')
    const err: any = new Error(m)
    err.data = e.response?.data
    err.status = e.response?.status
    return Promise.reject(err)
  },
)
export default http
""")

# ---- 申购页 ----
wfile(W + "/src/pages/Purchases.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface Bat { scope: string; ownerName: string | null; remainText: string; borrowable: boolean }
interface Matched { chemicalId: number; name: string; cas: string | null; hasStock: boolean; hasBorrowable: boolean; batches: Bat[] }
interface Precheck { hazmat: { listed: boolean; toxic: boolean; names: string[]; cas: string }; matched: Matched[]; hasStock: boolean; hasBorrowable: boolean; suggestion: string }
interface Req { id: number; name: string; cas: string | null; quantity: string | null; unit: string | null; reason: string | null; urgency: string; status: string; hazmatListed: boolean; hazmatToxic: boolean; dupNote: string | null; applicantName: string; reviewerName: string | null; reviewComment: string | null; createdAt: string }

const statusMap: Record<string, { t: string; c: string }> = {
  PENDING: { t: '待审批', c: 'bg-amber-100 text-amber-800' },
  APPROVED: { t: '已通过', c: 'bg-green-100 text-green-700' },
  REJECTED: { t: '已驳回', c: 'bg-red-100 text-red-700' },
  CANCELLED: { t: '已撤销', c: 'bg-slate-100 text-slate-500' },
}

export default function Purchases() {
  const { user } = useAuth()
  const isReviewer = user?.role === 'ADMIN' || user?.role === 'TUTOR'
  const [f, setF] = useState({ name: '', cas: '', quantity: '', unit: 'mL', reason: '', urgency: 'NORMAL' })
  const [pc, setPc] = useState<Precheck | null>(null)
  const [ack, setAck] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [mine, setMine] = useState<Req[]>([])
  const [pending, setPending] = useState<Req[]>([])

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
    const m: any = await http.get('/purchases?scope=mine')
    setMine(m)
    if (isReviewer) { const p: any = await http.get('/purchases?status=PENDING'); setPending(p) }
  }
  useEffect(() => { loadLists() }, [isReviewer])

  const needAck = !!pc && (pc.hasStock || pc.hasBorrowable)

  async function submit() {
    setMsg('')
    if (!f.name) { setMsg('请填写药品名称'); return }
    if (needAck && !ack) { setMsg('库内已有库存或可借，请先勾选确认仍需采购'); return }
    setBusy(true)
    try {
      await http.post('/purchases', { ...f, ackDup: ack })
      setMsg('✅ 申购单已提交，等待审批')
      setF({ name: '', cas: '', quantity: '', unit: 'mL', reason: '', urgency: 'NORMAL' })
      setPc(null); setAck(false)
      loadLists()
    } catch (e: any) {
      if (e.data?.code === 'DUP_NEEDS_ACK') { setPc(e.data.precheck); setMsg('⚠ ' + e.message) }
      else setMsg('提交失败：' + e.message)
    } finally { setBusy(false) }
  }

  async function review(id: number, action: 'approve' | 'reject') {
    const comment = window.prompt(action === 'approve' ? '审批意见（可空）' : '驳回理由', action === 'approve' ? '同意' : '')
    if (action === 'reject' && comment === null) return
    await http.post(`/purchases/${id}/${action}`, { comment })
    loadLists()
  }
  async function cancel(id: number) {
    if (!window.confirm('确认撤销该申购单？')) return
    await http.post(`/purchases/${id}/cancel`, {})
    loadLists()
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>提交申购（提交前自动查重 + 危化品识别）</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div><Label>药品名称 *</Label><Input value={f.name} onChange={(e) => set('name', e.target.value)} onBlur={precheck} placeholder="如 DMF / N,N-二甲基甲酰胺" /></div>
            <div><Label>CAS 号</Label><Input value={f.cas} onChange={(e) => set('cas', e.target.value)} onBlur={precheck} placeholder="如 68-12-2" /></div>
            <div><Label>数量</Label><Input value={f.quantity} onChange={(e) => set('quantity', e.target.value)} placeholder="如 500" /></div>
            <div><Label>单位</Label>
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={f.unit} onChange={(e) => set('unit', e.target.value)}>
                {['mL', 'L', 'g', 'kg', '瓶', '个'].map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </div>
            <div className="md:col-span-2"><Label>用途说明</Label><Input value={f.reason} onChange={(e) => set('reason', e.target.value)} placeholder="用于…" /></div>
          </div>

          {pc && (
            <div className="space-y-2">
              {pc.hazmat.listed && (
                <div className={'rounded-md border p-2 text-sm ' + (pc.hazmat.toxic ? 'border-red-300 bg-red-50' : 'border-amber-300 bg-amber-50')}>
                  {pc.hazmat.toxic ? '☠ 危险化学品 · 剧毒品' : '⚠ 危险化学品'}（{pc.hazmat.names.join('、')}）— 审批通过后须按危化品/剧毒规程入库领用。
                </div>
              )}
              {pc.matched.length > 0 ? (
                <div className="rounded-md border border-blue-300 bg-blue-50 p-3 text-sm">
                  <div className="font-semibold text-foreground">🔎 查重：库内已有同名/同 CAS 药品，建议先借用，避免重复采购</div>
                  {pc.matched.map((m) => (
                    <div key={m.chemicalId} className="mt-1">
                      <span className="font-medium">{m.name}</span>
                      <span className="ml-2 text-muted-foreground">
                        {m.batches.map((b, i) => (b.scope === 'PUBLIC' ? '公用' : b.ownerName || '个人') + b.remainText + (b.borrowable ? '【可借】' : '')).join('、') || '无库存'}
                      </span>
                    </div>
                  ))}
                  {needAck && (
                    <label className="mt-2 flex items-center gap-2 text-foreground">
                      <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
                      我已确认无法借用/现有库存不足，仍需采购
                    </label>
                  )}
                </div>
              ) : (
                <div className="rounded-md border border-green-300 bg-green-50 p-2 text-sm text-foreground">✓ 库内暂无同款，可正常申购。</div>
              )}
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={precheck} type="button">查重 / 检索</Button>
            <Button variant="accent" onClick={submit} disabled={busy}>{busy ? '提交中…' : '提交申购'}</Button>
            {msg && <span className="text-sm text-muted-foreground">{msg}</span>}
          </div>
        </CardContent>
      </Card>

      {isReviewer && (
        <Card>
          <CardHeader><CardTitle>待我审批（{pending.length}）</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <ReqTable rows={pending} empty="暂无待审批" actions={(r) => r.status === 'PENDING' ? (
              <div className="flex gap-2">
                <Button className="h-7 px-2 text-xs" onClick={() => review(r.id, 'approve')}>通过</Button>
                <Button variant="destructive" className="h-7 px-2 text-xs" onClick={() => review(r.id, 'reject')}>驳回</Button>
              </div>
            ) : null} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>我的申购</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <ReqTable rows={mine} empty="还没有申购记录" actions={(r) => r.status === 'PENDING' ? (
            <Button variant="ghost" className="h-7 px-2 text-xs" onClick={() => cancel(r.id)}>撤销</Button>
          ) : null} />
        </CardContent>
      </Card>
    </div>
  )

  function ReqTable({ rows, empty, actions }: { rows: Req[]; empty: string; actions: (r: Req) => any }) {
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 pr-3 font-medium">药品 / CAS</th>
            <th className="py-2 pr-3 font-medium">数量</th>
            <th className="py-2 pr-3 font-medium">申请人</th>
            <th className="py-2 pr-3 font-medium">状态</th>
            <th className="py-2 pr-3 font-medium">说明 / 审批</th>
            <th className="py-2 pr-3 font-medium"></th>
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
              <td className="py-2 pr-3 text-muted-foreground">{r.quantity || '—'}{r.unit || ''}</td>
              <td className="py-2 pr-3 text-muted-foreground">{r.applicantName}</td>
              <td className="py-2 pr-3"><span className={'rounded px-2 py-0.5 text-xs ' + (statusMap[r.status]?.c || '')}>{statusMap[r.status]?.t || r.status}</span></td>
              <td className="py-2 pr-3 text-xs text-muted-foreground">
                {r.reason && <div>{r.reason}</div>}
                {r.dupNote && <div className="text-amber-700">查重: {r.dupNote}</div>}
                {r.reviewerName && <div>审批: {r.reviewerName} {r.reviewComment ? '「' + r.reviewComment + '」' : ''}</div>}
              </td>
              <td className="py-2 pr-3">{actions(r)}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">{empty}</td></tr>}
        </tbody>
      </table>
    )
  }
}
""")

# ---- App.tsx 加路由 ----
wfile(W + "/src/App.tsx", """import { type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Chemicals from './pages/Chemicals'
import Purchases from './pages/Purchases'

function RequireAuth({ children }: { children: ReactElement }) {
  const token = localStorage.getItem('plm_token')
  return token ? children : <Navigate to=\"/login\" replace />
}
export default function App() {
  return (
    <Routes>
      <Route path=\"/login\" element={<Login />} />
      <Route path=\"/\" element={<RequireAuth><MainLayout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path=\"chemicals\" element={<Chemicals />} />
        <Route path=\"purchases\" element={<Purchases />} />
      </Route>
    </Routes>
  )
}
""")

# ---- MainLayout 加导航 ----
wfile(W + "/src/layouts/MainLayout.tsx", """import { useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

const roleMap: Record<string, string> = { ADMIN: '管理员', TUTOR: '导师', STUDENT: '学生' }
const linkCls = ({ isActive }: { isActive: boolean }) =>
  'block rounded-md px-3 py-2 text-sm font-medium ' + (isActive ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-muted')

export default function MainLayout() {
  const { user, fetchMe, logout } = useAuth()
  const nav = useNavigate()
  useEffect(() => { if (!user) fetchMe().catch(() => {}) }, [])
  return (
    <div className=\"min-h-screen bg-background text-foreground\">
      <header className=\"flex h-14 items-center justify-between bg-primary px-6 text-primary-foreground\">
        <span className=\"text-lg font-semibold\">聚酰亚胺实验室管理系统</span>
        <div className=\"flex items-center gap-4 text-sm\">
          <span>{user?.name || user?.username}（{roleMap[user?.role || ''] || ''}）</span>
          <button onClick={() => { logout(); nav('/login') }} className=\"rounded-md border border-white/40 px-3 py-1 text-sm hover:bg-white/10\">退出</button>
        </div>
      </header>
      <div className=\"flex\">
        <aside className=\"min-h-[calc(100vh-3.5rem)] w-52 border-r border-border bg-card p-3\">
          <nav className=\"space-y-1\">
            <NavLink to=\"/\" end className={linkCls}>工作台</NavLink>
            <NavLink to=\"/chemicals\" className={linkCls}>药品库</NavLink>
            <NavLink to=\"/purchases\" className={linkCls}>申购</NavLink>
          </nav>
        </aside>
        <main className=\"flex-1 p-6\"><Outlet /></main>
      </div>
    </div>
  )
}
""")

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (W, SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\\.js' | head -1")
cli.close()
print("\n=== DONE ===")
