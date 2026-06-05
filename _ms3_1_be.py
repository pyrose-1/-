# -*- coding: utf-8 -*-
import os, sys, json
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

# ---------- 实体 ----------
wfile(APP + "/src/entities/instrument.entity.ts", """import { Column, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_instruments')
export class Instrument {
  @PrimaryGeneratedColumn() id: number;
  @Column() name: string;
  @Column({ nullable: true }) model: string | null;
  @Column({ nullable: true }) brand: string | null;
  @Column({ nullable: true }) location: string | null;
  @Column({ nullable: true }) keeper: string | null;
  @Column({ nullable: true }) keeperPhone: string | null;
  @Column() category: string;        // VACUUM_OVEN/FURNACE/POLY_HEAD/DMA/TGA/OTHER
  @Column() blockType: string;       // FOUR_HOUR/HALF_DAY/FULL_DAY/FREE
  @Column({ default: false }) filmCapable: boolean;  // 可铺膜
  @Column({ default: false }) dryCapable: boolean;   // 可干燥
  @Column({ default: false }) piggyback: boolean;    // 支持蹭一下
  @Column({ default: true }) lottery: boolean;       // 参与抽签
  @Column({ default: false }) authRequired: boolean; // 授权制(聚合机头)
  @Column({ type: 'text', nullable: true }) note: string | null;
  @Column({ default: '正常' }) status: string;
  @Column({ default: true }) active: boolean;
}
""")

wfile(APP + "/src/entities/instr-priority.entity.ts", """import { Column, Entity, Index, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_instr_priority')
@Index(['userId', 'category'], { unique: true })
export class InstrPriority {
  @PrimaryGeneratedColumn() id: number;
  @Column() userId: number;
  @Column() category: string;        // VACUUM_OVEN/FURNACE/POLY_HEAD/DMA/TGA
  @Column({ type: 'double', default: 0 }) score: number;
}
""")

wfile(APP + "/src/entities/polyhead-auth.entity.ts", """import { Column, Entity, Index, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_polyhead_auth')
@Index(['userId', 'instrumentId'], { unique: true })
export class PolyHeadAuth {
  @PrimaryGeneratedColumn() id: number;
  @Column() userId: number;
  @Column() instrumentId: number;
}
""")

# ---------- service：播种 + 列表 ----------
wfile(APP + "/src/instruments/instruments.service.ts", r"""import { Injectable, OnApplicationBootstrap } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { Instrument } from '../entities/instrument.entity';
import { InstrPriority } from '../entities/instr-priority.entity';
import { PolyHeadAuth } from '../entities/polyhead-auth.entity';
import { User } from '../entities/user.entity';

export const LOTTERY_CATS = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA'];
export const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', FURNACE: '环化/马弗/管式/BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他' };
export const WEEK_CAP: Record<string, number> = { VACUUM_OVEN: 6, FURNACE: 2, POLY_HEAD: 7, DMA: 4, TGA: 4 };

// 真空烘箱：[名称, 可铺膜, 可干燥]
const VAC: [string, boolean, boolean][] = [
  ['C442真空烘箱-5#（门左侧上）铺膜用', true, false],
  ['C442真空烘箱-7#（靠窗-上）铺膜用', true, false],
  ['C442真空烘箱-8#（靠窗-下）铺膜用', true, false],
  ['C446真空烘箱-1#（门口下）铺膜用', true, false],
  ['C446真空烘箱-9#（门左侧-上）禁止铺膜', false, true],
  ['C446真空小烘箱-2#（上）不可铺膜', false, true],
  ['C446真空小烘箱-3#（中）不可铺膜', false, true],
  ['C446真空小烘箱-4#（下）不可铺膜', false, true],
  ['C442真空烘箱-6#（门左侧-下）', true, true],
  ['C442真空烘箱-10#', true, true],
  ['C442真空烘箱-11#', true, true],
  ['轻质楼316真空烘箱-1', true, true],
  ['轻质楼316真空烘箱-2', true, true],
  ['轻质楼316真空烘箱-3', true, true],
  ['轻质楼318真空烘箱-4', true, true],
  ['轻质楼318真空烘箱-5', true, true],
  ['轻质楼318真空烘箱-6', true, true],
];
// 环化/马弗/管式/BET：[名称, 支持蹭一下]
const FUR: [string, boolean][] = [
  ['C442高温真空烘箱（环化大烘箱）', true],
  ['C446高温真空烘箱（环化大烘箱·新）', true],
  ['轻质楼110高温充氮烘箱', true],
  ['轻质楼110马弗炉', true],
  ['C556真空管式干燥炉', false],
  ['A425自动比表面积分析测试仪（BET）', false],
];
const OTHERS = ['C556超临界CO2', 'C556热牵伸机', 'Mikrouna超级净化手套箱', 'C461纤维强度仪(XQ-1C)', '电化学 Autolab(PGSTAT302N)', '电化学工作站(CHI660D)', '冷冻干燥机（新）', '轻质楼202热压机', '万能材料试验机 A425'];

@Injectable()
export class InstrumentsService implements OnApplicationBootstrap {
  constructor(
    @InjectRepository(Instrument) private inst: Repository<Instrument>,
    @InjectRepository(InstrPriority) private prio: Repository<InstrPriority>,
    @InjectRepository(PolyHeadAuth) private auth: Repository<PolyHeadAuth>,
    @InjectRepository(User) private users: Repository<User>,
  ) {}

  async onApplicationBootstrap() {
    if ((await this.inst.count()) === 0) {
      const rows: any[] = [];
      for (const [name, film, dry] of VAC) rows.push({ name, category: 'VACUUM_OVEN', blockType: 'FOUR_HOUR', filmCapable: film, dryCapable: dry, piggyback: true, lottery: true });
      for (const [name, pig] of FUR) rows.push({ name, category: 'FURNACE', blockType: 'FULL_DAY', piggyback: pig, lottery: true });
      rows.push({ name: 'C461动态热机械分析仪（DMA·Q800）', model: 'Q800', brand: 'TA', category: 'DMA', blockType: 'FOUR_HOUR', lottery: true });
      rows.push({ name: 'C461热重分析仪（TGA·TG209F3）', model: 'TG209F3', brand: '耐驰', category: 'TGA', blockType: 'FOUR_HOUR', lottery: true });
      for (let i = 1; i <= 4; i++) rows.push({ name: '聚合机头-' + i + '#（测试）', category: 'POLY_HEAD', blockType: 'HALF_DAY', lottery: true, authRequired: true });
      for (const name of OTHERS) rows.push({ name, category: 'OTHER', blockType: 'FREE', lottery: false });
      await this.inst.save(rows.map((r) => this.inst.create(r)));
      console.log('[seed] instruments', rows.length);
    }
    await this.ensurePriorities();
    await this.ensureSampleHeadAuth();
  }

  // 为每个学生 × 每个抽签类别 生成 0+随机小数 初始优先级
  async ensurePriorities() {
    const students = await this.users.find({ where: { role: 'STUDENT' } });
    const existing = await this.prio.find();
    const has = new Set(existing.map((p) => p.userId + '|' + p.category));
    const add: any[] = [];
    for (const s of students) for (const c of LOTTERY_CATS) {
      if (!has.has(s.id + '|' + c)) add.push({ userId: s.id, category: c, score: Math.round(Math.random() * 1000) / 1000 });
    }
    if (add.length) { await this.prio.save(add.map((a) => this.prio.create(a))); console.log('[seed] priorities', add.length); }
  }

  // 测试：每4人用2台 -> 小明/小刚=1#2#，小红=3#4#
  async ensureSampleHeadAuth() {
    if ((await this.auth.count()) > 0) return;
    const heads = await this.inst.find({ where: { category: 'POLY_HEAD' }, order: { id: 'ASC' } });
    if (heads.length < 4) return;
    const map: Record<string, number[]> = { stu_xm: [0, 1], stu_xg: [0, 1], stu_xh: [2, 3] };
    const add: any[] = [];
    for (const [uname, idx] of Object.entries(map)) {
      const u = await this.users.findOne({ where: { username: uname } });
      if (!u) continue;
      for (const i of idx) add.push({ userId: u.id, instrumentId: heads[i].id });
    }
    if (add.length) { await this.auth.save(add.map((a) => this.auth.create(a))); console.log('[seed] polyhead auth', add.length); }
  }

  async list(category?: string) {
    const where: any = { active: true };
    if (category) where.category = category;
    const all = await this.inst.find({ where, order: { category: 'ASC', id: 'ASC' } });
    return all;
  }

  async myHeads(userId: number) {
    const a = await this.auth.find({ where: { userId } });
    const ids = a.map((x) => x.instrumentId);
    return ids.length ? this.inst.find({ where: { id: In(ids) } }) : [];
  }

  // 管理员：优先级总表（学生 × 类别）
  async priorityTable() {
    const students = await this.users.find({ where: { role: 'STUDENT' }, order: { id: 'ASC' } });
    const all = await this.prio.find();
    const m = new Map(all.map((p) => [p.userId + '|' + p.category, p.score]));
    return students.map((s) => ({
      id: s.id, name: s.name, username: s.username,
      scores: Object.fromEntries(LOTTERY_CATS.map((c) => [c, m.get(s.id + '|' + c) ?? null])),
    }));
  }

  meta() { return { categories: CAT_LABEL, caps: WEEK_CAP, lotteryCats: LOTTERY_CATS }; }
}
""")

# ---------- controller ----------
wfile(APP + "/src/instruments/instruments.controller.ts", """import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { InstrumentsService } from './instruments.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Roles } from '../common/roles.decorator';
import { CurrentUser } from '../common/current-user.decorator';

@Controller('instruments')
@UseGuards(JwtAuthGuard)
export class InstrumentsController {
  constructor(private readonly svc: InstrumentsService) {}
  @Get() list(@Query('category') c?: string) { return this.svc.list(c); }
  @Get('meta') meta() { return this.svc.meta(); }
  @Get('my-heads') myHeads(@CurrentUser() u: any) { return this.svc.myHeads(u.sub); }
  @Get('priorities') @UseGuards(RolesGuard) @Roles('ADMIN') priorities() { return this.svc.priorityTable(); }
}
""")

# ---------- module ----------
wfile(APP + "/src/instruments/instruments.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { InstrumentsService } from './instruments.service';
import { InstrumentsController } from './instruments.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Instrument } from '../entities/instrument.entity';
import { InstrPriority } from '../entities/instr-priority.entity';
import { PolyHeadAuth } from '../entities/polyhead-auth.entity';
import { User } from '../entities/user.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, User]),
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: (process.env.JWT_EXPIRES_IN || '7d') as any } }),
  ],
  controllers: [InstrumentsController],
  providers: [InstrumentsService, JwtAuthGuard, RolesGuard],
  exports: [InstrumentsService],
})
export class InstrumentsModule {}
""")

# ---------- app.module 注册 ----------
import base64, json
reps = [
  ["import { BorrowModule } from './borrow/borrow.module';",
   "import { BorrowModule } from './borrow/borrow.module';\nimport { InstrumentsModule } from './instruments/instruments.module';"],
  ["import { BorrowRequest } from './entities/borrow-request.entity';",
   "import { BorrowRequest } from './entities/borrow-request.entity';\nimport { Instrument } from './entities/instrument.entity';\nimport { InstrPriority } from './entities/instr-priority.entity';\nimport { PolyHeadAuth } from './entities/polyhead-auth.entity';"],
  ["entities: [User, Group, Chemical, ChemicalBatch, Hazmat, PurchaseRequest, BorrowRequest],",
   "entities: [User, Group, Chemical, ChemicalBatch, Hazmat, PurchaseRequest, BorrowRequest, Instrument, InstrPriority, PolyHeadAuth],"],
  ["    BorrowModule,\n  ],",
   "    BorrowModule,\n    InstrumentsModule,\n  ],"],
]
b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/app.module.ts'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:40])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('app.module ok')\nPYEOF" % (APP, b))
print("  ", o.strip(), e[-300:])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误 / 播种", "pm2 logs plm-api --lines 50 --nostream 2>&1 | grep -ciE 'error TS'; pm2 logs plm-api --lines 80 --nostream 2>&1 | grep -iE 'seed] instr|seed] prio|seed] poly|InstrumentsController' | tail -8")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o)
adm = login("admin", "Pniaef6b526!"); AD = "-H 'Authorization: Bearer %s'" % adm["token"]
print("\n## 各类别仪器台数")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments %s | python3 -c \"import sys,json,collections;d=json.load(sys.stdin);c=collections.Counter(x['category'] for x in d);print(dict(c),'共',len(d))\"" % AD)
print(o)
print("## 真空烘箱铺膜/干燥属性抽样")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments?category=VACUUM_OVEN' %s | python3 -c \"import sys,json;[print(' ',x['name'][:22],'铺膜' if x['filmCapable'] else '  ','干燥' if x['dryCapable'] else '') for x in json.load(sys.stdin)[:6]]\"" % AD)
print(o)
print("## 优先级总表(管理员)")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/priorities %s | python3 -c \"import sys,json;[print(' ',r['name'],{k:round(v,3) for k,v in r['scores'].items()}) for r in json.load(sys.stdin)]\"" % AD)
print(o)
print("## 小明 我的机头")
sm = login("stu_xm", "Plm@2026"); SM = "-H 'Authorization: Bearer %s'" % sm["token"]
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/my-heads %s | python3 -c \"import sys,json;print([x['name'] for x in json.load(sys.stdin)])\"" % SM)
print(o)
print("## 小红 我的机头")
xh = login("stu_xh", "Plm@2026"); XH = "-H 'Authorization: Bearer %s'" % xh["token"]
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/my-heads %s | python3 -c \"import sys,json;print([x['name'] for x in json.load(sys.stdin)])\"" % XH)
print(o)
cli.close()
print("\n=== DONE ===")
