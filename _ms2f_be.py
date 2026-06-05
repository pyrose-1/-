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
    b = base64.b64encode(json.dumps(replaces, ensure_ascii=False).encode()).decode()
    out, err = run("python3 - <<'PYEOF'\n"
        "import base64,json\n"
        "p=%r\n"
        "reps=json.loads(base64.b64decode('%s').decode('utf-8'))\n"
        "s=open(p,encoding='utf-8').read()\n"
        "for a,b in reps:\n"
        "    assert a in s, ('MISS: '+a[:60])\n"
        "    s=s.replace(a,b)\n"
        "open(p,'w',encoding='utf-8').write(s)\n"
        "print('edited %%d'%%len(reps))\n"
        "PYEOF" % (path, b))
    print("  edit", path.replace(APP, ""), out.strip(), err[-200:])

# ---------- 1) ChemicalBatch 加 sharedById ----------
pyedit(APP + "/src/entities/chemical-batch.entity.ts", [
  ["  @Column({ nullable: true }) location: string | null;",
   "  @Column({ nullable: true }) location: string | null;\n  @Column({ type: 'int', nullable: true }) sharedById: number | null;"],
])

# ---------- 2) UsersService 播种 公用药品维护 ----------
pyedit(APP + "/src/users/users.service.ts", [
  ["""    for (const s of students) {
      if (!(await this.repo.findOne({ where: { username: s.username } }))) {
        await this.repo.save(this.repo.create({ username: s.username, name: s.name, role: 'STUDENT', tutorId: tutorId[s.tutor], passwordHash: hash, status: 'ACTIVE' }));
        console.log('[seed] student', s.username);
      }
    }""",
   """    for (const s of students) {
      if (!(await this.repo.findOne({ where: { username: s.username } }))) {
        await this.repo.save(this.repo.create({ username: s.username, name: s.name, role: 'STUDENT', tutorId: tutorId[s.tutor], passwordHash: hash, status: 'ACTIVE' }));
        console.log('[seed] student', s.username);
      }
    }
    // 公用药品维护账号
    if (!(await this.repo.findOne({ where: { username: 'public_steward' } }))) {
      await this.repo.save(this.repo.create({ username: 'public_steward', name: '公用药品维护', role: 'ADMIN', passwordHash: hash, status: 'ACTIVE' }));
      console.log('[seed] public_steward created');
    }"""],
])

# ---------- 3) PurchasesModule 加 BorrowRequest ----------
pyedit(APP + "/src/purchases/purchases.module.ts", [
  ["import { User } from '../entities/user.entity';",
   "import { User } from '../entities/user.entity';\nimport { BorrowRequest } from '../entities/borrow-request.entity';"],
  ["TypeOrmModule.forFeature([PurchaseRequest, Chemical, ChemicalBatch, User]),",
   "TypeOrmModule.forFeature([PurchaseRequest, Chemical, ChemicalBatch, User, BorrowRequest]),"],
])

# ---------- 4) PurchasesService：注入 borrows，重写 holdings，加 shareBatch ----------
pyedit(APP + "/src/purchases/purchases.service.ts", [
  ["import { CreatePurchaseDto } from './dto/create-purchase.dto';",
   "import { CreatePurchaseDto } from './dto/create-purchase.dto';\nimport { BorrowRequest } from '../entities/borrow-request.entity';"],
  ["""    @InjectRepository(User) private users: Repository<User>,
    private hazmat: HazmatService,""",
   """    @InjectRepository(User) private users: Repository<User>,
    @InjectRepository(BorrowRequest) private borrows: Repository<BorrowRequest>,
    private hazmat: HazmatService,"""],
])

# 替换整个 holdings 方法
NEW_HOLDINGS = r"""  async holdings(userId: number) {
    // 我"申请并通过"的采购（金额永远算最初申请人）
    const myReqs = await this.reqs.find({ where: { applicantId: userId, status: 'APPROVED' }, order: { createdAt: 'DESC' } });
    const aBatchIds = myReqs.map((r) => r.batchId).filter(Boolean) as number[];
    const owned = await this.batch.find({ where: { ownerId: userId } });
    const bExtra = owned.filter((b) => !aBatchIds.includes(b.id)); // 我当前持有但非我采购（受让/公用维护）
    const allIds = [...new Set([...aBatchIds, ...bExtra.map((b) => b.id)])];
    const batches = allIds.length ? await this.batch.find({ where: { id: In(allIds) } }) : [];
    const bm = new Map(batches.map((b) => [b.id, b]));
    const chemIds = [...new Set(batches.map((b) => b.chemicalId))];
    const chems = chemIds.length ? await this.chem.find({ where: { id: In(chemIds) } }) : [];
    const cm = new Map(chems.map((c) => [c.id, c]));
    const borrows = allIds.length ? await this.borrows.find({ where: { batchId: In(allIds) } }) : [];
    const lentBy = new Map<number, number>();
    for (const br of borrows.sort((a, b) => a.id - b.id)) if (br.status === 'LENT') lentBy.set(br.batchId, br.borrowerId);
    const uids = new Set<number>();
    batches.forEach((b) => { if (b.ownerId) uids.add(b.ownerId); if (b.sharedById) uids.add(b.sharedById); });
    lentBy.forEach((v) => uids.add(v));
    const us = uids.size ? await this.users.find({ where: { id: In([...uids]) } }) : [];
    const um = new Map(us.map((u) => [u.id, u.name]));

    const build = (b: any, c: any, src: any, ownPrice: boolean) => {
      let dispState = 'HELD', dispText = '在库自用';
      if (!b) { dispState = 'NONE'; dispText = '—'; }
      else if (b.ownerId !== userId) { dispState = 'TRANSFERRED'; dispText = '已转让给 ' + (um.get(b.ownerId) || '?'); }
      else if (b.scope === 'PUBLIC' && b.sharedById === userId) { dispState = 'SHARED'; dispText = '已共享(公用)'; }
      else if (lentBy.get(b.id)) { dispState = 'LENT'; dispText = '已借出给 ' + (um.get(lentBy.get(b.id) as number) || '?'); }
      return {
        batchId: b?.id ?? null, batchNo: b?.batchNo ?? null,
        remainLevel: b?.remainLevel ?? null, location: b?.location ?? null,
        shareable: b?.shareable ?? false, scope: b?.scope ?? null,
        sharedBy: b?.sharedById ? (um.get(b.sharedById) || null) : null,
        chemicalId: b?.chemicalId ?? null, name: c?.name || src.name || '?', cas: c?.cas || src.cas || null,
        hazmat: this.hazmat.lookup(c?.cas || src.cas),
        price: src.price || null, productNo: src.productNo || null, quantity: src.quantity || null,
        unit: src.unit || c?.unit || null, purchaseDate: src.purchaseDate || null,
        ownPrice, editable: !!b && b.ownerId === userId, dispState, dispText, received: !!src.received,
      };
    };

    let totalAmount = 0;
    const items: any[] = [];
    for (const r of myReqs) {
      if (r.price) totalAmount += parseFloat(r.price) || 0;
      const b = r.batchId ? bm.get(r.batchId) : undefined;
      items.push(build(b, b ? cm.get(b.chemicalId) : undefined, { name: r.name, cas: r.cas, price: r.price, productNo: r.productNo, quantity: r.quantity, unit: r.unit, purchaseDate: r.stockedAt || r.submittedAt }, true));
    }
    for (const b of bExtra) {
      items.push(build(b, cm.get(b.chemicalId), { purchaseDate: b.receivedAt, received: true }, false));
    }
    return { totalAmount: Math.round(totalAmount * 100) / 100, count: items.length, items };
  }

  async shareBatch(user: any, batchId: number, body: { remainLevel?: string; location?: string }) {
    const b = await this.batch.findOne({ where: { id: batchId } });
    if (!b) throw new NotFoundException('批次不存在');
    if (b.ownerId !== user.sub && user.role !== 'ADMIN') throw new ForbiddenException('只能共享自己持有的药品');
    const LEVELS = ['FULL', 'ALMOST_FULL', 'HALF', 'LOW', 'LITTLE', 'EMPTY'];
    if (body.remainLevel && LEVELS.includes(body.remainLevel)) b.remainLevel = body.remainLevel;
    if (body.location !== undefined) b.location = body.location || null;
    b.scope = 'PUBLIC'; b.shareable = true; b.sharedById = user.sub;
    await this.batch.save(b);
    return { ok: true };
  }"""

# 用 python 把旧 holdings 整段换掉
old_marker_start = "  async holdings(userId: number) {"
old_marker_end = "  async updateMyBatch"
b64h = base64.b64encode(NEW_HOLDINGS.encode()).decode()
out, err = run("python3 - <<'PYEOF'\n"
    "import base64\n"
    "p='%s/src/purchases/purchases.service.ts'\n"
    "s=open(p,encoding='utf-8').read()\n"
    "i=s.index('  async holdings(userId: number) {')\n"
    "j=s.index('  async updateMyBatch')\n"
    "new=base64.b64decode('%s').decode('utf-8')\n"
    "s=s[:i]+new+'\\n\\n'+s[j:]\n"
    "open(p,'w',encoding='utf-8').write(s)\n"
    "print('holdings replaced')\n"
    "PYEOF" % (APP, b64h))
print("  ", out.strip(), err[-300:])

# ---------- 5) precheck 加 sharedBy ----------
pyedit(APP + "/src/purchases/purchases.service.ts", [
  ["""        batchId: b.id, scope: b.scope, ownerId: b.ownerId, ownerName: b.ownerId ? om.get(b.ownerId) || '?' : null,""",
   """        batchId: b.id, scope: b.scope, ownerId: b.ownerId, ownerName: b.ownerId ? om.get(b.ownerId) || '?' : null,
        sharedBy: b.sharedById ? (om.get(b.sharedById) || '?') : null,"""],
])

# ---------- 6) InventoryController 加 share ----------
pyedit(APP + "/src/purchases/inventory.controller.ts", [
  ["import { Body, Controller, Get, Param, Put, UseGuards } from '@nestjs/common';",
   "import { Body, Controller, Get, Param, Post, Put, UseGuards } from '@nestjs/common';"],
  ["  @Put('batches/:id') update(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.updateMyBatch(u, +id, b); }",
   "  @Put('batches/:id') update(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.updateMyBatch(u, +id, b); }\n  @Post('batches/:id/share') share(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.shareBatch(u, +id, b); }"],
])

# ---------- 7) chemicals.service withBatches 加 sharedBy ----------
pyedit(APP + "/src/chemicals/chemicals.service.ts", [
  ["    const ownerIds = [...new Set(batches.filter((b) => b.ownerId).map((b) => b.ownerId as number))];",
   "    const ownerIds = [...new Set(batches.flatMap((b) => [b.ownerId, b.sharedById]).filter(Boolean) as number[])];"],
  ["""        shareable: b.shareable, remainLevel: b.remainLevel, expiry: b.expiry,
      })),""",
   """        shareable: b.shareable, remainLevel: b.remainLevel, expiry: b.expiry,
        sharedById: b.sharedById || null, sharedBy: b.sharedById ? (om.get(b.sharedById) || '?') : null,
      })),"""],
])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -12 && echo BUILD_DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数 / 播种", "pm2 logs plm-api --lines 40 --nostream 2>&1 | grep -ciE 'error TS'; pm2 logs plm-api --lines 60 --nostream 2>&1 | grep -iE 'steward|error TS' | tail -5")

# 公用批次归 公用药品维护 + 全部可借出
step("公用批次关联 steward 且可借", "mysql -uplm -ppni38AWG4xy6wEyc plm -e \"UPDATE plm_chemical_batches b JOIN plm_users u ON u.username='public_steward' SET b.ownerId=u.id, b.shareable=1 WHERE b.scope='PUBLIC' AND b.sharedById IS NULL;\" 2>/dev/null; mysql -uplm -ppni38AWG4xy6wEyc plm -e \"SELECT id,chemicalId,scope,ownerId,shareable FROM plm_chemical_batches WHERE scope='PUBLIC' LIMIT 6;\" 2>/dev/null")

# ---------- 自检 ----------
def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o)
xm = login("stu_xm", "Plm@2026"); SM = "-H 'Authorization: Bearer %s'" % xm["token"]
print("\n## 小明 我的药品（金额应=自己采购合计, 含处置标签）")
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('总额',d['totalAmount'],'件',d['count']);[print(' ',i['name'],i['dispText'],'可借' if i['shareable'] else '不可借','editable' if i['editable'] else 'ro','¥'+str(i['price'])) for i in d['items']]\"" % SM)
print(o)
bid, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print([i['batchId'] for i in d['items'] if i['editable']][0])\"" % SM)
bid = bid.strip()
print("## 小明把 batch %s 共享为公用(满,B柜)" % bid)
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/inventory/batches/%s/share -H 'Content-Type: application/json' %s -d '{\"remainLevel\":\"FULL\",\"location\":\"公共试剂架\"}'" % (bid, SM))
print("  ", o)
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);b=[i for i in d['items'] if i['batchId']==%s][0];print('  小明该药状态:',b['dispText'],b['scope'])\"" % (SM, bid))
print(o)
print("## 药品库该药应显示 公开自小明")
adm = login("admin", "Pniaef6b526!"); AD = "-H 'Authorization: Bearer %s'" % adm["token"]
o, _ = run("curl -s 'http://127.0.0.1:3000/api/chemicals?keyword=' %s | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(c['name'],[(b['scope'],b.get('sharedBy'),b['remainLevel']) for b in c['batches']]) for c in d if any(b.get('sharedBy') for b in c['batches'])]\"" % AD)
print(o)
print("## 公用药品维护 我的药品(应能看到公用批次)")
ps = login("public_steward", "Plm@2026"); PS = "-H 'Authorization: Bearer %s'" % ps["token"]
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print('件',d['count'],'总额',d['totalAmount']);[print(' ',i['name'],i['dispText']) for i in d['items'][:6]]\"" % PS)
print(o)
cli.close()
print("\n=== DONE ===")
