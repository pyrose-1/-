import os,sys,base64,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
W="/www/wwwroot/plm-web"; SITE="/www/wwwroot/plm-web/dist"; PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=300):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
reps=[
 ["const CAT_ORDER = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA', 'OTHER']",
  "const CAT_ORDER = ['VACUUM_OVEN', 'CYCLE_OVEN', 'MUFFLE', 'TUBE', 'BET', 'POLY_HEAD', 'DMA', 'TGA', 'OTHER']"],
 ["const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', FURNACE: '环化 / 马弗 / 管式 / BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他（随用随约）' }",
  "const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', CYCLE_OVEN: '环化烘箱', MUFFLE: '马弗炉', TUBE: '管式炉', BET: 'BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他（随用随约）' }"],
 ["const CAP: Record<string, string> = { VACUUM_OVEN: '每周 8 格（铺膜=3格 / 干燥=1格）', FURNACE: '每周 2 个全天块', POLY_HEAD: '每周 7 个半天块', DMA: '每周 4 个 4h 块', TGA: '每周 4 个 4h 块', OTHER: '不限、不抽签' }",
  "const CAP: Record<string, string> = { VACUUM_OVEN: '每周 8 格（铺膜=3格 / 干燥=1格）', CYCLE_OVEN: '每周 2 个全天块 · 需填温度上限', MUFFLE: '每周 3 个全天块', TUBE: '每周 3 个全天块', BET: '不限全天块', POLY_HEAD: '每周 7 个半天块', DMA: '每周 4 个 4h 块', TGA: '每周 4 个 4h 块', OTHER: '不限、不抽签' }"],
]
b=base64.b64encode(json.dumps(reps,ensure_ascii=False).encode()).decode()
o,e=run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/pages/Instruments.tsx'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:40])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(W,b))
print(o,e[-200:])
o,e=run(PATHX+"cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -4"%W,420); print(o[-300:],e[-150:])
o,_=run("rm -rf /www/wwwroot/lab.dhupi.cn/index.html /www/wwwroot/lab.dhupi.cn/assets && cp -rf %s/dist/* /www/wwwroot/lab.dhupi.cn/ && chown -R www:www /www/wwwroot/lab.dhupi.cn 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1"%W)
print("deployed JS:",o)
cli.close()
