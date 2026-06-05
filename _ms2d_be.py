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

# ---------- 在 PurchasesService 末尾追加 holdings / myStudents / updateMyBatch ----------
# 直接重写整文件最稳：在现有基础上加 3 个方法 + REMAIN_LEVELS 常量
# 读现有 service 不便，采用追加：用 python 在 class 闭合前插入。改用 sed 在最后一个 '}' 前插入方法。
METHODS = r'''
  // ===== 库存视图 / 我的药品 =====
  async holdings(userId: number) {
    const batches = await this.batch.find({ where: { ownerId: userId }, order: { receivedAt: 'DESC' } });
    const chemIds = [...new Set(batches.map((b) => b.chemicalId))];
    const chems = chemIds.length ? await this.chem.find({ where: { id: In(chemIds) } }) : [];
    const cm = new Map(chems.map((c) => [c.id, c]));
    const batchIds = batches.map((b) => b.id);
    const prs = batchIds.length ? await this.reqs.find({ where: { batchId: In(batchIds) } }) : [];
    const pm = new Map(prs.map((p) => [p.batchId as number, p]));
    let totalAmount = 0;
    const items = batches.map((b) => {
      const c = cm.get(b.chemicalId);
      const pr = pm.get(b.id);
      if (pr?.price) totalAmount += parseFloat(pr.price) || 0;
      return {
        batchId: b.id, batchNo: b.batchNo, remainLevel: b.remainLevel, location: b.location,
        receivedAt: b.receivedAt, shareable: b.shareable, scope: b.scope,
        chemicalId: b.chemicalId, name: c?.name || '?', cas: c?.cas || null,
        hazmat: this.hazmat.lookup(c?.cas),
        price: pr?.price || null, productNo: pr?.productNo || null,
        quantity: pr?.quantity || null, unit: pr?.unit || c?.unit || null,
        purchaseDate: pr?.stockedAt || pr?.submittedAt || b.receivedAt,
      };
    });
    return { totalAmount: Math.round(totalAmount * 100) / 100, count: items.length, items };
  }

  async updateMyBatch(user: any, batchId: number, body: { location?: string; remainLevel?: string }) {
    const b = await this.batch.findOne({ where: { id: batchId } });
    if (!b) throw new NotFoundException('批次不存在');
    if (b.ownerId !== user.sub && user.role !== 'ADMIN') throw new ForbiddenException('只能维护自己持有的药品');
    const LEVELS = ['FULL', 'ALMOST_FULL', 'HALF', 'LOW', 'LITTLE', 'EMPTY'];
    if (body.location !== undefined) b.location = body.location || null;
    if (body.remainLevel && LEVELS.includes(body.remainLevel)) b.remainLevel = body.remainLevel;
    await this.batch.save(b);
    return { ok: true };
  }

  async myStudents(user: any) {
    let students: User[] = [];
    if (user.role === 'ADMIN') students = await this.users.find({ where: { role: 'STUDENT' }, order: { id: 'ASC' } });
    else if (user.role === 'TUTOR') students = await this.users.find({ where: { role: 'STUDENT', tutorId: user.sub }, order: { id: 'ASC' } });
    const approved = await this.reqs.find({ where: { status: 'APPROVED' } });
    const cnt = new Map<number, { n: number; amt: number }>();
    for (const a of approved) {
      const g = cnt.get(a.applicantId) || { n: 0, amt: 0 };
      g.n += 1; g.amt += parseFloat(a.price || '0') || 0; cnt.set(a.applicantId, g);
    }
    return students.map((s) => ({ id: s.id, name: s.name, username: s.username, items: cnt.get(s.id)?.n || 0, totalAmount: Math.round((cnt.get(s.id)?.amt || 0) * 100) / 100 }));
  }

  async studentHoldings(user: any, studentId: number) {
    const target = await this.users.findOne({ where: { id: studentId } });
    if (!target) throw new NotFoundException('用户不存在');
    if (user.role === 'TUTOR' && target.tutorId !== user.sub) throw new ForbiddenException('只能查看本人指导的学生');
    if (user.role !== 'ADMIN' && user.role !== 'TUTOR') throw new ForbiddenException('无权限');
    const h = await this.holdings(studentId);
    return { student: { id: target.id, name: target.name, username: target.username }, ...h };
  }
'''
# 用 awk 在文件最后一个右花括号前插入
import base64
b64 = base64.b64encode(METHODS.encode("utf-8")).decode()
run("python3 - <<'PYEOF'\n"
    "import base64\n"
    "p='%s/src/purchases/purchases.service.ts'\n"
    "s=open(p,encoding='utf-8').read()\n"
    "m=base64.b64decode('%s').decode('utf-8')\n"
    "i=s.rstrip().rfind('}')\n"
    "s=s[:i]+m+'\\n}'+s[i+1:]\n"
    "open(p,'w',encoding='utf-8').write(s)\n"
    "print('patched')\n"
    "PYEOF" % (APP, b64))
step("确认插入", "grep -nE 'async holdings|async myStudents|async studentHoldings|async updateMyBatch' %s/src/purchases/purchases.service.ts" % APP)

# ---------- InventoryController ----------
wfile(APP + "/src/purchases/inventory.controller.ts", """import { Body, Controller, Get, Param, Put, UseGuards } from '@nestjs/common';
import { PurchasesService } from './purchases.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Roles } from '../common/roles.decorator';
import { CurrentUser } from '../common/current-user.decorator';

@Controller('inventory')
@UseGuards(JwtAuthGuard)
export class InventoryController {
  constructor(private readonly svc: PurchasesService) {}
  @Get('mine') mine(@CurrentUser() u: any) { return this.svc.holdings(u.sub); }
  @Put('batches/:id') update(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.updateMyBatch(u, +id, b); }
  @Get('my-students') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR') students(@CurrentUser() u: any) { return this.svc.myStudents(u); }
  @Get('student/:id') @UseGuards(RolesGuard) @Roles('ADMIN', 'TUTOR') student(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.studentHoldings(u, +id); }
}
""")

# ---------- 注册 InventoryController ----------
wfile(APP + "/src/purchases/purchases.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { PurchasesService } from './purchases.service';
import { PurchasesController } from './purchases.controller';
import { InventoryController } from './inventory.controller';
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
  controllers: [PurchasesController, InventoryController],
  providers: [PurchasesService, JwtAuthGuard, RolesGuard],
})
export class PurchasesModule {}
""")

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -10 && echo BUILD_OK; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("启动检查", "pm2 logs plm-api --lines 40 --nostream 2>&1 | grep -iE 'error|inventory|my-students' | tail -12")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    try: return json.loads(o)
    except Exception: return {}

# 先让导师甲把小明小刚的待审批通过，制造库存
tj = login("tutor_jia", "Plm@2026"); T = "-H 'Authorization: Bearer %s'" % tj["token"]
ids, _ = run("curl -s 'http://127.0.0.1:3000/api/purchases?status=PENDING' %s | python3 -c \"import sys,json;print(','.join(str(r['id']) for r in json.load(sys.stdin)))\"" % T)
ids = ids.strip()
if ids:
    run("curl -s -X POST http://127.0.0.1:3000/api/purchases/approve-batch -H 'Content-Type: application/json' %s -d '{\"ids\":[%s]}'" % (T, ids))
    print("已通过入库:", ids)

print("\n## 导师甲 我的学生")
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/my-students %s" % T)
print("  ", o)
print("## 导师甲 看小明(id6)库存")
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/student/6 %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('学生',d['student']['name'],'总额',d['totalAmount'],'件数',d['count']);[print(' ',i['name'],i['remainLevel'],i['location'],'¥'+str(i['price']),str(i['purchaseDate'])[:10]) for i in d['items']]\"" % T)
print(o)
print("## 导师乙 越权看小明(应 403)")
ty = login("tutor_yi", "Plm@2026"); Y = "-H 'Authorization: Bearer %s'" % ty["token"]
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/student/6 %s" % Y)
print("  ", o[:120])
print("## 小明 我的药品 + 维护一条(改位置+余量)")
xm = login("stu_xm", "Plm@2026"); S = "-H 'Authorization: Bearer %s'" % xm["token"]
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('件数',d['count'],'总额',d['totalAmount']);print('first batchId', d['items'][0]['batchId'] if d['items'] else None)\"" % S)
print(o)
bid, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print(d['items'][0]['batchId'])\"" % S)
bid = bid.strip()
if bid.isdigit():
    o, _ = run("curl -s -X PUT http://127.0.0.1:3000/api/inventory/batches/%s -H 'Content-Type: application/json' %s -d '{\"location\":\"我的工位-3F\",\"remainLevel\":\"HALF\"}'" % (bid, S))
    print("  更新:", o)
    o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);b=d['items'][0];print('  现:',b['name'],b['remainLevel'],b['location'])\"" % S)
    print(o)
cli.close()
print("\n=== DONE ===")
