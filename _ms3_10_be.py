# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t)
    if o: print(o[-1800:])
    if e: print("[stderr]", e[-800:])
def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content)); print("  写", path.replace(APP, ""))
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

SVC = APP + "/src/instruments/instruments.service.ts"

# 实体
wfile(APP + "/src/entities/personal-event.entity.ts", """import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_events')
export class PersonalEvent {
  @PrimaryGeneratedColumn() id: number;
  @Column() userId: number;
  @Column() title: string;
  @Column({ nullable: true }) location: string | null;
  @Column({ type: 'datetime' }) startAt: Date;
  @Column({ type: 'datetime' }) endAt: Date;
  @CreateDateColumn() createdAt: Date;
}
""")

# 1) claim 过期拦截
pyedit(SVC, [
  ["""    const ex = await this.bookings.find({ where: { instrumentId: inst.id, date } });
    for (const b of ex) if (b.startHour < eh && sh < b.endHour) throw new BadRequestException('该时段已被占用');""",
   """    const slotStart = new Date(date + 'T' + String(sh).padStart(2, '0') + ':00:00');
    if (slotStart.getTime() < Date.now()) throw new BadRequestException('该时段已过期，不可预约');
    const ex = await this.bookings.find({ where: { instrumentId: inst.id, date } });
    for (const b of ex) if (b.startHour < eh && sh < b.endHour) throw new BadRequestException('该时段已被占用');"""],
])
# 2) decoratePigg CANCELLED + 3) piggCancel；事件方法 —— 追加方法块
M = r"""
  async piggCancel(user: any, id: number) {
    const r = await this.pigg.findOne({ where: { id } });
    if (!r) throw new NotFoundException('申请不存在');
    if (r.requesterId !== user.sub) throw new ForbiddenException('只能取消自己的蹭一下');
    if (r.status === 'REJECTED') throw new BadRequestException('该申请已被拒绝');
    r.status = 'CANCELLED'; r.decidedAt = new Date(); await this.pigg.save(r);
    return { ok: true };
  }

  // ===== 个人日程 =====
  async listEvents(userId: number, from?: string, to?: string) {
    const evs = await this.events.find({ where: { userId }, order: { startAt: 'ASC' } });
    return evs.filter((e) => { const s = new Date(e.startAt).toISOString().slice(0, 10); return (!from || s >= from) && (!to || s <= to); });
  }
  async createEvent(userId: number, dto: any) {
    if (!dto.title || !String(dto.title).trim()) throw new BadRequestException('请填写事项');
    const startAt = new Date(dto.startAt);
    if (isNaN(startAt.getTime())) throw new BadRequestException('开始时间无效');
    let endAt = dto.endAt ? new Date(dto.endAt) : new Date(startAt.getTime() + 3600000);
    if (isNaN(endAt.getTime()) || endAt.getTime() <= startAt.getTime()) endAt = new Date(startAt.getTime() + 3600000);
    const ev = this.events.create({ userId, title: String(dto.title).trim(), location: dto.location || null, startAt, endAt });
    return this.events.save(ev);
  }
  async deleteEvent(user: any, id: number) {
    const ev = await this.events.findOne({ where: { id } });
    if (!ev) throw new NotFoundException('日程不存在');
    if (ev.userId !== user.sub) throw new ForbiddenException('只能删除自己的日程');
    await this.events.remove(ev);
    return { ok: true };
  }
  async studentSchedule(user: any, studentId: number, week: string) {
    const target = await this.users.findOne({ where: { id: studentId } });
    if (!target) throw new NotFoundException('学生不存在');
    if (user.role === 'TUTOR' && target.tutorId !== user.sub) throw new ForbiddenException('只能查看本人指导的学生');
    if (user.role !== 'ADMIN' && user.role !== 'TUTOR') throw new ForbiddenException('无权限');
    const days = this.weekDates(week);
    const bookings = await this.myBookings(studentId, week);
    const events = await this.listEvents(studentId, days[0], days[6]);
    return { student: { id: target.id, name: target.name }, bookings, events };
  }
"""
b64 = base64.b64encode(M.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('methods inserted')\nPYEOF" % (SVC, b64))
print(" ", o.strip(), e[-150:])

# decoratePigg 状态加 CANCELLED + 注入 events repo + import
pyedit(SVC, [
  ["const ST: Record<string, string> = { PENDING: '待处理', APPROVED: '已同意', REJECTED: '已拒绝' };",
   "const ST: Record<string, string> = { PENDING: '待处理', APPROVED: '已同意', REJECTED: '已拒绝', CANCELLED: '已取消' };"],
  ["import { PiggybackRequest } from '../entities/piggyback.entity';",
   "import { PiggybackRequest } from '../entities/piggyback.entity';\nimport { PersonalEvent } from '../entities/personal-event.entity';"],
  ["""    @InjectRepository(PiggybackRequest) private pigg: Repository<PiggybackRequest>,
    @InjectRepository(User) private users: Repository<User>,""",
   """    @InjectRepository(PiggybackRequest) private pigg: Repository<PiggybackRequest>,
    @InjectRepository(PersonalEvent) private events: Repository<PersonalEvent>,
    @InjectRepository(User) private users: Repository<User>,"""],
])

# controller 路由
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Post('piggyback/:id/reject') piggNo(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.piggDecide(u, +id, false); }",
   """  @Post('piggyback/:id/reject') piggNo(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.piggDecide(u, +id, false); }
  @Post('piggyback/:id/cancel') piggCancel(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.piggCancel(u, +id); }
  @Get('events') listEvents(@CurrentUser() u: any, @Query('from') f?: string, @Query('to') t?: string) { return this.svc.listEvents(u.sub, f, t); }
  @Post('events') addEvent(@CurrentUser() u: any, @Body() b: any) { return this.svc.createEvent(u.sub, b); }
  @Delete('events/:id') delEvent(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.deleteEvent(u, +id); }
  @Get('student-schedule/:id') stuSched(@Param('id') id: string, @CurrentUser() u: any, @Query('week') w: string) { return this.svc.studentSchedule(u, +id, w); }"""],
])
# module + app.module 注册实体
pyedit(APP + "/src/instruments/instruments.module.ts", [
  ["import { PiggybackRequest } from '../entities/piggyback.entity';",
   "import { PiggybackRequest } from '../entities/piggyback.entity';\nimport { PersonalEvent } from '../entities/personal-event.entity';"],
  ["TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, User]),",
   "TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent, User]),"],
])
pyedit(APP + "/src/app.module.ts", [
  ["import { PiggybackRequest } from './entities/piggyback.entity';",
   "import { PiggybackRequest } from './entities/piggyback.entity';\nimport { PersonalEvent } from './entities/personal-event.entity';"],
  ["Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest],",
   "Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent],"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -8 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p)); return json.loads(o).get("token")
H = "-H 'Authorization: Bearer %s'" % login("1225071", "Plm@2026")
print("\n## 过期时段 claim(应拒)")
iid = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT id FROM plm_instruments WHERE category='DMA' LIMIT 1\" 2>/dev/null")[0].strip()
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/claim -H 'Content-Type: application/json' %s -d '{\"instrumentId\":%s,\"date\":\"2026-06-01\",\"startHour\":8,\"endHour\":12}'" % (H, iid)); print("  ", o[:120])
print("## 新增个人日程")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/events -H 'Content-Type: application/json' %s -d '{\"title\":\"组会\",\"location\":\"A301\",\"startAt\":\"2026-06-05T14:00:00\",\"endAt\":\"2026-06-05T15:00:00\"}'" % H); print("  ", o[:160])
o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments/events?from=2026-06-01&to=2026-06-07' %s | python3 -c \"import sys,json;[print(' ',e['title'],e['location'],e['startAt']) for e in json.load(sys.stdin)]\"" % H); print(o)
print("## 导师甲? -> 该生导师 查看其本周日程")
tut = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT t.username FROM plm_users s JOIN plm_users t ON t.id=s.tutorId WHERE s.username='1225071'\" 2>/dev/null")[0].strip()
print("  导师账号:", tut or "(无导师)")
cli.close(); print("\n=== DONE ===")
