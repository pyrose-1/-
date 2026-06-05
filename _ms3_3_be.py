# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=300):
    out, err = run(cmd, t); print("\n#### %s" % title)
    if out: print(out[-2600:])
    if err: print("[stderr]", err[-1400:])

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(APP, ""))

def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.replace(APP, ""), o.strip(), e[-200:])

# ---------- 实体 ----------
wfile(APP + "/src/entities/booking.entity.ts", """import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_bookings')
@Index(['cycleKey'])
@Index(['instrumentId', 'date'])
export class Booking {
  @PrimaryGeneratedColumn() id: number;
  @Column() cycleKey: string;
  @Column() instrumentId: number;
  @Column() userId: number;
  @Column() category: string;
  @Column() date: string;         // YYYY-MM-DD
  @Column() startHour: number;    // 8..24
  @Column() endHour: number;
  @Column() taskType: string;     // FILM/DRY/FULL_DAY/HALF_DAY/BLOCK
  @Column({ type: 'int', nullable: true }) tempCeiling: number | null;
  @Column({ default: 'LOTTERY' }) source: string; // LOTTERY/CLAIM
  @CreateDateColumn() createdAt: Date;
}
""")
wfile(APP + "/src/entities/lottery-run.entity.ts", """import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_lottery_runs')
export class LotteryRun {
  @PrimaryGeneratedColumn() id: number;
  @Index({ unique: true }) @Column() cycleKey: string;
  @Column({ type: 'datetime', nullable: true }) settledAt: Date | null;
  @CreateDateColumn() createdAt: Date;
}
""")

# ---------- 抽签引擎追加到 service ----------
ENGINE = r"""
  // ===== 抽签引擎（MS3-3）=====
  private weekDates(ck: string): string[] {
    const base = new Date(ck + 'T00:00:00Z');
    return Array.from({ length: 7 }, (_, i) => { const x = new Date(base); x.setUTCDate(base.getUTCDate() + i); return x.toISOString().slice(0, 10); });
  }

  async lotteryResult(cycleKey?: string) {
    const ck = cycleKey || this.cycleInfo().cycleKey;
    const bs = await this.bookings.find({ where: { cycleKey: ck }, order: { instrumentId: 'ASC', date: 'ASC', startHour: 'ASC' } });
    const iids = [...new Set(bs.map((b) => b.instrumentId))];
    const uids = [...new Set(bs.map((b) => b.userId))];
    const insts = iids.length ? await this.inst.find({ where: { id: In(iids) } }) : [];
    const users = uids.length ? await this.users.find({ where: { id: In(uids) } }) : [];
    const im = new Map(insts.map((i) => [i.id, i.name]));
    const um = new Map(users.map((u) => [u.id, u.name]));
    return { cycleKey: ck, items: bs.map((b) => ({ ...b, instrumentName: im.get(b.instrumentId) || ('#' + b.instrumentId), userName: um.get(b.userId) || ('#' + b.userId) })) };
  }

  async runLottery(cycleKey?: string) {
    const ck = cycleKey || this.cycleInfo().cycleKey;
    const dates = this.weekDates(ck);
    const insts = await this.inst.find({ where: { active: true } });
    const demands = await this.demands.find({ where: { cycleKey: ck } });
    const prios = await this.prio.find();
    const ps = new Map(prios.map((p) => [p.userId + '|' + p.category, p]));
    const prior = await this.runs.findOne({ where: { cycleKey: ck } });
    const doSettle = !prior;

    await this.bookings.delete({ cycleKey: ck, source: 'LOTTERY' });
    const out: any[] = [];
    const grant: Record<string, { req: number; got: number }> = {};
    const free: Record<string, boolean> = {};
    const allSat: Record<string, boolean> = {};
    const score = (uid: number, cat: string) => ps.get(uid + '|' + cat)?.score ?? 0;
    const push = (iid: number, uid: number, cat: string, di: number, sh: number, eh: number, task: string, temp: number | null) =>
      out.push({ cycleKey: ck, instrumentId: iid, userId: uid, category: cat, date: dates[di], startHour: sh, endHour: eh, taskType: task, tempCeiling: temp, source: 'LOTTERY' });

    for (const cat of LOTTERY_CATS) {
      const ds = demands.filter((d) => d.category === cat).sort((a, b) => score(b.userId, cat) - score(a.userId, cat));
      const pool = insts.filter((i) => i.category === cat);
      let cap = 0, got = 0;
      if (cat === 'VACUUM_OVEN') {
        cap = pool.length * 7 * 4;
        const filmUsed = new Set<string>(); const dryUsed = new Map<string, number>();
        for (const d of ds) {
          const set = (d.instrumentMode === 'SPECIFIC' && d.instrumentIds && d.instrumentIds.length) ? pool.filter((o) => d.instrumentIds!.includes(o.id)) : pool;
          let nf = d.filmCount, nd = d.dryCount;
          for (const o of set) { if (!o.filmCapable) continue; for (let dy = 0; dy < 7 && nf > 0; dy++) { const k = o.id + '|' + dy; if (!filmUsed.has(k)) { filmUsed.add(k); push(o.id, d.userId, cat, dy, 8, 20, 'FILM', null); nf--; got += 3; } } if (nf <= 0) break; }
          for (const o of set) { const dcap = o.filmCapable ? 1 : 4; for (let dy = 0; dy < 7 && nd > 0; dy++) { const k = o.id + '|' + dy; const u = dryUsed.get(k) || 0; if (u < dcap) { const idx = o.filmCapable ? 3 : u; dryUsed.set(k, u + 1); push(o.id, d.userId, cat, dy, 8 + 4 * idx, 12 + 4 * idx, 'DRY', null); nd--; got += 1; } } if (nd <= 0) break; }
          const req = d.filmCount * 3 + d.dryCount; grant[d.userId + '|' + cat] = { req, got: req - (nf * 3 + nd) };
        }
      } else if (cat === 'FURNACE') {
        cap = pool.length * 7; const used = new Set<string>();
        for (const d of ds) {
          const set = (d.instrumentMode === 'SPECIFIC' && d.instrumentIds && d.instrumentIds.length) ? pool.filter((o) => d.instrumentIds!.includes(o.id)) : pool;
          let need = d.blockCount;
          for (const o of set) { for (let dy = 0; dy < 7 && need > 0; dy++) { const k = o.id + '|' + dy; if (!used.has(k)) { used.add(k); push(o.id, d.userId, cat, dy, 8, 24, 'FULL_DAY', d.tempCeiling); need--; got++; } } if (need <= 0) break; }
          grant[d.userId + '|' + cat] = { req: d.blockCount, got: d.blockCount - need };
        }
      } else if (cat === 'POLY_HEAD') {
        cap = pool.length * 7 * 2; const used = new Map<string, number>();
        for (const d of ds) {
          const set = pool.filter((h) => (d.instrumentIds || []).includes(h.id));
          let need = d.blockCount;
          for (const h of set) { for (let dy = 0; dy < 7 && need > 0; dy++) { const k = h.id + '|' + dy; const u = used.get(k) || 0; if (u < 2) { used.set(k, u + 1); push(h.id, d.userId, cat, dy, 8 + 8 * u, 16 + 8 * u, 'HALF_DAY', null); need--; got++; } } if (need <= 0) break; }
          grant[d.userId + '|' + cat] = { req: d.blockCount, got: d.blockCount - need };
        }
      } else { // DMA / TGA
        const inst = pool[0]; cap = inst ? 7 * 4 : 0; const used = new Map<number, number>();
        for (const d of ds) {
          let need = d.blockCount;
          if (inst) for (let dy = 0; dy < 7 && need > 0; dy++) { let u = used.get(dy) || 0; while (u < 4 && need > 0) { push(inst.id, d.userId, cat, dy, 8 + 4 * u, 12 + 4 * u, 'BLOCK', null); u++; need--; got++; } used.set(dy, u); }
          grant[d.userId + '|' + cat] = { req: d.blockCount, got: d.blockCount - need };
        }
      }
      free[cat] = got < cap;
      allSat[cat] = ds.length > 0 && ds.every((d) => { const g = grant[d.userId + '|' + cat]; return g && g.got >= g.req; });
    }

    if (out.length) await this.bookings.insert(out);

    if (doSettle) {
      for (const cat of LOTTERY_CATS) {
        const had = demands.some((d) => d.category === cat);
        if (!had) continue;
        if (allSat[cat] && free[cat]) { for (const p of prios) if (p.category === cat) p.score = Math.round(Math.random() * 1000) / 1000; }
        else for (const p of prios) if (p.category === cat) { const g = grant[p.userId + '|' + cat]; if (!g) continue; const r = g.req > 0 ? g.got / g.req : 1; p.score += r >= 1 ? -2 : r >= 0.5 ? -1 : r > 0 ? 1 : 2; }
      }
      await this.prio.save(prios);
      await this.runs.save(this.runs.create({ cycleKey: ck, settledAt: new Date() }));
    }
    return { cycleKey: ck, bookings: out.length, settled: doSettle, perCat: LOTTERY_CATS.map((c) => ({ cat: c, free: free[c], allSatisfied: allSat[c] })) };
  }
"""
b64 = base64.b64encode(ENGINE.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s/src/instruments/instruments.service.ts'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('engine inserted')\nPYEOF" % (APP, b64))
print("  ", o.strip(), e[-200:])

# repo 注入
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["import { BookingDemand } from '../entities/booking-demand.entity';",
   "import { BookingDemand } from '../entities/booking-demand.entity';\nimport { Booking } from '../entities/booking.entity';\nimport { LotteryRun } from '../entities/lottery-run.entity';"],
  ["""    @InjectRepository(BookingDemand) private demands: Repository<BookingDemand>,
    @InjectRepository(User) private users: Repository<User>,""",
   """    @InjectRepository(BookingDemand) private demands: Repository<BookingDemand>,
    @InjectRepository(Booking) private bookings: Repository<Booking>,
    @InjectRepository(LotteryRun) private runs: Repository<LotteryRun>,
    @InjectRepository(User) private users: Repository<User>,"""],
])
# controller 路由
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Delete('booking/:id') delDemand(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.deleteDemand(u, +id); }",
   """  @Delete('booking/:id') delDemand(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.deleteDemand(u, +id); }
  @Get('lottery/result') result(@Query('cycle') c?: string) { return this.svc.lotteryResult(c); }
  @Post('lottery/run') @UseGuards(RolesGuard) @Roles('ADMIN') runLottery(@Body() b: any) { return this.svc.runLottery(b?.cycle); }"""],
])
# module + app.module 注册实体
pyedit(APP + "/src/instruments/instruments.module.ts", [
  ["import { BookingDemand } from '../entities/booking-demand.entity';",
   "import { BookingDemand } from '../entities/booking-demand.entity';\nimport { Booking } from '../entities/booking.entity';\nimport { LotteryRun } from '../entities/lottery-run.entity';"],
  ["TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, User]),",
   "TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, User]),"],
])
pyedit(APP + "/src/app.module.ts", [
  ["import { BookingDemand } from './entities/booking-demand.entity';",
   "import { BookingDemand } from './entities/booking-demand.entity';\nimport { Booking } from './entities/booking.entity';\nimport { LotteryRun } from './entities/lottery-run.entity';"],
  ["Instrument, InstrPriority, PolyHeadAuth, BookingDemand],",
   "Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun],"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 30 --nostream 2>&1 | grep -ciE 'error TS'")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o)
# 给小刚/小红补一些需求，制造多人场景
xg = login("stu_xg", "Plm@2026"); XG = "-H 'Authorization: Bearer %s'" % xg["token"]
xh = login("stu_xh", "Plm@2026"); XH = "-H 'Authorization: Bearer %s'" % xh["token"]
run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"VACUUM_OVEN\",\"filmCount\":2,\"dryCount\":0}'" % XG)
run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"DMA\",\"blockCount\":4}'" % XG)
run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"DMA\",\"blockCount\":3}'" % XH)
run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"POLY_HEAD\",\"blockCount\":2}'" % XH)

adm = login("admin", "Pniaef6b526!"); AD = "-H 'Authorization: Bearer %s'" % adm["token"]
print("\n## 抽签前 优先级")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/priorities %s | python3 -c \"import sys,json;[print(' ',r['name'],{k:round(v,3) for k,v in r['scores'].items()}) for r in json.load(sys.stdin)]\"" % AD); print(o)
print("## 运行抽签")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/lottery/run -H 'Content-Type: application/json' %s -d '{}'" % AD); print("  ", o)
print("## 抽签后 优先级（满足者应-2，机头小红 2/? 看比例）")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/priorities %s | python3 -c \"import sys,json;[print(' ',r['name'],{k:round(v,3) for k,v in r['scores'].items()}) for r in json.load(sys.stdin)]\"" % AD); print(o)
print("## 课表结果统计")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments/lottery/result' %s | python3 -c \"import sys,json,collections;d=json.load(sys.stdin)['items'];print('共',len(d),'条');c=collections.Counter((x['userName'],x['category'],x['taskType']) for x in d);[print('  ',k,v) for k,v in sorted(c.items())]\"" % AD); print(o)
print("## 抽样课表(前10条)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments/lottery/result' %s | python3 -c \"import sys,json;[print(' ',x['date'],'%02d-%02d'%(x['startHour'],x['endHour']),x['instrumentName'][:18],x['userName'],x['taskType']) for x in json.load(sys.stdin)['items'][:10]]\"" % AD); print(o)
cli.close()
print("\n=== DONE ===")
