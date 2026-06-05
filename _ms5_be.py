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
def run(cmd, t=480):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def step(t, c, to=480):
    o, e = run(c, to); print("\n#### %s"%t)
    if o: print(o[-2200:])
    if e: print("[stderr]", e[-700:])
def wfile(path, content):
    b = base64.b64encode(content.encode()).decode()
    o,e=run("mkdir -p $(dirname %s) && python3 - <<'PY'\nimport base64\nopen(%r,'w',encoding='utf-8').write(base64.b64decode('%s').decode())\nprint('w ok')\nPY"%(path,path,b))
    print("  写", path.replace(APP,""), o.strip(), e[-150:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:80])\n  s=s.replace(a,b,1)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF"%(path,b))
    print("  edit", path.split('/')[-1], o.strip(), e[-220:])
SVC = APP + "/src/instruments/instruments.service.ts"

# 1) 实体 InstrCategory
wfile(APP + "/src/entities/instr-category.entity.ts", """import { Column, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_instr_categories')
export class InstrCategory {
  @PrimaryGeneratedColumn() id: number;
  @Column({ unique: true }) key: string;
  @Column() label: string;
  @Column({ default: true }) lottery: boolean;
  @Column({ type: 'int', nullable: true }) weeklyCap: number | null; // null=不限
  @Column({ default: 1 }) slotsPerDay: number;
  @Column({ default: false }) builtin: boolean;
  @Column({ default: 100 }) sortOrder: number;
}
""")

# 2) 注册实体
pyedit(APP + "/src/instruments/instruments.module.ts", [
  ["import { PurchaseRequest } from '../entities/purchase-request.entity';",
   "import { PurchaseRequest } from '../entities/purchase-request.entity';\nimport { InstrCategory } from '../entities/instr-category.entity';"],
  ["TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent, PurchaseRequest, User]),",
   "TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent, PurchaseRequest, InstrCategory, User]),"],
])
pyedit(APP + "/src/app.module.ts", [
  ["import { PersonalEvent } from './entities/personal-event.entity';",
   "import { PersonalEvent } from './entities/personal-event.entity';\nimport { InstrCategory } from './entities/instr-category.entity';"],
  ["Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent],",
   "Instrument, InstrPriority, PolyHeadAuth, BookingDemand, Booking, LotteryRun, PiggybackRequest, PersonalEvent, InstrCategory],"],
])

# 3) service: import + inject this.cats
pyedit(SVC, [
  ["import { PurchaseRequest } from '../entities/purchase-request.entity';",
   "import { PurchaseRequest } from '../entities/purchase-request.entity';\nimport { InstrCategory } from '../entities/instr-category.entity';"],
  ["    @InjectRepository(PurchaseRequest) private purchases: Repository<PurchaseRequest>,",
   "    @InjectRepository(PurchaseRequest) private purchases: Repository<PurchaseRequest>,\n    @InjectRepository(InstrCategory) private cats: Repository<InstrCategory>,"],
])

# 4) bootstrap 调用 ensureCategories（最前）
pyedit(SVC, [
  ["  async onApplicationBootstrap() {\n    if ((await this.inst.count()) === 0) {",
   "  async onApplicationBootstrap() {\n    await this.ensureCategories();\n    if ((await this.inst.count()) === 0) {"],
])

# 5) 在 meta() 后插入 ensureCategories / customLotteryKeys / categories / createInstrument
ADD = r"""
  async ensureCategories() {
    const defs: [string, string, boolean, number | null, number, number][] = [
      ['VACUUM_OVEN', '真空烘箱', true, 8, 4, 10],
      ['CYCLE_OVEN', '环化烘箱', true, 2, 1, 20],
      ['MUFFLE', '马弗炉', true, 3, 1, 30],
      ['TUBE', '管式炉', true, 3, 1, 40],
      ['BET', 'BET', true, 7, 1, 50],
      ['POLY_HEAD', '聚合机头', true, 7, 2, 60],
      ['DMA', 'DMA', true, 4, 4, 70],
      ['TGA', 'TGA', true, 4, 4, 80],
      ['OTHER', '其他', false, null, 4, 200],
    ];
    for (const [key, label, lottery, cap, spd, so] of defs) {
      const ex = await this.cats.findOne({ where: { key } });
      if (!ex) await this.cats.save(this.cats.create({ key, label, lottery, weeklyCap: cap, slotsPerDay: spd, builtin: true, sortOrder: so }));
    }
  }
  async customLotteryKeys(): Promise<string[]> {
    const cs = await this.cats.find({ where: { lottery: true, builtin: false } });
    return cs.map((c) => c.key);
  }
  async categories() { return this.cats.find({ order: { sortOrder: 'ASC', id: 'ASC' } }); }

  async createInstrument(dto: any) {
    const name = String(dto.name || '').trim();
    if (!name) throw new BadRequestException('请输入设备名称');
    const BT: Record<string, string> = { '四块': 'FOUR_HOUR', '半天': 'HALF_DAY', '全天': 'FULL_DAY', '3+1': 'FILM_DRY' };
    const blockType = BT[dto.blockType] || dto.blockType || 'FOUR_HOUR';
    const slotsByBT: Record<string, number> = { FOUR_HOUR: 4, HALF_DAY: 2, FULL_DAY: 1, FILM_DRY: 4 };
    let category = '';
    let lottery = !!dto.lottery;
    if (dto.categoryMode === 'NEW') {
      const label = String(dto.newCategoryLabel || '').trim();
      if (!label) throw new BadRequestException('请输入新大类名称');
      const key = 'CUSTOM_' + Date.now();
      const cap = (dto.weeklyCap === '' || dto.weeklyCap == null) ? null : Math.max(1, +dto.weeklyCap);
      await this.cats.save(this.cats.create({ key, label, lottery, weeklyCap: lottery ? cap : null, slotsPerDay: slotsByBT[blockType] || 4, builtin: false, sortOrder: 150 }));
      category = key;
    } else if (dto.categoryMode === 'OTHER') {
      category = 'OTHER'; lottery = false;
    } else {
      category = String(dto.categoryKey || '');
      const cc = await this.cats.findOne({ where: { key: category } });
      if (!cc) throw new BadRequestException('大类不存在');
      lottery = cc.lottery;
      if (!cc.builtin && lottery && dto.weeklyCap !== undefined) { cc.weeklyCap = (dto.weeklyCap === '' || dto.weeklyCap == null) ? null : Math.max(1, +dto.weeklyCap); await this.cats.save(cc); }
    }
    const filmDry = blockType === 'FILM_DRY';
    const inst = this.inst.create({
      name, category, blockType: filmDry ? 'FOUR_HOUR' : blockType,
      filmCapable: filmDry, dryCapable: filmDry,
      piggyback: category === 'VACUUM_OVEN' || filmDry || category === 'CYCLE_OVEN' || category === 'MUFFLE',
      lottery, authRequired: category === 'POLY_HEAD', active: true,
      location: dto.location || null, model: dto.model || null, brand: dto.brand || null,
    });
    await this.inst.save(inst);
    if (lottery) await this.ensurePriorities();
    return this.inst.findOne({ where: { id: inst.id } });
  }
"""
b64 = base64.b64encode(ADD.encode()).decode()
o,e = run("python3 - <<'PYEOF'\nimport base64\np='%s'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\nanchor=\"  meta() { return { categories: CAT_LABEL, caps: WEEK_CAP, lotteryCats: LOTTERY_CATS }; }\"\nassert anchor in s,'MISS meta'\ns=s.replace(anchor, anchor+'\\n'+m, 1)\nopen(p,'w',encoding='utf-8').write(s)\nprint('meta-add ok')\nPYEOF"%(SVC,b64))
print(" ", o.strip(), e[-200:])

# 6) ensurePriorities 动态类别
pyedit(SVC, [
  ["    for (const s of students) for (const c of PRIO_CATS) {",
   "    const allCats = [...PRIO_CATS, ...(await this.customLotteryKeys())];\n    for (const s of students) for (const c of allCats) {"],
])

# 7) runLottery: 取 customCats + settle 含自定义
pyedit(SVC, [
  ["    const prios = await this.prio.find();\n    const ps = new Map(prios.map((p) => [p.userId + '|' + p.category, p]));",
   "    const prios = await this.prio.find();\n    const customCats = await this.cats.find({ where: { lottery: true, builtin: false } });\n    const ps = new Map(prios.map((p) => [p.userId + '|' + p.category, p]));"],
  ["      for (const cat of [...PRIO_CATS]) {",
   "      for (const cat of [...PRIO_CATS, ...customCats.map((c) => c.key)]) {"],
])
# 注意 settle 当前是 'for (const cat of PRIO_CATS) {'，替换之
pyedit(SVC, [
  ["      for (const cat of PRIO_CATS) {\n        const had = cat === 'VACUUM_FILM'",
   "      for (const cat of [...PRIO_CATS, ...customCats.map((c) => c.key)]) {\n        const had = cat === 'VACUUM_FILM'"],
])

# 8) 通用抽签分配（自定义大类）插入到 insert(out) 之前
GEN = r"""    // ===== 自定义大类：通用块分配（按优先级贪心，FULL/HALF/FOUR） =====
    {
      const LAY: Record<string, number[][]> = { FULL_DAY: [[8, 24]], HALF_DAY: [[8, 16], [16, 24]], FOUR_HOUR: [[8, 12], [12, 16], [16, 20], [20, 24]] };
      for (const cc of customCats) {
        const cat = cc.key;
        const pool = insts.filter((i) => i.category === cat);
        if (!pool.length) continue;
        const ds = demands.filter((d) => d.category === cat).sort((a, b) => score(b.userId, cat) - score(a.userId, cat));
        const usedSlot = new Set<string>();
        let got = 0, cap = 0;
        for (const o of pool) cap += 7 * (LAY[o.blockType] || LAY.FOUR_HOUR).length;
        for (const d of ds) {
          let need = d.blockCount;
          for (const o of pool) { const slots = LAY[o.blockType] || LAY.FOUR_HOUR; for (let dy = 0; dy < 7 && need > 0; dy++) { for (const [sh, eh] of slots) { if (need <= 0) break; const k = o.id + '|' + dy + '|' + sh; if (!usedSlot.has(k)) { usedSlot.add(k); push(o.id, d.userId, cat, dy, sh, eh, 'BLOCK', null); need--; got++; } } } if (need <= 0) break; }
          grant[d.userId + '|' + cat] = { req: d.blockCount, got: d.blockCount - need };
        }
        free[cat] = got < cap;
        allSat[cat] = ds.length > 0 && ds.every((d) => { const g = grant[d.userId + '|' + cat]; return g && g.got >= g.req; });
      }
    }

"""
b64 = base64.b64encode(GEN.encode()).decode()
o,e = run("python3 - <<'PYEOF'\nimport base64\np='%s'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\nanchor=\"    if (out.length) await this.bookings.insert(out);\"\nassert anchor in s,'MISS insert'\ns=s.replace(anchor, m+anchor, 1)\nopen(p,'w',encoding='utf-8').write(s)\nprint('gen-add ok')\nPYEOF"%(SVC,b64))
print(" ", o.strip(), e[-200:])

# 9) saveDemand: 允许自定义抽签类别 + cap 来自DB
pyedit(SVC, [
  ["""    const cat = dto.category;
    if (!LOTTERY_CATS.includes(cat)) throw new BadRequestException('该类别不参与抽签');
    const ck = this.cycleInfo().cycleKey;
    const cap = WEEK_CAP[cat];""",
   """    const cat = dto.category;
    let cap = WEEK_CAP[cat];
    let customLabel = '';
    if (!LOTTERY_CATS.includes(cat)) {
      const cc = await this.cats.findOne({ where: { key: cat, lottery: true } });
      if (!cc) throw new BadRequestException('该类别不参与抽签');
      cap = cc.weeklyCap ?? 9999; customLabel = cc.label;
    }
    const ck = this.cycleInfo().cycleKey;"""],
  ["      if (block > cap) throw new BadRequestException(`${CAT_LABEL[cat]} 每周上限 ${cap} 块`);",
   "      if (block > cap) throw new BadRequestException(`${CAT_LABEL[cat] || customLabel} 每周上限 ${cap} 块`);"],
])

# 10) overview 紧俏度：真空拆铺膜/干燥
pyedit(SVC, [
  ["      { key: 'VACUUM_OVEN', label: '真空烘箱', demand: dsum('VACUUM_OVEN', 'film') + dsum('VACUUM_OVEN', 'dry'), cap: filmCap + dryCap },",
   "      { key: 'VACUUM_FILM', label: '真空铺膜', demand: dsum('VACUUM_OVEN', 'film'), cap: filmCap },\n      { key: 'VACUUM_DRY', label: '真空干燥', demand: dsum('VACUUM_OVEN', 'dry'), cap: dryCap },"],
])

# 11) claim 支持非抽签仪器记录 + releaseClaim 允许 RECORD
OLD_CLAIM = """  async claim(user: any, body: any) {
    if (user.role !== 'STUDENT') throw new ForbiddenException('仅学生可预约');
    const inst = await this.inst.findOne({ where: { id: +body.instrumentId, active: true } });
    if (!inst) throw new NotFoundException('仪器不存在');
    if (!inst.lottery) throw new BadRequestException('该仪器随用随约，无需排班');
    const date = String(body.date); const sh = +body.startHour; const eh = +body.endHour;
    if (!date || !(eh > sh)) throw new BadRequestException('时段无效');
    if (inst.category === 'POLY_HEAD') {
      const a = await this.auth.findOne({ where: { userId: user.sub, instrumentId: inst.id } });
      if (!a) throw new ForbiddenException('你未被授权使用该机头');
    }
    const slotStart = new Date(date + 'T' + String(sh).padStart(2, '0') + ':00:00');
    if (slotStart.getTime() < Date.now()) throw new BadRequestException('该时段已过期，不可预约');
    const ex = await this.bookings.find({ where: { instrumentId: inst.id, date } });
    for (const b of ex) if (b.startHour < eh && sh < b.endHour) throw new BadRequestException('该时段已被占用');
    const task = inst.blockType === 'FULL_DAY' ? 'FULL_DAY' : inst.blockType === 'HALF_DAY' ? 'HALF_DAY' : 'BLOCK';
    await this.bookings.insert({ cycleKey: this.mondayOf(date), instrumentId: inst.id, userId: user.sub, category: inst.category, date, startHour: sh, endHour: eh, taskType: task, tempCeiling: null, source: 'CLAIM' } as any);
    return { ok: true };
  }"""
NEW_CLAIM = """  async claim(user: any, body: any) {
    const inst = await this.inst.findOne({ where: { id: +body.instrumentId, active: true } });
    if (!inst) throw new NotFoundException('仪器不存在');
    const date = String(body.date); const sh = +body.startHour; const eh = +body.endHour;
    if (!date || !(eh > sh)) throw new BadRequestException('时段无效');
    const recording = !inst.lottery; // 非抽签仪器=使用记录，任何人可登记
    if (!recording) {
      if (user.role !== 'STUDENT') throw new ForbiddenException('仅学生可预约');
      if (inst.category === 'POLY_HEAD') {
        const a = await this.auth.findOne({ where: { userId: user.sub, instrumentId: inst.id } });
        if (!a) throw new ForbiddenException('你未被授权使用该机头');
      }
      const slotStart = new Date(date + 'T' + String(sh).padStart(2, '0') + ':00:00');
      if (slotStart.getTime() < Date.now()) throw new BadRequestException('该时段已过期，不可预约');
    }
    const ex = await this.bookings.find({ where: { instrumentId: inst.id, date } });
    for (const b of ex) if (b.startHour < eh && sh < b.endHour) throw new BadRequestException('该时段已被占用');
    const task = recording ? 'BLOCK' : (inst.blockType === 'FULL_DAY' ? 'FULL_DAY' : inst.blockType === 'HALF_DAY' ? 'HALF_DAY' : 'BLOCK');
    await this.bookings.insert({ cycleKey: this.mondayOf(date), instrumentId: inst.id, userId: user.sub, category: inst.category, date, startHour: sh, endHour: eh, taskType: task, tempCeiling: null, source: recording ? 'RECORD' : 'CLAIM' } as any);
    return { ok: true };
  }"""
pyedit(SVC, [[OLD_CLAIM, NEW_CLAIM]])
pyedit(SVC, [
  ["    if (b.source !== 'CLAIM') throw new BadRequestException('抽签结果不可在此取消');",
   "    if (b.source !== 'CLAIM' && b.source !== 'RECORD') throw new BadRequestException('抽签结果不可在此取消');"],
])

# 12) controller: categories + admin create
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["  @Get('meta') meta() { return this.svc.meta(); }",
   "  @Get('meta') meta() { return this.svc.meta(); }\n  @Get('categories') categories() { return this.svc.categories(); }\n  @Post('admin/instrument') @UseGuards(RolesGuard) @Roles('ADMIN') createInst(@Body() b: any) { return this.svc.createInstrument(b); }"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -16 && echo BUILT"%APP, 520)
step("重启", PATHX + "pm2 restart plm-api >/dev/null 2>&1; sleep 5; pm2 logs plm-api --lines 6 --nostream 2>&1 | tail -8")
# 校验
import json as J
def login(u,p):
    o,_=run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'"%(u,p)); return J.loads(o).get("token")
TA="-H 'Authorization: Bearer %s'"%login("admin","Pniaef6b526!")
o,_=run("curl -s http://127.0.0.1:3000/api/instruments/categories %s"%TA); print("\n## categories:", o[:600])
cli.close(); print("\n=== DONE ===")
