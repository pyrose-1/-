# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"; W = "/www/wwwroot/plm-web"; SITE = "/www/wwwroot/lab.dhupi.cn"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t)
    if o: print(o[-2000:])
    if e: print("[stderr]", e[-800:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

# 1) 真空上限 6 -> 8
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["export const WEEK_CAP: Record<string, number> = { VACUUM_OVEN: 6, FURNACE: 2, POLY_HEAD: 7, DMA: 4, TGA: 4 };",
   "export const WEEK_CAP: Record<string, number> = { VACUUM_OVEN: 8, FURNACE: 2, POLY_HEAD: 7, DMA: 4, TGA: 4 };"],
])

# 2) forecast 方法
FC = r"""
  // 中签概率预估：至少约到1次（按当前优先级 + 当前报名）
  async forecast(userId: number, cycle?: string) {
    const ck = cycle || this.cycleInfo().cycleKey;
    const demands = await this.demands.find({ where: { cycleKey: ck } });
    const prios = await this.prio.find();
    const ps = new Map(prios.map((p) => [p.userId + '|' + p.category, p.score]));
    const insts = await this.inst.find({ where: { active: true } });
    const vac = insts.filter((i) => i.category === 'VACUUM_OVEN');
    const filmOvens = vac.filter((i) => i.filmCapable).length;
    const dryPerDay = vac.reduce((s, i) => s + (i.filmCapable ? 1 : 4), 0);
    const heads = insts.filter((i) => i.category === 'POLY_HEAD').length;
    const furn = insts.filter((i) => i.category === 'FURNACE').length;
    const SPREAD = 1.0;
    const sc = (uid: number, cat: string) => ps.get(uid + '|' + cat) ?? 0;

    const prob = (cat: string, cap: number, key: 'film' | 'dry' | 'block', chunk: number) => {
      const cont: { uid: number; score: number; demand: number }[] = [];
      for (const d of demands.filter((x) => x.category === cat)) {
        const dem = key === 'film' ? d.filmCount : key === 'dry' ? d.dryCount : d.blockCount;
        if (dem > 0) cont.push({ uid: d.userId, score: sc(d.userId, cat), demand: dem });
      }
      if (!cont.find((c) => c.uid === userId)) cont.push({ uid: userId, score: sc(userId, cat), demand: 1 });
      cont.sort((a, b) => b.score - a.score);
      let cum = 0, lastServed: number | null = null, firstUnserved: number | null = null;
      for (const x of cont) {
        const consume = chunk ? Math.min(x.demand, chunk) : x.demand;
        if (cum < cap) { lastServed = x.score; cum += consume; }
        else if (firstUnserved === null) firstUnserved = x.score;
      }
      const cutoff = firstUnserved === null ? -999 : (lastServed !== null ? (lastServed + firstUnserved) / 2 : firstUnserved);
      const my = sc(userId, cat);
      return Math.round(100 / (1 + Math.exp(-(my - cutoff) / SPREAD)));
    };

    return {
      cycle: ck,
      VACUUM_FILM: prob('VACUUM_OVEN', filmOvens * 7, 'film', 0),
      VACUUM_DRY: prob('VACUUM_OVEN', dryPerDay * 7, 'dry', 0),
      FURNACE: prob('FURNACE', furn * 7, 'block', 0),
      POLY_HEAD: prob('POLY_HEAD', heads * 7 * 2, 'block', 0),
      DMA: prob('DMA', 28, 'block', 2),
      TGA: prob('TGA', 28, 'block', 2),
    };
  }
"""
b64 = base64.b64encode(FC.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s/src/instruments/instruments.service.ts'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('forecast inserted')\nPYEOF" % (APP, b64))
print(" ", o.strip(), e[-150:])
# 路由
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Get('booking/cycle') cycle() { return this.svc.cycleInfo(); }",
   "  @Get('booking/cycle') cycle() { return this.svc.cycleInfo(); }\n  @Get('forecast') forecast(@CurrentUser() u: any, @Query('cycle') c?: string) { return this.svc.forecast(u.sub, c); }"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -6 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p)); return json.loads(o).get("token")
# 用有竞争的 06-15 周看概率（取一个高优先级与一个低优先级学生对比）
adm = "-H 'Authorization: Bearer %s'" % login("admin", "Pniaef6b526!")
hi = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT u.username FROM plm_instr_priority p JOIN plm_users u ON u.id=p.userId WHERE p.category='DMA' ORDER BY p.score DESC LIMIT 1\" 2>/dev/null")[0].strip()
lo = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT u.username FROM plm_instr_priority p JOIN plm_users u ON u.id=p.userId WHERE p.category='DMA' ORDER BY p.score ASC LIMIT 1\" 2>/dev/null")[0].strip()
for who, un in [("高优先级", hi), ("低优先级", lo)]:
    H = "-H 'Authorization: Bearer %s'" % login(un, "Plm@2026")
    o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments/forecast?cycle=2026-06-15' %s" % H)
    print("%s(%s):" % (who, un), o)
cli.close(); print("\n=== DONE-BE ===")
