import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
MIRROR = "export PRISMA_ENGINES_MIRROR=https://registry.npmmirror.com/-/binary/prisma; export PRISMA_BINARIES_MIRROR=https://registry.npmmirror.com/-/binary/prisma; "
APP = "/www/wwwroot/plm-server"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK ===")

def step(title, cmd, t=300):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out[-4000:])
    if err: print("[stderr]", err[-1500:])
    return out

step("先测后端能否连上 plm(用 mysql 客户端验证账号密码)",
     "MYSQL_PWD='pni38AWG4xy6wEyc' mysql -uplm -h127.0.0.1 -e 'SELECT 1 AS ok;' 2>&1")
step("prisma db push (完整输出, 国内引擎镜像)",
     PATHX + MIRROR + "cd %s && npx prisma db push 2>&1" % APP, 360)
step("确认 plm 表", "MYSQL_PWD='pni38AWG4xy6wEyc' mysql -uplm -h127.0.0.1 -N -e 'SHOW TABLES FROM plm;' 2>&1")
cli.close()
print("\n=== DONE ===")
