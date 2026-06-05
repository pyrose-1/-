# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
DBP = "pni38AWG4xy6wEyc"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def sql(q, t=120):
    out, _ = run("mysql -uplm -p%s plm -N -e \"%s\" 2>/dev/null" % (DBP, q), t); return out
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t)
    if o: print(o[-2200:])
    if e: print("[stderr]", e[-1000:])
def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content)); print("  写", path.replace(APP, ""))
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.replace(APP, ""), o.strip(), e[-150:])

# 实体
wfile(APP + "/src/entities/piggyback.entity.ts", """import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_piggyback')
export class PiggybackRequest {
  @PrimaryGeneratedColumn() id: number;
  @Column() bookingId: number;
  @Column() requesterId: number;
  @Column() ownerId: number;
  @Column() instrumentId: number;
  @Column({ default: 'PENDING' }) status: string;
  @Column({ type: 'datetime', nullable: true }) decidedAt: Date | null;
  @CreateDateColumn() createdAt: Date;
}
""")

# 方法块
M = r"""
  private async getPrio(userId: number, category: string) {
    let p = await this.prio.findOne({ where: { userId, category } });
    if (!p) p = await this.prio.save(this.prio.create({ userId, category, score: Math.round(Math.random() * 1000) / 1000 }));
    return p;
  }

  async myBookings(userId: number, cycle?: string) {
    const ck = cycle || this.cycleInfo().cycleKey;
    const bs = await this.bookings.find({ where: { userId, cycleKey: ck }, order: { date: 'ASC', startHour: 'ASC' } });
    const iids = [...new Set(bs.map((b) => b.instrumentId))];
    const insts = iids.length ? await this.inst.find({ where: { id: In(iids) } }) : [];
    const im = new Map(insts.map((i) => [i.id, i.name]));
    return bs.map((b) => ({ ...b, instrumentName: im.get(b.instrumentId) || ('#' + b.instrumentId) }));
  }

  async cancelBooking(user: any, id: number) {
    const b = await this.bookings.findOne({ where: { id } });
    if (!b) throw new NotFoundException('预约不存在');
    if (b.userId !== user.sub) throw new ForbiddenException('只能取消自己的预约');
    const start = new Date(b.date + 'T' + String(b.startHour).padStart(2, '0') + ':00:00');
    const hrs = (start.getTime() - Date.now()) / 3600000;
    let bonus = false;
    if (hrs >= 72) { const p = await this.getPrio(b.userId, b.category); p.score += 1; await this.prio.save(p); bonus = true; }
    await this.bookings.remove(b);
    return { ok: true, earlyBonus: bonus };
  }

  async transferBooking(user: any, id: number, target: string) {
    const b = await this.bookings.findOne({ where: { id } });
    if (!b) throw new NotFoundException('预约不存在');
    if (b.userId !== user.sub) throw new ForbiddenException('只能转赠自己的预约');
    const t = (target || '').trim();
    if (!t) throw new BadRequestException('请输入对方姓名或学号');
    const cands = await this.users.find({ where: [{ name: t, role: 'STUDENT' as any }, { username: t, role: 'STUDENT' as any }] });
    const uniq = [...new Map(cands.map((u) => [u.id, u])).values()];
    if (!uniq.length) throw new BadRequestException('未找到该学生，请确认姓名或改用学号');
    if (uniq.length > 1) throw new BadRequestException('同名多人，请改用学号');
    const to = uniq[0];
    if (to.id === user.sub) throw new BadRequestException('不能转赠给自己');
    const pa = await this.getPrio(user.sub, b.category);
    const pb = await this.getPrio(to.id, b.category);
    const a = pa.score, bb = pb.score;
    pa.score = bb - 0.5; pb.score = a - 0.5;
    await this.prio.save([pa, pb]);
    b.userId = to.id; await this.bookings.save(b);
    return { ok: true, to: to.name };
  }

  async piggybackRequest(user: any, bookingId: number) {
    if (user.role !== 'STUDENT') throw new ForbiddenException('仅学生可申请');
    const b = await this.bookings.findOne({ where: { id: bookingId } });
    if (!b) throw new NotFoundException('预约不存在');
    const inst = await this.inst.findOne({ where: { id: b.instrumentId } });
    if (!inst || !inst.piggyback) throw new BadRequestException('该仪器不支持蹭一下');
    if (b.userId === user.sub) throw new BadRequestException('这是你自己的预约');
    const dup = await this.pigg.findOne({ where: { bookingId, requesterId: user.sub, status: 'PENDING' } });
    if (dup) throw new BadRequestException('已申请，等待对方处理');
    await this.pigg.save(this.pigg.create({ bookingId, requesterId: user.sub, ownerId: b.userId, instrumentId: b.instrumentId, status: 'PENDING' }));
    return { ok: true };
  }

  private async decoratePigg(rs: PiggybackRequest[]) {
    const bids = [...new Set(rs.map((r) => r.bookingId))];
    const bs = bids.length ? await this.bookings.find({ where: { id: In(bids) } }) : [];
    const bm = new Map(bs.map((b) => [b.id, b]));
    const iids = [...new Set(bs.map((b) => b.instrumentId))];
    const insts = iids.length ? await this.inst.find({ where: { id: In(iids) } }) : [];
    const im = new Map(insts.map((i) => [i.id, i.name]));
    const uids = [...new Set(rs.flatMap((r) => [r.requesterId, r.ownerId]))];
    const us = uids.length ? await this.users.find({ where: { id: In(uids) } }) : [];
    const um = new Map(us.map((u) => [u.id, u.name]));
    const ST: Record<string, string> = { PENDING: '待处理', APPROVED: '已同意', REJECTED: '已拒绝' };
    return rs.map((r) => { const b = bm.get(r.bookingId); return {
      id: r.id, status: r.status, statusText: ST[r.status] || r.status,
      requesterName: um.get(r.requesterId) || '?', ownerName: um.get(r.ownerId) || '?',
      instrumentName: b ? (im.get(b.instrumentId) || '?') : '?',
      date: b ? b.date : null, startHour: b ? b.startHour : null, endHour: b ? b.endHour : null, taskType: b ? b.taskType : null, tempCeiling: b ? b.tempCeiling : null,
    }; });
  }
  async piggIncoming(user: any) { return this.decoratePigg(await this.pigg.find({ where: { ownerId: user.sub }, order: { createdAt: 'DESC' } })); }
  async piggMine(user: any) { return this.decoratePigg(await this.pigg.find({ where: { requesterId: user.sub }, order: { createdAt: 'DESC' } })); }
  async piggDecide(user: any, id: number, ok: boolean) {
    const r = await this.pigg.findOne({ where: { id } });
    if (!r) throw new NotFoundException('申请不存在');
    if (r.ownerId !== user.sub) throw new ForbiddenException('只能处理蹭你预约的申请');
    if (r.status !== 'PENDING') throw new BadRequestException('已处理');
    r.status = ok ? 'APPROVED' : 'REJECTED'; r.decidedAt = new Date(); await this.pigg.save(r);
    return { ok: true };
  }
"""
b64 = base64.b64encode(M.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s/src/instruments/instruments.service.ts'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('methods inserted')\nPYEOF" % (APP, b64))
print(" ", o.strip(), e[-150:])

# 注入 pigg repo + 导入
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["import { LotteryRun } from '../entities/lottery-run.entity';",
   "import { LotteryRun } from '../entities/lottery-run.entity';\nimport { PiggybackRequest } from '../entities/piggyback.entity';"],
  ["""    @InjectRepository(LotteryRun) private runs: Repository<LotteryRun>,
    @InjectRepository(User) private users: Repository<User>,""",
   """    @InjectRepository(LotteryRun) private runs: Repository<LotteryRun>,
    @InjectRepository(PiggybackRequest) private pigg: Repository<PiggybackRequest>,
    @InjectRepository(User) private users: Repository<User>,"""],
])

# controller 路由
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Delete('booking/claim/:id') release(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.releaseClaim(u, +id); }",
   """  @Delete('booking/claim/:id') release(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.releaseClaim(u, +id); }
  @Get('my-bookings') myBookings(@CurrentUser() u: any, @Query('cycle') c?: string) { return this.svc.myBookings(u.sub, c); }
  @Post('booking/cancel/:id') cancelBk(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.cancelBooking(u, +id); }
  @Post('booking/transfer/:id') transferBk(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.transferBooking(u, +id, b?.target); }
  @Post('piggyback') piggReq(@CurrentUser() u: any, @Body() b: any) { return this.svc.piggybackRequest(u, +b.bookingId); }
  @Get('piggyback/incoming') piggIn(@CurrentUser() u: any) { return this.svc.piggIncoming(u); }
  @Get('piggyback/mine') piggMine(@CurrentUser() u: any) { return this.svc.piggMine(u); }
  @Post('piggyback/:id/approve') piggOk(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.piggDecide(u, +id, true); }
  @Post('piggyback/:id/reject') piggNo(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.piggDecide(u, +id, false); }"""],
])

# module + app.module 注册实体
pyedit(APP + "/src/instruments/instruments.module.ts", [
  ["import { LotteryRun } from '../entities/lottery-run.entity';",
   "import { LotteryRun } from '../entities/lottery-run.entity';\nimport { PiggybackRequest } from '../entities/piggyback.entity';"],
  ["TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, User]),",
   "TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, User]),"],
])
pyedit(APP + "/src/app.module.ts", [
  ["import { LotteryRun } from './entities/lottery-run.entity';",
   "import { LotteryRun } from './entities/lottery-run.entity';\nimport { PiggybackRequest } from './entities/piggyback.entity';"],
  ["Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun],",
   "Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest],"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 25 --nostream 2>&1 | grep -ciE 'error TS'")

# ===== 拷贝有数据的两周 -> 本周(06-01)/下周(06-08) =====
sql("DELETE FROM plm_bookings WHERE cycleKey IN ('2026-06-01','2026-06-08')")
sql("INSERT INTO plm_bookings (cycleKey,instrumentId,userId,category,date,startHour,endHour,taskType,tempCeiling,source) "
    "SELECT '2026-06-01',instrumentId,userId,category,DATE_FORMAT(DATE_SUB(date,INTERVAL 14 DAY),'%Y-%m-%d'),startHour,endHour,taskType,tempCeiling,source "
    "FROM plm_bookings WHERE cycleKey='2026-06-15'")
sql("INSERT INTO plm_bookings (cycleKey,instrumentId,userId,category,date,startHour,endHour,taskType,tempCeiling,source) "
    "SELECT '2026-06-08',instrumentId,userId,category,DATE_FORMAT(DATE_SUB(date,INTERVAL 14 DAY),'%Y-%m-%d'),startHour,endHour,taskType,tempCeiling,source "
    "FROM plm_bookings WHERE cycleKey='2026-06-22'")
print("\n本周/下周条数:", sql("SELECT cycleKey,COUNT(*) FROM plm_bookings WHERE cycleKey IN ('2026-06-01','2026-06-08') GROUP BY cycleKey").replace("\n", "  "))

# ===== 自检 =====
def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p)); return json.loads(o).get("token")
H = "-H 'Authorization: Bearer %s'" % login("1225071", "Plm@2026")  # 陈卓
print("\n## 陈卓 本周我的预约（前几条）")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments/my-bookings?cycle=2026-06-01' %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('共',len(d),'条');[print(' ',x['date'],x['startHour'],x['instrumentName'][:16],x['taskType']) for x in d[:4]]\"" % H)
print(o)
# 取一条做取消(早于72h的未来格 → 本周多为过去; 用下周06-08里的一条)
H2 = "-H 'Authorization: Bearer %s'" % login("1225071", "Plm@2026")
bid = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT id FROM plm_bookings WHERE userId=(SELECT id FROM plm_users WHERE username='1225071') AND cycleKey='2026-06-08' ORDER BY date DESC LIMIT 1\" 2>/dev/null")[0].strip()
print("## 取消下周一条预约 id=%s（远期→应+1优先级）" % bid)
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/cancel/%s -H 'Content-Type: application/json' %s -d '{}'" % (bid, H2)); print("  ", o[:160])
# 蹭一下：找一条真空/环化的别人预约
ob = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT b.id FROM plm_bookings b JOIN plm_instruments i ON i.id=b.instrumentId WHERE b.cycleKey='2026-06-08' AND i.piggyback=1 AND b.userId<>(SELECT id FROM plm_users WHERE username='1225071') LIMIT 1\" 2>/dev/null")[0].strip()
print("## 陈卓 申请蹭 booking id=%s" % ob)
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/piggyback -H 'Content-Type: application/json' %s -d '{\"bookingId\":%s}'" % (H2, ob)); print("  ", o[:160])
# 该 booking 的 owner 处理
owner_uname = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT u.username FROM plm_bookings b JOIN plm_users u ON u.id=b.userId WHERE b.id=%s\" 2>/dev/null" % ob)[0].strip()
OH = "-H 'Authorization: Bearer %s'" % login(owner_uname, "Plm@2026")
print("## owner(%s) 收到的蹭一下申请" % owner_uname)
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/piggyback/incoming %s | python3 -c \"import sys,json;[print(' ',r['id'],r['requesterName'],'蹭',r['instrumentName'][:14],r['date'],r['statusText']) for r in json.load(sys.stdin)[:3]]\"" % OH)
print(o)
pid = run("curl -s http://127.0.0.1:3000/api/instruments/piggyback/incoming %s | python3 -c \"import sys,json;print(json.load(sys.stdin)[0]['id'])\"" % OH)[0].strip()
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/piggyback/%s/approve -H 'Content-Type: application/json' %s -d '{}'" % (pid, OH)); print("  通过:", o[:80])
print("## 陈卓 我蹭到的(应显示已同意+预约信息)")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/piggyback/mine %s | python3 -c \"import sys,json;[print(' ',r['instrumentName'][:14],r['date'],r['startHour'],r['statusText']) for r in json.load(sys.stdin)[:3]]\"" % H2)
print(o)
# 转赠
bid2 = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT id,category FROM plm_bookings WHERE userId=(SELECT id FROM plm_users WHERE username='1225071') AND cycleKey='2026-06-08' LIMIT 1\" 2>/dev/null")[0].strip().split('\t')
print("## 转赠 booking id=%s 给 尚瑞" % bid2[0])
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/transfer/%s -H 'Content-Type: application/json' %s -d '{\"target\":\"尚瑞\"}'" % (bid2[0], H2)); print("  ", o[:160])
cli.close(); print("\n=== DONE ===")
