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

# ---------- borrow.service 重写：公用免审批 + 前两借用人 + 借用完毕 ----------
wfile(APP + "/src/borrow/borrow.service.ts", r"""import { BadRequestException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { BorrowRequest } from '../entities/borrow-request.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { Chemical } from '../entities/chemical.entity';
import { User } from '../entities/user.entity';

const levelText: Record<string, string> = { FULL: '满', ALMOST_FULL: '几乎满', HALF: '半瓶', LOW: '快没了', LITTLE: '一点点', EMPTY: '空' };
const statusText: Record<string, string> = { PENDING: '待处理', REJECTED: '已拒绝', LENT: '已同意借用', TRANSFERRED: '已转让', CANCELLED: '已取消', USING: '借用中', DONE: '已完成' };
const LEVELS = ['FULL', 'ALMOST_FULL', 'HALF', 'LOW', 'LITTLE', 'EMPTY'];

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
    if (!b.ownerId) throw new BadRequestException('该药品无持有人');
    const dup = await this.reqs.findOne({ where: { batchId, borrowerId, status: In(['PENDING', 'USING']) } });
    if (dup) throw new BadRequestException('你已有进行中的该药品借用记录');
    // 公用药品：免审批，直接进入借用中
    const isPublic = b.scope === 'PUBLIC';
    const r = this.reqs.create({ batchId, chemicalId: b.chemicalId, ownerId: b.ownerId, borrowerId, note: note || null, status: isPublic ? 'USING' : 'PENDING' } as any);
    return this.reqs.save(r);
  }

  private async decorate(rows: BorrowRequest[]) {
    const bids = [...new Set(rows.map((r) => r.batchId))];
    const cids = [...new Set(rows.map((r) => r.chemicalId))];
    // 同批次的全部借用记录（用于"前两个借用人"）
    const related = bids.length ? await this.reqs.find({ where: { batchId: In(bids) } }) : [];
    const uids = [...new Set([...rows.flatMap((r) => [r.ownerId, r.borrowerId]), ...related.map((x) => x.borrowerId)])];
    const us = uids.length ? await this.users.find({ where: { id: In(uids) } }) : [];
    const cs = cids.length ? await this.chem.find({ where: { id: In(cids) } }) : [];
    const bs = bids.length ? await this.batch.find({ where: { id: In(bids) } }) : [];
    const um = new Map(us.map((u) => [u.id, u.name]));
    const cm = new Map(cs.map((c) => [c.id, c]));
    const bm = new Map(bs.map((b) => [b.id, b]));
    return rows.map((r) => {
      const c = cm.get(r.chemicalId); const b = bm.get(r.batchId);
      // 前两个借用人：同批次、非本人、按时间倒序去重取2
      const prev: string[] = [];
      const seen = new Set<number>([r.borrowerId]);
      for (const x of related.filter((x) => x.batchId === r.batchId && x.id !== r.id).sort((a, b2) => b2.id - a.id)) {
        if (seen.has(x.borrowerId)) continue;
        seen.add(x.borrowerId); prev.push(um.get(x.borrowerId) || '?');
        if (prev.length >= 2) break;
      }
      return {
        ...r, statusText: statusText[r.status] || r.status,
        ownerName: um.get(r.ownerId) || '?', borrowerName: um.get(r.borrowerId) || '?',
        chemicalName: c?.name || '?', cas: c?.cas || null,
        scope: b?.scope || null, remainLevel: b?.remainLevel || null, remainText: b ? levelText[b.remainLevel] || b.remainLevel : null,
        location: b?.location || null, prevBorrowers: prev,
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

  // 借用完毕：更新余量/位置；若全部领用则划归个人
  async finish(id: number, user: any, body: { remainLevel?: string; location?: string; fullyTaken?: boolean }) {
    const r = await this.reqs.findOne({ where: { id } });
    if (!r) throw new NotFoundException('借用记录不存在');
    if (r.borrowerId !== user.sub) throw new ForbiddenException('只能由借用人登记完毕');
    if (r.status !== 'USING') throw new BadRequestException('该记录不是借用中状态');
    const b = await this.batch.findOne({ where: { id: r.batchId } });
    if (!b) throw new NotFoundException('药品批次不存在');
    if (body.location !== undefined) b.location = body.location || null;
    if (body.fullyTaken) {
      // 全部领用 → 划归借用人个人药品
      b.scope = 'PERSONAL'; b.ownerId = r.borrowerId; b.sharedById = null; b.shareable = true;
      b.remainLevel = body.remainLevel && LEVELS.includes(body.remainLevel) ? body.remainLevel : 'FULL';
      r.decisionNote = '全部领用，已划归个人';
    } else {
      if (body.remainLevel && LEVELS.includes(body.remainLevel)) b.remainLevel = body.remainLevel;
      r.decisionNote = '部分取用，已更新余量/位置';
    }
    await this.batch.save(b);
    r.status = 'DONE'; r.decidedAt = new Date();
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

# ---------- controller 加 finish ----------
pyrep = [
  ["  @Post(':id/transfer') transfer(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.decide(+id, u, 'TRANSFER', b?.note); }",
   "  @Post(':id/transfer') transfer(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.decide(+id, u, 'TRANSFER', b?.note); }\n  @Post(':id/finish') finish(@Param('id') id: string, @CurrentUser() u: any, @Body() b: any) { return this.svc.finish(+id, u, b || {}); }"],
]
import base64
b = base64.b64encode(json.dumps(pyrep, ensure_ascii=False).encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/borrow/borrow.controller.ts'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (APP, b))
print("  controller:", o.strip(), e[-200:])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -8 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 30 --nostream 2>&1 | grep -ciE 'error TS'")

# ---------- 自检：小红借用公用药品(免审批USING) -> 借用完毕(部分) ; 再全部领用划归个人 ----------
def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p))
    return json.loads(o)
xh = login("stu_xh", "Plm@2026"); XH = "-H 'Authorization: Bearer %s'" % xh["token"]
# 找一个公用批次id（DMF chem1 public batch1）
print("\n## 小红借用公用药品 batch1（应直接 USING）")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/borrow -H 'Content-Type: application/json' %s -d '{\"batchId\":1}'" % XH)
print("  ", o[:200])
rid, _ = run("curl -s http://127.0.0.1:3000/api/borrow/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);print([r['id'] for r in d if r['status']=='USING'][0])\"" % XH)
rid = rid.strip()
print("## 小红 我的借用（看 余量/位置/前两借用人/状态）")
o, _ = run("curl -s http://127.0.0.1:3000/api/borrow/mine %s | python3 -c \"import sys,json;[print(r['chemicalName'],r['statusText'],'余'+str(r['remainText']),'位'+str(r['location']),'前两借用人',r['prevBorrowers']) for r in json.load(sys.stdin)]\"" % XH)
print(o)
print("## 借用完毕（部分取用：余量改半瓶，位置B柜）")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/borrow/%s/finish -H 'Content-Type: application/json' %s -d '{\"remainLevel\":\"HALF\",\"location\":\"B柜-2层\",\"fullyTaken\":false}'" % (rid, XH))
print("  ", o[:200])
# 全部领用演示：小刚借另一个公用批次然后全部领用
xg = login("stu_xg", "Plm@2026"); XG = "-H 'Authorization: Bearer %s'" % xg["token"]
run("curl -s -X POST http://127.0.0.1:3000/api/borrow -H 'Content-Type: application/json' %s -d '{\"batchId\":4}'" % XG)
rid2, _ = run("curl -s http://127.0.0.1:3000/api/borrow/mine %s | python3 -c \"import sys,json;print([r['id'] for r in json.load(sys.stdin) if r['status']=='USING'][0])\"" % XG)
rid2 = rid2.strip()
print("## 小刚 batch4 借用完毕（全部领用→划归个人）")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/borrow/%s/finish -H 'Content-Type: application/json' %s -d '{\"remainLevel\":\"ALMOST_FULL\",\"location\":\"小刚工位\",\"fullyTaken\":true}'" % (rid2, XG))
print("  ", o[:200])
print("## 验证 batch4 是否变为小刚个人药品")
o, _ = run("mysql -uplm -ppni38AWG4xy6wEyc plm -e \"SELECT id,chemicalId,scope,ownerId,remainLevel,location FROM plm_chemical_batches WHERE id=4;\" 2>/dev/null")
print(o)
o, _ = run("curl -s http://127.0.0.1:3000/api/inventory/mine %s | python3 -c \"import sys,json;d=json.load(sys.stdin);[print(' 小刚持有:',i['name'],i['dispText']) for i in d['items'] if i['batchId']==4]\"" % XG)
print(o)
cli.close()
print("\n=== DONE ===")
