import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"
SITE = "/www/wwwroot/lab.dhupi.cn"
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
    if out: print(out[-2400:])
    if err: print("[stderr]", err[-1200:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(W, ''))

step("装 react-router/zustand/axios", PATHX + "cd %s && npm i react-router-dom zustand axios 2>&1 | tail -2" % W, 240)

print("\n#### 写主题 + 组件 + 页面")
wfile(W+"/src/index.css", """@import \"tailwindcss\";

:root {
  --radius: 0.625rem;
  --background: #F8FAFC;
  --foreground: #334155;
  --card: #FFFFFF;
  --card-foreground: #334155;
  --popover: #FFFFFF;
  --popover-foreground: #334155;
  --primary: #1E3A8A;
  --primary-foreground: #FFFFFF;
  --secondary: #E2E8F0;
  --secondary-foreground: #334155;
  --muted: #F1F5F9;
  --muted-foreground: #64748B;
  --accent: #D97706;
  --accent-foreground: #FFFFFF;
  --destructive: #DC2626;
  --border: #E2E8F0;
  --input: #CBD5E1;
  --ring: #1E3A8A;
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
}

* { border-color: var(--border); }
html, body, #root { height: 100%; }
body { margin: 0; background-color: var(--background); color: var(--foreground); font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", \"Microsoft YaHei\", sans-serif; }
""")
wfile(W+"/src/lib/utils.ts", """import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
""")
wfile(W+"/src/components/ui/button.tsx", """import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm',
        accent: 'bg-accent text-accent-foreground hover:bg-accent/90 shadow-sm',
        outline: 'border border-input bg-background hover:bg-muted',
        ghost: 'hover:bg-muted',
        link: 'text-primary underline-offset-4 hover:underline',
        destructive: 'bg-destructive text-white hover:bg-destructive/90',
      },
      size: { default: 'h-9 px-4 py-2', sm: 'h-8 px-3 text-xs', lg: 'h-11 px-6 text-base', icon: 'h-9 w-9' },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
)
Button.displayName = 'Button'
export { buttonVariants }
""")
wfile(W+"/src/components/ui/card.tsx", """import * as React from 'react'
import { cn } from '@/lib/utils'
type D = React.HTMLAttributes<HTMLDivElement>
export const Card = ({ className, ...p }: D) => <div className={cn('rounded-xl border border-border bg-card text-card-foreground shadow-sm', className)} {...p} />
export const CardHeader = ({ className, ...p }: D) => <div className={cn('flex flex-col gap-1.5 p-6', className)} {...p} />
export const CardTitle = ({ className, ...p }: D) => <div className={cn('font-semibold leading-none tracking-tight', className)} {...p} />
export const CardDescription = ({ className, ...p }: D) => <div className={cn('text-sm text-muted-foreground', className)} {...p} />
export const CardContent = ({ className, ...p }: D) => <div className={cn('p-6 pt-0', className)} {...p} />
export const CardFooter = ({ className, ...p }: D) => <div className={cn('flex items-center p-6 pt-0', className)} {...p} />
""")
wfile(W+"/src/components/ui/input.tsx", """import * as React from 'react'
import { cn } from '@/lib/utils'
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input type={type} ref={ref}
      className={cn('flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50', className)}
      {...props} />
  ),
)
Input.displayName = 'Input'
""")
wfile(W+"/src/components/ui/label.tsx", """import * as React from 'react'
import { cn } from '@/lib/utils'
export const Label = ({ className, ...p }: React.LabelHTMLAttributes<HTMLLabelElement>) => (
  <label className={cn('text-sm font-medium leading-none text-foreground', className)} {...p} />
)
""")
wfile(W+"/src/lib/api.ts", """import axios from 'axios'
const http = axios.create({ baseURL: '/api', timeout: 15000 })
http.interceptors.request.use((c) => { const t = localStorage.getItem('plm_token'); if (t) c.headers.Authorization = 'Bearer ' + t; return c })
http.interceptors.response.use(
  (r) => r.data,
  (e) => {
    if (e.response?.status === 401) { localStorage.removeItem('plm_token'); if (location.pathname !== '/login') location.href = '/login' }
    let m = e.response?.data?.message || e.message || '请求失败'
    if (Array.isArray(m)) m = m.join('; ')
    return Promise.reject(new Error(m))
  },
)
export default http
""")
wfile(W+"/src/store/auth.ts", """import { create } from 'zustand'
import http from '../lib/api'
interface Me { id: number; username: string; name: string; role: string; groupId: number | null }
interface S { token: string; user: Me | null; login: (u: string, p: string) => Promise<void>; fetchMe: () => Promise<void>; logout: () => void }
export const useAuth = create<S>((set) => ({
  token: localStorage.getItem('plm_token') || '',
  user: null,
  login: async (username, password) => { const d: any = await http.post('/auth/login', { username, password }); localStorage.setItem('plm_token', d.token); set({ token: d.token, user: d.user }) },
  fetchMe: async () => { const u: any = await http.get('/users/me'); set({ user: u }) },
  logout: () => { localStorage.removeItem('plm_token'); set({ token: '', user: null }) },
}))
""")
wfile(W+"/src/main.tsx", """import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <StrictMode><BrowserRouter><App /></BrowserRouter></StrictMode>,
)
""")
wfile(W+"/src/App.tsx", """import { type ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'

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
      </Route>
    </Routes>
  )
}
""")
wfile(W+"/src/layouts/MainLayout.tsx", """import { useEffect } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import { Button } from '@/components/ui/button'

const roleMap: Record<string, string> = { ADMIN: '管理员', TUTOR: '导师', STUDENT: '学生' }
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
          <Link to=\"/\" className=\"block rounded-md bg-primary/10 px-3 py-2 text-sm font-medium text-primary\">工作台</Link>
        </aside>
        <main className=\"flex-1 p-6\"><Outlet /></main>
      </div>
    </div>
  )
}
""")
wfile(W+"/src/pages/Login.tsx", """import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../store/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function Login() {
  const [username, setU] = useState('')
  const [password, setP] = useState('')
  const [loading, setL] = useState(false)
  const [err, setErr] = useState('')
  const { login } = useAuth()
  const nav = useNavigate()
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr('')
    if (!username || !password) { setErr('请输入用户名和密码'); return }
    setL(true)
    try { await login(username, password); nav('/') } catch (e: any) { setErr(e.message || '登录失败') } finally { setL(false) }
  }
  return (
    <div className=\"flex min-h-screen items-center justify-center bg-gradient-to-br from-primary to-[#0f2566] p-4\">
      <Card className=\"w-full max-w-sm\">
        <CardHeader><CardTitle className=\"text-center text-xl text-primary\">聚酰亚胺实验室管理系统</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className=\"space-y-4\">
            <div className=\"space-y-1.5\"><Label>用户名</Label><Input value={username} onChange={(e) => setU(e.target.value)} placeholder=\"用户名\" /></div>
            <div className=\"space-y-1.5\"><Label>密码</Label><Input type=\"password\" value={password} onChange={(e) => setP(e.target.value)} placeholder=\"密码\" /></div>
            {err && <p className=\"text-sm text-destructive\">{err}</p>}
            <Button type=\"submit\" className=\"w-full\" disabled={loading}>{loading ? '登录中…' : '登 录'}</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
""")
wfile(W+"/src/pages/Dashboard.tsx", """import { useAuth } from '../store/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function Dashboard() {
  const { user } = useAuth()
  const cards: [string, string][] = [['—', '待我审批'], ['—', '我的预约'], ['—', '低库存预警']]
  return (
    <div className=\"space-y-4\">
      <Card>
        <CardHeader><CardTitle>工作台</CardTitle></CardHeader>
        <CardContent>
          <p className=\"text-muted-foreground\">欢迎，{user?.name || '用户'}！系统已上线，后续模块（药品管理、仪器预约）将陆续开放。</p>
          <div className=\"mt-4\"><Button variant=\"accent\">立即预约（高亮按钮示例）</Button></div>
        </CardContent>
      </Card>
      <div className=\"grid grid-cols-3 gap-4\">
        {cards.map(([n, l]) => (
          <Card key={l}><CardContent className=\"pt-6 text-center\"><div className=\"text-3xl font-bold text-primary\">{n}</div><div className=\"mt-1 text-sm text-muted-foreground\">{l}</div></CardContent></Card>
        ))}
      </div>
    </div>
  )
}
""")
wfile(W+"/index.html", """<!doctype html>
<html lang=\"zh-CN\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>聚酰亚胺实验室管理系统</title>
  </head>
  <body>
    <div id=\"root\"></div>
    <script type=\"module\" src=\"/src/main.tsx\"></script>
  </body>
</html>
""")
step("改 build 脚本为 vite build", "cd %s && sed -i 's#\"build\": \"[^\"]*\"#\"build\": \"vite build\"#' package.json && grep '\"build\"' package.json" % W)
step("构建", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -14" % W, 420)
step("部署到站点根目录", "ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; ls %s | head" % (W, SITE, SITE, W, SITE, SITE, SITE))
step("自检 8080 首页", "curl -s http://127.0.0.1:8080/ | head -c 420; echo")
step("自检 8080 资源+API", "A=$(curl -s http://127.0.0.1:8080/ | grep -oE '/assets/[^\"]+\\.js' | head -1); echo asset=$A; curl -s -o /dev/null -w 'asset=%{http_code}\\n' http://127.0.0.1:8080$A; curl -s http://127.0.0.1:8080/api/health; echo")
cli.close()
print("\n=== DONE ===")
