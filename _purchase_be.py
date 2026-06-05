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

# ---------- 实体 ----------
wfile(APP + "/src/entities/purchase-request.entity.ts", """import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_purchase_requests')
export class PurchaseRequest {
  @PrimaryGeneratedColumn() id: number;
  @Column() applicantId: number;
  @Column({ type: 'int', nullable: true }) chemicalId: number | null;
  @Column() name: string;
  @Column({ length: 64, nullable: true }) cas: string | null;
  @Column({ length: 64, nullable: true }) quantity: string | null;
  @Column({ length: 16, nullable: true }) unit: string | null;
  @Column({ type: 'text', nullable: true }) reason: string | null;
  @Column({ default: 'NORMAL' }) urgency: string;
  @Column({ default: 'PENDING' }) status: string;
  @Column({ default: false }) hazmatListed: boolean;
  @Column({ default: false }) hazmatToxic: boolean;
  @Column({ type: 'text', nullable: true }) dupNote: string | null;
  @Column({ default: false }) ackDup: boolean;
  @Column({ type: 'int', nullable: true }) reviewerId: number | null;
  @Column({ type: 'text', nullable: true }) reviewComment: string | null;
  @Column({ type: 'datetime', nullable: true }) reviewedAt: Date | null;
  @CreateDateColumn() createdAt: Date;
}
""")

# ---------- DTO ----------
wfile(APP + "/src/purchases/dto/create-purchase.dto.ts", """import { IsBoolean, IsOptional, IsString, MinLength } from 'class-validator';

export class CreatePurchaseDto {
  @IsString() @MinLength(1) name: string;
  @IsOptional() @IsString() cas?: string;
  @IsOptional() @IsString() quantity?: string;
  @IsOptional() @IsString() unit?: string;
  @IsOptional() @IsString() reason?: string;
  @IsOptional() @IsString() urgency?: string;
  @IsOptional() @IsBoolean() ackDup?: boolean;
}
""")

# ---------- service ----------
wfile(APP + "/src/purchases/purchases.service.ts", r"""import { BadRequestException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
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

  // 申购前双查：库存查重 + 危化品目录
  async precheck(name?: string, cas?: string) {
    const hz = this.hazmat.lookup(cas);
    const c = normCas(cas);
    const nm = (name || '').trim().toLowerCase();
    let matched: Chemical[] = [];
    const all = await this.chem.find({ where: { active: true } });
    if (c) matched = all.filter((x) => normCas(x.cas) === c);
    if (matched.length === 0 && nm) {
      matched = all.filter((x) =>
        x.name.toLowerCase().includes(nm) ||
        (x.aliases || []).some((a) => a.toLowerCase().includes(nm)),
      );
    }
    const ids = matched.map((m) => m.id);
    const batches = ids.length ? await this.batch.find({ where: { chemicalId: In(ids) } }) : [];
    const ownerIds = [...new Set(batches.filter((b) => b.ownerId).map((b) => b.ownerId as number))];
    const owners = ownerIds.length ? await this.users.find({ where: { id: In(ownerIds) } }) : [];
    const om = new Map(owners.map((u) => [u.id, u.name]));
    const items = matched.map((m) => {
      const bs = batches.filter((b) => b.chemicalId === m.id).map((b) => ({
        scope: b.scope,
        ownerName: b.ownerId ? om.get(b.ownerId) || '?' : null,
        remainLevel: b.remainLevel,
        remainText: levelText[b.remainLevel] || b.remainLevel,
        shareable: b.shareable,
        borrowable: b.shareable && NONEMPTY.includes(b.remainLevel),
      }));
      return {
        chemicalId: m.id, name: m.name, cas: m.cas,
        hasStock: bs.some((b) => NONEMPTY.includes(b.remainLevel)),
        hasBorrowable: bs.some((b) => b.borrowable),
        batches: bs,
      };
    });
    const hasBorrowable = items.some((i) => i.hasBorrowable);
    const hasStock = items.some((i) => i.hasStock);
    const suggestion = hasBorrowable ? 'BORROW' : hasStock ? 'STOCK_EXISTS' : 'NONE';
    return { hazmat: hz, matched: items, hasStock, hasBorrowable, suggestion };
  }

  private dupNoteOf(pc: any): string {
    if (!pc.matched.length) return '';
    const parts: string[] = [];
    for (const m of pc.matched) {
      const bs = m.batches.map((b: any) =>
        (b.scope === 'PUBLIC' ? '公用' : b.ownerName || '个人') + b.remainText + (b.borrowable ? '(可借)' : ''),
      );
      parts.push(`${m.name}: ${bs.join('、') || '无库存'}`);
    }
    return parts.join(' ; ');
  }

  async create(userId: number, dto: CreatePurchaseDto) {
    const pc = await this.precheck(dto.name, dto.cas);
    // 已有库存/可借时，必须显式确认才放行（防重复采购的硬拦截）
    if ((pc.hasStock || pc.hasBorrowable) && !dto.ackDup) {
      throw new BadRequestException({
        code: 'DUP_NEEDS_ACK',
        message: '库内已有相同药品或有可借库存，请确认后再提交',
        precheck: pc,
      });
    }
    const r = this.reqs.create({
      applicantId: userId,
      chemicalId: pc.matched[0]?.chemicalId ?? null,
      name: dto.name,
      cas: dto.cas ? normCas(dto.cas) : null,
      quantity: dto.quantity || null,
      unit: dto.unit || null,
      reason: dto.reason || null,
      urgency: dto.urgency === 'URGENT' ? 'URGENT' : 'NORMAL',
      status: 'PENDING',
      hazmatListed: pc.hazmat.listed,
      hazmatToxic: pc.hazmat.toxic,
      dupNote: this.dupNoteOf(pc) || null,
      ackDup: !!dto.ackDup,
    } as any);
    return this.reqs.save(r);
  }

  private async decorate(rows: PurchaseRequest[]) {
    const uids = [...new Set(rows.flatMap((r) => [r.applicantId, r.reviewerId].filter(Boolean) as number[]))];
    const us = uids.length ? await this.users.find({ where: { id: In(uids) } }) : [];
    const um = new Map(us.map((u) => [u.id, u.name]));
    return rows.map((r) => ({
      ...r,
      applicantName: um.get(r.applicantId) || '?',
      reviewerName: r.reviewerId ? um.get(r.reviewerId) || '?' : null,
    }));
  }

  async list(user: any, status?: string, scope?: string) {
    const where: any = {};
    const isReviewer = user.role === 'ADMIN' || user.role === 'TUTOR';
    if (!isReviewer || scope === 'mine') where.applicantId = user.sub;
    if (status) where.status = status;
    const rows = await this.reqs.find({ where, order: { createdAt: 'DESC' } });
    return this.decorate(rows);
  }

  async review(id: number, user: any, action: 'APPROVE' | 'REJECT', comment?: string) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('申购单不存在');
    if (r.status !== 'PENDING') throw new BadRequestException('该申购单已处理');
    r.status = action === 'APPROVE' ? 'APPROVED' : 'REJECTED';
    r.reviewerId = user.sub;
    r.reviewComment = comment || null;
    r.reviewedAt = new Date();
    await this.reqs.save(r);
    return (await this.decorate([r]))[0];
  }

  async cancel(id: number, user: any) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('申购单不存在');
    if (r.applicantId !== user.sub) throw new ForbiddenException('只能撤销自己的申购单');
    if (r.status !== 'PENDING') throw new BadRequestException('已处理，无法撤销');
    r.status = 'CANCELLED';
    await this.reqs.save(r);
    return (await this.decorate([r]))[0];
  }
}
""")

# ---------- controller ----------
wfile(APP + "/src/purchases/purchases.controller.ts", """import { Body, Controller, Get, Param, Post, Query, UseGuards } from '@nestjs/common';
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

  @Get('precheck') precheck(@Query('name') name?: string, @Query('cas') cas?: string) {
    return this.svc.precheck(name, cas);
  }
  @Get() list(@CurrentUser() u: any, @Query('status') s?: string, @Query('scope') sc?: string) {
    return this.svc.list(u, s, sc);
  }
  @Post() create(@CurrentUser() u: any, @Body() dto: CreatePurchaseDto) {
    return this.svc.create(u.sub, dto);
  }
  @Post(':id/approve') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  approve(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) {
    return this.svc.review(+id, u, 'APPROVE', b?.comment);
  }
  @Post(':id/reject') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  reject(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) {
    return this.svc.review(+id, u, 'REJECT', b?.comment);
  }
  @Post(':id/cancel') cancel(@Param('id') id: string, @CurrentUser() u: any) {
    return this.svc.cancel(+id, u);
  }
}
""")

# ---------- module ----------
wfile(APP + "/src/purchases/purchases.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { PurchasesService } from './purchases.service';
import { PurchasesController } from './purchases.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { PurchaseRequest } from '../entities/purchase-request.entity';
import { Chemical } from '../entities/chemical.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { User } from '../entities/user.entity';
import { HazmatModule } from '../hazmat/hazmat.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([PurchaseRequest, Chemical, ChemicalBatch, User]),
    HazmatModule,
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: (process.env.JWT_EXPIRES_IN || '7d') as any } }),
  ],
  controllers: [PurchasesController],
  providers: [PurchasesService, JwtAuthGuard, RolesGuard],
})
export class PurchasesModule {}
""")

# ---------- app.module.ts 重写：加实体 + 模块 ----------
wfile(APP + "/src/app.module.ts", """import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { ChemicalsModule } from './chemicals/chemicals.module';
import { HazmatModule } from './hazmat/hazmat.module';
import { PurchasesModule } from './purchases/purchases.module';
import { User } from './entities/user.entity';
import { Group } from './entities/group.entity';
import { Chemical } from './entities/chemical.entity';
import { ChemicalBatch } from './entities/chemical-batch.entity';
import { Hazmat } from './entities/hazmat.entity';
import { PurchaseRequest } from './entities/purchase-request.entity';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRoot({
      type: 'mysql',
      host: process.env.DB_HOST || '127.0.0.1',
      port: Number(process.env.DB_PORT || 3306),
      username: process.env.DB_USER || 'plm',
      password: process.env.DB_PASS || '',
      database: process.env.DB_NAME || 'plm',
      entities: [User, Group, Chemical, ChemicalBatch, Hazmat, PurchaseRequest],
      synchronize: true,
      charset: 'utf8mb4',
    }),
    AuthModule,
    UsersModule,
    ChemicalsModule,
    HazmatModule,
    PurchasesModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
""")

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -8 && echo BUILD_OK; pm2 restart plm-api >/dev/null 2>&1; sleep 2; echo restarted" % APP, 400)
step("启动错误?", "pm2 logs plm-api --lines 6 --nostream 2>&1 | grep -iE 'error|Purchase|Mapped.*purchases' | tail -10")

# ---------- 自检 ----------
tok, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"%s\"}'" % ADMINPW)
try: token = json.loads(tok).get("token")
except Exception: token = None
H = "-H 'Authorization: Bearer %s'" % token
print("\n## precheck DMF (应命中库存+可借+危化品)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases/precheck?cas=68-12-2&name=DMF' %s" % H)
print(o[:900])
print("\n## 直接申购DMF不确认 (应被拦截 DUP_NEEDS_ACK)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"DMF\",\"cas\":\"68-12-2\",\"quantity\":\"500\",\"unit\":\"mL\",\"reason\":\"做实验\"}'" % H)
print(o[:400])
print("\n## 确认后申购 (应成功 PENDING)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"丙酮\",\"cas\":\"67-64-1\",\"quantity\":\"500\",\"unit\":\"mL\",\"reason\":\"清洗\",\"ackDup\":true}'" % H)
print(o[:500])
pid = None
try: pid = json.loads(o).get("id")
except Exception: pass
print("\n## 列表")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases' %s | python3 -c \"import sys,json;[print(r['id'],r['name'],r['status'],'危' if r['hazmatListed'] else '',r['applicantName']) for r in json.load(sys.stdin)]\"" % H)
print(o)
if pid:
    print("\n## 审批通过 #%s" % pid)
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases/%s/approve -H 'Content-Type: application/json' %s -d '{\"comment\":\"同意\"}'" % (pid, H))
    print(o[:400])
cli.close()
print("\n=== DONE ===")
