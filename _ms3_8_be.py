# -*- coding: utf-8 -*-
import os, sys, json, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"; DBP = "pni38AWG4xy6wEyc"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def sql(q, t=120):
    out, _ = run("mysql -uplm -p%s plm -N -e \"%s\" 2>/dev/null" % (DBP, q), t); return out
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t)
    if o: print(o[-2000:])
    if e: print("[stderr]", e[-800:])
def pyedit(path, reps):
    b = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
    o, e = run("python3 - <<'PYEOF'\nimport base64,json\np=%r\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,('MISS '+a[:60])\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ok')\nPYEOF" % (path, b))
    print("  edit", path.split('/')[-1], o.strip(), e[-150:])

SVC = APP + "/src/instruments/instruments.service.ts"
# 1) 常量
pyedit(SVC, [
  ["export const LOTTERY_CATS = ['VACUUM_OVEN', 'FURNACE', 'POLY_HEAD', 'DMA', 'TGA'];",
   "export const LOTTERY_CATS = ['VACUUM_OVEN', 'CYCLE_OVEN', 'MUFFLE', 'TUBE', 'BET', 'POLY_HEAD', 'DMA', 'TGA'];"],
  ["export const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', FURNACE: '环化/马弗/管式/BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他' };",
   "export const CAT_LABEL: Record<string, string> = { VACUUM_OVEN: '真空烘箱', CYCLE_OVEN: '环化烘箱', MUFFLE: '马弗炉', TUBE: '管式炉', BET: 'BET', POLY_HEAD: '聚合机头', DMA: 'DMA', TGA: 'TGA', OTHER: '其他' };"],
  ["export const WEEK_CAP: Record<string, number> = { VACUUM_OVEN: 8, FURNACE: 2, POLY_HEAD: 7, DMA: 4, TGA: 4 };",
   "export const WEEK_CAP: Record<string, number> = { VACUUM_OVEN: 8, CYCLE_OVEN: 2, MUFFLE: 3, TUBE: 3, BET: 7, POLY_HEAD: 7, DMA: 4, TGA: 4 };"],
])
# 2) FUR 种子带类别
pyedit(SVC, [
  ["""const FUR: [string, boolean][] = [
  ['C442高温真空烘箱（环化大烘箱）', true],
  ['C446高温真空烘箱（环化大烘箱·新）', true],
  ['轻质楼110高温充氮烘箱', true],
  ['轻质楼110马弗炉', true],
  ['C556真空管式干燥炉', false],
  ['A425自动比表面积分析测试仪（BET）', false],
];""",
   """const FUR: [string, string, boolean][] = [
  ['C442高温真空烘箱（环化大烘箱）', 'CYCLE_OVEN', true],
  ['C446高温真空烘箱（环化大烘箱·新）', 'CYCLE_OVEN', true],
  ['轻质楼110高温充氮烘箱', 'CYCLE_OVEN', true],
  ['轻质楼110马弗炉', 'MUFFLE', true],
  ['C556真空管式干燥炉', 'TUBE', false],
  ['A425自动比表面积分析测试仪（BET）', 'BET', false],
];"""],
  ["for (const [name, pig] of FUR) rows.push({ name, category: 'FURNACE', blockType: 'FULL_DAY', piggyback: pig, lottery: true });",
   "for (const [name, c, pig] of FUR) rows.push({ name, category: c, blockType: 'FULL_DAY', piggyback: pig, lottery: true });"],
])
# 3) 引擎全天分支
pyedit(SVC, [
  ["      } else if (cat === 'FURNACE') {",
   "      } else if (cat === 'CYCLE_OVEN' || cat === 'MUFFLE' || cat === 'TUBE' || cat === 'BET') {"],
])
# 4) forecast 拆分
pyedit(SVC, [
  ["    const furn = insts.filter((i) => i.category === 'FURNACE').length;",
   "    const nCyc = insts.filter((i) => i.category === 'CYCLE_OVEN').length;\n    const nMuf = insts.filter((i) => i.category === 'MUFFLE').length;\n    const nTub = insts.filter((i) => i.category === 'TUBE').length;\n    const nBet = insts.filter((i) => i.category === 'BET').length;"],
  ["      FURNACE: prob('FURNACE', furn * 7, 'block', 0),",
   "      CYCLE_OVEN: prob('CYCLE_OVEN', nCyc * 7, 'block', 0),\n      MUFFLE: prob('MUFFLE', nMuf * 7, 'block', 0),\n      TUBE: prob('TUBE', nTub * 7, 'block', 0),\n      BET: prob('BET', nBet * 7, 'block', 0),"],
])
# 5) 重写 saveDemand（支持 0=清空、新类别、温度仅环化）
NEW_SAVE = r"""  async saveDemand(user: any, dto: any) {
    if (user.role !== 'STUDENT') throw new ForbiddenException('仅学生参与预约报名');
    const cat = dto.category;
    if (!LOTTERY_CATS.includes(cat)) throw new BadRequestException('该类别不参与抽签');
    const ck = this.cycleInfo().cycleKey;
    const cap = WEEK_CAP[cat];
    const clear = async () => {
      const ex = await this.demands.findOne({ where: { userId: user.sub, category: cat, cycleKey: ck } });
      if (ex) await this.demands.remove(ex);
      return this.myDemands(user.sub);
    };
    let film = 0, dry = 0, block = 0, temp: number | null = null, grids = 0;
    if (cat === 'VACUUM_OVEN') {
      film = Math.max(0, +dto.filmCount || 0); dry = Math.max(0, +dto.dryCount || 0); grids = film * 3 + dry;
      if (grids < 1) return clear();
      if (grids > cap) throw new BadRequestException(`真空烘箱每周上限 ${cap} 格，当前 ${grids} 格`);
    } else {
      block = Math.max(0, +dto.blockCount || 0); grids = block;
      if (block < 1) return clear();
      if (block > cap) throw new BadRequestException(`${CAT_LABEL[cat]} 每周上限 ${cap} 块`);
      if (cat === 'CYCLE_OVEN') {
        temp = dto.tempCeiling != null && dto.tempCeiling !== '' ? +dto.tempCeiling : null;
        if (temp == null || temp <= 0) throw new BadRequestException('请填写升温程序温度上限(℃)');
      }
    }
    const mode = dto.instrumentMode === 'SPECIFIC' ? 'SPECIFIC' : 'CATEGORY';
    let instrumentIds: number[] | null = null;
    if (cat === 'POLY_HEAD') {
      const auth = await this.auth.find({ where: { userId: user.sub } });
      const authIds = auth.map((a) => a.instrumentId);
      if (!authIds.length) throw new BadRequestException('你暂无授权的机头，请联系管理员');
      if (mode === 'SPECIFIC') {
        instrumentIds = (dto.instrumentIds || []).map((x: any) => +x).filter((x: number) => authIds.includes(x));
        if (!instrumentIds.length) throw new BadRequestException('请选择你被授权的机头');
      } else instrumentIds = authIds;
    } else if (mode === 'SPECIFIC') {
      const wanted = (dto.instrumentIds || []).map((x: any) => +x);
      const insts = wanted.length ? await this.inst.find({ where: { id: In(wanted) } }) : [];
      instrumentIds = insts.filter((i) => i.category === cat).map((i) => i.id);
      if (!instrumentIds.length) throw new BadRequestException('请选择该类别下的具体仪器');
      if (cat === 'VACUUM_OVEN' && film > 0 && !insts.some((i) => i.filmCapable)) throw new BadRequestException('所选烘箱均不可铺膜，请至少选一台可铺膜的');
    }
    let d = await this.demands.findOne({ where: { userId: user.sub, category: cat, cycleKey: ck } });
    if (!d) d = this.demands.create({ userId: user.sub, category: cat, cycleKey: ck });
    Object.assign(d, { instrumentMode: mode, instrumentIds, filmCount: film, dryCount: dry, blockCount: block, tempCeiling: temp, gridsTotal: grids });
    await this.demands.save(d);
    return this.myDemands(user.sub);
  }
"""
b64 = base64.b64encode(NEW_SAVE.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s'\ns=open(p,encoding='utf-8').read()\ni=s.index('  async saveDemand(user: any, dto: any) {')\nj=s.index('  async deleteDemand(user: any, id: number) {')\nnew=base64.b64decode('%s').decode('utf-8')\ns=s[:i]+new+'\\n'+s[j:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('saveDemand replaced')\nPYEOF" % (SVC, b64))
print(" ", o.strip(), e[-200:])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -8 && echo DONE" % APP, 400)

# 6) 数据迁移：仪器类别 + 历史 bookings 类别；清掉旧 FURNACE 需求/优先级
sql("UPDATE plm_instruments SET category='CYCLE_OVEN' WHERE name LIKE '%环化大烘箱%' OR name LIKE '%充氮烘箱%'")
sql("UPDATE plm_instruments SET category='MUFFLE' WHERE name LIKE '%马弗炉%'")
sql("UPDATE plm_instruments SET category='TUBE' WHERE name LIKE '%管式%'")
sql("UPDATE plm_instruments SET category='BET' WHERE name LIKE '%BET%'")
sql("UPDATE plm_bookings b JOIN plm_instruments i ON i.id=b.instrumentId SET b.category=i.category WHERE b.category='FURNACE'")
sql("DELETE FROM plm_booking_demands WHERE category='FURNACE'")
sql("DELETE FROM plm_instr_priority WHERE category='FURNACE'")
print("\n迁移后仪器类别分布:", sql("SELECT category,COUNT(*) FROM plm_instruments GROUP BY category").replace("\n", " | "))

step("重启 + 重建优先级", "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; pm2 restart plm-api >/dev/null 2>&1; sleep 4; echo restarted")
print("优先级类别:", sql("SELECT category,COUNT(*) FROM plm_instr_priority GROUP BY category").replace("\n", " | "))
step("TS错误数", "pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")

def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p)); return json.loads(o).get("token")
H = "-H 'Authorization: Bearer %s'" % login("1225071", "Plm@2026")
print("\n## forecast(含新类别)")
o, _ = run("curl -s 'http://127.0.0.1:3000/api/instruments/forecast?cycle=2026-06-15' %s" % H); print("  ", o)
print("## 报名 马弗炉 3块 / BET 5块 / 环化2块缺温度(应拦)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"MUFFLE\",\"blockCount\":3}'" % H); print("  MUFFLE:", o[:80])
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"BET\",\"blockCount\":5}'" % H); print("  BET:", o[:80])
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"CYCLE_OVEN\",\"blockCount\":2}'" % H); print("  环化缺温:", o[:120])
print("## DMA 报0块(应清空, 不报错)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking -H 'Content-Type: application/json' %s -d '{\"category\":\"DMA\",\"blockCount\":0}'" % H); print("  DMA0:", o[:80])
cli.close(); print("\n=== DONE ===")
