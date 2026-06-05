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
def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()
def step(t, c, to=300):
    o, e = run(c, to); print("\n#### %s" % t);
    if o: print(o[-2200:])
    if e: print("[stderr]", e[-1000:])

# 在 service 末尾追加 claim + mondayOf
M = r"""
  mondayOf(dateStr: string): string {
    const d = new Date(dateStr + 'T00:00:00Z'); const wd = d.getUTCDay(); const diff = wd === 0 ? -6 : 1 - wd;
    const m = new Date(d); m.setUTCDate(d.getUTCDate() + diff); return m.toISOString().slice(0, 10);
  }

  async claim(user: any, body: any) {
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
    const ex = await this.bookings.find({ where: { instrumentId: inst.id, date } });
    for (const b of ex) if (b.startHour < eh && sh < b.endHour) throw new BadRequestException('该时段已被占用');
    const task = inst.blockType === 'FULL_DAY' ? 'FULL_DAY' : inst.blockType === 'HALF_DAY' ? 'HALF_DAY' : 'BLOCK';
    await this.bookings.insert({ cycleKey: this.mondayOf(date), instrumentId: inst.id, userId: user.sub, category: inst.category, date, startHour: sh, endHour: eh, taskType: task, tempCeiling: null, source: 'CLAIM' } as any);
    return { ok: true };
  }

  async releaseClaim(user: any, id: number) {
    const b = await this.bookings.findOne({ where: { id } });
    if (!b) throw new NotFoundException('不存在');
    if (b.userId !== user.sub) throw new ForbiddenException('只能取消自己的预约');
    if (b.source !== 'CLAIM') throw new BadRequestException('抽签结果不可在此取消');
    await this.bookings.remove(b);
    return { ok: true };
  }
"""
b = base64.b64encode(M.encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64\np='%s/src/instruments/instruments.service.ts'\ns=open(p,encoding='utf-8').read()\nm=base64.b64decode('%s').decode('utf-8')\ni=s.rstrip().rfind('}')\ns=s[:i]+m+'\\n}'+s[i+1:]\nopen(p,'w',encoding='utf-8').write(s)\nprint('claim inserted')\nPYEOF" % (APP, b))
print(" ", o.strip(), e[-200:])

# controller 加路由
reps = [["  @Post('lottery/run') @UseGuards(RolesGuard) @Roles('ADMIN') runLottery(@Body() b: any) { return this.svc.runLottery(b?.cycle); }",
         "  @Post('lottery/run') @UseGuards(RolesGuard) @Roles('ADMIN') runLottery(@Body() b: any) { return this.svc.runLottery(b?.cycle); }\n  @Post('booking/claim') claim(@CurrentUser() u: any, @Body() b: any) { return this.svc.claim(u, b); }\n  @Delete('booking/claim/:id') release(@Param('id') id: string, @CurrentUser() u: any) { return this.svc.releaseClaim(u, +id); }"]]
bb = base64.b64encode(json.dumps(reps, ensure_ascii=False).encode()).decode()
o, e = run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/instruments/instruments.controller.ts'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('ctrl ok')\nPYEOF" % (APP, bb))
print(" ", o.strip(), e[-200:])

step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -8 && echo DONE; pm2 restart plm-api >/dev/null 2>&1; sleep 3; echo restarted" % APP, 400)
step("TS错误数", "pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")

# 自检：某真空烘箱空格点击即得
def login(u, p):
    o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"%s\",\"password\":\"%s\"}'" % (u, p)); return json.loads(o).get("token")
import json as J
tj = login("tutor_jia", "Plm@2026")
# 找一个学生
sid = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT username FROM plm_users WHERE role='STUDENT' LIMIT 1\" 2>/dev/null")[0].strip()
st = login(sid, "Plm@2026"); SH = "-H 'Authorization: Bearer %s'" % st
# 取一台DMA, 在某周三个空格抢一个 (用一个无人约的周 2026-06-15 末尾时段试)
iid = run("mysql -uplm -ppni38AWG4xy6wEyc plm -N -e \"SELECT id FROM plm_instruments WHERE category='VACUUM_OVEN' AND dryCapable=1 ORDER BY id LIMIT 1\" 2>/dev/null")[0].strip()
print("\n## 学生", sid, "在真空烘箱", iid, "抢 2026-06-20 8-12")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/claim -H 'Content-Type: application/json' %s -d '{\"instrumentId\":%s,\"date\":\"2026-06-20\",\"startHour\":8,\"endHour\":12}'" % (SH, iid)); print("  ", o[:160])
print("## 再抢同一格(应冲突)")
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/claim -H 'Content-Type: application/json' %s -d '{\"instrumentId\":%s,\"date\":\"2026-06-20\",\"startHour\":8,\"endHour\":12}'" % (SH, iid)); print("  ", o[:160])
print("## 导师抢(应被拒-仅学生)")
TH = "-H 'Authorization: Bearer %s'" % tj
o, _ = run("curl -s -X POST http://127.0.0.1:3000/api/instruments/booking/claim -H 'Content-Type: application/json' %s -d '{\"instrumentId\":%s,\"date\":\"2026-06-20\",\"startHour\":12,\"endHour\":16}'" % (TH, iid)); print("  ", o[:160])
cli.close(); print("\n=== DONE ===")
