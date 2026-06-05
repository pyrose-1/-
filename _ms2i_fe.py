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
    o,e=run(c,to); print("\n#### %s"%t); print(o[-2000:])
    if e: print("[stderr]",e[-800:])
def pyedit(path,reps):
    b=base64.b64encode(json.dumps(reps,ensure_ascii=False).encode()).decode()
    o,e=run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:70])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit",path.replace(W,""),o.strip(),e[-200:])

pyedit(W+"/src/pages/Chemicals.tsx",[
  # 引入 useNavigate
  ["import { useAuth } from '../store/auth'",
   "import { useAuth } from '../store/auth'\nimport { useNavigate } from 'react-router-dom'"],
  # 用 dialog 取代 borrowMsg
  ["""  const [borrowMsg, setBorrowMsg] = useState('')
  async function quickBorrow(b: Batch) {
    try {
      await http.post('/borrow', { batchId: b.id })
      setBorrowMsg(b.scope === 'PUBLIC'
        ? '✅ 公用药品借用成功，可直接取用；用完到「借用申请」点『借用完毕』登记余量'
        : `✅ 已向 ${b.sharedBy || b.ownerName || '持有人'} 发起借用申请，请到「借用申请」查看进度`)
    } catch (e: any) { setBorrowMsg('借用失败：' + e.message) }
  }""",
   """  const navigate = useNavigate()
  const [dialog, setDialog] = useState<{ ok: boolean; text: string } | null>(null)
  async function quickBorrow(b: Batch) {
    try {
      await http.post('/borrow', { batchId: b.id })
      setDialog({ ok: true, text: b.scope === 'PUBLIC'
        ? '公用药品借用成功，可直接取用。用完后请到「借用申请」点击『借用完毕』登记余量与位置。'
        : `已向 ${b.sharedBy || b.ownerName || '持有人'} 发起借用申请，请联系持有人确认药品情况，进度可在「借用申请」查看。` })
    } catch (e: any) { setDialog({ ok: false, text: '借用失败：' + e.message }) }
  }"""],
  # 去掉内联提示
  ["""          {borrowMsg && <div className="mt-2 text-sm text-accent">{borrowMsg}</div>}
""", ""],
  # 空瓶不显示可借（修正 fallback）
  ["""                              : (b.shareable ? <span className="text-xs font-medium text-accent">可借</span> : null)}""",
   """                              : (b.shareable && b.remainLevel !== 'EMPTY' ? <span className="text-xs font-medium text-accent">可借</span> : null)}"""],
  # 末尾加确认弹框
  ["""            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}""",
   """            </tbody>
          </table>
        </CardContent>
      </Card>

      {dialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setDialog(null)}>
          <div className="w-full max-w-sm rounded-lg bg-card p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className={'mb-2 text-base font-semibold ' + (dialog.ok ? 'text-foreground' : 'text-red-600')}>{dialog.ok ? '借用提交成功' : '借用未成功'}</h3>
            <p className="text-sm text-muted-foreground">{dialog.text}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialog(null)}>知道了</Button>
              {dialog.ok && <Button variant="accent" onClick={() => navigate('/borrow')}>前往借用申请</Button>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}"""],
])
step("构建前端",PATHX+"cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -8"%W,420)
step("部署","ls %s/dist/index.html 2>&1 && rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed"%(W,SITE,SITE,W,SITE,SITE))
step("自检 首页JS","curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
