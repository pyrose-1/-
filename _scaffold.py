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
    if out: print(out[-2500:])
    if err: print("[stderr]", err[-800:])
    return out

step("创建 NestJS 项目 (nest new)", PATHX + "cd /www/wwwroot && rm -rf plm-server && npx -y @nestjs/cli@10 new plm-server --package-manager npm --skip-git 2>&1 | tail -12", 480)
step("确认项目已生成", "ls %s/package.json %s/src/main.ts 2>&1" % (APP, APP))
step("安装 Prisma/JWT/校验等依赖", PATHX + "cd %s && npm i @prisma/client @nestjs/jwt @nestjs/config bcryptjs class-validator class-transformer 2>&1 | tail -4 && npm i -D prisma @types/bcryptjs 2>&1 | tail -4" % APP, 360)

schema = """generator client {
  provider = "prisma-client-js"
}
datasource db {
  provider = "mysql"
  url      = env("DATABASE_URL")
}

enum Role { STUDENT TUTOR ADMIN }

model Group {
  id        Int      @id @default(autoincrement())
  name      String   @unique
  users     User[]
  createdAt DateTime @default(now())
  @@map("plm_groups")
}

model User {
  id           Int      @id @default(autoincrement())
  username     String   @unique
  passwordHash String
  name         String
  role         Role     @default(STUDENT)
  groupId      Int?
  group        Group?   @relation(fields: [groupId], references: [id])
  phone        String?
  email        String?
  status       String   @default("ACTIVE")
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  @@map("plm_users")
}
"""
step("写 prisma/schema.prisma", "mkdir -p %s/prisma && cat > %s/prisma/schema.prisma <<'PEOF'\n%s\nPEOF\necho ok" % (APP, APP, schema))

env = ('DATABASE_URL="mysql://plm:%s@127.0.0.1:3306/plm"\n'
       'JWT_SECRET="%s"\n'
       'JWT_EXPIRES_IN="7d"\n'
       'ADMIN_USERNAME="admin"\n'
       'ADMIN_PASSWORD="%s"\n'
       'PORT=3000\n') % (DBPW, JWT, ADMINPW)
step("写 .env", "cat > %s/.env <<'EEOF'\n%s\nEEOF\necho ok; echo '.env' >> %s/.gitignore" % (APP, env, APP))

step("Prisma 生成 + 建表(db push)", PATHX + "cd %s && npx prisma generate 2>&1 | tail -3 && npx prisma db push --skip-generate 2>&1 | tail -8" % APP, 240)
step("确认 plm 库里的表", "MYSQL_PWD='%s' mysql -uroot -N -e 'SHOW TABLES FROM plm;'" % os.environ.get("MYSQLPW", ""))
step("验证默认项目可编译 (nest build)", PATHX + "cd %s && npm run build 2>&1 | tail -6 && ls dist/main.js && echo BUILD_OK" % APP, 240)
cli.close()
print("\n=== DONE ===  ADMIN_PASSWORD =", ADMINPW)
