import os, sys, json
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
W = "/www/wwwroot/plm-web"
SITE = "/www/wwwroot/lab.dhupi.cn"
ADMINPW = "Pniaef6b526!"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
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
    print("  写", path)

# --- 修后端 TS 报错 + 重建 ---
step("修后端类型报错", "sed -i 's#const c = await this.chem.save#const c: any = await this.chem.save#' %s/src/chemicals/chemicals.service.ts && echo ok" % APP)
step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -5 && echo OK; pm2 restart plm-api >/dev/null 2>&1; echo restarted" % APP, 300)

# --- 前端页面 ---
wfile(W+"/src/pages/Chemicals.tsx", """import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface Batch { id: number; batchNo: string; scope: string; ownerName: string | null; shareable: boolean; remainLevel: string; expiry: string | null }
interface Chem { id: number; name: string; aliases: string[] | null; cas: string | null; hazardLevel: string; unit: string; location: string | null; safetyStock: string; batches: Batch[] }

const hazardMap: Record<string, { t: string; c: string }> = {
  LOW: { t: '低危', c: 'bg-slate-100 text-slate-600' },
  MODERATE: { t: '中危', c: 'bg-blue-100 text-blue-800' },
  HIGH: { t: '高危', c: 'bg-amber-100 text-amber-800' },
  CONTROLLED: { t: '管控', c: 'bg-red-100 text-red-700' },
}
const levelMap: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' }

export default function Chemicals() {
  const [kw, setKw] = useState('')
  const [hazard, setHazard] = useState('')
  const [list, setList] = useState<Chem[]>([])
  const [loading, setLoading] = useState(false)
  async function load() {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      if (kw) p.set('keyword', kw)
      if (hazard) p.set('hazard', hazard)
      const d: any = await http.get('/chemicals?' + p.toString())
      setList(d)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])
  return (
    <div className=\"space-y-4\">
      <Card>
        <CardHeader><CardTitle>药品库（全实验室共享 · 申购前先看这里）</CardTitle></CardHeader>
        <CardContent>
          <div className=\"flex flex-wrap items-center gap-2\">
            <Input className=\"max-w-xs\" placeholder=\"搜索 名称 / 拼音 / CAS / 别名\" value={kw}
              onChange={(e) => setKw(e.target.value)} onKeyUp={(e) => { if (e.key === 'Enter') load() }} />
            <select className=\"h-9 rounded-md border border-input bg-background px-3 text-sm\" value={hazard} onChange={(e) => setHazard(e.target.value)}>
              <option value=\"\">全部危险等级</option>
              <option value=\"LOW\">低危</option>
              <option value=\"MODERATE\">中危</option>
              <option value=\"HIGH\">高危</option>
              <option value=\"CONTROLLED\">管控</option>
            </select>
            <Button onClick={load} disabled={loading}>{loading ? '查询中…' : '搜索'}</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className=\"overflow-x-auto pt-6\">
          <table className=\"w-full text-sm\">
            <thead>
              <tr className=\"border-b border-border text-left text-muted-foreground\">
                <th className=\"py-2 pr-3 font-medium\">名称 / 别名</th>
                <th className=\"py-2 pr-3 font-medium\">CAS</th>
                <th className=\"py-2 pr-3 font-medium\">危险</th>
                <th className=\"py-2 pr-3 font-medium\">位置</th>
                <th className=\"py-2 pr-3 font-medium\">库存（持有人 / 余量）</th>
              </tr>
            </thead>
            <tbody>
              {list.map((c) => (
                <tr key={c.id} className=\"border-b border-border/60 align-top\">
                  <td className=\"py-2 pr-3\">
                    <div className=\"font-medium text-foreground\">{c.name}</div>
                    {c.aliases?.length ? <div className=\"text-xs text-muted-foreground\">{c.aliases.join(' / ')}</div> : null}
                  </td>
                  <td className=\"py-2 pr-3 text-muted-foreground\">{c.cas || '—'}</td>
                  <td className=\"py-2 pr-3\"><span className={'inline-block rounded px-2 py-0.5 text-xs ' + (hazardMap[c.hazardLevel]?.c || '')}>{hazardMap[c.hazardLevel]?.t || c.hazardLevel}</span></td>
                  <td className=\"py-2 pr-3 text-muted-foreground\">{c.location || '—'}</td>
                  <td className=\"py-2 pr-3\">
                    {c.batches.length === 0 ? <span className=\"text-muted-foreground\">无库存</span> : (
                      <div className=\"flex flex-col gap-1\">
                        {c.batches.map((b) => (
                          <div key={b.id} className=\"flex items-center gap-2\">
                            <span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>
                              {b.scope === 'PUBLIC' ? '公用' : (b.ownerName || '个人')}
                            </span>
                            <span className=\"text-foreground\">{levelMap[b.remainLevel] || b.remainLevel}</span>
                            {b.shareable && <span className=\"text-xs font-medium text-accent\">可借</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {list.length === 0 && !loading && <tr><td colSpan={5} className=\"py-8 text-center text-muted-foreground\">没有匹配的药品</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
""")
wfile(W+"/src/App.tsx", """import { type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Chemicals from './pages/Chemicals'

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
      </Route>
    </Routes>
  )
}
""")
wfile(W+"/src/layouts/MainLayout.tsx", """import { useEffect } from 'react'
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

tok, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"%s\"}'" % ADMINPW)
try:
    token = json.loads(tok).get("token")
except Exception:
    token = None
step("自检 8080 首页", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\\.js' | head -1")
if token:
    step("自检 经8080的 /api/chemicals", "curl -s 'http://127.0.0.1:8080/api/chemicals?keyword=dmf' -H 'Authorization: Bearer %s' | python3 -c \"import sys,json;d=json.load(sys.stdin);print('命中:',[c['name'] for c in d])\"" % token)
cli.close()
print("\n=== DONE ===")
