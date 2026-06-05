# -*- coding: utf-8 -*-
import os,sys,json,base64
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
W="/www/wwwroot/plm-web"; SITE="/www/wwwroot/lab.dhupi.cn"
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
print("=== SSH OK ===")
def run(c,t=300):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace").rstrip(),e.read().decode("utf-8","replace").rstrip()
def step(t,c,to=300):
    o,e=run(c,to); print("\n#### %s"%t); print(o[-2000:]); 
    if e: print("[stderr]",e[-800:])
def pyedit(path,reps):
    b=base64.b64encode(json.dumps(reps,ensure_ascii=False).encode()).decode()
    o,e=run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit",path.replace(W,""),o.strip(),e[-200:])

pyedit(W+"/src/pages/Chemicals.tsx",[
  ["import http from '../lib/api'",
   "import http from '../lib/api'\nimport { useAuth } from '../store/auth'"],
  ["interface Batch { id: number; batchNo: string; scope: string; ownerName: string | null; sharedBy: string | null; shareable: boolean; remainLevel: string }",
   "interface Batch { id: number; batchNo: string; scope: string; ownerId: number | null; ownerName: string | null; sharedBy: string | null; shareable: boolean; remainLevel: string }"],
  ["""export default function Chemicals() {
  const [kw, setKw] = useState('')""",
   """export default function Chemicals() {
  const { user } = useAuth()
  const myId = (user as any)?.id as number | undefined
  const [borrowMsg, setBorrowMsg] = useState('')
  async function quickBorrow(b: Batch) {
    try {
      await http.post('/borrow', { batchId: b.id })
      setBorrowMsg(b.scope === 'PUBLIC'
        ? '✅ 公用药品借用成功，可直接取用；用完到「借用申请」点『借用完毕』登记余量'
        : `✅ 已向 ${b.sharedBy || b.ownerName || '持有人'} 发起借用申请，请到「借用申请」查看进度`)
    } catch (e: any) { setBorrowMsg('借用失败：' + e.message) }
  }
  const [kw, setKw] = useState('')"""],
  ["""            <Button onClick={load} disabled={loading}>{loading ? '查询中…' : '搜索'}</Button>
          </div>
        </CardContent>""",
   """            <Button onClick={load} disabled={loading}>{loading ? '查询中…' : '搜索'}</Button>
          </div>
          {borrowMsg && <div className="mt-2 text-sm text-accent">{borrowMsg}</div>}
        </CardContent>"""],
  ["""                            {b.shareable && <span className="text-xs font-medium text-accent">可借</span>}""",
   """                            {b.shareable && b.remainLevel !== 'EMPTY' && b.ownerId != null && b.ownerId !== myId
                              ? <button onClick={() => quickBorrow(b)} className="rounded bg-accent px-1.5 py-0.5 text-xs font-medium text-white hover:opacity-90">可借·借用</button>
                              : (b.shareable ? <span className="text-xs font-medium text-accent">可借</span> : null)}"""],
])
step("构建前端",PATHX+"cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8"%W,420)
step("部署","ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed"%(W,SITE,SITE,W,SITE,SITE))
step("自检 首页JS","curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*\.js' | head -1")
cli.close(); print("\n=== DONE ===")
