import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, banner_timeout=15, auth_timeout=15,
            look_for_keys=False, allow_agent=False)
print("=== SSH OK（服务器在线、SSH 正常）===")

def step(title, cmd, t=60):
    i, o, e = cli.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace").rstrip()
    err = e.read().decode("utf-8", "replace").rstrip()
    print("\n#### %s" % title)
    if out: print(out)
    if err: print("[stderr]", err)
    return out

step("开机时长", "uptime -p; echo 开机时间: $(who -b 2>/dev/null | awk '{print $3,$4}')")
step("宝塔服务状态", "/etc/init.d/bt status 2>&1 | head -12; echo '--- systemd ---'; systemctl is-active bt 2>/dev/null; systemctl is-enabled bt 2>/dev/null")
ports = step("关键端口监听", "ss -tlnp 2>/dev/null | grep -E ':(8888|888|80|443|3306|22)\\b' || echo '(无匹配)'")
step("防火墙(firewalld)", "systemctl is-active firewalld 2>/dev/null; firewall-cmd --state 2>/dev/null; echo 放行端口: $(firewall-cmd --list-ports 2>/dev/null)")
step("面板端口/入口/IP限制", "echo -n '面板端口='; cat /www/server/panel/data/port.pl 2>/dev/null; echo; echo -n '安全入口='; cat /www/server/panel/data/admin_path.pl 2>/dev/null; echo; echo -n 'IP限制='; cat /www/server/panel/data/limitip.conf 2>/dev/null; echo -n '面板SSL='; cat /www/server/panel/data/ssl.pl 2>/dev/null")
step("我们的服务", PATHX + "echo -n 'plm-api: '; pm2 pid plm-api 2>/dev/null; curl -s http://127.0.0.1:3000/api/health; echo; echo -n 'nginx进程数: '; ps -C nginx --no-headers 2>/dev/null | wc -l; echo -n 'mysql: '; systemctl is-active mysqld 2>/dev/null || (ps -C mysqld --no-headers|wc -l)")

# 若 8888 没在监听，尝试启动宝塔
if ":8888" not in ports:
    print("\n[!] 8888 未监听 → 尝试启动宝塔面板 …")
    step("启动宝塔", "/etc/init.d/bt start 2>&1 | tail -8")
    step("启动后再查 8888", "sleep 4; ss -tlnp 2>/dev/null | grep ':8888' || echo '仍未监听'")
else:
    print("\n[i] 8888 正在监听，面板服务本身在跑。")
cli.close()
print("\n=== DONE ===")
