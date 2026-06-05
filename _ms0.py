import os, sys, subprocess
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    import paramiko
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "paramiko"], check=True)
    import paramiko

HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    cli.connect(HOST, port=22, username=USER, password=PWD, timeout=12,
                banner_timeout=12, auth_timeout=12, look_for_keys=False, allow_agent=False)
    print("=== SSH LOGIN_OK as root ===")
except paramiko.AuthenticationException:
    print("=== AUTH_FAILED for root（密码不对或禁止 root 密码登录）==="); sys.exit(0)
except Exception as e:
    print("=== ERROR:", type(e).__name__, e, "==="); sys.exit(0)

def run(cmd, t=40):
    i, o, e = cli.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "replace").rstrip(), e.read().decode("utf-8", "replace").rstrip()

steps = [
 ("系统 / 资源", "echo OS: $(grep PRETTY /etc/os-release | cut -d= -f2); echo KERNEL: $(uname -r); echo UPTIME: $(uptime -p); echo CPU核: $(nproc); echo; free -h; echo; df -h / 2>/dev/null"),
 ("监听端口(含进程)", "ss -tlnp 2>/dev/null | awk 'NR==1 || /LISTEN/' | head -40"),
 ("已装运行环境", "for c in node npm git mysql redis-server pm2 docker nginx openresty; do printf '%-12s ' $c; (command -v $c >/dev/null 2>&1 && $c --version 2>&1 | head -1) || echo '(未装)'; done"),
 ("面板检测", "printf '1panel: '; (command -v 1pctl >/dev/null 2>&1 && systemctl is-active 1panel 2>/dev/null) || echo no; printf 'bt(宝塔): '; (command -v bt >/dev/null 2>&1 && echo yes) || echo no; ls -d /opt/1panel 2>/dev/null; ls -d /www/server/panel 2>/dev/null"),
 ("1Panel 状态 / 入口", "systemctl status 1panel --no-pager 2>/dev/null | head -8; echo '--- user-info ---'; 1pctl user-info 2>/dev/null"),
 ("Docker 容器", "docker ps -a --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}' 2>/dev/null | head -25"),
 ("80 端口在跑啥", "ss -tlnp 2>/dev/null | grep -E ':80\\s' ; echo '--- 1panel站点 ---'; ls /opt/1panel/www/sites 2>/dev/null; echo '--- nginx conf ---'; ls /etc/nginx/conf.d 2>/dev/null /www/server/panel/vhost/nginx 2>/dev/null"),
]
for title, cmd in steps:
    out, err = run(cmd)
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)

print("\n#### 面板处理")
act, _ = run("systemctl is-active 1panel 2>/dev/null")
act = act.strip()
if act == "active":
    print("1panel 已 active，无需重启。")
else:
    print("1panel 当前状态:", act or "(未知)", "→ 尝试重启 …")
    o2, e2 = run("systemctl restart 1panel 2>&1; sleep 4; systemctl is-active 1panel 2>/dev/null")
    print("重启后:", (o2 + " " + e2).strip())
cli.close()
print("\n=== DONE ===")
