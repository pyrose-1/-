# -*- coding: utf-8 -*-
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
W = "/www/wwwroot/plm-web"
SITE = "/www/wwwroot/lab.dhupi.cn"
ADMINPW = "Pniaef6b526!"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def run(cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=300):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2600:])
    if err: print("[stderr]", err[-1200:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(APP, "").replace(W, ""))

# ---------- 上传危化品目录 JSON ----------
run("mkdir -p %s/data" % APP)
sftp = cli.open_sftp()
sftp.put("hazmat_catalog.json", APP + "/data/hazmat_catalog.json")
sftp.close()
o, _ = run("wc -c %s/data/hazmat_catalog.json" % APP)
print("  上传 JSON:", o)

# ---------- 实体 ----------
wfile(APP + "/src/entities/hazmat.entity.ts", """import { Column, Entity, Index, PrimaryGeneratedColumn } from 'typeorm';

@Entity('plm_hazmat')
export class Hazmat {
  @PrimaryGeneratedColumn() id: number;
  @Index({ unique: true })
  @Column({ length: 32 }) cas: string;
  @Column({ type: 'json', nullable: true }) names: string[] | null;
  @Column({ type: 'text', nullable: true }) alias: string | null;
  @Column({ default: false }) toxic: boolean;
}
""")

# ---------- service ----------
wfile(APP + "/src/hazmat/hazmat.service.ts", """import { Injectable, OnApplicationBootstrap } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { Hazmat } from '../entities/hazmat.entity';

export function normCas(s?: string | null): string {
  if (!s) return '';
  return String(s).trim().replace(/\\s+/g, '').replace(/[\\uFF0D\\u2010-\\u2015\\u2212]/g, '-');
}

export interface HazmatResult {
  cas: string; listed: boolean; toxic: boolean; names: string[]; alias: string | null;
}

@Injectable()
export class HazmatService implements OnApplicationBootstrap {
  private map = new Map<string, Hazmat>();
  constructor(@InjectRepository(Hazmat) private repo: Repository<Hazmat>) {}

  async onApplicationBootstrap() {
    if ((await this.repo.count()) === 0) {
      const candidates = [
        join(process.cwd(), 'data', 'hazmat_catalog.json'),
        join(__dirname, '..', '..', 'data', 'hazmat_catalog.json'),
      ];
      const file = candidates.find((p) => existsSync(p));
      if (file) {
        const arr = JSON.parse(readFileSync(file, 'utf-8'));
        const rows = arr
          .map((r: any) => ({ cas: normCas(r.cas), names: r.names || [], alias: r.alias || null, toxic: !!r.toxic }))
          .filter((r: any) => r.cas);
        for (let i = 0; i < rows.length; i += 500) await this.repo.insert(rows.slice(i, i + 500));
        console.log('[seed] hazmat seeded', rows.length);
      } else {
        console.warn('[seed] hazmat_catalog.json not found');
      }
    }
    await this.refresh();
  }

  async refresh() {
    const all = await this.repo.find();
    this.map = new Map(all.map((h) => [h.cas, h]));
    console.log('[hazmat] loaded', this.map.size);
  }

  lookup(cas?: string | null): HazmatResult {
    const c = normCas(cas);
    if (!c) return { cas: '', listed: false, toxic: false, names: [], alias: null };
    const h = this.map.get(c);
    return h
      ? { cas: c, listed: true, toxic: h.toxic, names: h.names || [], alias: h.alias }
      : { cas: c, listed: false, toxic: false, names: [], alias: null };
  }
}
""")

# ---------- controller ----------
wfile(APP + "/src/hazmat/hazmat.controller.ts", """import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { HazmatService } from './hazmat.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';

@Controller('hazmat')
@UseGuards(JwtAuthGuard)
export class HazmatController {
  constructor(private readonly svc: HazmatService) {}
  @Get('lookup') lookup(@Query('cas') cas?: string) { return this.svc.lookup(cas); }
}
""")

# ---------- module ----------
wfile(APP + "/src/hazmat/hazmat.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { HazmatService } from './hazmat.service';
import { HazmatController } from './hazmat.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { Hazmat } from '../entities/hazmat.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([Hazmat]),
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: (process.env.JWT_EXPIRES_IN || '7d') as any } }),
  ],
  controllers: [HazmatController],
  providers: [HazmatService, JwtAuthGuard],
  exports: [HazmatService],
})
export class HazmatModule {}
""")

# ---------- app.module.ts 重写（加 Hazmat 实体 + HazmatModule） ----------
wfile(APP + "/src/app.module.ts", """import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { ChemicalsModule } from './chemicals/chemicals.module';
import { HazmatModule } from './hazmat/hazmat.module';
import { User } from './entities/user.entity';
import { Group } from './entities/group.entity';
import { Chemical } from './entities/chemical.entity';
import { ChemicalBatch } from './entities/chemical-batch.entity';
import { Hazmat } from './entities/hazmat.entity';

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
      entities: [User, Group, Chemical, ChemicalBatch, Hazmat],
      synchronize: true,
      charset: 'utf8mb4',
    }),
    AuthModule,
    UsersModule,
    ChemicalsModule,
    HazmatModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
""")

# ---------- chemicals.module.ts 重写（导入 HazmatModule） ----------
wfile(APP + "/src/chemicals/chemicals.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { ChemicalsService } from './chemicals.service';
import { ChemicalsController } from './chemicals.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Chemical } from '../entities/chemical.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { User } from '../entities/user.entity';
import { HazmatModule } from '../hazmat/hazmat.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([Chemical, ChemicalBatch, User]),
    HazmatModule,
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: (process.env.JWT_EXPIRES_IN || '7d') as any } }),
  ],
  controllers: [ChemicalsController],
  providers: [ChemicalsService, JwtAuthGuard, RolesGuard],
})
export class ChemicalsModule {}
""")

# ---------- 给 chemicals.service.ts 注入 HazmatService 并标注 ----------
# 1) 加 import
run("grep -q \"hazmat/hazmat.service\" %s/src/chemicals/chemicals.service.ts || "
    "sed -i \"s#import { CreateChemicalDto } from './dto/create-chemical.dto';#import { CreateChemicalDto } from './dto/create-chemical.dto';\\nimport { HazmatService } from '../hazmat/hazmat.service';#\" %s/src/chemicals/chemicals.service.ts"
    % (APP, APP))
# 2) 构造函数注入
run("grep -q 'private hazmat: HazmatService' %s/src/chemicals/chemicals.service.ts || "
    "sed -i \"s#@InjectRepository(User) private users: Repository<User>,#@InjectRepository(User) private users: Repository<User>,\\n    private hazmat: HazmatService,#\" %s/src/chemicals/chemicals.service.ts"
    % (APP, APP))
# 3) withBatches 返回里加 hazmat 标记（在 batches: 之前插入）
run("grep -q 'hazmat: this.hazmat.lookup' %s/src/chemicals/chemicals.service.ts || "
    "sed -i \"s#      ...c,#      ...c,\\n      hazmat: this.hazmat.lookup(c.cas),#\" %s/src/chemicals/chemicals.service.ts"
    % (APP, APP))
step("确认 service 注入", "grep -nE 'HazmatService|private hazmat|hazmat: this.hazmat' %s/src/chemicals/chemicals.service.ts" % APP)

# ---------- 构建后端 + 重启 ----------
step("重建后端", PATHX + "cd %s && npm run build 2>&1 | tail -6 && echo BUILD_OK; pm2 restart plm-api >/dev/null 2>&1; sleep 2; echo restarted" % APP, 400)
step("后端日志(看播种)", "pm2 logs plm-api --lines 12 --nostream 2>&1 | grep -iE 'hazmat|seed|error' | tail -12")

# ---------- 自检接口 ----------
tok, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"%s\"}'" % ADMINPW)
try:
    token = json.loads(tok).get("token")
except Exception:
    token = None
if token:
    for cas in ["68-12-2", "7664-93-9", "75-09-2", "64-17-5", "120-61-6", "107-13-1"]:
        o, _ = run("curl -s 'http://127.0.0.1:3000/api/hazmat/lookup?cas=%s' -H 'Authorization: Bearer %s'" % (cas, token))
        print("  lookup", cas, "->", o)
    o, _ = run("curl -s 'http://127.0.0.1:3000/api/chemicals?keyword=DCM' -H 'Authorization: Bearer %s' | python3 -c \"import sys,json;d=json.load(sys.stdin);print([(c['name'],c.get('hazmat')) for c in d])\"" % token)
    print("  chemicals+hazmat:", o)
cli.close()
print("\n=== DONE ===")
