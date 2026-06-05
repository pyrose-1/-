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
def run(cmd, t=400):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def step(t, c, to=400):
    o, e = run(c, to); print("\n#### %s" % t)
    if o: print(o[-2200:])
    if e: print("[stderr]", e[-700:])
def wfile(path, content):
    b = base64.b64encode(content.encode()).decode()
    run("python3 - <<'PY'\nimport base64\nopen(%r,'w',encoding='utf-8').write(base64.b64decode('%s').decode())\nprint('w')\nPY" % (path, b))
    print("  写", path.replace(APP, ""))
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:70])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-200:])

# ---------- .env ----------
step("追加邮件配置到 .env", "grep -q MAIL_HOST %s/.env || cat >> %s/.env <<'EOF'\nMAIL_HOST=smtp.163.com\nMAIL_PORT=465\nMAIL_USER=dhupilab@163.com\nMAIL_PASS=ANQccwewpz4YanF4\nMAIL_TEST_TO=zhangpeihuohuo@gmail.com\nEOF\necho appended; tail -6 %s/.env" % (APP, APP, APP))

# ---------- MailService / MailModule ----------
wfile(APP + "/src/mail/mail.service.ts", """import { Injectable, Logger } from '@nestjs/common';
import * as nodemailer from 'nodemailer';

@Injectable()
export class MailService {
  private readonly log = new Logger('Mail');
  private tx = nodemailer.createTransport({
    host: process.env.MAIL_HOST || 'smtp.163.com',
    port: Number(process.env.MAIL_PORT || 465),
    secure: Number(process.env.MAIL_PORT || 465) === 465,
    auth: { user: process.env.MAIL_USER, pass: process.env.MAIL_PASS },
  });
  get from() { return `\\"聚酰亚胺实验室管理系统\\" <${process.env.MAIL_USER}>`; }
  async send(to: string, subject: string, html: string) {
    if (!process.env.MAIL_USER) { this.log.warn('MAIL_USER 未配置，跳过发送'); return { skipped: true }; }
    const info = await this.tx.sendMail({ from: this.from, to, subject, html });
    this.log.log(`已发送 -> ${to} (${info.messageId})`);
    return { messageId: info.messageId };
  }
}
""")
wfile(APP + "/src/mail/mail.module.ts", """import { Global, Module } from '@nestjs/common';
import { MailService } from './mail.service';

@Global()
@Module({ providers: [MailService], exports: [MailService] })
export class MailModule {}
""")

# ---------- app.module: ScheduleModule + MailModule ----------
pyedit(APP + "/src/app.module.ts", [
  ["import { ConfigModule } from '@nestjs/config';",
   "import { ConfigModule } from '@nestjs/config';\nimport { ScheduleModule } from '@nestjs/schedule';\nimport { MailModule } from './mail/mail.module';"],
  ["    ConfigModule.forRoot({ isGlobal: true }),",
   "    ConfigModule.forRoot({ isGlobal: true }),\n    ScheduleModule.forRoot(),\n    MailModule,"],
])

# ---------- users.service: safe()+phone/email, updateMe ----------
pyedit(APP + "/src/users/users.service.ts", [
  ["import { ConflictException, Injectable, OnApplicationBootstrap } from '@nestjs/common';",
   "import { BadRequestException, ConflictException, Injectable, NotFoundException, OnApplicationBootstrap } from '@nestjs/common';"],
  ["  safe(u: User) { return { id: u.id, username: u.username, name: u.name, role: u.role, groupId: u.groupId, tutorId: u.tutorId, status: u.status }; }",
   """  safe(u: User) { return { id: u.id, username: u.username, name: u.name, role: u.role, groupId: u.groupId, tutorId: u.tutorId, phone: u.phone ?? null, email: u.email ?? null, status: u.status }; }
  async updateMe(id: number, dto: any) {
    const u = await this.repo.findOne({ where: { id } });
    if (!u) throw new NotFoundException('用户不存在');
    if (dto.name !== undefined && String(dto.name).trim()) u.name = String(dto.name).trim();
    if (dto.phone !== undefined) u.phone = dto.phone ? String(dto.phone).trim() : null;
    if (dto.email !== undefined) {
      const em = dto.email ? String(dto.email).trim() : '';
      if (em && !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(em)) throw new BadRequestException('邮箱格式不正确');
      u.email = em || null;
    }
    if (dto.tutorId !== undefined && dto.tutorId !== null && dto.tutorId !== '') {
      const t = await this.repo.findOne({ where: { id: Number(dto.tutorId) } });
      if (!t || t.role !== 'TUTOR') throw new BadRequestException('所选导师无效');
      u.tutorId = t.id;
    }
    await this.repo.save(u);
    return this.safe(u);
  }"""],
])
pyedit(APP + "/src/users/users.controller.ts", [
  ["  @Get('me') me(@CurrentUser() u: any) { return this.users.me(u.sub); }",
   "  @Get('me') me(@CurrentUser() u: any) { return this.users.me(u.sub); }\n  @Post('me') updateMe(@CurrentUser() u: any, @Body() b: any) { return this.users.updateMe(u.sub, b); }"],
])

# ---------- instruments.module: PurchaseRequest forFeature ----------
pyedit(APP + "/src/instruments/instruments.module.ts", [
  ["import { PersonalEvent } from '../entities/personal-event.entity';",
   "import { PersonalEvent } from '../entities/personal-event.entity';\nimport { PurchaseRequest } from '../entities/purchase-request.entity';"],
  ["TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent, User]),",
   "TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent, PurchaseRequest, User]),"],
])

# ---------- instruments.service: imports + ctor inject + helpers + live list + overview + cron mail ----------
SVC = APP + "/src/instruments/instruments.service.ts"
pyedit(SVC, [
  ["import { BadRequestException, ForbiddenException, Injectable, NotFoundException, OnApplicationBootstrap } from '@nestjs/common';",
   "import { BadRequestException, ForbiddenException, Injectable, Logger, NotFoundException, OnApplicationBootstrap } from '@nestjs/common';\nimport { Cron } from '@nestjs/schedule';\nimport { MailService } from '../mail/mail.service';\nimport { PurchaseRequest } from '../entities/purchase-request.entity';"],
  ["    @InjectRepository(PersonalEvent) private events: Repository<PersonalEvent>,\n    @InjectRepository(User) private users: Repository<User>,",
   "    @InjectRepository(PersonalEvent) private events: Repository<PersonalEvent>,\n    @InjectRepository(PurchaseRequest) private purchases: Repository<PurchaseRequest>,\n    @InjectRepository(User) private users: Repository<User>,\n    private mail: MailService,"],
  # live status in list()
  ["""  async list(category?: string) {
    const where: any = { active: true };
    if (category) where.category = category;
    const all = await this.inst.find({ where, order: { category: 'ASC', id: 'ASC' } });
    return all;
  }""",
   """  private todayLocal() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
  private addDaysStr(iso: string, n: number) { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }

  async list(category?: string) {
    const where: any = { active: true };
    if (category) where.category = category;
    const all = await this.inst.find({ where, order: { category: 'ASC', id: 'ASC' } });
    const today = this.todayLocal(); const h = new Date().getHours();
    const todayBks = await this.bookings.find({ where: { date: today } });
    const occ = new Set(todayBks.filter((b) => b.startHour <= h && h < b.endHour).map((b) => b.instrumentId));
    return all.map((i) => ({ ...i, occupied: occ.has(i.id) }));
  }"""],
])

# 追加 overview + 邮件方法到类末尾
M = r"""
  // ===== 本周实验室总览 =====
  async overview(week?: string) {
    const ck = week || this.mondayOf(this.todayLocal());
    const insts = await this.inst.find({ where: { active: true } });
    const bks = await this.bookings.find({ where: { cycleKey: ck } });
    const demands = await this.demands.find({ where: { cycleKey: ck } });
    const n = (cat: string) => insts.filter((i) => i.category === cat).length;
    const used = (cat: string) => bks.filter((b) => b.category === cat).length;
    const rate = (u: number, c: number) => (c > 0 ? Math.round((u / c) * 100) : 0);
    const vac = insts.filter((i) => i.category === 'VACUUM_OVEN');
    const filmOvens = vac.filter((i) => i.filmCapable).length;
    const dryPerDay = vac.reduce((s, i) => s + (i.filmCapable ? 1 : 4), 0);
    const filmCap = filmOvens * 7, dryCap = dryPerDay * 7;
    const filmUsed = bks.filter((b) => b.category === 'VACUUM_OVEN' && b.taskType === 'FILM').length;
    const dryUsed = bks.filter((b) => b.category === 'VACUUM_OVEN' && b.taskType === 'DRY').length;
    const util = [
      { key: 'VACUUM_FILM', label: '真空烘箱·铺膜位', used: filmUsed, cap: filmCap, rate: rate(filmUsed, filmCap) },
      { key: 'VACUUM_DRY', label: '真空烘箱·干燥位', used: dryUsed, cap: dryCap, rate: rate(dryUsed, dryCap) },
      { key: 'CYCLE_OVEN', label: '环化烘箱', used: used('CYCLE_OVEN'), cap: n('CYCLE_OVEN') * 7, rate: rate(used('CYCLE_OVEN'), n('CYCLE_OVEN') * 7) },
      { key: 'MUFFLE', label: '马弗炉', used: used('MUFFLE'), cap: n('MUFFLE') * 7, rate: rate(used('MUFFLE'), n('MUFFLE') * 7) },
      { key: 'TUBE', label: '管式炉', used: used('TUBE'), cap: n('TUBE') * 7, rate: rate(used('TUBE'), n('TUBE') * 7) },
      { key: 'BET', label: 'BET', used: used('BET'), cap: n('BET') * 7, rate: rate(used('BET'), n('BET') * 7) },
      { key: 'POLY_HEAD', label: '聚合机头', used: used('POLY_HEAD'), cap: n('POLY_HEAD') * 7 * 2, rate: rate(used('POLY_HEAD'), n('POLY_HEAD') * 7 * 2) },
      { key: 'DMA', label: 'DMA', used: used('DMA'), cap: n('DMA') * 7 * 4, rate: rate(used('DMA'), n('DMA') * 7 * 4) },
      { key: 'TGA', label: 'TGA', used: used('TGA'), cap: n('TGA') * 7 * 4, rate: rate(used('TGA'), n('TGA') * 7 * 4) },
    ];

    // 上周(周一~周日)审批通过申购总金额
    const lastMon = this.addDaysStr(this.mondayOf(this.todayLocal()), -7);
    const lastSun = this.addDaysStr(lastMon, 6);
    const lo = new Date(lastMon + 'T00:00:00').getTime();
    const hi = new Date(this.addDaysStr(lastMon, 7) + 'T00:00:00').getTime();
    const reqs = await this.purchases.find({ where: { status: 'APPROVED' } });
    let amount = 0, count = 0;
    for (const r of reqs) { const t = r.reviewedAt ? new Date(r.reviewedAt).getTime() : 0; if (t >= lo && t < hi) { amount += Number(r.price || 0); count++; } }

    // 本周紧俏程度：需求格子数 / 可约格子数
    const dsum = (cat: string, key: 'film' | 'dry' | 'block') => demands.filter((d) => d.category === cat).reduce((s, d) => s + (key === 'film' ? d.filmCount : key === 'dry' ? d.dryCount : d.blockCount), 0);
    const tcats = [
      { key: 'VACUUM_OVEN', label: '真空烘箱', demand: dsum('VACUUM_OVEN', 'film') + dsum('VACUUM_OVEN', 'dry'), cap: filmCap + dryCap },
      { key: 'CYCLE_OVEN', label: '环化烘箱', demand: dsum('CYCLE_OVEN', 'block'), cap: n('CYCLE_OVEN') * 7 },
      { key: 'MUFFLE', label: '马弗炉', demand: dsum('MUFFLE', 'block'), cap: n('MUFFLE') * 7 },
      { key: 'TUBE', label: '管式炉', demand: dsum('TUBE', 'block'), cap: n('TUBE') * 7 },
      { key: 'BET', label: 'BET', demand: dsum('BET', 'block'), cap: n('BET') * 7 },
      { key: 'POLY_HEAD', label: '聚合机头', demand: dsum('POLY_HEAD', 'block'), cap: n('POLY_HEAD') * 7 * 2 },
      { key: 'DMA', label: 'DMA', demand: dsum('DMA', 'block'), cap: n('DMA') * 7 * 4 },
      { key: 'TGA', label: 'TGA', demand: dsum('TGA', 'block'), cap: n('TGA') * 7 * 4 },
    ].map((c) => ({ ...c, ratio: c.cap > 0 ? Math.round((c.demand / c.cap) * 100) / 100 : 0 }));
    const totDem = tcats.reduce((s, c) => s + c.demand, 0);
    const totCap = tcats.reduce((s, c) => s + c.cap, 0);
    const ratio = totCap > 0 ? totDem / totCap : 0;
    const score = Math.round(Math.min(ratio, 1) * 100) / 10; // 0~10 分
    const level = score >= 8 ? '非常紧张' : score >= 6 ? '紧张' : score >= 4 ? '适中' : score >= 2 ? '较宽松' : '宽松';
    tcats.sort((a, b) => b.ratio - a.ratio);

    return { cycleKey: ck, util, lastWeekPurchase: { amount: Math.round(amount * 100) / 100, count, from: lastMon, to: lastSun }, tightness: { score, level, totalDemand: totDem, totalCap, cats: tcats } };
  }

  // ===== 每周一 8:30 起陆续发送 抽签结果 + 本周日程 =====
  private sleep(ms: number) { return new Promise((r) => setTimeout(r, ms)); }
  private async buildWeeklyHtml(uid: number, name: string, ck: string) {
    const days = this.weekDates(ck);
    const WD = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    const TASK: Record<string, string> = { FILM: '铺膜', DRY: '干燥', FULL_DAY: '全天', HALF_DAY: '半天', BLOCK: '占用' };
    const bks = await this.myBookings(uid, ck);
    const evs = await this.listEvents(uid, days[0], days[6]);
    const fmt = (d: string) => d.slice(5);
    let rows = '';
    for (let i = 0; i < 7; i++) {
      const day = days[i];
      const dayBks = bks.filter((b: any) => b.date === day).map((b: any) => `${b.startHour}:00-${b.endHour}:00 ${b.instrumentName} ${TASK[b.taskType] || ''}${b.fromName ? '（来自' + b.fromName + '）' : ''}`);
      const dayEvs = evs.filter((e: any) => new Date(e.startAt).toISOString().slice(0, 10) === day).map((e: any) => `${new Date(e.startAt).getHours()}:00 ${e.title}${e.location ? ' @' + e.location : ''}`);
      const cell = [...dayBks.map((x) => '🔬 ' + x), ...dayEvs.map((x) => '📌 ' + x)].join('<br>') || '<span style="color:#94a3b8">—</span>';
      rows += `<tr><td style="padding:6px 10px;border:1px solid #e2e8f0;white-space:nowrap;font-weight:600">${WD[i]} ${fmt(day)}</td><td style="padding:6px 10px;border:1px solid #e2e8f0">${cell}</td></tr>`;
    }
    return `<div style="font-family:system-ui,Arial,sans-serif;color:#334155;max-width:680px">
      <h2 style="color:#1E3A8A;margin:0 0 4px">本周仪器排班 & 日程</h2>
      <p style="margin:0 0 12px;color:#64748b">${name} 同学，以下是你本周（${days[0]} ~ ${days[6]}）的仪器预约与个人日程。</p>
      <table style="border-collapse:collapse;width:100%;font-size:14px"><tbody>${rows}</tbody></table>
      <p style="margin:14px 0 0;color:#94a3b8;font-size:12px">🔬 仪器预约 · 📌 个人日程 ｜ 本邮件由聚酰亚胺实验室管理系统自动发送，请勿直接回复。</p>
    </div>`;
  }
  async sendWeeklyMail(testTo?: string) {
    const ck = this.mondayOf(this.todayLocal());
    if (testTo) {
      const html = await this.buildWeeklyHtml(0, '测试', ck).catch(() => '<p>测试内容生成失败</p>');
      const r = await this.mail.send(testTo, '【实验室管理系统】邮件服务测试', `<div style="font-family:system-ui,Arial,sans-serif;color:#334155"><h2 style="color:#1E3A8A">邮件服务连通测试</h2><p>这是一封来自<b>聚酰亚胺实验室管理系统</b>的测试邮件，说明 SMTP（163）配置正确，每周一 8:30 的抽签结果与日程推送已就绪。</p><hr style="border:none;border-top:1px solid #e2e8f0"/><p style="color:#64748b;font-size:13px">下方为周报样式预览：</p>${html}</div>`);
      return { test: true, ...r };
    }
    const us = await this.users.find({ where: { role: 'STUDENT' as any } });
    const targets = us.filter((u) => u.email && /@/.test(u.email));
    let sent = 0;
    for (const u of targets) {
      try { const html = await this.buildWeeklyHtml(u.id, u.name, ck); await this.mail.send(u.email!, '【实验室】本周仪器排班与日程提醒', html); sent++; }
      catch (e) { /* 单封失败不影响其余 */ }
      await this.sleep(22000); // 陆续发送，约 30 分钟内发完
    }
    return { sent, total: targets.length };
  }
  @Cron('30 8 * * 1')
  async cronWeeklyMail() { try { await this.sendWeeklyMail(); } catch (e) { new Logger('Mail').error('周报发送失败', e as any); } }
"""
b64 = base64.b64encode(M.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('methods inserted')\nPYEOF" % (SVC, b64))
print(" ", o.strip(), e[-200:])

# ---------- controller: overview + mail test ----------
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Get('student-schedule/:id') stuSched(@Param('id') id: string, @CurrentUser() u: any, @Query('week') w: string) { return this.svc.studentSchedule(u, +id, w); }",
   """  @Get('student-schedule/:id') stuSched(@Param('id') id: string, @CurrentUser() u: any, @Query('week') w: string) { return this.svc.studentSchedule(u, +id, w); }
  @Get('overview') overview(@Query('week') w?: string) { return this.svc.overview(w); }
  @Post('mail/test') mailTest(@CurrentUser() u: any, @Body() b: any) { return this.svc.sendWeeklyMail(b?.to || process.env.MAIL_TEST_TO); }"""],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -12 && echo BUILT" % APP, 480)
step("重启", PATHX + "pm2 restart plm-api >/dev/null 2>&1; sleep 4; pm2 logs plm-api --lines 6 --nostream 2>&1 | tail -8")
cli.close(); print("\n=== DONE ===")
