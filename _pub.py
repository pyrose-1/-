import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)

def step(title, cmd, t=40):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)

step("经本机回环(应正常)", "curl -s -o /dev/null -w '首页code=%{http_code}\\n' -H 'Host: lab.dhupi.cn' http://127.0.0.1/; curl -s -H 'Host: lab.dhupi.cn' http://127.0.0.1/api/health; echo")
step("经公网IP(外部视角)", "curl -s -m 10 -o /dev/null -w '首页code=%{http_code}\\n' -H 'Host: lab.dhupi.cn' http://111.229.7.15/; curl -s -m 10 -H 'Host: lab.dhupi.cn' http://111.229.7.15/api/health; echo")
step("80端口是谁在听", "ss -tlnp 2>/dev/null | grep ':80 '")
step("lab站点 error 日志尾部", "tail -n 8 /www/wwwlogs/lab.dhupi.cn.error.log 2>/dev/null || echo '(无日志)'")
cli.close()
print("\n=== DONE ===")
