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
    o, e = run(c, to); print("\n#### %s" % t); print(o[-1800:])
    if e: print("[stderr]", e[-700:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

# ---- 后端 ----
# 1) Booking 加 fromUserId
pyedit(APP + "/src/entities/booking.entity.ts", [
  ["  @Column({ default: 'LOTTERY' }) source: string; // LOTTERY/CLAIM",
   "  @Column({ default: 'LOTTERY' }) source: string; // LOTTERY/CLAIM\n  @Column({ type: 'int', nullable: true }) fromUserId: number | null;"],
])
# 2) cancel：仅 LOTTERY 早退 +1
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["    if (hrs >= 72) { const p = await this.getPrio(b.userId, b.category); p.score += 1; await this.prio.save(p); bonus = true; }",
   "    if (b.source === 'LOTTERY' && hrs >= 72) { const p = await this.getPrio(b.userId, b.category); p.score += 1; await this.prio.save(p); bonus = true; }"],
])
# 3) transfer：仅 LOTTERY 换分，记录 fromUserId
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["""    const pa = await this.getPrio(user.sub, b.category);
    const pb = await this.getPrio(to.id, b.category);
    const a = pa.score, bb = pb.score;
    pa.score = bb - 0.5; pb.score = a - 0.5;
    await this.prio.save([pa, pb]);
    b.userId = to.id; await this.bookings.save(b);""",
   """    if (b.source === 'LOTTERY') {
      const pa = await this.getPrio(user.sub, b.category);
      const pb = await this.getPrio(to.id, b.category);
      const a = pa.score, bb = pb.score;
      pa.score = bb - 0.5; pb.score = a - 0.5;
      await this.prio.save([pa, pb]);
    }
    b.fromUserId = user.sub; b.userId = to.id; await this.bookings.save(b);"""],
])
# 4) myBookings 加 fromName
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["""    const im = new Map(insts.map((i) => [i.id, i.name]));
    return bs.map((b) => ({ ...b, instrumentName: im.get(b.instrumentId) || ('#' + b.instrumentId) }));""",
   """    const im = new Map(insts.map((i) => [i.id, i.name]));
    const fids = [...new Set(bs.map((b) => b.fromUserId).filter(Boolean) as number[])];
    const fus = fids.length ? await this.users.find({ where: { id: In(fids) } }) : [];
    const fm = new Map(fus.map((u) => [u.id, u.name]));
    return bs.map((b) => ({ ...b, instrumentName: im.get(b.instrumentId) || ('#' + b.instrumentId), fromName: b.fromUserId ? (fm.get(b.fromUserId) || '?') : null }));"""],
])
# 5) lotteryResult 加 fromName
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["    const uids = [...new Set(bs.map((b) => b.userId))];\n    const insts = iids.length ? await this.inst.find({ where: { id: In(iids) } }) : [];",
   "    const uids = [...new Set(bs.flatMap((b) => [b.userId, b.fromUserId]).filter(Boolean) as number[])];\n    const insts = iids.length ? await this.inst.find({ where: { id: In(iids) } }) : [];"],
  ["    return { cycleKey: ck, items: bs.map((b) => ({ ...b, instrumentName: im.get(b.instrumentId) || ('#' + b.instrumentId), userName: um.get(b.userId) || ('#' + b.userId) })) };",
   "    return { cycleKey: ck, items: bs.map((b) => ({ ...b, instrumentName: im.get(b.instrumentId) || ('#' + b.instrumentId), userName: um.get(b.userId) || ('#' + b.userId), fromName: b.fromUserId ? (um.get(b.fromUserId) || '?') : null })) };"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -6 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")

# ---- 前端 ----
# MyInstruments: 去优先级字样 + 来源来自XX
pyedit(W + "/src/pages/MyInstruments.tsx", [
  ["interface Bk { id: number; instrumentId: number; instrumentName: string; category: string; date: string; startHour: number; endHour: number; taskType: string; tempCeiling: number | null; source: string }",
   "interface Bk { id: number; instrumentId: number; instrumentName: string; category: string; date: string; startHour: number; endHour: number; taskType: string; tempCeiling: number | null; source: string; fromName: string | null }"],
  ["""      <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (b.source === 'CLAIM' ? 'bg-green-100 text-green-700' : 'bg-primary/10 text-primary')}>{b.source === 'CLAIM' ? '点击即得' : '抽签'}</span></td>""",
   """      <td className="py-2 pr-3"><span className={'rounded px-1.5 py-0.5 text-xs ' + (b.fromName ? 'bg-purple-100 text-purple-700' : b.source === 'CLAIM' ? 'bg-green-100 text-green-700' : 'bg-primary/10 text-primary')}>{b.fromName ? '来自' + b.fromName : b.source === 'CLAIM' ? '点击即得' : '抽签'}</span></td>"""],
  ["    if (!window.confirm(`取消 ${b.date} ${b.startHour}–${b.endHour} 的 ${b.instrumentName}？提前72h取消可+1优先级。`)) return",
   "    if (!window.confirm(`取消 ${b.date} ${b.startHour}–${b.endHour} 的 ${b.instrumentName}？`)) return"],
  ["    try { const r: any = await http.post('/instruments/booking/cancel/' + b.id, {}); setMsg(r.earlyBonus ? '✅ 已取消（提前取消，+1 优先级）' : '✅ 已取消'); load(); if (showPast) loadPast(pastWk) }",
   "    try { await http.post('/instruments/booking/cancel/' + b.id, {}); setMsg('✅ 已取消'); load(); if (showPast) loadPast(pastWk) }"],
  ["""<td className="py-2 pr-3 text-muted-foreground">{b.source === 'CLAIM' ? '点击即得' : '抽签'}</td></tr>)}""",
   """<td className="py-2 pr-3 text-muted-foreground">{b.fromName ? '来自' + b.fromName : b.source === 'CLAIM' ? '点击即得' : '抽签'}</td></tr>)}"""],
])
# Schedule: Bk 加 fromName + 显示来自
pyedit(W + "/src/pages/Schedule.tsx", [
  ["interface Bk { id: number; instrumentId: number; userId: number; userName: string; date: string; startHour: number; endHour: number; taskType: string; tempCeiling: number | null; source: string }",
   "interface Bk { id: number; instrumentId: number; userId: number; userName: string; date: string; startHour: number; endHour: number; taskType: string; tempCeiling: number | null; source: string; fromName: string | null }"],
  ["""            {b.startHour}–{b.endHour} {TASK[b.taskType] || ''}·{b.userName}{b.tempCeiling ? `(${b.tempCeiling}℃)` : ''}""",
   """            {b.startHour}–{b.endHour} {TASK[b.taskType] || ''}·{b.userName}{b.tempCeiling ? `(${b.tempCeiling}℃)` : ''}{b.fromName ? ` ←${b.fromName}` : ''}"""],
])

step("构建前端", PATHX + "cd %s && NODE_OPTIONS=--max-old-space-size=1536 npm run build 2>&1 | tail -6" % W, 420)
step("部署", "rm -rf %s/index.html %s/assets && cp -rf %s/dist/* %s/ && chown -R www:www %s 2>/dev/null; echo deployed" % (SITE, SITE, W, SITE, SITE))
step("自检 首页JS", "curl -s http://127.0.0.1:8080/ | grep -o '/assets/[^\"]*[.]js' | head -1")
cli.close(); print("\n=== DONE ===")
