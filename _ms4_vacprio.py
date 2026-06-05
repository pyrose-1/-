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
def run(cmd, t=480):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def step(t, c, to=480):
    o, e = run(c, to); print("\n#### %s"%t)
    if o: print(o[-2000:])
    if e: print("[stderr]", e[-700:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:80])\n  s=s.replace(a,b,1)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit", path.split('/')[-1], o.strip(), e[-220:])

SVC = APP + "/src/instruments/instruments.service.ts"

# 1) 常量：PRIO_CATS + CAT_LABEL 加铺膜/干燥
pyedit(SVC, [
  ["export const LOTTERY_CATS = ['VACUUM_OVEN', 'CYCLE_OVEN', 'MUFFLE', 'TUBE', 'BET', 'POLY_HEAD', 'DMA', 'TGA'];",
   "export const LOTTERY_CATS = ['VACUUM_OVEN', 'CYCLE_OVEN', 'MUFFLE', 'TUBE', 'BET', 'POLY_HEAD', 'DMA', 'TGA'];\nexport const PRIO_CATS = ['VACUUM_FILM', 'VACUUM_DRY', 'CYCLE_OVEN', 'MUFFLE', 'TUBE', 'BET', 'POLY_HEAD', 'DMA', 'TGA'];"],
  ["export const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱',",
   "export const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', VACUUM_FILM: '真空铺膜', VACUUM_DRY: '真空干燥',"],
])

# 2) ensurePriorities + priorityTable 用 PRIO_CATS
pyedit(SVC, [
  ["    for (const s of students) for (const c of LOTTERY_CATS) {",
   "    for (const s of students) for (const c of PRIO_CATS) {"],
  ["      scores: Object.fromEntries(LOTTERY_CATS.map((c) => [c, m.get(s.id + '|' + c) ?? null])),",
   "      scores: Object.fromEntries(PRIO_CATS.map((c) => [c, m.get(s.id + '|' + c) ?? null])),"],
])

# 3) runLottery 真空块：铺膜/干燥分优先级
OLD_VAC = """      if (cat === 'VACUUM_OVEN') {
        cap = pool.length * 7 * 4;
        const filmUsed = new Set<string>(); const dryUsed = new Map<string, number>();
        for (const d of ds) {
          const set = (d.instrumentMode === 'SPECIFIC' && d.instrumentIds && d.instrumentIds.length) ? pool.filter((o) => d.instrumentIds!.includes(o.id)) : pool;
          let nf = d.filmCount, nd = d.dryCount;
          for (const o of set) { if (!o.filmCapable) continue; for (let dy = 0; dy < 7 && nf > 0; dy++) { const k = o.id + '|' + dy; if (!filmUsed.has(k)) { filmUsed.add(k); push(o.id, d.userId, cat, dy, 8, 20, 'FILM', null); nf--; got += 3; } } if (nf <= 0) break; }
          for (const o of set) { const dcap = o.filmCapable ? 1 : 4; for (let dy = 0; dy < 7 && nd > 0; dy++) { const k = o.id + '|' + dy; const u = dryUsed.get(k) || 0; if (u < dcap) { const idx = o.filmCapable ? 3 : u; dryUsed.set(k, u + 1); push(o.id, d.userId, cat, dy, 8 + 4 * idx, 12 + 4 * idx, 'DRY', null); nd--; got += 1; } } if (nd <= 0) break; }
          const req = d.filmCount * 3 + d.dryCount; grant[d.userId + '|' + cat] = { req, got: req - (nf * 3 + nd) };
        }
      } else if (cat === 'CYCLE_OVEN'"""
NEW_VAC = """      if (cat === 'VACUUM_OVEN') {
        const filmUsed = new Set<string>(); const dryUsed = new Map<string, number>();
        const filmCap = pool.filter((o) => o.filmCapable).length * 7;
        const dryCap = pool.reduce((s, o) => s + (o.filmCapable ? 1 : 4), 0) * 7;
        const setOf = (d: any) => (d.instrumentMode === 'SPECIFIC' && d.instrumentIds && d.instrumentIds.length) ? pool.filter((o) => d.instrumentIds!.includes(o.id)) : pool;
        // 铺膜：按 VACUUM_FILM 优先级
        let filmGot = 0;
        const fds = ds.filter((d) => d.filmCount > 0).sort((a, b) => score(b.userId, 'VACUUM_FILM') - score(a.userId, 'VACUUM_FILM'));
        for (const d of fds) {
          let nf = d.filmCount;
          for (const o of setOf(d)) { if (!o.filmCapable) continue; for (let dy = 0; dy < 7 && nf > 0; dy++) { const k = o.id + '|' + dy; if (!filmUsed.has(k)) { filmUsed.add(k); push(o.id, d.userId, cat, dy, 8, 20, 'FILM', null); nf--; filmGot++; } } if (nf <= 0) break; }
          grant[d.userId + '|VACUUM_FILM'] = { req: d.filmCount, got: d.filmCount - nf };
        }
        // 干燥：按 VACUUM_DRY 优先级
        let dryGot = 0;
        const dds = ds.filter((d) => d.dryCount > 0).sort((a, b) => score(b.userId, 'VACUUM_DRY') - score(a.userId, 'VACUUM_DRY'));
        for (const d of dds) {
          let nd = d.dryCount;
          for (const o of setOf(d)) { const dcap = o.filmCapable ? 1 : 4; for (let dy = 0; dy < 7 && nd > 0; dy++) { const k = o.id + '|' + dy; const u = dryUsed.get(k) || 0; if (u < dcap) { const idx = o.filmCapable ? 3 : u; dryUsed.set(k, u + 1); push(o.id, d.userId, cat, dy, 8 + 4 * idx, 12 + 4 * idx, 'DRY', null); nd--; dryGot++; } } if (nd <= 0) break; }
          grant[d.userId + '|VACUUM_DRY'] = { req: d.dryCount, got: d.dryCount - nd };
        }
        free['VACUUM_FILM'] = filmGot < filmCap;
        free['VACUUM_DRY'] = dryGot < dryCap;
        allSat['VACUUM_FILM'] = fds.length > 0 && fds.every((d) => { const g = grant[d.userId + '|VACUUM_FILM']; return g && g.got >= g.req; });
        allSat['VACUUM_DRY'] = dds.length > 0 && dds.every((d) => { const g = grant[d.userId + '|VACUUM_DRY']; return g && g.got >= g.req; });
      } else if (cat === 'CYCLE_OVEN'"""
pyedit(SVC, [[OLD_VAC, NEW_VAC]])

# 4) 通用 free/allSat 跳过真空
pyedit(SVC, [
  ["""      free[cat] = got < cap;
      allSat[cat] = ds.length > 0 && ds.every((d) => { const g = grant[d.userId + '|' + cat]; return g && g.got >= g.req; });""",
   """      if (cat !== 'VACUUM_OVEN') {
        free[cat] = got < cap;
        allSat[cat] = ds.length > 0 && ds.every((d) => { const g = grant[d.userId + '|' + cat]; return g && g.got >= g.req; });
      }"""],
])

# 5) settle 循环 + perCat 用 PRIO_CATS
pyedit(SVC, [
  ["""      for (const cat of LOTTERY_CATS) {
        const had = demands.some((d) => d.category === cat);
        if (!had) continue;""",
   """      for (const cat of PRIO_CATS) {
        const had = cat === 'VACUUM_FILM' ? demands.some((d) => d.category === 'VACUUM_OVEN' && d.filmCount > 0)
          : cat === 'VACUUM_DRY' ? demands.some((d) => d.category === 'VACUUM_OVEN' && d.dryCount > 0)
          : demands.some((d) => d.category === cat);
        if (!had) continue;"""],
  ["perCat: LOTTERY_CATS.map((c) => ({ cat: c, free: free[c], allSatisfied: allSat[c] })) };",
   "perCat: PRIO_CATS.map((c) => ({ cat: c, free: free[c], allSatisfied: allSat[c] })) };"],
])

# 6) prioCat 帮助函数（紧跟 getPrio 之后）
pyedit(SVC, [
  ["""  private async getPrio(userId: number, category: string) {
    let p = await this.prio.findOne({ where: { userId, category } });
    if (!p) p = await this.prio.save(this.prio.create({ userId, category, score: Math.round(Math.random() * 1000) / 1000 }));
    return p;
  }""",
   """  private async getPrio(userId: number, category: string) {
    let p = await this.prio.findOne({ where: { userId, category } });
    if (!p) p = await this.prio.save(this.prio.create({ userId, category, score: Math.round(Math.random() * 1000) / 1000 }));
    return p;
  }
  private prioCat(b: any) { return b.category === 'VACUUM_OVEN' ? (b.taskType === 'FILM' ? 'VACUUM_FILM' : 'VACUUM_DRY') : b.category; }"""],
])

# 7) cancel / transfer 用 prioCat
pyedit(SVC, [
  ["if (b.source === 'LOTTERY' && hrs >= 72) { const p = await this.getPrio(b.userId, b.category); p.score += 1; await this.prio.save(p); bonus = true; }",
   "if (b.source === 'LOTTERY' && hrs >= 72) { const p = await this.getPrio(b.userId, this.prioCat(b)); p.score += 1; await this.prio.save(p); bonus = true; }"],
  ["      const pa = await this.getPrio(user.sub, b.category);\n      const pb = await this.getPrio(to.id, b.category);",
   "      const pa = await this.getPrio(user.sub, this.prioCat(b));\n      const pb = await this.getPrio(to.id, this.prioCat(b));"],
])

# 8) forecast：prob 增加 pcat 参数 + 调用
OLD_PROB = """    const prob = (cat: string, cap: number, key: 'film' | 'dry' | 'block', chunk: number) => {
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
    };"""
NEW_PROB = """    const prob = (dcat: string, pcat: string, cap: number, key: 'film' | 'dry' | 'block', chunk: number) => {
      const cont: { uid: number; score: number; demand: number }[] = [];
      for (const d of demands.filter((x) => x.category === dcat)) {
        const dem = key === 'film' ? d.filmCount : key === 'dry' ? d.dryCount : d.blockCount;
        if (dem > 0) cont.push({ uid: d.userId, score: sc(d.userId, pcat), demand: dem });
      }
      if (!cont.find((c) => c.uid === userId)) cont.push({ uid: userId, score: sc(userId, pcat), demand: 1 });
      cont.sort((a, b) => b.score - a.score);
      let cum = 0, lastServed: number | null = null, firstUnserved: number | null = null;
      for (const x of cont) {
        const consume = chunk ? Math.min(x.demand, chunk) : x.demand;
        if (cum < cap) { lastServed = x.score; cum += consume; }
        else if (firstUnserved === null) firstUnserved = x.score;
      }
      const cutoff = firstUnserved === null ? -999 : (lastServed !== null ? (lastServed + firstUnserved) / 2 : firstUnserved);
      const my = sc(userId, pcat);
      return Math.round(100 / (1 + Math.exp(-(my - cutoff) / SPREAD)));
    };"""
pyedit(SVC, [[OLD_PROB, NEW_PROB]])
pyedit(SVC, [
  ["""      VACUUM_FILM: prob('VACUUM_OVEN', filmOvens * 7, 'film', 0),
      VACUUM_DRY: prob('VACUUM_OVEN', dryPerDay * 7, 'dry', 0),
      CYCLE_OVEN: prob('CYCLE_OVEN', nCyc * 7, 'block', 0),
      MUFFLE: prob('MUFFLE', nMuf * 7, 'block', 0),
      TUBE: prob('TUBE', nTub * 7, 'block', 0),
      BET: prob('BET', nBet * 7, 'block', 0),
      POLY_HEAD: prob('POLY_HEAD', heads * 7 * 2, 'block', 0),
      DMA: prob('DMA', 28, 'block', 2),
      TGA: prob('TGA', 28, 'block', 2),""",
   """      VACUUM_FILM: prob('VACUUM_OVEN', 'VACUUM_FILM', filmOvens * 7, 'film', 0),
      VACUUM_DRY: prob('VACUUM_OVEN', 'VACUUM_DRY', dryPerDay * 7, 'dry', 0),
      CYCLE_OVEN: prob('CYCLE_OVEN', 'CYCLE_OVEN', nCyc * 7, 'block', 0),
      MUFFLE: prob('MUFFLE', 'MUFFLE', nMuf * 7, 'block', 0),
      TUBE: prob('TUBE', 'TUBE', nTub * 7, 'block', 0),
      BET: prob('BET', 'BET', nBet * 7, 'block', 0),
      POLY_HEAD: prob('POLY_HEAD', 'POLY_HEAD', heads * 7 * 2, 'block', 0),
      DMA: prob('DMA', 'DMA', 28, 'block', 2),
      TGA: prob('TGA', 'TGA', 28, 'block', 2),"""],
])

# 9) 前端 Priorities.tsx 列
pyedit(W + "/src/pages/Priorities.tsx", [
  ["const CATS = [['VACUUM_OVEN', '真空烘箱'], ['CYCLE_OVEN', '环化'], ['MUFFLE', '马弗'], ['TUBE', '管式'], ['BET', 'BET'], ['POLY_HEAD', '机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]",
   "const CATS = [['VACUUM_FILM', '真空铺膜'], ['VACUUM_DRY', '真空干燥'], ['CYCLE_OVEN', '环化'], ['MUFFLE', '马弗'], ['TUBE', '管式'], ['BET', 'BET'], ['POLY_HEAD', '机头'], ['DMA', 'DMA'], ['TGA', 'TGA']]"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -14 && echo BUILT"%APP, 480)
step("重启 + 迁移优先级(VACUUM_OVEN -> FILM/DRY 复制, 删旧)", PATHX + "pm2 restart plm-api >/dev/null 2>&1; sleep 5; mysql -uplm -ppni38AWG4xy6wEyc plm -e \"INSERT IGNORE INTO plm_instr_priority(userId,category,score) SELECT userId,'VACUUM_FILM',score FROM plm_instr_priority WHERE category='VACUUM_OVEN'; INSERT IGNORE INTO plm_instr_priority(userId,category,score) SELECT userId,'VACUUM_DRY',score FROM plm_instr_priority WHERE category='VACUUM_OVEN'; DELETE FROM plm_instr_priority WHERE category='VACUUM_OVEN';\" 2>/dev/null; echo migrated; pm2 logs plm-api --lines 4 --nostream 2>&1 | tail -5")

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -5"%W, 480)
step("部署前端", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1"%(SITE,SITE,W,SITE,SITE))

# 校验
import json as J
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p)); return J.loads(o).get("token")
TA="-H 'Authorization: Bearer %s'"%login("admin","Pniaef6b526!")
o,_=run("curl -s http://127.0.0.1:3000/api/instruments/priorities %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('优先级列:', list(d[0]['scores'].keys()) if d else 'none')\""%TA)
print("\n## 优先级表列:", o)
o,_=run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT category,COUNT(*) FROM plm_instr_priority GROUP BY category ORDER BY category\" 2>/dev/null")
print("## 优先级行数(按类别):\n", o)
cli.close(); print("\n=== DONE ===")
