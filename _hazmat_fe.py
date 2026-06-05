# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W = "/www/wwwroot/plm-web"
SITE = "/www/wwwroot/lab.dhupi.cn"
ADMINPW = "Pniaef6b526!"
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

wfile(W + "/src/pages/Chemicals.tsx", r"""import { useEffect, useState } from 'react'
import http from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface Batch { id: number; batchNo: string; scope: string; ownerName: string | null; shareable: boolean; remainLevel: string; expiry: string | null }
interface Hazmat { cas: string; listed: boolean; toxic: boolean; names: string[]; alias: string | null }
interface Chem { id: number; name: string; aliases: string[] | null; cas: string | null; hazardLevel: string; unit: string; location: string | null; safetyStock: string; batches: Batch[]; hazmat?: Hazmat }

const hazardMap: Record<string, { t: string; c: string }> = {
  LOW: { t: '低危', c: 'bg-slate-100 text-slate-600' },
  MODERATE: { t: '中危', c: 'bg-blue-100 text-blue-800' },
  HIGH: { t: '高危', c: 'bg-amber-100 text-amber-800' },
  CONTROLLED: { t: '管控', c: 'bg-red-100 text-red-700' },
}
const levelMap: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' }

function HazTag({ h }: { h?: Hazmat }) {
  if (!h || !h.listed) return null
  if (h.toxic) return <span className="ml-1 inline-block rounded bg-red-600 px-1.5 py-0.5 text-xs font-medium text-white">☠ 剧毒·危化品</span>
  return <span className="ml-1 inline-block rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700">⚠ 危化品</span>
}

export default function Chemicals() {
  const [kw, setKw] = useState('')
  const [hazard, setHazard] = useState('')
  const [list, setList] = useState<Chem[]>([])
  const [loading, setLoading] = useState(false)

  // CAS 速查
  const [casQ, setCasQ] = useState('')
  const [casRes, setCasRes] = useState<Hazmat | null>(null)
  const [casLoading, setCasLoading] = useState(false)
  async function checkCas() {
    const c = casQ.trim()
    if (!c) return
    setCasLoading(true)
    try {
      const d: any = await http.get('/hazmat/lookup?cas=' + encodeURIComponent(c))
      setCasRes(d)
    } finally { setCasLoading(false) }
  }

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
    <div className="space-y-4">
      {/* CAS 危化品速查 */}
      <Card>
        <CardHeader><CardTitle>CAS 危化品速查（对照《危险化学品目录》2015 共 2657 个 CAS）</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <Input className="max-w-xs" placeholder="录入 CAS 号，如 68-12-2" value={casQ}
              onChange={(e) => setCasQ(e.target.value)} onKeyUp={(e) => { if (e.key === 'Enter') checkCas() }} />
            <Button variant="accent" onClick={checkCas} disabled={casLoading}>{casLoading ? '检索中…' : '检索'}</Button>
          </div>
          {casRes && (
            casRes.listed ? (
              <div className={'mt-3 rounded-md border p-3 text-sm ' + (casRes.toxic ? 'border-red-300 bg-red-50' : 'border-amber-300 bg-amber-50')}>
                <div className="font-semibold text-foreground">
                  {casRes.toxic ? '☠ 属于危险化学品 · 剧毒品' : '⚠ 属于危险化学品'}
                  <span className="ml-2 font-normal text-muted-foreground">CAS {casRes.cas}</span>
                </div>
                <div className="mt-1 text-foreground">目录名称：{casRes.names.join('、') || '—'}</div>
                {casRes.alias && <div className="text-xs text-muted-foreground">别名：{casRes.alias}</div>}
                <div className="mt-1 text-xs text-muted-foreground">
                  {casRes.toxic ? '需双人双签领用、专柜上锁、台账逐次登记。' : '入库与领用需登记台账，按危化品管理。'}
                </div>
              </div>
            ) : (
              <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <span className="font-semibold text-foreground">未收录</span>
                <span className="ml-2 text-muted-foreground">CAS {casRes.cas} 不在《危险化学品目录》内（仍可能有其他危害，按 SDS 处理）。</span>
              </div>
            )
          )}
        </CardContent>
      </Card>

      {/* 搜索 */}
      <Card>
        <CardHeader><CardTitle>药品库（全实验室共享 · 申购前先看这里）</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <Input className="max-w-xs" placeholder="搜索 名称 / 拼音 / CAS / 别名" value={kw}
              onChange={(e) => setKw(e.target.value)} onKeyUp={(e) => { if (e.key === 'Enter') load() }} />
            <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={hazard} onChange={(e) => setHazard(e.target.value)}>
              <option value="">全部危险等级</option>
              <option value="LOW">低危</option>
              <option value="MODERATE">中危</option>
              <option value="HIGH">高危</option>
              <option value="CONTROLLED">管控</option>
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
                <th className="py-2 pr-3 font-medium">危险 / 目录</th>
                <th className="py-2 pr-3 font-medium">位置</th>
                <th className="py-2 pr-3 font-medium">库存（持有人 / 余量）</th>
              </tr>
            </thead>
            <tbody>
              {list.map((c) => (
                <tr key={c.id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-medium text-foreground">{c.name}</div>
                    {c.aliases?.length ? <div className="text-xs text-muted-foreground">{c.aliases.join(' / ')}</div> : null}
                  </td>
                  <td className="py-2 pr-3 text-muted-foreground">{c.cas || '—'}</td>
                  <td className="py-2 pr-3">
                    <span className={'inline-block rounded px-2 py-0.5 text-xs ' + (hazardMap[c.hazardLevel]?.c || '')}>{hazardMap[c.hazardLevel]?.t || c.hazardLevel}</span>
                    <HazTag h={c.hazmat} />
                  </td>
                  <td className="py-2 pr-3 text-muted-foreground">{c.location || '—'}</td>
                  <td className="py-2 pr-3">
                    {c.batches.length === 0 ? <span className="text-muted-foreground">无库存</span> : (
                      <div className="flex flex-col gap-1">
                        {c.batches.map((b) => (
                          <div key={b.id} className="flex items-center gap-2">
                            <span className={'rounded px-1.5 py-0.5 text-xs ' + (b.scope === 'PUBLIC' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-800')}>
                              {b.scope === 'PUBLIC' ? '公用' : (b.ownerName || '个人')}
                            </span>
                            <span className="text-foreground">{levelMap[b.remainLevel] || b.remainLevel}</span>
                            {b.shareable && <span className="text-xs font-medium text-accent">可借</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {list.length === 0 && !loading && <tr><td colSpan={5} className="py-8 text-center text-muted-foreground">没有匹配的药品</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
""")

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8" % W, 420)
step("部署", "ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (W, SITE, SITE, W, SITE, SITE))
step("自检 8080 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\\.js' | head -1")
cli.close()
print("\n=== DONE ===")
