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

# ---------- DTO：cas / 货号 / 价格 必填 ----------
wfile(APP + "/src/purchases/dto/create-purchase.dto.ts", """import { IsBoolean, IsOptional, IsString, MinLength } from 'class-validator';

export class CreatePurchaseDto {
  @IsString() @MinLength(1, { message: '请填写药品名称' }) name: string;
  @IsString() @MinLength(1, { message: '请填写 CAS 号' }) cas: string;
  @IsString() @MinLength(1, { message: '请填写采购货号' }) productNo: string;
  @IsString() @MinLength(1, { message: '请填写价格' }) price: string;
  @IsOptional() @IsString() quantity?: string;
  @IsOptional() @IsString() unit?: string;
  @IsOptional() @IsString() reason?: string;
  @IsOptional() @IsString() urgency?: string;
  @IsOptional() @IsBoolean() ackDup?: boolean;
}
""")

# ---------- service：去掉位置入库 + 批量通过 + 历史已购次数 ----------
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

  async addDraft(userId: number, dto: CreatePurchaseDto) {
    const pc = await this.precheck(dto.name, dto.cas);
    if ((pc.hasStock || pc.hasBorrowable) && !dto.ackDup) {
      throw new BadRequestException({ code: 'DUP_NEEDS_ACK', message: '库内已有相同药品或有可借库存，请确认后再加入清单', precheck: pc });
    }
    const r = this.reqs.create({
      applicantId: userId, chemicalId: pc.matched[0]?.chemicalId ?? null,
      name: dto.name, cas: normCas(dto.cas), productNo: dto.productNo, price: dto.price,
      quantity: dto.quantity || null, unit: dto.unit || null, reason: dto.reason || null,
      urgency: dto.urgency === 'URGENT' ? 'URGENT' : 'NORMAL', status: 'DRAFT',
      hazmatListed: pc.hazmat.listed, hazmatToxic: pc.hazmat.toxic,
      dupNote: this.dupNoteOf(pc) || null, ackDup: !!dto.ackDup,
    } as any);
    return this.reqs.save(r);
  }

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
    // 历史已购次数：按 CAS 统计 APPROVED 的申购单数量
    const casList = [...new Set(rows.map((r) => normCas(r.cas)).filter(Boolean))];
    const histMap = new Map<string, number>();
    if (casList.length) {
      const approved = await this.reqs.find({ where: { status: 'APPROVED' } });
      for (const a of approved) { const c = normCas(a.cas); if (c) histMap.set(c, (histMap.get(c) || 0) + 1); }
    }
    return rows.map((r) => ({
      ...r,
      applicantName: um.get(r.applicantId) || '?',
      reviewerName: r.reviewerId ? um.get(r.reviewerId) || '?' : null,
      tutorName: r.tutorId ? um.get(r.tutorId) || '?' : null,
      historyCount: histMap.get(normCas(r.cas)) || 0,
    }));
  }

  async list(user: any, status?: string, scope?: string) {
    const where: any = {};
    const isAdmin = user.role === 'ADMIN';
    const isTutor = user.role === 'TUTOR';
    if (scope === 'mine') where.applicantId = user.sub;
    else if (isAdmin) { /* all */ }
    else if (isTutor) where.tutorId = user.sub;
    else where.applicantId = user.sub;
    if (status) where.status = status;
    const rows = await this.reqs.find({ where, order: { createdAt: 'DESC' } });
    return this.decorate(rows);
  }

  // 审批通过 → 自动入库（归持有人=申请学生，记录日期；不再手填位置）
  private async approveOne(r: PurchaseRequest, user: any) {
    if (r.status !== 'PENDING') return;
    if (user.role === 'TUTOR' && r.tutorId !== user.sub) throw new ForbiddenException('只能审批本人学生的申购');
    r.status = 'APPROVED'; r.reviewerId = user.sub; r.reviewedAt = new Date();
    let chem = r.cas ? (await this.chem.find({ where: { active: true } })).find((x) => normCas(x.cas) === normCas(r.cas)) : undefined;
    if (!chem) chem = (await this.chem.findOne({ where: { name: r.name, active: true } })) || undefined;
    if (!chem) {
      const hazard = r.hazmatToxic ? 'CONTROLLED' : r.hazmatListed ? 'HIGH' : 'MODERATE';
      let py = { pinyin: '', pinyinInitials: '' };
      try { py = { pinyin: pinyin(r.name, { toneType: 'none', separator: '' }).toLowerCase(), pinyinInitials: pinyin(r.name, { pattern: 'first', toneType: 'none', separator: '' }).toLowerCase() }; } catch {}
      chem = await this.chem.save(this.chem.create({ name: r.name, aliases: [], cas: r.cas, hazardLevel: hazard, unit: r.unit || 'mL', pinyin: py.pinyin, pinyinInitials: py.pinyinInitials } as any)) as any;
    }
    const ymd = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const batchNo = 'IN' + ymd + '-' + Date.now().toString(36).slice(-5).toUpperCase() + r.id;
    const b: any = await this.batch.save(this.batch.create({
      chemicalId: chem!.id, batchNo, scope: 'PERSONAL', ownerId: r.applicantId,
      shareable: false, remainLevel: 'FULL',
    } as any));
    r.chemicalId = chem!.id; r.batchId = b.id; r.stockedAt = new Date();
    await this.reqs.save(r);
  }

  async review(id: number, user: any, action: 'APPROVE' | 'REJECT', comment?: string) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('申购单不存在');
    if (r.status !== 'PENDING') throw new BadRequestException('该申购单已处理');
    if (user.role === 'TUTOR' && r.tutorId !== user.sub) throw new ForbiddenException('只能审批本人学生的申购');
    if (action === 'REJECT') { r.status = 'REJECTED'; r.reviewerId = user.sub; r.reviewComment = comment || null; r.reviewedAt = new Date(); await this.reqs.save(r); }
    else { if (comment) { r.reviewComment = comment; } await this.approveOne(r, user); }
    return (await this.decorate([r]))[0];
  }

  // 批量通过
  async approveBatch(ids: number[], user: any, comment?: string) {
    if (!ids?.length) throw new BadRequestException('未选择申购单');
    const rows = await this.reqs.find({ where: { id: In(ids) } });
    let ok = 0;
    for (const r of rows) {
      if (r.status !== 'PENDING') continue;
      if (comment) r.reviewComment = comment;
      await this.approveOne(r, user); ok++;
    }
    return { approved: ok };
  }
}
""")

# ---------- controller：approve 去 location；加 approve-batch ----------
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
  @Post('approve-batch') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  approveBatch(@CurrentUser() u: any, @Body() b: any) { return this.svc.approveBatch((b?.ids || []).map((x: any) => +x), u, b?.comment); }
  @Delete(':id') del(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.deleteDraft(+id, u); }
  @Post(':id/approve') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  approve(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.review(+id, u, 'APPROVE', b?.comment); }
  @Post(':id/reject') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR')
  reject(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.review(+id, u, 'REJECT', b?.comment); }
}
""")

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -8 && echo BUILD_OK; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("启动检查", "pm2 logs plm-api --lines 40 --nostream 2>&1 | grep -iE 'error|approve-batch' | tail -10")

# 清申购单重新演示
step("清申购单", "mysql -uplm -ppni38AWG4xy6wEyc plm -e 'DELETE FROM plm_purchase_requests;' 2>/dev/null; echo cleared")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    try: return json.loads(o)
    except Exception: return {}

# 必填校验
xm = login("stu_xm", "Plm@2026"); sH = "-H 'Authorization: Bearer %s'" % xm.get("token")
print("\n## 缺货号/价格 应被拦(400)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"甲苯\",\"cas\":\"108-88-3\"}'" % sH)
print("  ", o[:200])
print("## 完整字段加入清单")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"甲苯\",\"cas\":\"108-88-3\",\"productNo\":\"T-22\",\"price\":\"60\",\"quantity\":\"500\",\"unit\":\"mL\"}'" % sH)
print("  ", o[:160])
run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"乙腈\",\"cas\":\"75-05-8\",\"productNo\":\"ACN-1\",\"price\":\"120\",\"quantity\":\"1\",\"unit\":\"L\"}'" % sH)
run("curl -s -X POST http://127.0.0.1:3000/api/purchases/submit -H 'Content-Type: application/json' %s -d '{}'" % sH)
# 小刚(也是导师甲)
xg = login("stu_xg", "Plm@2026"); gH = "-H 'Authorization: Bearer %s'" % xg.get("token")
run("curl -s -X POST http://127.0.0.1:3000/api/purchases -H 'Content-Type: application/json' %s -d '{\"name\":\"乙酸乙酯\",\"cas\":\"141-78-6\",\"productNo\":\"EA-9\",\"price\":\"55\",\"quantity\":\"500\",\"unit\":\"mL\"}'" % gH)
run("curl -s -X POST http://127.0.0.1:3000/api/purchases/submit -H 'Content-Type: application/json' %s -d '{}'" % gH)

tj = login("tutor_jia", "Plm@2026"); tH = "-H 'Authorization: Bearer %s'" % tj.get("token")
print("\n## 导师甲待审批(应见小明2项+小刚1项, 含历史已购次数)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s | python3 -c \"import sys,json;[print(r['id'],r['applicantName'],r['name'],'¥'+str(r['price']),'历史已购',r['historyCount']) for r in json.load(sys.stdin)]\"" % tH)
print(o)
ids, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s | python3 -c \"import sys,json;print(','.join(str(r['id']) for r in json.load(sys.stdin)))\"" % tH)
ids = ids.strip()
print("## 批量通过全部:", ids)
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/purchases/approve-batch -H 'Content-Type: application/json' %s -d '{\"ids\":[%s]}'" % (tH, ids))
print("  ", o[:200])
print("## 再查待审批(应空)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s" % tH)
print("  ", o[:80])
cli.close()
print("\n=== DONE ===")
