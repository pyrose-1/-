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

def run(cmd, t=240):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

def step(title, cmd, t=240):
    out, err = run(cmd, t)
    print("\n#### %s" % title)
    if out: print(out[-2500:])
    if err: print("[stderr]", err[-1000:])
    return out

def wfile(path, content):
    o, e = run("mkdir -p $(dirname %s) && cat > %s <<'FEOF'\n%s\nFEOF\necho ok" % (path, path, content))
    print("  写 %s -> %s" % (path.replace(APP, ''), o or e))

print("\n#### 写后端文件")
wfile(APP+"/src/common/jwt-auth.guard.ts", """import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';

@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(private readonly jwt: JwtService) {}
  async canActivate(ctx: ExecutionContext): Promise<boolean> {
    const req = ctx.switchToHttp().getRequest();
    const auth = (req.headers['authorization'] || '') as string;
    const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;
    if (!token) throw new UnauthorizedException('未登录');
    try { req.user = await this.jwt.verifyAsync(token); return true; }
    catch { throw new UnauthorizedException('登录已过期，请重新登录'); }
  }
}
""")
wfile(APP+"/src/common/roles.decorator.ts", """import { SetMetadata } from '@nestjs/common';
export const ROLES_KEY = 'roles';
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
""")
wfile(APP+"/src/common/roles.guard.ts", """import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ROLES_KEY } from './roles.decorator';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}
  canActivate(ctx: ExecutionContext): boolean {
    const roles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [ctx.getHandler(), ctx.getClass()]);
    if (!roles || roles.length === 0) return true;
    const req = ctx.switchToHttp().getRequest();
    if (!req.user || !roles.includes(req.user.role)) throw new ForbiddenException('无权限');
    return true;
  }
}
""")
wfile(APP+"/src/common/current-user.decorator.ts", """import { createParamDecorator, ExecutionContext } from '@nestjs/common';
export const CurrentUser = createParamDecorator((_d, ctx: ExecutionContext) => ctx.switchToHttp().getRequest().user);
""")
wfile(APP+"/src/auth/dto/login.dto.ts", """import { IsNotEmpty, IsString } from 'class-validator';
export class LoginDto {
  @IsString() @IsNotEmpty() username: string;
  @IsString() @IsNotEmpty() password: string;
}
""")
wfile(APP+"/src/auth/auth.service.ts", """import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcryptjs';
import { User } from '../entities/user.entity';

@Injectable()
export class AuthService {
  constructor(
    @InjectRepository(User) private readonly users: Repository<User>,
    private readonly jwt: JwtService,
  ) {}
  async login(username: string, password: string) {
    const user = await this.users.findOne({ where: { username } });
    if (!user || user.status !== 'ACTIVE') throw new UnauthorizedException('账号或密码错误');
    const ok = await bcrypt.compare(password, user.passwordHash);
    if (!ok) throw new UnauthorizedException('账号或密码错误');
    const token = await this.jwt.signAsync({ sub: user.id, username: user.username, role: user.role });
    return { token, user: { id: user.id, username: user.username, name: user.name, role: user.role, groupId: user.groupId } };
  }
}
""")
wfile(APP+"/src/auth/auth.controller.ts", """import { Body, Controller, Post } from '@nestjs/common';
import { AuthService } from './auth.service';
import { LoginDto } from './dto/login.dto';

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}
  @Post('login')
  login(@Body() dto: LoginDto) { return this.auth.login(dto.username, dto.password); }
}
""")
wfile(APP+"/src/auth/auth.module.ts", """import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthService } from './auth.service';
import { AuthController } from './auth.controller';
import { User } from '../entities/user.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([User]),
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: process.env.JWT_EXPIRES_IN || '7d' } }),
  ],
  controllers: [AuthController],
  providers: [AuthService],
})
export class AuthModule {}
""")
wfile(APP+"/src/users/dto/create-user.dto.ts", """import { IsIn, IsInt, IsOptional, IsString, MinLength } from 'class-validator';
export class CreateUserDto {
  @IsString() @MinLength(2) username: string;
  @IsString() @MinLength(6) password: string;
  @IsString() name: string;
  @IsOptional() @IsIn(['STUDENT', 'TUTOR', 'ADMIN']) role?: 'STUDENT' | 'TUTOR' | 'ADMIN';
  @IsOptional() @IsInt() groupId?: number;
}
""")
wfile(APP+"/src/users/users.service.ts", """import { ConflictException, Injectable, OnApplicationBootstrap } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcryptjs';
import { User } from '../entities/user.entity';
import { CreateUserDto } from './dto/create-user.dto';

@Injectable()
export class UsersService implements OnApplicationBootstrap {
  constructor(@InjectRepository(User) private readonly repo: Repository<User>) {}

  async onApplicationBootstrap() {
    const username = process.env.ADMIN_USERNAME || 'admin';
    const found = await this.repo.findOne({ where: { username } });
    if (!found) {
      const passwordHash = await bcrypt.hash(process.env.ADMIN_PASSWORD || 'admin123456', 10);
      await this.repo.save(this.repo.create({ username, name: '系统管理员', role: 'ADMIN', passwordHash, status: 'ACTIVE' }));
      console.log('[seed] admin user created:', username);
    }
  }
  safe(u: User) { return { id: u.id, username: u.username, name: u.name, role: u.role, groupId: u.groupId, status: u.status }; }
  async list() { const us = await this.repo.find({ order: { id: 'ASC' } }); return us.map((u) => this.safe(u)); }
  async me(id: number) { const u = await this.repo.findOne({ where: { id } }); return u ? this.safe(u) : null; }
  async create(dto: CreateUserDto) {
    if (await this.repo.findOne({ where: { username: dto.username } })) throw new ConflictException('用户名已存在');
    const passwordHash = await bcrypt.hash(dto.password, 10);
    const u = await this.repo.save(this.repo.create({ username: dto.username, name: dto.name, role: dto.role || 'STUDENT', groupId: dto.groupId ?? null, passwordHash, status: 'ACTIVE' }));
    return this.safe(u);
  }
}
""")
wfile(APP+"/src/users/users.controller.ts", """import { Body, Controller, Get, Post, UseGuards } from '@nestjs/common';
import { UsersService } from './users.service';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { Roles } from '../common/roles.decorator';
import { CurrentUser } from '../common/current-user.decorator';
import { CreateUserDto } from './dto/create-user.dto';

@Controller('users')
@UseGuards(JwtAuthGuard)
export class UsersController {
  constructor(private readonly users: UsersService) {}
  @Get('me') me(@CurrentUser() u: any) { return this.users.me(u.sub); }
  @Get() @UseGuards(RolesGuard) @Roles('ADMIN') list() { return this.users.list(); }
  @Post() @UseGuards(RolesGuard) @Roles('ADMIN') create(@Body() dto: CreateUserDto) { return this.users.create(dto); }
}
""")
wfile(APP+"/src/users/users.module.ts", """import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { JwtModule } from '@nestjs/jwt';
import { UsersService } from './users.service';
import { UsersController } from './users.controller';
import { JwtAuthGuard } from '../common/jwt-auth.guard';
import { RolesGuard } from '../common/roles.guard';
import { User } from '../entities/user.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([User]),
    JwtModule.register({ secret: process.env.JWT_SECRET || 'dev-secret', signOptions: { expiresIn: process.env.JWT_EXPIRES_IN || '7d' } }),
  ],
  controllers: [UsersController],
  providers: [UsersService, JwtAuthGuard, RolesGuard],
})
export class UsersModule {}
""")
wfile(APP+"/src/app.module.ts", """import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AppController } from './app.controller';
import { AuthModule } from './auth/auth.module';
import { UsersModule } from './users/users.module';
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
    AuthModule,
    UsersModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
""")

step("构建 nest build", PATHX + "cd %s && npm run build 2>&1 | tail -12 && ls dist/main.js && echo BUILD_OK" % APP, 300)
step("PM2 重启", PATHX + "pm2 restart plm-api 2>&1 | tail -3; sleep 4")
step("启动/seed 日志", PATHX + "pm2 logs plm-api --lines 30 --nostream 2>&1 | grep -iE 'seed|error|started|mapped' | tail -15")
step("自检 health", "curl -s http://127.0.0.1:3000/api/health; echo")

# 登录验证
login_out, _ = run("curl -s -X POST http://127.0.0.1:3000/api/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"%s\"}'" % ADMINPW)
print("\n#### 登录 admin\n" + login_out)
token = None
try:
    token = json.loads(login_out).get("token")
except Exception:
    pass
if token:
    print("  -> 拿到 JWT (前24位):", token[:24], "...")
    step("用 token 取 /users/me", "curl -s http://127.0.0.1:3000/api/users/me -H 'Authorization: Bearer %s'; echo" % token)
    step("用 token 取 /users 列表(admin)", "curl -s http://127.0.0.1:3000/api/users -H 'Authorization: Bearer %s'; echo" % token)
    step("无 token 访问 /users(应 401)", "curl -s -o /dev/null -w 'code=%{http_code}\\n' http://127.0.0.1:3000/api/users")
else:
    print("  [!] 登录未拿到 token，见上方输出")
cli.close()
print("\n=== DONE ===")
