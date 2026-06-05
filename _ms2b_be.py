# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
ADMINPW = "Pniaef6b526!"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=300):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2600:])
    if err: print("[stderr]", err[-1400:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(APP, ""))

# ---------- User 实体 加 tutorId ----------
wfile(APP + "/src/entities/user.entity.ts", """import { Column, CreateDateColumn, Entity, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { Group } from './group.entity';

export type Role = 'STUDENT' | 'TUTOR' | 'ADMIN';

@Entity('plm_users')
export class User {
  @PrimaryGeneratedColumn() id: number;
  @Column({ unique: true }) username: string;
  @Column() passwordHash: string;
  @Column() name: string;
  @Column({ type: 'enum', enum: ['STUDENT', 'TUTOR', 'ADMIN'], default: 'STUDENT' }) role: Role;
  @Column({ nullable: true }) groupId: number | null;
  @ManyToOne(() => Group, (g) => g.users, { nullable: true }) @JoinColumn({ name: 'groupId' }) group?: Group;
  @Column({ type: 'int', nullable: true }) tutorId: number | null;
  @Column({ nullable: true }) phone: string | null;
  @Column({ nullable: true }) email: string | null;
  @Column({ default: 'ACTIVE' }) status: string;
  @CreateDateColumn() createdAt: Date;
  @UpdateDateColumn() updatedAt: Date;
}
""")

# ---------- ChemicalBatch 加 location ----------
wfile(APP + "/src/entities/chemical-batch.entity.ts", """import { Column, CreateDateColumn, Entity, JoinColumn, ManyToOne, PrimaryGeneratedColumn } from 'typeorm';
import { Chemical } from './chemical.entity';

@Entity('plm_chemical_batches')
export class ChemicalBatch {
  @PrimaryGeneratedColumn() id: number;
  @Column() chemicalId: number;
  @ManyToOne(() => Chemical, (c) => c.batches) @JoinColumn({ name: 'chemicalId' }) chemical: Chemical;
  @Column({ unique: true }) batchNo: string;
  @Column({ default: 'PUBLIC' }) scope: string;
  @Column({ nullable: true }) ownerId: number | null;
  @Column({ default: false }) shareable: boolean;
  @Column({ default: 'FULL' }) remainLevel: string;
  @Column({ nullable: true }) manufacturer: string | null;
  @Column({ nullable: true }) location: string | null;
  @Column({ type: 'date', nullable: true }) expiry: string | null;
  @Column({ type: 'datetime', nullable: true }) openedAt: Date | null;
  @Column({ type: 'datetime', nullable: true }) lastUsedAt: Date | null;
  @Column({ nullable: true }) qrCodePath: string | null;
  @CreateDateColumn() receivedAt: Date;
}
""")

# ---------- PurchaseRequest 加 货号/价格/导师/入库字段 + DRAFT ----------
wfile(APP + "/src/entities/purchase-request.entity.ts", """import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_purchase_requests')
export class PurchaseRequest {
  @PrimaryGeneratedColumn() id: number;
  @Column() applicantId: number;
  @Column({ type: 'int', nullable: true }) tutorId: number | null;
  @Column({ type: 'int', nullable: true }) chemicalId: number | null;
  @Column() name: string;
  @Column({ length: 64, nullable: true }) cas: string | null;
  @Column({ length: 64, nullable: true }) productNo: string | null;
  @Column({ type: 'decimal', precision: 12, scale: 2, nullable: true }) price: string | null;
  @Column({ length: 64, nullable: true }) quantity: string | null;
  @Column({ length: 16, nullable: true }) unit: string | null;
  @Column({ type: 'text', nullable: true }) reason: string | null;
  @Column({ default: 'NORMAL' }) urgency: string;
  @Column({ default: 'DRAFT' }) status: string;
  @Column({ default: false }) hazmatListed: boolean;
  @Column({ default: false }) hazmatToxic: boolean;
  @Column({ type: 'text', nullable: true }) dupNote: string | null;
  @Column({ default: false }) ackDup: boolean;
  @Column({ type: 'int', nullable: true }) reviewerId: number | null;
  @Column({ type: 'text', nullable: true }) reviewComment: string | null;
  @Column({ type: 'datetime', nullable: true }) reviewedAt: Date | null;
  @Column({ type: 'int', nullable: true }) batchId: number | null;
  @Column({ nullable: true }) stockLocation: string | null;
  @Column({ type: 'datetime', nullable: true }) stockedAt: Date | null;
  @Column({ type: 'datetime', nullable: true }) submittedAt: Date | null;
  @CreateDateColumn() createdAt: Date;
}
""")

# ---------- CreateUserDto 加 tutorId ----------
wfile(APP + "/src/users/dto/create-user.dto.ts", """import { IsIn, IsInt, IsOptional, IsString, MinLength } from 'class-validator';
export class CreateUserDto {
  @IsString() @MinLength(2) username: string;
  @IsString() @MinLength(6) password: string;
  @IsString() name: string;
  @IsOptional() @IsIn(['STUDENT', 'TUTOR', 'ADMIN']) role?: 'STUDENT' | 'TUTOR' | 'ADMIN';
  @IsOptional() @IsInt() groupId?: number;
  @IsOptional() @IsInt() tutorId?: number;
}
""")

# ---------- CreatePurchaseDto 加 货号/价格 ----------
wfile(APP + "/src/purchases/dto/create-purchase.dto.ts", """import { IsBoolean, IsOptional, IsString, MinLength } from 'class-validator';

export class CreatePurchaseDto {
  @IsString() @MinLength(1) name: string;
  @IsOptional() @IsString() cas?: string;
  @IsOptional() @IsString() productNo?: string;
  @IsOptional() @IsString() price?: string;
  @IsOptional() @IsString() quantity?: string;
  @IsOptional() @IsString() unit?: string;
  @IsOptional() @IsString() reason?: string;
  @IsOptional() @IsString() urgency?: string;
  @IsOptional() @IsBoolean() ackDup?: boolean;
}
""")

# ---------- users.service 重写：播种导师/学生 + tutors + safe(tutorId) ----------
wfile(APP + "/src/users/users.service.ts", r"""import { ConflictException, Injectable, OnApplicationBootstrap } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcryptjs';
import { User } from '../entities/user.entity';
import { CreateUserDto } from './dto/create-user.dto';

const DEMO_PW = 'Plm@2026';

@Injectable()
export class UsersService implements OnApplicationBootstrap {
  constructor(@InjectRepository(User) private readonly repo: Repository<User>) {}

  async onApplicationBootstrap() {
    // 管理员
    const adminName = process.env.ADMIN_USERNAME || 'admin';
    if (!(await this.repo.findOne({ where: { username: adminName } }))) {
      const passwordHash = await bcrypt.hash(process.env.ADMIN_PASSWORD || 'admin123456', 10);
      await this.repo.save(this.repo.create({ username: adminName, name: '系统管理员', role: 'ADMIN', passwordHash, status: 'ACTIVE' }));
      console.log('[seed] admin created');
    }
    // 四位导师 甲乙丙丁
    const tutors = [
      { username: 'tutor_jia', name: '导师甲' },
      { username: 'tutor_yi', name: '导师乙' },
      { username: 'tutor_bing', name: '导师丙' },
      { username: 'tutor_ding', name: '导师丁' },
    ];
    const hash = await bcrypt.hash(DEMO_PW, 10);
    const tutorId: Record<string, number> = {};
    for (const t of tutors) {
      let u = await this.repo.findOne({ where: { username: t.username } });
      if (!u) { u = await this.repo.save(this.repo.create({ username: t.username, name: t.name, role: 'TUTOR', passwordHash: hash, status: 'ACTIVE' })); console.log('[seed] tutor', t.username); }
      tutorId[t.username] = u.id;
    }
    // 学生（分属不同导师）
    const students = [
      { username: 'stu_xm', name: '学生小明', tutor: 'tutor_jia' },
      { username: 'stu_xg', name: '学生小刚', tutor: 'tutor_jia' },
      { username: 'stu_xh', name: '学生小红', tutor: 'tutor_yi' },
    ];
    for (const s of students) {
      if (!(await this.repo.findOne({ where: { username: s.username } }))) {
        await this.repo.save(this.repo.create({ username: s.username, name: s.name, role: 'STUDENT', tutorId: tutorId[s.tutor], passwordHash: hash, status: 'ACTIVE' }));
        console.log('[seed] student', s.username);
      }
    }
  }

  safe(u: User) { return { id: u.id, username: u.username, name: u.name, role: u.role, groupId: u.groupId, tutorId: u.tutorId, status: u.status }; }
  async list() { const us = await this.repo.find({ order: { id: 'ASC' } }); return us.map((u) => this.safe(u)); }
  async tutors() { const us = await this.repo.find({ where: { role: 'TUTOR', status: 'ACTIVE' }, order: { id: 'ASC' } }); return us.map((u) => ({ id: u.id, name: u.name })); }
  async me(id: number) { const u = await this.repo.findOne({ where: { id } }); return u ? this.safe(u) : null; }
  async create(dto: CreateUserDto) {
    if (await this.repo.findOne({ where: { username: dto.username } })) throw new ConflictException('用户名已存在');
    const passwordHash = await bcrypt.hash(dto.password, 10);
    const u = await this.repo.save(this.repo.create({ username: dto.username, name: dto.name, role: dto.role || 'STUDENT', groupId: dto.groupId ?? null, tutorId: dto.tutorId ?? null, passwordHash, status: 'ACTIVE' }));
    return this.safe(u);
  }
}
""")

# ---------- users.controller 加 GET tutors ----------
wfile(APP + "/src/users/users.controller.ts", """import { Body, Controller, Get, Post, UseGuards } from '@nestjs/common';
import { UsersService } from './users.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Roles } from '../common/roles.decorator';
import { CurrentUser } from '../common/current-user.decorator';
import { CreateUserDto } from './dto/create-user.dto';

@Controller('users')
@UseGuards(JwtAuthGuard)
export class UsersController {
  constructor(private readonly users: UsersService) {}
  @Get('me') me(@CurrentUser() u: any) { return this.users.me(u.sub); }
  @Get('tutors') tutors() { return this.users.tutors(); }
  @Get() @UseGuards(RolesGuard) @Roles('ADMIN') list() { return this.users.list(); }
  @Post() @UseGuards(RolesGuard) @Roles('ADMIN') create(@Body() dto: CreateUserDto) { return this.users.create(dto); }
}
""")

# ---------- purchases.service 重写：DRAFT购物车 + submit + 自动入库 ----------
wfile(APP + "/src/purchases/purchases.service.ts", r"""import { BadRequestException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { pinyin } from 'pinyin-pro';
import { PurchaseRequest } from '../entities/purchase-request.entity';
import { Chemical } from '../entities/chemical.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { User } from '../entities/user.entity';
import { HazmatService, normCas } from '../hazmat/hazmat.service';
import { CreatePurchaseDto } from './dto/create-purchase.dto';

const levelText: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' };
const NONEMPTY = ['FULL', 'ALMOST_FULL', 'HALF', 'LOW', 'LITTLE'];

@Injectable()
export class PurchasesService {
  constructor(
    @InjectRepository(PurchaseRequest) private reqs: Repository<PurchaseRequest>,
    @InjectRepository(Chemical) private chem: Repository<Chemical>,
    @InjectRepository(ChemicalBatch) private batch: Repository<ChemicalBatch>,
    @InjectRepository(User) private users: Repository<User>,
    private hazmat: HazmatService,
  ) {}

  async precheck(name?: string, cas?: string) {
    const hz = this.hazmat.lookup(cas);
    const c = normCas(cas);
    const nm = (name || '').trim().toLowerCase();
    let matched: Chemical[] = [];
    const all = await this.chem.find({ where: { active: true } });
    if (c) matched = all.filter((x) => normCas(x.cas) === c);
    if (matched.length === 0 && nm) matched = all.filter((x) => x.name.toLowerCase().includes(nm) || (x.aliases || []).some((a) => a.toLowerCase().includes(nm)));
    const ids = matched.map((m) => m.id);
    const batches = ids.length ? await this.batch.find({ where: { chemicalId: In(ids) } }) : [];
    const ownerIds = [...new Set(batches.filter((b) => b.ownerId).map((b) => b.ownerId as number))];
    const owners = ownerIds.length ? await this.users.find({ where: { id: In(ownerIds) } }) : [];
    const om = new Map(owners.map((u) => [u.id, u.name]));
    const items = matched.map((m) => {
      const bs = batches.filter((b) => b.chemicalId === m.id).map((b) => ({
        scope: b.scope, ownerName: b.ownerId ? om.get(b.ownerId) || '?' : null,
        remainLevel: b.remainLevel, remainText: levelText[b.remainLevel] || b.remainLevel,
        shareable: b.shareable, borrowable: b.shareable && NONEMPTY.includes(b.remainLevel),
      }));
      return { chemicalId: m.id, name: m.name, cas: m.cas, hasStock: bs.some((b) => NONEMPTY.includes(b.remainLevel)), hasBorrowable: bs.some((b) => b.borrowable), batches: bs };
    });
    const hasBorrowable = items.some((i) => i.hasBorrowable);
    const hasStock = items.some((i) => i.hasStock);
    return { hazmat: hz, matched: items, hasStock, hasBorrowable, suggestion: hasBorrowable ? 'BORROW' : hasStock ? 'STOCK_EXISTS' : 'NONE' };
  }

  private dupNoteOf(pc: any): string {
    if (!pc.matched.length) return '';
    return pc.matched.map((m: any) => `${m.name}: ${m.batches.map((b: any) => (b.scope === 'PUBLIC' ? '公用' : b.ownerName || '个人') + b.remainText + (b.borrowable ? '(可借)' : '')).join('、') || '无库存'}`).join(' ; ');
  }

  // 学生添加到个人申购清单（草稿）
  async addDraft(userId: number, dto: CreatePurchaseDto) {
    const pc = await this.precheck(dto.name, dto.cas);
    if ((pc.hasStock || pc.hasBorrowable) && !dto.ackDup) {
      throw new BadRequestException({ code: 'DUP_NEEDS_ACK', message: '库内已有相同药品或有可借库存，请确认后再加入清单', precheck: pc });
    }
    const r = this.reqs.create({
      applicantId: userId, chemicalId: pc.matched[0]?.chemicalId ?? null,
      name: dto.name, cas: dto.cas ? normCas(dto.cas) : null,
      productNo: dto.productNo || null, price: dto.price || null,
      quantity: dto.quantity || null, unit: dto.unit || null, reason: dto.reason || null,
      urgency: dto.urgency === 'URGENT' ? 'URGENT' : 'NORMAL', status: 'DRAFT',
      hazmatListed: pc.hazmat.listed, hazmatToxic: pc.hazmat.toxic,
      dupNote: this.dupNoteOf(pc) || null, ackDup: !!dto.ackDup,
    } as any);
    return this.reqs.save(r);
  }

  // 一键发送给导师审核：把我所有草稿转为待审批
  async submit(user: any, tutorId?: number) {
    const drafts = await this.reqs.find({ where: { applicantId: user.sub, status: 'DRAFT' } });
    if (!drafts.length) throw new BadRequestException('申购清单为空');
    let tid = tutorId;
    if (!tid) { const me = await this.users.findOne({ where: { id: user.sub } }); tid = me?.tutorId ?? undefined; }
    if (!tid) throw new BadRequestException('未指定审核导师，请选择导师');
    const tutor = await this.users.findOne({ where: { id: tid, role: 'TUTOR' } });
    if (!tutor) throw new BadRequestException('所选导师无效');
    const now = new Date();
    for (const d of drafts) { d.status = 'PENDING'; d.tutorId = tid!; d.submittedAt = now; }
    await this.reqs.save(drafts);
    return { submitted: drafts.length, tutor: tutor.name };
  }

  async deleteDraft(id: number, user: any) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('不存在');
    if (r.applicantId !== user.sub) throw new ForbiddenException('只能删除自己的清单项');
    if (r.status !== 'DRAFT') throw new BadRequestException('已提交，无法删除');
    await this.reqs.remove(r);
    return { ok: true };
  }

  private async decorate(rows: PurchaseRequest[]) {
    const uids = [...new Set(rows.flatMap((r) => [r.applicantId, r.reviewerId, r.tutorId].filter(Boolean) as number[]))];
    const us = uids.length ? await this.users.find({ where: { id: In(uids) } }) : [];
    const um = new Map(us.map((u) => [u.id, u.name]));
    return rows.map((r) => ({ ...r, applicantName: um.get(r.applicantId) || '?', reviewerName: r.reviewerId ? um.get(r.reviewerId) || '?' : null, tutorName: r.tutorId ? um.get(r.tutorId) || '?' : null }));
  }

  async list(user: any, status?: string, scope?: string) {
    const where: any = {};
    const isAdmin = user.role === 'ADMIN';
    const isTutor = user.role === 'TUTOR';
    if (scope === 'mine') where.applicantId = user.sub;
    else if (isAdmin) { /* all */ }
    else if (isTutor) where.tutorId = user.sub; // 导师只看自己学生提交的
    else where.applicantId = user.sub;
    if (status) where.status = status;
    const rows = await this.reqs.find({ where, order: { createdAt: 'DESC' } });
    return this.decorate(rows);
  }

  // 审批通过 → 自动入库（归到持有人=申请学生，记录日期+位置）
  async review(id: number, user: any, action: 'APPROVE' | 'REJECT', comment?: string, location?: string) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('申购单不存在');
    if (r.status !== 'PENDING') throw new BadRequestException('该申购单已处理');
    if (user.role === 'TUTOR' && r.tutorId !== user.sub) throw new ForbiddenException('只能审批本人学生的申购');
    r.reviewerId = user.sub; r.reviewComment = comment || null; r.reviewedAt = new Date();
    if (action === 'REJECT') { r.status = 'REJECTED'; await this.reqs.save(r); return (await this.decorate([r]))[0]; }

    // 通过 → 自动入库
    r.status = 'APPROVED';
    let chem = r.cas ? (await this.chem.find({ where: { active: true } })).find((x) => normCas(x.cas) === normCas(r.cas)) : undefined;
    if (!chem) chem = (await this.chem.findOne({ where: { name: r.name, active: true } })) || undefined;
    if (!chem) {
      const hazard = r.hazmatToxic ? 'CONTROLLED' : r.hazmatListed ? 'HIGH' : 'MODERATE';
      let py = { pinyin: '', pinyinInitials: '' };
      try { py = { pinyin: pinyin(r.name, { toneType: 'none', separator: '' }).toLowerCase(), pinyinInitials: pinyin(r.name, { pattern: 'first', toneType: 'none', separator: '' }).toLowerCase() }; } catch {}
      chem = await this.chem.save(this.chem.create({ name: r.name, aliases: [], cas: r.cas, hazardLevel: hazard, unit: r.unit || 'mL', location: location || null, pinyin: py.pinyin, pinyinInitials: py.pinyinInitials } as any)) as any;
    } else if (location && !chem.location) {
      chem.location = location; await this.chem.save(chem);
    }
    const ymd = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const batchNo = 'IN' + ymd + '-' + Date.now().toString(36).slice(-5).toUpperCase();
    const b: any = await this.batch.save(this.batch.create({
      chemicalId: chem!.id, batchNo, scope: 'PERSONAL', ownerId: r.applicantId,
      shareable: false, remainLevel: 'FULL', location: location || chem!.location || null,
    } as any));
    r.chemicalId = chem!.id; r.batchId = b.id; r.stockLocation = location || chem!.location || null; r.stockedAt = new Date();
    await this.reqs.save(r);
    return (await this.decorate([r]))[0];
  }
}
""")

# ---------- purchases.controller 加 submit/delete，approve带location ----------
wfile(APP + "/src/purchases/purchases.controller.ts", """import { Body, Controller, Delete, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
import { PurchasesService } from './purchases.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Roles } from '../common/roles.decorator';
import { CurrentUser } from '../common/current-user.decorator';
import { CreatePurchaseDto } from './dto/create-purchase.dto';

@Controller('purchases')
@UseGuards(JwtAuthGuard)
export class PurchasesController {
  constructor(private readonly svc: PurchasesService) {}

  @Get('precheck') precheck(@Query('name') name?: string, @Query('cas') cas?: string) { return this.svc.precheck(name, cas); }
  @Get() list(@CurrentUser() u: any, @Query('status') s?: string, @Query('scope') sc?: string) { return this.svc.list(u, s, sc); }
  @Post() add(@CurrentUser() u: any, @Body() dto: CreatePurchaseDto) { return this.svc.addDraft(u.sub, dto); }
  @Post('submit') submit(@CurrentUser() u: any, @Body() b: any) { return this.svc.submit(u, b?.tutorId ? +b.tutorId : undefined); }
  @Delete(':id') del(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.deleteDraft(+id, u); }
  @Post(':id/approve') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  approve(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.review(+id, u, 'APPROVE', b?.comment, b?.location); }
  @Post(':id/reject') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  reject(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.review(+id, u, 'REJECT', b?.comment); }
}
""")

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo BUILD_OK; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("启动错误/路由", "pm2 logs plm-api --lines 60 --nostream 2>&1 | grep -iE 'seed|error|tutors|submit' | tail -20")

# 清掉之前的测试申购单，干净演示
step("清空旧申购单", "mysql -uplm -ppni38AWG4xy6wEyc plm -e 'DELETE FROM plm_purchase_requests;' 2>/dev/null; echo cleared")

# ---------- 端到端自检：小明(导师甲)申购→草稿→提交→导师甲审批入库 ----------
def login(uname, pw):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (uname, pw))
    try: return json.loads(o)
    except Exception: return {"raw": o}

stu = login("stu_xm", "Plm@2026")
print("\n## 学生小明登录:", stu.get("user"))
sH = "-H 'Authorization: Bearer %s'" % stu.get("token")
print("## 小明把『丙酮』加入清单(库里没有, 应直接成功 DRAFT)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"丙酮\",\"cas\":\"67-64-1\",\"productNo\":\"A-1001\",\"price\":\"85.00\",\"quantity\":\"500\",\"unit\":\"mL\",\"reason\":\"清洗\"}'" % sH)
print("  ", o[:260])
print("## 小明把『DMF』加入清单(库里有可借, 不确认应被拦)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"DMF\",\"cas\":\"68-12-2\",\"quantity\":\"500\",\"unit\":\"mL\"}'" % sH)
print("  ", o[:160])
print("## 小明发送给导师审核(用其分配的导师甲)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases/submit -H 'Content-Type: application/json' %s -d '{}'" % sH)
print("  ", o[:200])

tj = login("tutor_jia", "Plm@2026")
tH = "-H 'Authorization: Bearer %s'" % tj.get("token")
print("\n## 导师甲看待审批(应只看到小明的丙酮)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s | python3 -c \"import sys,json;[print(r['id'],r['name'],r['applicantName'],'货号',r['productNo'],'¥'+str(r['price'])) for r in json.load(sys.stdin)]\"" % tH)
print(o)
pid = None
try:
    o2, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s" % tH)
    pid = json.loads(o2)[0]["id"]
except Exception: pass
ty = login("tutor_yi", "Plm@2026")
yH = "-H 'Authorization: Bearer %s'" % ty.get("token")
print("## 导师乙看待审批(应为空, 隔离验证)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s" % yH)
print("  ", o[:120])
if pid:
    print("## 导师甲审批通过 #%s 并入库到B柜" % pid)
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases/%s/approve -H 'Content-Type: application/json' %s -d '{\"comment\":\"同意\",\"location\":\"B柜-2层\"}'" % (pid, tH))
    print("  ", o[:400])
    print("## 验证: 丙酮是否已自动入库, 归到小明")
    aH = "-H 'Authorization: Bearer %s'" % login("admin", ADMINPW).get("token")
    o, _ = run("curl -s 'http://127.0.0.1:3000/api/chemicals?keyword=丙酮' %s | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(c['name'],[(b['ownerName'],b['remainLevel']) for b in c['batches']]) for c in d]\"" % aH)
    print("  ", o)
cli.close()
print("\n=== DONE ===")
