# -*- coding: utf-8 -*-
import os, sys, html
from datetime import date
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
DBP = "pni38AWG4xy6wEyc"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=20, look_for_keys=False, allow_agent=False)
def run(c, t=180):
    i, o, e = cli.exec_command(c, timeout=t); return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")

cycles = ["2026-06-15", "2026-06-22", "2026-06-29", "2026-07-06", "2026-07-13"]
clause = "','".join(cycles)
q = ("SELECT b.cycleKey,b.date,b.startHour,b.endHour,b.taskType,IFNULL(b.tempCeiling,0),i.name,i.category,u.name "
     "FROM plm_bookings b JOIN plm_instruments i ON i.id=b.instrumentId JOIN plm_users u ON u.id=b.userId "
     "WHERE b.cycleKey IN ('%s') ORDER BY i.category,i.id,b.date,b.startHour;" % clause)
out, _ = run("mysql -uplm -p%s plm -N -e \"%s\" 2>/dev/null" % (DBP, q))
cli.close()

TASK = {"FILM": "铺膜", "DRY": "干燥", "FULL_DAY": "全天", "HALF_DAY": "半天", "BLOCK": ""}
CATLABEL = {"VACUUM_OVEN": "真空烘箱", "FURNACE": "环化/马弗/管式/BET（全天）", "POLY_HEAD": "聚合机头（半天）", "DMA": "DMA", "TGA": "TGA"}
CATORD = ["VACUUM_OVEN", "FURNACE", "POLY_HEAD", "DMA", "TGA"]
WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# data[cycle][cat][instName][dateIdx] = list of cell strings
data = {}
inst_order = {}  # cat -> ordered inst names
for line in out.splitlines():
    if not line.strip():
        continue
    ck, dt, sh, eh, tt, temp, iname, cat, uname = line.split("\t")
    sh, eh = int(sh), int(eh)
    d0 = date.fromisoformat(ck)
    di = (date.fromisoformat(dt) - d0).days
    label = "%d–%d %s%s" % (sh, eh, TASK.get(tt, ""), uname)
    if tt == "FULL_DAY" and temp != "0":
        label += "(%s℃)" % temp
    data.setdefault(ck, {}).setdefault(cat, {}).setdefault(iname, {}).setdefault(di, []).append(label)
    inst_order.setdefault(cat, [])
    if iname not in inst_order[cat]:
        inst_order[cat].append(iname)

def esc(s):
    return html.escape(str(s))

parts = ["""<!doctype html><html lang=zh><head><meta charset=utf-8><title>仪器抽签结果 · 5 轮</title>
<style>
body{font-family:-apple-system,'Microsoft YaHei',sans-serif;color:#334155;background:#F8FAFC;margin:0;padding:24px;}
h1{color:#1E3A8A;} h2{color:#1E3A8A;border-bottom:2px solid #1E3A8A;padding-bottom:4px;margin-top:36px;}
h3{color:#D97706;margin:18px 0 6px;}
table{border-collapse:collapse;width:100%;margin-bottom:8px;font-size:12px;}
th,td{border:1px solid #cbd5e1;padding:4px 6px;vertical-align:top;text-align:left;}
th{background:#1E3A8A;color:#fff;font-weight:500;}
td.inst{background:#eef2ff;font-weight:600;white-space:nowrap;color:#1E3A8A;}
.cell div{padding:1px 0;border-bottom:1px dotted #e2e8f0;}
.film{color:#1d4ed8;} .dry{color:#475569;} .full{color:#b45309;} .empty{color:#cbd5e1;}
.toc a{margin-right:14px;}
</style></head><body>
<h1>聚酰亚胺实验室 · 仪器抽签结果（连续 5 轮）</h1>
<p>共 5 个周期，每周 周一–周日。单元格格式：<b>起–止时 任务 学生</b>（环化附温度上限）。空白=无人预约（开奖后可点击即得）。</p>
<div class=toc>"""]
parts.append(" ".join('<a href="#r%d">第%d轮 %s</a>' % (wi + 1, wi + 1, ck) for wi, ck in enumerate(cycles)))
parts.append("</div>")

for wi, ck in enumerate(cycles):
    parts.append('<h2 id="r%d">第 %d 轮 — %s 那周</h2>' % (wi + 1, wi + 1, ck))
    cd = data.get(ck, {})
    for cat in CATORD:
        insts = inst_order.get(cat, [])
        if not insts:
            continue
        parts.append("<h3>%s</h3>" % CATLABEL[cat])
        parts.append("<table><tr><th>仪器</th>" + "".join("<th>%s<br>%s</th>" % (WD[i], (date.fromisoformat(ck).toordinal() and (date.fromordinal(date.fromisoformat(ck).toordinal() + i)).isoformat()[5:])) for i in range(7)) + "</tr>")
        catdata = cd.get(cat, {})
        for iname in insts:
            row = ["<td class=inst>%s</td>" % esc(iname)]
            dd = catdata.get(iname, {})
            for di in range(7):
                cells = dd.get(di, [])
                if cells:
                    inner = "".join("<div>%s</div>" % esc(x) for x in cells)
                else:
                    inner = '<span class=empty>—</span>'
                row.append('<td class=cell>%s</td>' % inner)
            parts.append("<tr>" + "".join(row) + "</tr>")
        parts.append("</table>")

parts.append("</body></html>")
open("抽签结果.html", "w", encoding="utf-8").write("".join(parts))
print("已生成 抽签结果.html")

# 文字样张：第1轮 周一
print("\n===== 样张：第1轮(2026-06-15) 周一 各设备分配 =====")
ck = cycles[0]; cd = data.get(ck, {})
for cat in CATORD:
    insts = inst_order.get(cat, [])
    shown = False
    for iname in insts:
        cells = cd.get(cat, {}).get(iname, {}).get(0, [])
        if cells:
            if not shown:
                print("\n--- %s ---" % CATLABEL[cat]); shown = True
            print("  %-30s %s" % (iname[:30], " | ".join(cells)))
