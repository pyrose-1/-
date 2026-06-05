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

# ---------- 仪器页 ----------
wfile(W + "/src/pages/Instruments.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { useAuth } from '../store/auth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Inst { id: number; name: string; category: string; blockType: string; filmCapable: boolean; dryCapable: boolean; piggyback: boolean; lottery: boolean; authRequired: boolean; note: string | null; status: string }
const CAT_ORDER = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA', 'OTHER']
const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', FURNACE: '环化 / 马弗 / 管式 / BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他（随用随约）' }
const CAP: Record<string, string> = { VACUUM_OVEN: '每周 6 格（铺膜=3格 / 干燥=1格）', FURNACE: '每周 2 个全天块', POLY_HEAD: '每周 7 个半天块', DMA: '每周 4 个 4h 块', TGA: '每周 4 个 4h 块', OTHER: '不限、不抽签' }
const BLOCK_LABEL: Record<string, string> = { FOUR_HOUR: '4h 块', HALF_DAY: '半天块', FULL_DAY: '全天块', FREE: '随用随约' }

export default function Instruments() {
  const { user } = useAuth()
  const isStudent = user?.role === 'STUDENT'
  const [list, setList] = useState<Inst[]>([])
  const [myHeadIds, setMyHeadIds] = useState<number[]>([])
  useEffect(() => {
    http.get('/instruments').then((d: any) => setList(d))
    http.get('/instruments/my-heads').then((d: any) => setMyHeadIds(d.map((x: Inst) => x.id))).catch(() => {})
  }, [])

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">抽签时间线：每周日 24:00 截止报名 → 周一 02:00–04:00 系统抽签分配 → 出下一周课表；空格点击即得。导师/管理员不参与预约。</p>
      {CAT_ORDER.map((cat) => {
        let items = list.filter((x) => x.category === cat)
        if (cat === 'POLY_HEAD' && isStudent) items = items.filter((x) => myHeadIds.includes(x.id))
        if (!items.length && !(cat === 'POLY_HEAD')) return null
        return (
          <Card key={cat}>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-baseline gap-2">
                {CAT_LABEL[cat]}
                <span className="text-sm font-normal text-muted-foreground">· {BLOCK_LABEL[items[0]?.blockType] || ''} · {CAP[cat]} · 共 {items.length} 台</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {cat === 'POLY_HEAD' && isStudent && <p className="mb-2 text-xs text-muted-foreground">只显示你被授权使用的机头。</p>}
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border text-left text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">仪器名</th>
                  <th className="py-2 pr-3 font-medium">类型</th>
                  <th className="py-2 pr-3 font-medium">属性</th>
                  <th className="py-2 pr-3 font-medium">状态</th>
                </tr></thead>
                <tbody>
                  {items.map((x) => (
                    <tr key={x.id} className="border-b border-border/60">
                      <td className="py-2 pr-3 font-medium text-foreground">{x.name}{x.note ? <div className="text-xs text-muted-foreground">{x.note}</div> : null}</td>
                      <td className="py-2 pr-3 text-muted-foreground">{BLOCK_LABEL[x.blockType]}</td>
                      <td className="py-2 pr-3">
                        <div className="flex flex-wrap gap-1">
                          {x.category === 'VACUUM_OVEN' && x.filmCapable && <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">可铺膜</span>}
                          {x.category === 'VACUUM_OVEN' && x.dryCapable && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">可干燥</span>}
                          {x.piggyback && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">可蹭一下</span>}
                          {x.authRequired && <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs text-purple-700">授权制</span>}
                          {!x.lottery && <span className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">随用随约</span>}
                        </div>
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">{x.status}</td>
                    </tr>
                  ))}
                  {items.length === 0 && <tr><td colSpan={4} className="py-4 text-center text-muted-foreground">{cat === 'POLY_HEAD' ? '你暂无授权的机头，请联系管理员' : '—'}</td></tr>}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
""")

# ---------- 管理员 优先级页 ----------
wfile(W + "/src/pages/Priorities.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Row { id: number; name: string; username: string; scores: Record<string, number | null> }
const CATS = [['VACUUM_OVEN', '真空烘箱'], ['FURNACE', '环化/马弗/管式/BET'], ['POLY_HEAD', '聚合机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]

export default function Priorities() {
  const [rows, setRows] = useState<Row[]>([])
  useEffect(() => { http.get('/instruments/priorities').then((d: any) => setRows(d)) }, [])
  return (
    <Card>
      <CardHeader><CardTitle>学生优先级总表（仅管理员可见）</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <p className="mb-2 text-xs text-muted-foreground">初始 0 + 随机小数；分数越高抽签越优先。赛后：全满足 −2 / 部分(≥50%) −1 / 未提需求 0 / 少量(&lt;50%) +1 / 完全没分到 +2；全员满足且有余则重置该类。</p>
        <table className="w-full text-sm">
          <thead><tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 pr-3 font-medium">学生</th>
            {CATS.map(([k, t]) => <th key={k} className="py-2 pr-3 font-medium">{t}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-border/60">
                <td className="py-2 pr-3 font-medium text-foreground">{r.name}<span className="ml-1 text-xs text-muted-foreground">{r.username}</span></td>
                {CATS.map(([k]) => <td key={k} className="py-2 pr-3 text-foreground">{r.scores[k] != null ? Number(r.scores[k]).toFixed(3) : '—'}</td>)}
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">暂无数据</td></tr>}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
""")

# ---------- App.tsx 路由 ----------
pyedit(W + "/src/App.tsx", [
  ["import Borrow from './pages/Borrow'",
   "import Borrow from './pages/Borrow'\nimport Instruments from './pages/Instruments'\nimport Priorities from './pages/Priorities'"],
  ["""        <Route path=\"borrow\" element={<Borrow />} />""",
   """        <Route path=\"borrow\" element={<Borrow />} />
        <Route path=\"instruments\" element={<Instruments />} />
        <Route path=\"priorities\" element={<Priorities />} />"""],
])

# ---------- 导航 ----------
pyedit(W + "/src/layouts/MainLayout.tsx", [
  ["""            <NavLink to=\"/borrow\" className={linkCls}>借用申请</NavLink>""",
   """            <NavLink to=\"/borrow\" className={linkCls}>借用申请</NavLink>
            <NavLink to=\"/instruments\" className={linkCls}>仪器</NavLink>"""],
  ["""            {isReviewer && <NavLink to=\"/my-students\" className={linkCls}>我的学生</NavLink>}""",
   """            {isReviewer && <NavLink to=\"/my-students\" className={linkCls}>我的学生</NavLink>}
            {user?.role === 'ADMIN' && <NavLink to=\"/priorities\" className={linkCls}>优先级</NavLink>}"""],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close()
print("\n=== DONE ===")
