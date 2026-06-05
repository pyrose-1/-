import os, sys, secrets
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
DBPW = "pni38AWG4xy6wEyc"
JWT = secrets.token_hex(32)
ADMINPW = "Pni" + secrets.token_hex(4) + "!"
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===  ADMIN_PASSWORD =", ADMINPW)

def step(title, cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out[-3000:])
    if err: print("[stderr]", err[-1200:])
    return out

def wfile(path, content):
    step("写 " + path, "mkdir -p $(dirname %s); cat > %s <<'FEOF'\n%s\nFEOF\necho ok" % (path, path, content))

step("装 TypeORM + mysql2", PATHX + "cd %s && npm i @nestjs/typeorm typeorm mysql2 2>&1 | tail -3" % APP, 240)
step("清理默认文件", "cd %s && rm -f src/app.service.ts src/app.controller.spec.ts && echo ok" % APP)

wfile(APP + "/src/entities/group.entity.ts", """import { Column, CreateDateColumn, Entity, OneToMany, PrimaryGeneratedColumn } from 'typeorm';
import { User } from './user.entity';

@Entity('plm_groups')
export class Group {
  @PrimaryGeneratedColumn() id: number;
  @Column({ unique: true }) name: string;
  @OneToMany(() => User, (u) => u.group) users: User[];
  @CreateDateColumn() createdAt: Date;
}
""")

wfile(APP + "/src/entities/user.entity.ts", """import { Column, CreateDateColumn, Entity, JoinColumn, ManyToOne, PrimaryGeneratedColumn, UpdateDateColumn } from 'typeorm';
import { Group } from './group.entity';

export type Role = 'STUDENT' | 'TUTOR' | 'ADMIN';

@Entity('plm_users')
export class User {
  @PrimaryGeneratedColumn() id: number;
  @Column({ unique: true }) username: string;
  @Column() passwordHash: string;
  @Column() name: string;
  @Column({ type: 'enum', enum: ['STUDENT', 'TUTOR', 'ADMIN'], default: 'STUDENT' }) role: Role;
  @Column({ nullable: true }) groupId: number | null;
  @ManyToOne(() => Group, (g) => g.users, { nullable: true }) @JoinColumn({ name: 'groupId' }) group?: Group;
  @Column({ nullable: true }) phone: string | null;
  @Column({ nullable: true }) email: string | null;
  @Column({ default: 'ACTIVE' }) status: string;
  @CreateDateColumn() createdAt: Date;
  @UpdateDateColumn() updatedAt: Date;
}
""")

wfile(APP + "/src/app.controller.ts", """import { Controller, Get } from '@nestjs/common';
import { DataSource } from 'typeorm';

@Controller()
export class AppController {
  constructor(private readonly ds: DataSource) {}

  @Get('health')
  async health() {
    let db = 'down';
    try { await this.ds.query('SELECT 1'); db = 'up'; } catch (e) {}
    return { code: 0, service: 'plm-server', orm: 'typeorm', db, ts: new Date().toISOString() };
  }
}
""")

wfile(APP + "/src/app.module.ts", """import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { User } from './entities/user.entity';
import { Group } from './entities/group.entity';

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
      entities: [User, Group],
      synchronize: true,
      charset: 'utf8mb4',
    }),
    TypeOrmModule.forFeature([User, Group]),
  ],
  controllers: [AppController],
})
export class AppModule {}
""")

wfile(APP + "/src/main.ts", """import 'dotenv/config';
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('api');
  app.enableCors();
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
  const port = process.env.PORT ? Number(process.env.PORT) : 3000;
  await app.listen(port, '127.0.0.1');
  console.log('plm-server (NestJS+TypeORM) listening on 127.0.0.1:' + port);
}
bootstrap();
""")

env = ('DB_HOST=127.0.0.1\nDB_PORT=3306\nDB_USER=plm\nDB_PASS=%s\nDB_NAME=plm\n'
       'JWT_SECRET=%s\nJWT_EXPIRES_IN=7d\nADMIN_USERNAME=admin\nADMIN_PASSWORD=%s\nPORT=3000\n') % (DBPW, JWT, ADMINPW)
step("写 .env", "cat > %s/.env <<'EEOF'\n%s\nEEOF\necho ok" % (APP, env))

step("构建 nest build", PATHX + "cd %s && npm run build 2>&1 | tail -8 && ls dist/main.js && echo BUILD_OK" % APP, 240)
step("PM2 切到新后端", PATHX + "pm2 delete plm-api >/dev/null 2>&1; cd %s && pm2 start dist/main.js --name plm-api --cwd %s 2>&1 | tail -4; pm2 save 2>&1 | tail -1" % (APP, APP), 90)
step("启动日志", PATHX + "sleep 4; pm2 logs plm-api --lines 12 --nostream 2>&1 | tail -16")
step("自检 /api/health", "curl -s http://127.0.0.1:3000/api/health; echo")
step("确认 plm 表(synchronize 应已建表)", "MYSQL_PWD='pni38AWG4xy6wEyc' mysql -uplm -h127.0.0.1 -N -e 'SHOW TABLES FROM plm;'")
cli.close()
print("\n=== DONE ===  ADMIN_PASSWORD =", ADMINPW)
