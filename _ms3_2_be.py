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

# ---------- 报名需求实体 ----------
wfile(APP + "/src/entities/booking-demand.entity.ts", """import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';

@Entity('plm_booking_demands')
@Index(['userId', 'category', 'cycleKey'], { unique: true })
export class BookingDemand {
  @PrimaryGeneratedColumn() id: number;
  @Column() userId: number;
  @Column() cycleKey: string;          // 目标周周一日期 YYYY-MM-DD
  @Column() category: string;          // VACUUM_OVEN/FURNACE/POLY_HEAD/DMA/TGA
  @Column({ default: 'CATEGORY' }) instrumentMode: string; // CATEGORY/SPECIFIC
  @Column({ type: 'json', nullable: true }) instrumentIds: number[] | null;
  @Column({ default: 0 }) filmCount: number;   // 铺膜数(真空)
  @Column({ default: 0 }) dryCount: number;    // 干燥数(真空)
  @Column({ default: 0 }) blockCount: number;  // 块数(环化/机头/DMA/TGA)
  @Column({ type: 'int', nullable: true }) tempCeiling: number | null; // 升温温度上限(环化)
  @Column({ default: 0 }) gridsTotal: number;  // 折算占用(真空=铺3+干1; 其余=块数)
  @CreateDateColumn() createdAt: Date;
  @UpdateDateColumn() updatedAt: Date;
}
""")

# ---------- 在 InstrumentsService 末尾插入报名相关方法 ----------
BOOK = r"""
  // ===== 报名（MS3-2）=====
  cycleInfo() {
    const now = new Date();
    const day = now.getDay(); // 0 周日..6 周六
    const daysToMon = ((8 - day) % 7) || 7;
    const nextMon = new Date(now); nextMon.setDate(now.getDate() + daysToMon);
    const target = new Date(nextMon); target.setDate(nextMon.getDate() + 7); // 排"下一周"
    const ck = target.toISOString().slice(0, 10);
    const end = new Date(target); end.setDate(target.getDate() + 6);
    const deadline = new Date(target); deadline.setDate(target.getDate() - 8); // 目标周前的周日
    return { cycleKey: ck, start: ck, end: end.toISOString().slice(0, 10), deadline: deadline.toISOString().slice(0, 10), open: true };
  }

  async myDemands(userId: number) {
    const ck = this.cycleInfo().cycleKey;
    const ds = await this.demands.find({ where: { userId, cycleKey: ck }, order: { id: 'ASC' } });
    const ids = [...new Set(ds.flatMap((d) => d.instrumentIds || []))];
    const insts = ids.length ? await this.inst.find({ where: { id: In(ids) } }) : [];
    const nm = new Map(insts.map((i) => [i.id, i.name]));
    return ds.map((d) => ({ ...d, instrumentNames: (d.instrumentIds || []).map((i) => nm.get(i) || ('#' + i)) }));
  }

  async saveDemand(user: any, dto: any) {
    if (user.role !== 'STUDENT') throw new ForbiddenException('仅学生参与预约报名');
    const cat = dto.category;
    if (!LOTTERY_CATS.includes(cat)) throw new BadRequestException('该类别不参与抽签');
    const ck = this.cycleInfo().cycleKey;
    let film = 0, dry = 0, block = 0, temp: number | null = null, grids = 0;
    if (cat === 'VACUUM_OVEN') {
      film = Math.max(0, +dto.filmCount || 0); dry = Math.max(0, +dto.dryCount || 0);
      grids = film * 3 + dry * 1;
      if (grids < 1) throw new BadRequestException('请填写铺膜或干燥数量');
      if (grids > WEEK_CAP[cat]) throw new BadRequestException(`真空烘箱每周上限 ${WEEK_CAP[cat]} 格，当前 ${grids} 格`);
    } else if (cat === 'FURNACE') {
      block = Math.max(0, +dto.blockCount || 0);
      if (block < 1) throw new BadRequestException('请填写全天块数量');
      if (block > WEEK_CAP[cat]) throw new BadRequestException(`环化类每周上限 ${WEEK_CAP[cat]} 个全天块`);
      temp = dto.tempCeiling != null && dto.tempCeiling !== '' ? +dto.tempCeiling : null;
      if (temp == null || temp <= 0) throw new BadRequestException('请填写升温程序温度上限(℃)');
      grids = block;
    } else if (cat === 'POLY_HEAD') {
      block = Math.max(0, +dto.blockCount || 0);
      if (block < 1) throw new BadRequestException('请填写半天块数量');
      if (block > WEEK_CAP[cat]) throw new BadRequestException(`聚合机头每周上限 ${WEEK_CAP[cat]} 个半天块`);
      grids = block;
    } else { // DMA / TGA
      block = Math.max(0, +dto.blockCount || 0);
      if (block < 1) throw new BadRequestException('请填写块数量');
      if (block > WEEK_CAP[cat]) throw new BadRequestException(`${cat} 每周上限 ${WEEK_CAP[cat]} 个块`);
      grids = block;
    }
    // 指定仪器校验
    let mode = dto.instrumentMode === 'SPECIFIC' ? 'SPECIFIC' : 'CATEGORY';
    let instrumentIds: number[] | null = null;
    if (cat === 'POLY_HEAD') {
      const auth = await this.auth.find({ where: { userId: user.sub } });
      const authIds = auth.map((a) => a.instrumentId);
      if (!authIds.length) throw new BadRequestException('你暂无授权的机头，请联系管理员');
      if (mode === 'SPECIFIC') {
        instrumentIds = (dto.instrumentIds || []).map((x: any) => +x).filter((x: number) => authIds.includes(x));
        if (!instrumentIds.length) throw new BadRequestException('请选择你被授权的机头');
      } else { instrumentIds = authIds; }
    } else if (mode === 'SPECIFIC') {
      const wanted = (dto.instrumentIds || []).map((x: any) => +x);
      const insts = wanted.length ? await this.inst.find({ where: { id: In(wanted) } }) : [];
      instrumentIds = insts.filter((i) => i.category === cat).map((i) => i.id);
      if (!instrumentIds.length) throw new BadRequestException('请选择该类别下的具体仪器');
      if (cat === 'VACUUM_OVEN' && film > 0 && !insts.some((i) => i.filmCapable)) throw new BadRequestException('所选烘箱均不可铺膜，请至少选一台可铺膜的');
    }
    // upsert
    let d = await this.demands.findOne({ where: { userId: user.sub, category: cat, cycleKey: ck } });
    if (!d) d = this.demands.create({ userId: user.sub, category: cat, cycleKey: ck } as any);
    Object.assign(d, { instrumentMode: mode, instrumentIds, filmCount: film, dryCount: dry, blockCount: block, tempCeiling: temp, gridsTotal: grids });
    await this.demands.save(d);
    return this.myDemands(user.sub);
  }

  async deleteDemand(user: any, id: number) {
    const d = await this.demands.findOne({ where: { id } });
    if (!d) throw new NotFoundException('不存在');
    if (d.userId !== user.sub) throw new ForbiddenException('只能删除自己的报名');
    await this.demands.remove(d);
    return this.myDemands(user.sub);
  }
"""
b64 = base64.b64encode(BOOK.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s/src/instruments/instruments.service.ts'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('methods inserted')\nPYEOF" % (APP, b64))
print("  ", o.strip(), e[-200:])

# service 需要 demands repo + 额外异常导入
pyedit(APP + "/src/instruments/instruments.service.ts", [
  ["import { Injectable, OnApplicationBootstrap } from '@nestjs/common';",
   "import { BadRequestException, ForbiddenException, Injectable, NotFoundException, OnApplicationBootstrap } from '@nestjs/common';"],
  ["import { PolyHeadAuth } from '../entities/polyhead-auth.entity';",
   "import { PolyHeadAuth } from '../entities/polyhead-auth.entity';\nimport { BookingDemand } from '../entities/booking-demand.entity';"],
  ["""    @InjectRepository(PolyHeadAuth) private auth: Repository<PolyHeadAuth>,
    @InjectRepository(User) private users: Repository<User>,
  ) {}""",
   """    @InjectRepository(PolyHeadAuth) private auth: Repository<PolyHeadAuth>,
    @InjectRepository(BookingDemand) private demands: Repository<BookingDemand>,
    @InjectRepository(User) private users: Repository<User>,
  ) {}"""],
])

# controller 加路由
pyedit(APP + "/src/instruments/instruments.controller.ts", [
  ["import { Controller, Get, Query, UseGuards } from '@nestjs/common';",
   "import { Body, Controller, Delete, Get, Param, Post, Query, UseGuards } from '@nestjs/common';"],
  ["  @Get('priorities') @UseGuards(RolesGuard) @Roles('ADMIN') priorities() { return this.svc.priorityTable(); }",
   """  @Get('priorities') @UseGuards(RolesGuard) @Roles('ADMIN') priorities() { return this.svc.priorityTable(); }
  @Get('booking/cycle') cycle() { return this.svc.cycleInfo(); }
  @Get('booking/mine') myDemands(@CurrentUser() u: any) { return this.svc.myDemands(u.sub); }
  @Post('booking') saveDemand(@CurrentUser() u: any, @Body() b: any) { return this.svc.saveDemand(u, b); }
  @Delete('booking/:id') delDemand(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.deleteDemand(u, +id); }"""],
])

# module 注册 BookingDemand
pyedit(APP + "/src/instruments/instruments.module.ts", [
  ["import { PolyHeadAuth } from '../entities/polyhead-auth.entity';",
   "import { PolyHeadAuth } from '../entities/polyhead-auth.entity';\nimport { BookingDemand } from '../entities/booking-demand.entity';"],
  ["TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, User]),",
   "TypeOrmModule.forFeature([Instrument, InstrPriority, PolyHeadAuth, BookingDemand, User]),"],
])

# app.module 注册实体
pyedit(APP + "/src/app.module.ts", [
  ["import { PolyHeadAuth } from './entities/polyhead-auth.entity';",
   "import { PolyHeadAuth } from './entities/polyhead-auth.entity';\nimport { BookingDemand } from './entities/booking-demand.entity';"],
  ["Instrument, InstrPriority, PolyHeadAuth],",
   "Instrument, InstrPriority, PolyHeadAuth, BookingDemand],"],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 30 --nostream 2>&1 | grep -ciE 'error TS'")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o)
sm = login("stu_xm", "Plm@2026"); SM = "-H 'Authorization: Bearer %s'" % sm["token"]
print("\n## 报名周期")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/booking/cycle %s" % SM); print("  ", o)
print("## 小明报真空烘箱 1铺膜+3干燥(=6格, 合法)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"VACUUM_OVEN\",\"filmCount\":1,\"dryCount\":3}'" % SM); print("  ", o[:200])
print("## 小明报真空烘箱 2铺膜+1干燥(=7格, 应超限)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"VACUUM_OVEN\",\"filmCount\":2,\"dryCount\":1}'" % SM); print("  ", o[:160])
print("## 小明报环化 缺温度(应拦)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"FURNACE\",\"blockCount\":1}'" % SM); print("  ", o[:160])
print("## 小明报环化 2全天块+温度300")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"FURNACE\",\"blockCount\":2,\"tempCeiling\":300}'" % SM); print("  ", o[:200])
print("## 小明报机头(授权1#2#) 5半天块")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"POLY_HEAD\",\"blockCount\":5}'" % SM); print("  ", o[:120])
print("## 小红报机头(她授权3#4#) 指定1#(无权, 应拦)")
xh = login("stu_xh", "Plm@2026"); XH = "-H 'Authorization: Bearer %s'" % xh["token"]
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/my-heads %s | python3 -c \"import sys,json;print('小红机头ids',[x['id'] for x in json.load(sys.stdin)])\"" % XH); print("  ", o)
print("## 小明 我的报名汇总")
o, _ = run("curl -s http://127.0.0.1:3000/api/instruments/booking/mine %s | python3 -c \"import sys,json;[print(' ',d['category'],'铺'+str(d['filmCount']),'干'+str(d['dryCount']),'块'+str(d['blockCount']),'温'+str(d['tempCeiling']),'占'+str(d['gridsTotal']),'格') for d in json.load(sys.stdin)]\"" % SM); print(o)
cli.close()
print("\n=== DONE ===")
