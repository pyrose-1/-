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
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2600:])
    if err: print("[stderr]", err[-1400:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(APP, ""))

def pyedit(path, replaces):
    """在服务器上对文件做精确字符串替换"""
    b = base64.b64encode(json.dumps(replaces, ensure_ascii=False).encode()).decode()
    out, err = run("python3 - <<'PYEOF'\n"
        "import base64,json\n"
        "p=%r\n"
        "reps=json.loads(base64.b64decode('%s').decode('utf-8'))\n"
        "s=open(p,encoding='utf-8').read()\n"
        "for a,b in reps:\n"
        "    assert a in s, ('MISS: '+a[:50])\n"
        "    s=s.replace(a,b)\n"
        "open(p,'w',encoding='utf-8').write(s)\n"
        "print('edited %%d'%%len(reps))\n"
        "PYEOF" % (path, b))
    print("  edit", path.replace(APP, ""), out, err[-200:])

# ---------- 1) 借用实体 ----------
wfile(APP + "/src/entities/borrow-request.entity.ts", """import { Column, CreateDateColumn, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_borrow_requests')
export class BorrowRequest {
  @PrimaryGeneratedColumn() id: number;
  @Column() batchId: number;
  @Column() chemicalId: number;
  @Column() ownerId: number;      // 出借人（申请时的持有人）
  @Column() borrowerId: number;   // 借用人
  @Column({ default: 'PENDING' }) status: string; // PENDING/REJECTED/LENT/TRANSFERRED/CANCELLED
  @Column({ type: 'text', nullable: true }) note: string | null;
  @Column({ type: 'text', nullable: true }) decisionNote: string | null;
  @Column({ type: 'datetime', nullable: true }) decidedAt: Date | null;
  @CreateDateColumn() createdAt: Date;
}
""")

# ---------- 2) 借用 service ----------
wfile(APP + "/src/borrow/borrow.service.ts", r"""import { BadRequestException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { BorrowRequest } from '../entities/borrow-request.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { Chemical } from '../entities/chemical.entity';
import { User } from '../entities/user.entity';

const levelText: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' };
const statusText: Record<string, string> = { PENDING: '待处理', REJECTED: '已拒绝', LENT: '已同意借用', TRANSFERRED: '已转让', CANCELLED: '已取消' };

@Injectable()
export class BorrowService {
  constructor(
    @InjectRepository(BorrowRequest) private reqs: Repository<BorrowRequest>,
    @InjectRepository(ChemicalBatch) private batch: Repository<ChemicalBatch>,
    @InjectRepository(Chemical) private chem: Repository<Chemical>,
    @InjectRepository(User) private users: Repository<User>,
  ) {}

  async create(borrowerId: number, batchId: number, note?: string) {
    const b = await this.batch.findOne({ where: { id: batchId } });
    if (!b) throw new NotFoundException('药品批次不存在');
    if (b.ownerId === borrowerId) throw new BadRequestException('不能借用自己持有的药品');
    if (!b.shareable) throw new BadRequestException('该药品未设为可借出');
    if (b.remainLevel === 'EMPTY') throw new BadRequestException('该药品已用空');
    if (!b.ownerId) throw new BadRequestException('该药品为公用，无需借用');
    const dup = await this.reqs.findOne({ where: { batchId, borrowerId, status: 'PENDING' } });
    if (dup) throw new BadRequestException('你已提交过该药品的借用申请，等待对方处理');
    const r = this.reqs.create({ batchId, chemicalId: b.chemicalId, ownerId: b.ownerId, borrowerId, note: note || null, status: 'PENDING' } as any);
    return this.reqs.save(r);
  }

  private async decorate(rows: BorrowRequest[]) {
    const uids = [...new Set(rows.flatMap((r) => [r.ownerId, r.borrowerId]))];
    const cids = [...new Set(rows.map((r) => r.chemicalId))];
    const bids = [...new Set(rows.map((r) => r.batchId))];
    const us = uids.length ? await this.users.find({ where: { id: In(uids) } }) : [];
    const cs = cids.length ? await this.chem.find({ where: { id: In(cids) } }) : [];
    const bs = bids.length ? await this.batch.find({ where: { id: In(bids) } }) : [];
    const um = new Map(us.map((u) => [u.id, u.name]));
    const cm = new Map(cs.map((c) => [c.id, c]));
    const bm = new Map(bs.map((b) => [b.id, b]));
    return rows.map((r) => {
      const c = cm.get(r.chemicalId); const b = bm.get(r.batchId);
      return {
        ...r, statusText: statusText[r.status] || r.status,
        ownerName: um.get(r.ownerId) || '?', borrowerName: um.get(r.borrowerId) || '?',
        chemicalName: c?.name || '?', cas: c?.cas || null,
        remainLevel: b?.remainLevel || null, remainText: b ? levelText[b.remainLevel] || b.remainLevel : null,
        location: b?.location || null, ownerStillHolds: b ? b.ownerId === r.ownerId : false,
      };
    });
  }

  async mine(user: any) { return this.decorate(await this.reqs.find({ where: { borrowerId: user.sub }, order: { createdAt: 'DESC' } })); }
  async toMe(user: any) { return this.decorate(await this.reqs.find({ where: { ownerId: user.sub }, order: { createdAt: 'DESC' } })); }

  async decide(id: number, user: any, action: 'REJECT' | 'LEND' | 'TRANSFER', note?: string) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('借用申请不存在');
    if (r.ownerId !== user.sub) throw new ForbiddenException('只有持有人可以处理');
    if (r.status !== 'PENDING') throw new BadRequestException('该申请已处理');
    if (action === 'REJECT') r.status = 'REJECTED';
    else if (action === 'LEND') r.status = 'LENT';
    else if (action === 'TRANSFER') {
      const b = await this.batch.findOne({ where: { id: r.batchId } });
      if (b) { b.ownerId = r.borrowerId; await this.batch.save(b); }
      r.status = 'TRANSFERRED';
    } else throw new BadRequestException('未知操作');
    r.decisionNote = note || null; r.decidedAt = new Date();
    await this.reqs.save(r);
    return (await this.decorate([r]))[0];
  }

  async cancel(id: number, user: any) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('不存在');
    if (r.borrowerId !== user.sub) throw new ForbiddenException('只能取消自己的申请');
    if (r.status !== 'PENDING') throw new BadRequestException('已处理，无法取消');
    r.status = 'CANCELLED'; await this.reqs.save(r);
    return { ok: true };
  }
}
""")

# ---------- 3) 借用 controller ----------
wfile(APP + "/src/borrow/borrow.controller.ts", """import { Body, Controller, Get, Param, Post, UseGuards } from '@nestjs/common';
import { BorrowService } from './borrow.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { CurrentUser } from '../common/current-user.decorator';

@Controller('borrow')
@UseGuards(JwtAuthGuard)
export class BorrowController {
  constructor(private readonly svc: BorrowService) {}
  @Post() create(@CurrentUser() u: any, @Body() b: any) { return this.svc.create(u.sub, +b.batchId, b?.note); }
  @Get('mine') mine(@CurrentUser() u: any) { return this.svc.mine(u); }
  @Get('to-me') toMe(@CurrentUser() u: any) { return this.svc.toMe(u); }
  @Post(':id/reject') reject(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.decide(+id, u, 'REJECT', b?.note); }
  @Post(':id/lend') lend(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.decide(+id, u, 'LEND', b?.note); }
  @Post(':id/transfer') transfer(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.decide(+id, u, 'TRANSFER', b?.note); }
  @Post(':id/cancel') cancel(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.cancel(+id, u); }
}
""")

# ---------- 4) 借用 module ----------
wfile(APP + "/src/borrow/borrow.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { BorrowService } from './borrow.service';
import { BorrowController } from './borrow.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { BorrowRequest } from '../entities/borrow-request.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { Chemical } from '../entities/chemical.entity';
import { User } from '../entities/user.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([BorrowRequest, ChemicalBatch, Chemical, User]),
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: (process.env.JWT_EXPIRES_IN || '7d') as any } }),
  ],
  controllers: [BorrowController],
  providers: [BorrowService, JwtAuthGuard],
})
export class BorrowModule {}
""")

# ---------- 5) app.module 重写：加 BorrowRequest 实体 + BorrowModule ----------
wfile(APP + "/src/app.module.ts", """import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { ChemicalsModule } from './chemicals/chemicals.module';
import { HazmatModule } from './hazmat/hazmat.module';
import { PurchasesModule } from './purchases/purchases.module';
import { BorrowModule } from './borrow/borrow.module';
import { User } from './entities/user.entity';
import { Group } from './entities/group.entity';
import { Chemical } from './entities/chemical.entity';
import { ChemicalBatch } from './entities/chemical-batch.entity';
import { Hazmat } from './entities/hazmat.entity';
import { PurchaseRequest } from './entities/purchase-request.entity';
import { BorrowRequest } from './entities/borrow-request.entity';

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
      entities: [User, Group, Chemical, ChemicalBatch, Hazmat, PurchaseRequest, BorrowRequest],
      synchronize: true,
      charset: 'utf8mb4',
    }),
    AuthModule,
    UsersModule,
    ChemicalsModule,
    HazmatModule,
    PurchasesModule,
    BorrowModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
""")

# ---------- 6) 改 purchases.service：precheck带batchId/ownerId；自动入库默认可借；updateMyBatch支持shareable ----------
pyedit(APP + "/src/purchases/purchases.service.ts", [
  [
"""      const bs = batches.filter((b) => b.chemicalId === m.id).map((b) => ({
        scope: b.scope, ownerName: b.ownerId ? om.get(b.ownerId) || '?' : null,
        remainLevel: b.remainLevel, remainText: levelText[b.remainLevel] || b.remainLevel,
        shareable: b.shareable, borrowable: b.shareable && NONEMPTY.includes(b.remainLevel),
      }));""",
"""      const bs = batches.filter((b) => b.chemicalId === m.id).map((b) => ({
        batchId: b.id, scope: b.scope, ownerId: b.ownerId, ownerName: b.ownerId ? om.get(b.ownerId) || '?' : null,
        remainLevel: b.remainLevel, remainText: levelText[b.remainLevel] || b.remainLevel,
        shareable: b.shareable, borrowable: b.shareable && NONEMPTY.includes(b.remainLevel),
      }));"""
  ],
  [
"      shareable: false, remainLevel: 'FULL',",
"      shareable: true, remainLevel: 'FULL',"
  ],
  [
"""    if (body.location !== undefined) b.location = body.location || null;
    if (body.remainLevel && LEVELS.includes(body.remainLevel)) b.remainLevel = body.remainLevel;""",
"""    if (body.location !== undefined) b.location = body.location || null;
    if (body.remainLevel && LEVELS.includes(body.remainLevel)) b.remainLevel = body.remainLevel;
    if (body.shareable !== undefined) b.shareable = !!body.shareable;"""
  ],
])

# 既有个人批次默认设为可借出
step("既有个人批次设可借出", "mysql -uplm -ppni38AWG4xy6wEyc plm -e \"UPDATE plm_chemical_batches SET shareable=1 WHERE scope='PERSONAL';\" 2>/dev/null; echo ok")

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo BUILD_OK; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("路由检查", "pm2 logs plm-api --lines 50 --nostream 2>&1 | grep -iE 'error|borrow' | tail -12")

# ---------- 端到端：小红(导师乙)申购DMF -> 发现admin可借 -> 借用 -> admin转让 ----------
def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o)

xh = login("stu_xh", "Plm@2026"); XH = "-H 'Authorization: Bearer %s'" % xh["token"]
print("\n## 小红 precheck DMF（应看到 admin 可借, 带 batchId/ownerId）")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases/precheck?cas=68-12-2&name=DMF' %s | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(b) for m in d['matched'] for b in m['batches']]\"" % XH)
print(o)
bid, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases/precheck?cas=68-12-2' %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print([b['batchId'] for m in d['matched'] for b in m['batches'] if b['borrowable']][0])\"" % XH)
bid = bid.strip()
print("## 小红对 batch %s 发起借用" % bid)
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/borrow -H 'Content-Type: application/json' %s -d '{\"batchId\":%s,\"note\":\"借50mL做反应\"}'" % (XH, bid))
print("  ", o[:200])
adm = login("admin", "Pniaef6b526!"); AD = "-H 'Authorization: Bearer %s'" % adm["token"]
print("## admin 我的借出（应见小红申请）")
o, _ = run("curl -s http://127.0.0.1:3000/api/borrow/to-me %s | python3 -c \"import sys,json;[print(r['id'],r['borrowerName'],'借',r['chemicalName'],r['remainText'],r['statusText'],'note='+str(r['note'])) for r in json.load(sys.stdin)]\"" % AD)
print(o)
rid, _ = run("curl -s http://127.0.0.1:3000/api/borrow/to-me %s | python3 -c \"import sys,json;print(json.load(sys.stdin)[0]['id'])\"" % AD)
rid = rid.strip()
print("## admin 选择『借一点』#%s" % rid)
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/borrow/%s/lend -H 'Content-Type: application/json' %s -d '{\"note\":\"柜子里自取\"}'" % (rid, AD))
print("  ", o[:200])
print("## 小红 我的借用")
o, _ = run("curl -s http://127.0.0.1:3000/api/borrow/mine %s | python3 -c \"import sys,json;[print(r['chemicalName'],'拥有人',r['ownerName'],r['statusText'],'批复='+str(r['decisionNote'])) for r in json.load(sys.stdin)]\"" % XH)
print(o)
cli.close()
print("\n=== DONE ===")
