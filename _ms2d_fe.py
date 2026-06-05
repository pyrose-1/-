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

# ---------- Chemicals.tsx：危险列改“是否危化品” ----------
wfile(W + "/src/pages/Chemicals.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface Batch { id: number; batchNo: string; scope: string; ownerName: string | null; shareable: boolean; remainLevel: string }
interface Hazmat { cas: string; listed: boolean; toxic: boolean; names: string[]; alias: string | null }
interface Chem { id: number; name: string; aliases: string[] | null; cas: string | null; location: string | null; batches: Batch[]; hazmat?: Hazmat }

const levelMap: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' }

export default function Chemicals() {
  const [kw, setKw] = useState('')
  const [filter, setFilter] = useState('')   // '' | YES | NO
  const [list, setList] = useState<Chem[]>([])
  const [loading, setLoading] = useState(false)

  const [casQ, setCasQ] = useState('')
  const [casRes, setCasRes] = useState<Hazmat | null>(null)
  const [casLoading, setCasLoading] = useState(false)
  async function checkCas() {
    const c = casQ.trim(); if (!c) return
    setCasLoading(true)
    try { const d: any = await http.get('/hazmat/lookup?cas=' + encodeURIComponent(c)); setCasRes(d) } finally { setCasLoading(false) }
  }

  async function load() {
    setLoading(true)
    try {
      const p = new URLSearchParams(); if (kw) p.set('keyword', kw)
      const d: any = await http.get('/chemicals?' + p.toString())
      setList(d)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const shown = list.filter((c) => filter === '' ? true : filter === 'YES' ? c.hazmat?.listed : !c.hazmat?.listed)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>CAS 危化品速查（对照《危险化学品目录》2015 · 2657 个 CAS）</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <Input className="max-w-xs" placeholder="录入 CAS 号，如 68-12-2" value={casQ}
              onChange={(e) => setCasQ(e.target.value)} onKeyUp={(e) => { if (e.key === 'Enter') checkCas() }} />
            <Button variant="accent" onClick={checkCas} disabled={casLoading}>{casLoading ? '检索中…' : '检索'}</Button>
          </div>
          {casRes && (casRes.listed ? (
            <div className={'mt-3 rounded-md border p-3 text-sm ' + (casRes.toxic ? 'border-red-300 bg-red-50' : 'border-amber-300 bg-amber-50')}>
              <div className="font-semibold text-foreground">{casRes.toxic ? '☠ 危险化学品 · 剧毒品' : '⚠ 危险化学品'}<span className="ml-2 font-normal text-muted-foreground">CAS {casRes.cas}</span></div>
              <div className="mt-1 text-foreground">目录名称：{casRes.names.join('、') || '—'}</div>
              {casRes.alias && <div className="text-xs text-muted-foreground">别名：{casRes.alias}</div>}
            </div>
          ) : (
            <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
              <span className="font-semibold text-foreground">未收录</span>
              <span className="ml-2 text-muted-foreground">CAS {casRes.cas} 不在《危险化学品目录》内。</span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>药品库（全实验室共享 · 申购前先看这里）</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <Input className="max-w-xs" placeholder="搜索 名称 / 拼音 / CAS / 别名" value={kw}
              onChange={(e) => setKw(e.target.value)} onKeyUp={(e) => { if (e.key === 'Enter') load() }} />
            <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">全部</option>
              <option value="YES">仅危化品</option>
              <option value="NO">仅非危化品</option>
            </select>
            <Button onClick={load} disabled={loading}>{loading ? '查询中…' : '搜索'}</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="overflow-x-auto pt-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-2 pr-3 font-medium">名称 / 别名</th>
                <th className="py-2 pr-3 font-medium">CAS</th>
                <th className="py-2 pr-3 font-medium">是否危化品</th>
                <th className="py-2 pr-3 font-medium">位置</th>
                <th className="py-2 pr-3 font-medium">库存（持有人 / 余量）</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((c) => (
                <tr key={c.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-medium text-foreground">{c.name}</div>
                    {c.aliases?.length ? <div className="text-xs text-muted-foreground">{c.aliases.join(' / ')}</div> : null}
                  </td>
                  <td className="py-2 pr-3 text-muted-foreground">{c.cas || '—'}</td>
                  <td className="py-2 pr-3">
                    {c.hazmat?.listed
                      ? (c.hazmat.toxic
                        ? <span className="inline-block rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white">是 · 剧毒</span>
                        : <span className="inline-block rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">是</span>)
                      : <span className="inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">否</span>}
                  </td>
                  <td className="py-2 pr-3 text-muted-foreground">{c.location || '—'}</td>
                  <td className="py-2 pr-3">
                    {c.batches.length === 0 ? <span className="text-muted-foreground">无库存</span> : (
                      <div className="flex flex-col gap-1">
                        {c.batches.map((b) => (
                          <div key={b.id} className="flex items-center gap-2">
                            <span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>{b.scope === 'PUBLIC' ? '公用' : (b.ownerName || '个人')}</span>
                            <span className="text-foreground">{levelMap[b.remainLevel] || b.remainLevel}</span>
                            {b.shareable && <span className="text-xs font-medium text-accent">可借</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {shown.length === 0 && !loading && <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">没有匹配的药品</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
""")

# ---------- MyChemicals.tsx（我的药品，可维护 存放地点/剩余情况） ----------
wfile(W + "/src/pages/MyChemicals.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface Item { batchId: number; batchNo: string; name: string; cas: string | null; hazmat?: { listed: boolean; toxic: boolean }; price: string | null; productNo: string | null; quantity: string | null; unit: string | null; purchaseDate: string | null; location: string | null; remainLevel: string }
const LEVELS = [['FULL', '满'], ['ALMOST_FULL', '几乎满'], ['HALF', '半瓶'], ['LOW', '快没了'], ['LITTLE', '一点点'], ['EMPTY', '空']]

function Row({ it, onSaved }: { it: Item; onSaved: () => void }) {
  const [loc, setLoc] = useState(it.location || '')
  const [lv, setLv] = useState(it.remainLevel)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const dirty = loc !== (it.location || '') || lv !== it.remainLevel
  async function save() {
    setSaving(true)
    try { await http.put('/inventory/batches/' + it.batchId, { location: loc, remainLevel: lv }); setDone(true); setTimeout(() => setDone(false), 1500); onSaved() }
    finally { setSaving(false) }
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
      <td className="py-2 pr-3 text-foreground">{it.price ? '¥' + it.price : '—'}</td>
      <td className="py-2 pr-3 text-muted-foreground">{it.purchaseDate ? String(it.purchaseDate).slice(0, 10) : '—'}</td>
      <td className="py-2 pr-3"><Input className="h-8 w-36" value={loc} onChange={(e) => setLoc(e.target.value)} placeholder="如 B柜-2层 / 工位" /></td>
      <td className="py-2 pr-3">
        <select className="h-8 rounded-md border border-input bg-background px-2 text-sm" value={lv} onChange={(e) => setLv(e.target.value)}>
          {LEVELS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
        </select>
      </td>
      <td className="py-2 pr-3">
        <Button className="h-7 px-2 text-xs" disabled={!dirty || saving} onClick={save}>{saving ? '保存中' : done ? '已保存' : '保存'}</Button>
      </td>
    </tr>
  )
}

export default function MyChemicals() {
  const [data, setData] = useState<{ totalAmount: number; count: number; items: Item[] }>({ totalAmount: 0, count: 0, items: [] })
  async function load() { const d: any = await http.get('/inventory/mine'); setData(d) }
  useEffect(() => { load() }, [])
  return (
    <Card>
      <CardHeader><CardTitle>我的药品（共 {data.count} 瓶 · 累计采购金额 ¥{data.totalAmount?.toFixed?.(2) ?? data.totalAmount}）</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">药品 / CAS / 批次</th>
              <th className="py-2 pr-3 font-medium">货号</th>
              <th className="py-2 pr-3 font-medium">价格</th>
              <th className="py-2 pr-3 font-medium">申购日期</th>
              <th className="py-2 pr-3 font-medium">存放地点</th>
              <th className="py-2 pr-3 font-medium">剩余情况</th>
              <th className="py-2 pr-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((it) => <Row key={it.batchId} it={it} onSaved={load} />)}
            {data.items.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-muted-foreground">还没有持有的药品（申购通过后会自动归到这里）</td></tr>}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
""")

# ---------- MyStudents.tsx（导师：我的学生 -> 学生库存） ----------
wfile(W + "/src/pages/MyStudents.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface Stu { id: number; name: string; username: string; items: number; totalAmount: number }
interface Item { batchId: number; batchNo: string; name: string; cas: string | null; hazmat?: { listed: boolean; toxic: boolean }; price: string | null; productNo: string | null; purchaseDate: string | null; location: string | null; remainLevel: string }
const levelMap: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' }

export default function MyStudents() {
  const [students, setStudents] = useState<Stu[]>([])
  const [sel, setSel] = useState<Stu | null>(null)
  const [detail, setDetail] = useState<{ totalAmount: number; count: number; items: Item[] } | null>(null)

  useEffect(() => { http.get('/inventory/my-students').then((d: any) => setStudents(d)) }, [])
  async function open(s: Stu) { setSel(s); const d: any = await http.get('/inventory/student/' + s.id); setDetail(d) }

  if (sel && detail) {
    return (
      <div className="space-y-4">
        <Button variant="outline" onClick={() => { setSel(null); setDetail(null) }}>← 返回学生列表</Button>
        <Card>
          <CardHeader><CardTitle>{sel.name} 的药品库存（共 {detail.count} 瓶 · 累计采购 ¥{detail.totalAmount?.toFixed?.(2) ?? detail.totalAmount}）</CardTitle></CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">药品 / CAS</th>
                  <th className="py-2 pr-3 font-medium">货号</th>
                  <th className="py-2 pr-3 font-medium">价格</th>
                  <th className="py-2 pr-3 font-medium">申购日期</th>
                  <th className="py-2 pr-3 font-medium">存放地点</th>
                  <th className="py-2 pr-3 font-medium">剩余</th>
                </tr>
              </thead>
              <tbody>
                {detail.items.map((it) => (
                  <tr key={it.batchId} className="border-b border-border/60">
                    <td className="py-2 pr-3"><div className="font-medium text-foreground">{it.name}{it.hazmat?.listed && <span className={'ml-1 rounded px-1 py-0.5 text-xs ' + (it.hazmat.toxic ? 'bg-red-600 text-white' : 'bg-red-100 text-red-700')}>{it.hazmat.toxic ? '剧毒' : '危化'}</span>}</div><div className="text-xs text-muted-foreground">{it.cas || '—'}</div></td>
                    <td className="py-2 pr-3 text-muted-foreground">{it.productNo || '—'}</td>
                    <td className="py-2 pr-3 text-foreground">{it.price ? '¥' + it.price : '—'}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{it.purchaseDate ? String(it.purchaseDate).slice(0, 10) : '—'}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{it.location || '—'}</td>
                    <td className="py-2 pr-3 text-foreground">{levelMap[it.remainLevel] || it.remainLevel}</td>
                  </tr>
                ))}
                {detail.items.length === 0 && <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">该学生暂无持有药品</td></tr>}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>近期仪器预约记录</CardTitle></CardHeader>
          <CardContent className="py-6 text-sm text-muted-foreground">仪器预约模块开发中，稍后接入。</CardContent>
        </Card>
      </div>
    )
  }

  return (
    <Card>
      <CardHeader><CardTitle>我的学生（{students.length}）</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-3 font-medium">姓名</th>
              <th className="py-2 pr-3 font-medium">账号</th>
              <th className="py-2 pr-3 font-medium">持有药品</th>
              <th className="py-2 pr-3 font-medium">累计采购金额</th>
              <th className="py-2 pr-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.id} className="border-b border-border/60">
                <td className="py-2 pr-3 font-medium text-foreground">{s.name}</td>
                <td className="py-2 pr-3 text-muted-foreground">{s.username}</td>
                <td className="py-2 pr-3 text-muted-foreground">{s.items} 瓶</td>
                <td className="py-2 pr-3 text-foreground">¥{s.totalAmount?.toFixed?.(2) ?? s.totalAmount}</td>
                <td className="py-2 pr-3"><Button className="h-7 px-2 text-xs" onClick={() => open(s)}>查看库存</Button></td>
              </tr>
            ))}
            {students.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">暂无学生</td></tr>}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
""")

# ---------- App.tsx 路由 ----------
wfile(W + "/src/App.tsx", """import { type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Chemicals from './pages/Chemicals'
import Purchases from './pages/Purchases'
import Approvals from './pages/Approvals'
import MyChemicals from './pages/MyChemicals'
import MyStudents from './pages/MyStudents'

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
        <Route path=\"my-chemicals\" element={<MyChemicals />} />
        <Route path=\"purchases\" element={<Purchases />} />
        <Route path=\"approvals\" element={<Approvals />} />
        <Route path=\"my-students\" element={<MyStudents />} />
      </Route>
    </Routes>
  )
}
""")

# ---------- MainLayout 导航 ----------
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
  const isReviewer = user?.role === 'ADMIN' || user?.role === 'TUTOR'
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
            <NavLink to=\"/my-chemicals\" className={linkCls}>我的药品</NavLink>
            <NavLink to=\"/purchases\" className={linkCls}>申购</NavLink>
            {isReviewer && <NavLink to=\"/approvals\" className={linkCls}>审批</NavLink>}
            {isReviewer && <NavLink to=\"/my-students\" className={linkCls}>我的学生</NavLink>}
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
