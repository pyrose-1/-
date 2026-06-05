# -*- coding: utf-8 -*-
import os, sys, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import paramiko
HOST, USER, PWD = "111.229.7.15", "root", os.environ.get("SSHPW", "")
PATHX = "export PATH=/usr/local/bin:/usr/bin:/bin:$PATH; "
APP = "/www/wwwroot/plm-server"
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=15, look_for_keys=False, allow_agent=False)
def run(cmd, t=400):
    i, o, e = cli.exec_command(cmd, timeout=t); return o.read().decode("utf-8","replace").rstrip(), e.read().decode("utf-8","replace").rstrip()
def wfile(path, content):
    b = base64.b64encode(content.encode()).decode()
    o,e=run("mkdir -p $(dirname %s) && python3 - <<'PY'\nimport base64\nopen(%r,'w',encoding='utf-8').write(base64.b64decode('%s').decode())\nprint('w ok')\nPY" % (path, path, b))
    print("  写", path.replace(APP, ""), o.strip(), e[-150:])
wfile(APP + "/src/mail/mail.service.ts", """import { Injectable, Logger } from '@nestjs/common';
import * as nodemailer from 'nodemailer';

@Injectable()
export class MailService {
  private readonly log = new Logger('Mail');
  private tx = nodemailer.createTransport({
    host: process.env.MAIL_HOST || 'smtp.163.com',
    port: Number(process.env.MAIL_PORT || 465),
    secure: Number(process.env.MAIL_PORT || 465) === 465,
    auth: { user: process.env.MAIL_USER, pass: process.env.MAIL_PASS },
  });
  get from() { return `"\\u805a\\u9170\\u4e9a\\u80fa\\u5b9e\\u9a8c\\u5ba4\\u7ba1\\u7406\\u7cfb\\u7edf" <${process.env.MAIL_USER}>`; }
  async send(to: string, subject: string, html: string) {
    if (!process.env.MAIL_USER) { this.log.warn('MAIL_USER not set, skip'); return { skipped: true }; }
    const info = await this.tx.sendMail({ from: this.from, to, subject, html });
    this.log.log(`sent -> ${to} (${info.messageId})`);
    return { messageId: info.messageId };
  }
}
""")
wfile(APP + "/src/mail/mail.module.ts", """import { Global, Module } from '@nestjs/common';
import { MailService } from './mail.service';

@Global()
@Module({ providers: [MailService], exports: [MailService] })
export class MailModule {}
""")
o,_=run("ls -la %s/src/mail"%APP); print(o)
o,e=run(PATHX+"cd %s && npm run build 2>&1 | tail -16 && echo BUILT"%APP, 480)
print(o); print("[stderr]", e[-300:])
o,_=run(PATHX+"pm2 restart plm-api >/dev/null 2>&1; sleep 4; pm2 logs plm-api --lines 5 --nostream 2>&1 | tail -6")
print(o)
cli.close()
