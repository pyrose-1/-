import os,sys,base64,json
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
import paramiko
HOST,USER,PWD="111.229.7.15","root",os.environ.get("SSHPW","")
APP="/www/wwwroot/plm-server"; PATHX="export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,22,USER,PWD,timeout=15,look_for_keys=False,allow_agent=False)
def run(c,t=300):
    i,o,e=cli.exec_command(c,timeout=t); return o.read().decode("utf-8","replace"),e.read().decode("utf-8","replace")
old = """      } else { // DMA / TGA
        const inst = pool[0]; cap = inst ? 7 * 4 : 0; const used = new Map<number, number>();
        for (const d of ds) {
          let need = d.blockCount;
          if (inst) for (let dy = 0; dy < 7 && need > 0; dy++) { let u = used.get(dy) || 0; while (u < 4 && need > 0) { push(inst.id, d.userId, cat, dy, 8 + 4 * u, 12 + 4 * u, 'BLOCK', null); u++; need--; got++; } used.set(dy, u); }
          grant[d.userId + '|' + cat] = { req: d.blockCount, got: d.blockCount - need };
        }
      }"""
new = """      } else { // DMA / TGA：按优先级分块轮换，每2格重选一次（瓶颈设备提高轮换频率）
        const inst = pool[0]; cap = inst ? 7 * 4 : 0;
        const work = ds.map((d) => ({ uid: d.userId, need: d.blockCount, w: score(d.userId, cat) }));
        for (const x of work) grant[x.uid + '|' + cat] = { req: x.need, got: 0 };
        const slots: number[][] = [];
        if (inst) for (let dy = 0; dy < 7; dy++) for (let bl = 0; bl < 4; bl++) slots.push([dy, bl]);
        let si = 0;
        while (si < slots.length) {
          let best: any = null;
          for (const x of work) if (x.need > 0 && (!best || x.w > best.w)) best = x;
          if (!best) break;
          let chunk = 0;
          while (chunk < 2 && best.need > 0 && si < slots.length) {
            const s = slots[si++]; push(inst!.id, best.uid, cat, s[0], 8 + 4 * s[1], 12 + 4 * s[1], 'BLOCK', null);
            best.need--; got++; chunk++; grant[best.uid + '|' + cat].got++;
          }
          best.w -= 2;
        }
      }"""
b=base64.b64encode(json.dumps([[old,new]],ensure_ascii=False).encode()).decode()
o,e=run("python3 - <<'PYEOF'\nimport base64,json\np='%s/src/instruments/instruments.service.ts'\nreps=json.loads(base64.b64decode('%s').decode())\ns=open(p,encoding='utf-8').read()\nfor a,b in reps:\n  assert a in s,'MISS'\n  s=s.replace(a,b)\nopen(p,'w',encoding='utf-8').write(s)\nprint('edited')\nPYEOF"%(APP,b))
print(o,e[-200:])
o,e=run(PATHX+"cd %s && npm run build 2>&1 | tail -5"%APP,400); print(o[-300:],e[-150:])
o,_=run("pm2 restart plm-api >/dev/null 2>&1; sleep 2; echo restarted; pm2 logs plm-api --lines 20 --nostream 2>&1 | grep -ciE 'error TS'")
print(o)
cli.close()
