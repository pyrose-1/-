import os, sys, json
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
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
    if out: print(out[-2400:])
    if err: print("[stderr]", err[-1200:])
    return out

def wfile(path, content):
    run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF" % (path, path, content))
    print("  写", path.replace(APP, ''))

step("装 pinyin-pro", PATHX + "cd %s && npm i pinyin-pro 2>&1 | tail -2" % APP, 180)

print("\n#### 写实体 + 模块")
wfile(APP+"/src/entities/chemical.entity.ts", """import { Column, Entity, OneToMany, PrimaryGeneratedColumn } from 'typeorm';
import { ChemicalBatch } from './chemical-batch.entity';

@Entity('plm_chemicals')
export class Chemical {
  @PrimaryGeneratedColumn() id: number;
  @Column() name: string;
  @Column({ type: 'json', nullable: true }) aliases: string[] | null;
  @Column({ default: '' }) pinyin: string;
  @Column({ default: '' }) pinyinInitials: string;
  @Column({ nullable: true }) cas: string | null;
  @Column({ nullable: true }) formula: string | null;
  @Column({ default: 'MODERATE' }) hazardLevel: string;
  @Column({ nullable: true }) storage: string | null;
  @Column({ nullable: true }) location: string | null;
  @Column({ default: 'mL' }) unit: string;
  @Column({ type: 'decimal', precision: 12, scale: 2, default: 0 }) safetyStock: string;
  @Column({ default: true }) active: boolean;
  @OneToMany(() => ChemicalBatch, (b) => b.chemical) batches: ChemicalBatch[];
}
""")
wfile(APP+"/src/entities/chemical-batch.entity.ts", """import { Column, CreateDateColumn, Entity, JoinColumn, ManyToOne, PrimaryGeneratedColumn } from 'typeorm';
import { Chemical } from './chemical.entity';

@Entity('plm_chemical_batches')
export class ChemicalBatch {
  @PrimaryGeneratedColumn() id: number;
  @Column() chemicalId: number;
  @ManyToOne(() => Chemical, (c) => c.batches) @JoinColumn({ name: 'chemicalId' }) chemical: Chemical;
  @Column({ unique: true }) batchNo: string;
  @Column({ default: 'PUBLIC' }) scope: string;
  @Column({ nullable: true }) ownerId: number | null;
  @Column({ default: false }) shareable: boolean;
  @Column({ default: 'FULL' }) remainLevel: string;
  @Column({ nullable: true }) manufacturer: string | null;
  @Column({ type: 'date', nullable: true }) expiry: string | null;
  @Column({ type: 'datetime', nullable: true }) openedAt: Date | null;
  @Column({ type: 'datetime', nullable: true }) lastUsedAt: Date | null;
  @Column({ nullable: true }) qrCodePath: string | null;
  @CreateDateColumn() receivedAt: Date;
}
""")
wfile(APP+"/src/chemicals/dto/create-chemical.dto.ts", """import { IsArray, IsIn, IsOptional, IsString, MinLength } from 'class-validator';
export class CreateChemicalDto {
  @IsString() @MinLength(1) name: string;
  @IsOptional() @IsArray() aliases?: string[];
  @IsOptional() @IsString() cas?: string;
  @IsOptional() @IsString() formula?: string;
  @IsOptional() @IsIn(['LOW', 'MODERATE', 'HIGH', 'CONTROLLED']) hazardLevel?: string;
  @IsOptional() @IsString() storage?: string;
  @IsOptional() @IsString() location?: string;
  @IsOptional() @IsString() unit?: string;
}
""")
wfile(APP+"/src/chemicals/chemicals.service.ts", """import { Injectable, NotFoundException, OnApplicationBootstrap } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { pinyin } from 'pinyin-pro';
import { Chemical } from '../entities/chemical.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { User } from '../entities/user.entity';
import { CreateChemicalDto } from './dto/create-chemical.dto';

function py(name: string) {
  try {
    return {
      pinyin: pinyin(name, { toneType: 'none', separator: '' }).toLowerCase(),
      pinyinInitials: pinyin(name, { pattern: 'first', toneType: 'none', separator: '' }).toLowerCase(),
    };
  } catch { return { pinyin: '', pinyinInitials: '' }; }
}

@Injectable()
export class ChemicalsService implements OnApplicationBootstrap {
  constructor(
    @InjectRepository(Chemical) private chem: Repository<Chemical>,
    @InjectRepository(ChemicalBatch) private batch: Repository<ChemicalBatch>,
    @InjectRepository(User) private users: Repository<User>,
  ) {}

  async onApplicationBootstrap() {
    if ((await this.chem.count()) > 0) return;
    const seed: any[] = [
      { name: 'N,N-二甲基甲酰胺', aliases: ['DMF'], cas: '68-12-2', formula: 'C3H7NO', hazardLevel: 'MODERATE', unit: 'mL', location: 'A柜-2层', safetyStock: 500, batches: [{ level: 'FULL', scope: 'PUBLIC' }, { level: 'ALMOST_FULL', scope: 'PERSONAL', owner: 1, shareable: true }] },
      { name: 'N-甲基吡咯烷酮', aliases: ['NMP'], cas: '872-50-4', hazardLevel: 'MODERATE', unit: 'mL', location: 'A柜-2层', safetyStock: 500, batches: [{ level: 'HALF', scope: 'PUBLIC' }] },
      { name: 'N,N-二甲基乙酰胺', aliases: ['DMAc'], cas: '127-19-5', hazardLevel: 'MODERATE', unit: 'mL', location: 'A柜-2层', safetyStock: 300, batches: [{ level: 'FULL', scope: 'PUBLIC' }] },
      { name: '四氢呋喃', aliases: ['THF'], cas: '109-99-9', hazardLevel: 'HIGH', unit: 'mL', location: 'B柜-1层', safetyStock: 500, batches: [{ level: 'LOW', scope: 'PUBLIC' }] },
      { name: '二氯甲烷', aliases: ['DCM'], cas: '75-09-2', hazardLevel: 'MODERATE', unit: 'mL', location: 'B柜-1层', safetyStock: 500, batches: [{ level: 'FULL', scope: 'PUBLIC' }] },
      { name: '均苯四甲酸二酐', aliases: ['PMDA'], cas: '89-32-7', hazardLevel: 'MODERATE', unit: 'g', location: '干燥柜', safetyStock: 100, batches: [{ level: 'ALMOST_FULL', scope: 'PUBLIC' }] },
      { name: \"4,4'-二氨基二苯醚\", aliases: ['ODA'], cas: '101-80-4', hazardLevel: 'MODERATE', unit: 'g', location: '干燥柜', safetyStock: 100, batches: [{ level: 'HALF', scope: 'PUBLIC' }] },
      { name: '浓硫酸', aliases: [], cas: '7664-93-9', hazardLevel: 'HIGH', unit: 'mL', location: '酸柜', safetyStock: 500, batches: [{ level: 'FULL', scope: 'PUBLIC' }] },
      { name: '三乙胺', aliases: ['TEA'], cas: '121-44-8', hazardLevel: 'MODERATE', unit: 'mL', location: 'B柜-2层', safetyStock: 100, batches: [{ level: 'LITTLE', scope: 'PUBLIC' }] },
      { name: '无水乙醇', aliases: ['乙醇', 'EtOH'], cas: '64-17-5', hazardLevel: 'LOW', unit: 'mL', location: 'B柜-3层', safetyStock: 1000, batches: [{ level: 'FULL', scope: 'PUBLIC' }] },
    ];
    let n = 1;
    const d = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    for (const s of seed) {
      const p = py(s.name);
      const c = await this.chem.save(this.chem.create({
        name: s.name, aliases: s.aliases, cas: s.cas, formula: s.formula || null,
        hazardLevel: s.hazardLevel, unit: s.unit, location: s.location, safetyStock: s.safetyStock,
        pinyin: p.pinyin, pinyinInitials: p.pinyinInitials,
      } as any));
      for (const b of s.batches) {
        await this.batch.save(this.batch.create({
          chemicalId: c.id, batchNo: 'B' + d + '-' + String(n++).padStart(3, '0'),
          scope: b.scope, ownerId: b.owner ?? null, shareable: !!b.shareable, remainLevel: b.level,
        } as any));
      }
    }
    console.log('[seed] chemicals seeded');
  }

  private async withBatches(chems: Chemical[]) {
    const ids = chems.map((c) => c.id);
    const batches = ids.length ? await this.batch.find({ where: { chemicalId: In(ids) } }) : [];
    const ownerIds = [...new Set(batches.filter((b) => b.ownerId).map((b) => b.ownerId as number))];
    const owners = ownerIds.length ? await this.users.find({ where: { id: In(ownerIds) } }) : [];
    const om = new Map(owners.map((u) => [u.id, u.name]));
    return chems.map((c) => ({
      ...c,
      batches: batches.filter((b) => b.chemicalId === c.id).map((b) => ({
        id: b.id, batchNo: b.batchNo, scope: b.scope, ownerId: b.ownerId,
        ownerName: b.ownerId ? (om.get(b.ownerId) || '?') : null,
        shareable: b.shareable, remainLevel: b.remainLevel, expiry: b.expiry,
      })),
    }));
  }

  async list(keyword?: string, hazard?: string) {
    let chems = await this.chem.find({ where: { active: true }, order: { name: 'ASC' } });
    if (keyword) {
      const k = keyword.trim().toLowerCase();
      chems = chems.filter((c) =>
        c.name.toLowerCase().includes(k) ||
        (c.cas || '').toLowerCase().includes(k) ||
        (c.pinyin || '').includes(k) ||
        (c.pinyinInitials || '').includes(k) ||
        (c.aliases || []).some((a) => a.toLowerCase().includes(k)),
      );
    }
    if (hazard) chems = chems.filter((c) => c.hazardLevel === hazard);
    return this.withBatches(chems);
  }

  async get(id: number) {
    const c = await this.chem.findOne({ where: { id } });
    if (!c) throw new NotFoundException('药品不存在');
    return (await this.withBatches([c]))[0];
  }

  async create(dto: CreateChemicalDto) {
    const p = py(dto.name);
    return this.chem.save(this.chem.create({ ...dto, ...p } as any));
  }
  async update(id: number, dto: any) {
    await this.chem.update(id, dto);
    return this.get(id);
  }
}
""")
wfile(APP+"/src/chemicals/chemicals.controller.ts", """import { Body, Controller, Get, Param, Post, Put, Query, UseGuards } from '@nestjs/common';
import { ChemicalsService } from './chemicals.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Roles } from '../common/roles.decorator';
import { CreateChemicalDto } from './dto/create-chemical.dto';

@Controller('chemicals')
@UseGuards(JwtAuthGuard)
export class ChemicalsController {
  constructor(private readonly svc: ChemicalsService) {}
  @Get() list(@Query('keyword') k?: string, @Query('hazard') h?: string) { return this.svc.list(k, h); }
  @Get(':id') get(@Param('id') id: string) { return this.svc.get(+id); }
  @Post() @UseGuards(RolesGuard) @Roles('ADMIN') create(@Body() dto: CreateChemicalDto) { return this.svc.create(dto); }
  @Put(':id') @UseGuards(RolesGuard) @Roles('ADMIN') update(@Param('id') id: string, @Body() dto: any) { return this.svc.update(+id, dto); }
}
""")
wfile(APP+"/src/chemicals/chemicals.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { ChemicalsService } from './chemicals.service';
import { ChemicalsController } from './chemicals.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Chemical } from '../entities/chemical.entity';
import { ChemicalBatch } from '../entities/chemical-batch.entity';
import { User } from '../entities/user.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([Chemical, ChemicalBatch, User]),
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: (process.env.JWT_EXPIRES_IN || '7d') as any } }),
  ],
  controllers: [ChemicalsController],
  providers: [ChemicalsService, JwtAuthGuard, RolesGuard],
})
export class ChemicalsModule {}
""")
wfile(APP+"/src/app.module.ts", """import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
import { ChemicalsModule } from './chemicals/chemicals.module';
import { User } from './entities/user.entity';
import { Group } from './entities/group.entity';
import { Chemical } from './entities/chemical.entity';
import { ChemicalBatch } from './entities/chemical-batch.entity';

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
      entities: [User, Group, Chemical, ChemicalBatch],
      synchronize: true,
      charset: 'utf8mb4',
    }),
    AuthModule,
    UsersModule,
    ChemicalsModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
""")

step("构建", PATHX + "cd %s && npm run build 2>&1 | tail -12 && ls dist/main.js && echo BUILD_OK" % APP, 300)
step("重启 + seed", PATHX + "pm2 restart plm-api 2>&1 | tail -2; sleep 4; pm2 logs plm-api --lines 30 --nostream 2>&1 | grep -iE 'seed|error|Mapped .*chemical|started' | tail -12")

tok, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"%s\"}'" % ADMINPW)
try:
    token = json.loads(tok).get("token")
except Exception:
    token = None
if token:
    step("药品总数 + 前2条", "curl -s 'http://127.0.0.1:3000/api/chemicals' -H 'Authorization: Bearer %s' | python3 -c \"import sys,json; d=json.load(sys.stdin); print('总数=',len(d)); [print(c['name'],'| CAS',c.get('cas'),'| 批次',len(c['batches']),'|', [b['remainLevel']+('(可借)' if b['shareable'] else '')+('@'+str(b['ownerName']) if b['ownerName'] else '') for b in c['batches']]) for c in d[:2]]\"" % token)
    step("搜索 dmf", "curl -s 'http://127.0.0.1:3000/api/chemicals?keyword=dmf' -H 'Authorization: Bearer %s' | python3 -c \"import sys,json; d=json.load(sys.stdin); print([c['name'] for c in d])\"" % token)
    step("搜索拼音 ejj", "curl -s 'http://127.0.0.1:3000/api/chemicals?keyword=njb' -H 'Authorization: Bearer %s' | python3 -c \"import sys,json; d=json.load(sys.stdin); print([c['name'] for c in d])\"" % token)
else:
    print("登录失败:", tok[:200])
cli.close()
print("\n=== DONE ===")
