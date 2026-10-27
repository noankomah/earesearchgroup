# OVH deployment — Ubuntu 24.04

These commands are for you to run on your OVH VPS. They do not run automatically. The application is the Django repository at `https://github.com/noankomah/earesearchgroup.git`, installed directly in `/srv/earg`. Keep your existing working copy and its database until the live site and data have been verified.

## Before starting

- Push the intended Django commit to the new repository yourself.
- Have an Ubuntu 24.04 VPS and an SSH account with sudo access. Confirm it is the intended server before changing anything.
- Point the domain's A record at this VPS, and configure `www` too if you want to use it. Remove or correct stale AAAA records if the VPS is not serving that IPv6 address. Allow time for DNS to update.
- Ensure OVH networking and the host firewall permit SSH, HTTP (80), and HTTPS (443). Keep your existing SSH session open while adjusting a firewall. Do not expose PostgreSQL or Gunicorn publicly.
- Git access is required for the account running `git clone` below. A private repository needs an appropriately authorized SSH deploy key or Git credential helper. Do not embed a token in the URL. If using a deploy key, use the SSH clone URL instead of HTTPS. Do not copy private keys into the repository.

The first-deployment commands below assume a **new VPS** without an existing EARG installation. If `/srv/earg`, `/etc/earg.env`, an `earg` database/role, or an EARG Nginx/service configuration already exists, inspect that installation and use the update procedure instead. Do not overwrite it or reset passwords blindly.

## 1. Install packages and clone the code

SSH into the VPS, then enter a root shell:

```bash
sudo -i
set -e
umask 0027
apt update
apt install -y git python3 python3-venv postgresql postgresql-contrib nginx certbot
systemctl enable --now postgresql
```

Set your public domain names. Keeping `earesearch.org` as the canonical non-www hostname preserves the hostname used by the old sitemap. Replace these examples only if your intended domain differs; these are not credentials:

```bash
export SITE_DOMAIN=earesearch.org
export SITE_WWW=www.earesearch.org
```

Only include a `www` hostname if its DNS also points to this server. The remaining example assumes both names are used.

Create the service account and clone into an empty directory:

```bash
adduser --system --group --home /var/lib/earg earg
usermod -aG www-data earg
git clone https://github.com/noankomah/earesearchgroup.git /srv/earg
cd /srv/earg
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
chgrp -R www-data /srv/earg
chmod -R g+rX /srv/earg
install -d -o earg -g www-data -m 2750 /srv/earg/media
install -d -o earg -g www-data -m 2750 /srv/earg/staticfiles
```

The source remains owned by the deployment account (root in this example), while the runtime account can read it and write uploads. The systemd service also makes source and collected static files read-only at runtime.

## 2. Generate the production configuration once

This creates `/etc/earg.env` with mode `0600` and fresh random secrets. It refuses to overwrite an existing file. Preserve this file on later updates: changing the secret signs users out and changing the database password requires a coordinated database change.

```bash
python3 - <<'PY'
import os
import secrets
from pathlib import Path
site = os.environ['SITE_DOMAIN']
www = os.environ['SITE_WWW']
text = '\n'.join([
    'DJANGO_DEBUG=0',
    'DJANGO_SECRET_KEY=' + secrets.token_hex(48),
    'DJANGO_ALLOWED_HOSTS=' + site + ',' + www,
    'DJANGO_CSRF_TRUSTED_ORIGINS=https://' + site + ',https://' + www,
    'DJANGO_TRUST_PROXY_IP=1',
    'POSTGRES_DB=earg',
    'POSTGRES_USER=earg',
    'POSTGRES_PASSWORD=' + secrets.token_hex(32),
    'POSTGRES_HOST=127.0.0.1',
    'POSTGRES_PORT=5432',
]) + '\n'
fd = os.open('/etc/earg.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    output.write(text)
print('Created /etc/earg.env; secrets were not printed.')
PY
```

Provision PostgreSQL using that saved password. The password goes through standard input, not shell/process arguments. This refuses to use an existing `earg` role or database:

```bash
python3 - <<'PY'
from pathlib import Path
import subprocess
values = dict(line.split('=', 1) for line in Path('/etc/earg.env').read_text().splitlines() if line and not line.startswith('#'))
base = ['runuser', '-u', 'postgres', '--', 'psql', '--dbname=postgres', '--set=ON_ERROR_STOP=1']
query = "SELECT (EXISTS(SELECT 1 FROM pg_roles WHERE rolname='earg') OR EXISTS(SELECT 1 FROM pg_database WHERE datname='earg'))::int;"
exists = subprocess.check_output(base + ['--tuples-only', '--no-align', '--command', query], text=True, cwd='/').strip()
if exists != '0':
    raise SystemExit('The earg role/database already exists; inspect it instead of overwriting it.')
password = values['POSTGRES_PASSWORD'].replace("'", "''")
sql = "CREATE ROLE earg LOGIN PASSWORD '" + password + "';\nCREATE DATABASE earg OWNER earg;\n"
subprocess.run(base, input=sql, text=True, check=True, cwd='/')
PY
```

Load the environment in this root shell without printing it:

```bash
set -a
. /etc/earg.env
set +a
cd /srv/earg
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py migrate
```

## 3. Bring your content across, then initialize

Git contains source code, not your local database, messages, survey submissions, admin accounts or uploads. If you want existing Django edits and accounts on the server, transfer them privately **before** seeding or creating new accounts.

For a current Django database, export from the working folder that actually contains your data (the original development preview used `/home/nana-ankomah/earg-site/django`). Run this on your own machine, not on the VPS:

```bash
cd /home/nana-ankomah/earg-site/django
umask 077
DJANGO_DEBUG=1 .venv/bin/python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude sessions --exclude admin.logentry --exclude website.requestlimit \
  --indent 2 > /tmp/earg-private-content.json
```

That file contains account password hashes and potentially private contact/survey data. Do not put it in Git or a public web directory. Copy it over SSH from your own machine (replace the username and server):

```bash
scp /tmp/earg-private-content.json YOUR_SSH_USER@YOUR_SERVER:/tmp/earg-private-content.json
```

Back in the VPS root shell, move it to a private directory and load it while the environment from step 2 is loaded:

```bash
install -d -m 0700 /root/earg-import
install -m 0600 /tmp/earg-private-content.json /root/earg-import/earg-private-content.json
rm /tmp/earg-private-content.json
cd /srv/earg
.venv/bin/python manage.py loaddata /root/earg-import/earg-private-content.json
```

Transfer `media/` and any legacy `static/assets/uploads/` or `static/assets/documents/` directories separately if they contain files. Preserve their relative paths. After copying new Django uploads, set:

```bash
chown -R earg:www-data /srv/earg/media
find /srv/earg/media -type d -exec chmod 2750 {} +
find /srv/earg/media -type f -exec chmod 0640 {} +
for folder in static/assets/uploads static/assets/documents; do
    if [ -d "/srv/earg/$folder" ]; then
        chgrp -R www-data "/srv/earg/$folder"
        chmod -R g+rX "/srv/earg/$folder"
    fi
done
```

The optional PHP-to-Django JSON import is documented in README.md if production data is still on the old host; it is a separate alternative to copying an existing Django database.

Now finish initialization on the VPS:

```bash
cd /srv/earg
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py seed_site
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py collectstatic --noinput
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py check --deploy
```

If you did not import an administrator account, create one interactively:

```bash
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py createsuperuser
```

Check that a published founder story, publications/opportunities and other intended content exist. Seeding restores the original page copy, people, hero slides, navigation and survey definitions; it does not create a founder story or invent publications/opportunities. A founder story is needed for its public page to return 200.

## 4. Start Gunicorn through systemd

Check there is no existing EARG service before installing a first one:

```bash
test ! -e /etc/systemd/system/earg.service
install -m 0644 /srv/earg/deploy/earg.service /etc/systemd/system/earg.service
systemctl daemon-reload
systemctl enable --now earg
systemctl status earg --no-pager
```

For failures, inspect `journalctl -u earg -n 80 --no-pager`. Do not paste credentials or complete configuration files into public logs/issues.

## 5. Bootstrap HTTP, obtain TLS, then enable HTTPS

Do not install the final HTTPS configuration before certificate files exist: Nginx would fail its configuration test.

Create an HTTP-only bootstrap configuration. It serves ACME challenges and shows a temporary maintenance response elsewhere. The checks stop existing EARG configuration from being overwritten:

```bash
install -d -m 0755 /var/www/letsencrypt/.well-known/acme-challenge
test ! -e /etc/nginx/sites-available/earg
test ! -e /etc/nginx/sites-enabled/earg
cat > /etc/nginx/sites-available/earg <<EOF_HTTP
server {
    listen 80;
    server_name ${SITE_DOMAIN} ${SITE_WWW};
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }
    location / {
        return 503;
    }
}
EOF_HTTP
ln -s /etc/nginx/sites-available/earg /etc/nginx/sites-enabled/earg
nginx -t
systemctl enable --now nginx
systemctl reload nginx
```

If another enabled site already declares either hostname, resolve that conflict before continuing. Once both DNS names reach this server and port 80 is accessible, request the certificate (Certbot asks for email/terms):

```bash
certbot certonly --webroot -w /var/www/letsencrypt \
  -d "$SITE_DOMAIN" -d "$SITE_WWW"
```

Create the final config from `deploy/nginx.conf`, substituting the public domain. It must retain the HTTP ACME challenge location so automatic renewals work. Do not change the `location /media/` handling or the localhost-only upstream without understanding the effect.

```bash
cp -p /etc/nginx/sites-available/earg /root/earg-nginx-bootstrap.conf
sed "s/example\.org/${SITE_DOMAIN}/g" /srv/earg/deploy/nginx.conf > /etc/nginx/sites-available/earg
nginx -t
systemctl reload nginx
certbot renew --dry-run
systemctl list-timers --all | grep certbot
```

This template assumes `www` is `www.<SITE_DOMAIN>` and the certificate's primary name is `<SITE_DOMAIN>`. HTTP and HTTPS `www` requests redirect to the canonical non-www HTTPS hostname, while the HTTP ACME path stays available for renewals. If yours differ, adjust `server_name` and certificate paths accordingly before `nginx -t`. If the final config test fails, do not reload; keep the running bootstrap configuration while correcting the file.

## 6. Verify the complete public site

Open `https://<your-domain>/` and check the homepage, hero images, About/team pages, Founder’s Story, publication/opportunity pages, contact form, newsletter sign-up and survey. Confirm actual submitted messages/responses appear in the live admin. Check admin/team sign-in and restricted editing, new image uploads and phone layouts. Review logs for server errors. Confirm HTTPS and `www` behaviour.

Contact messages currently save in the admin inbox; automatic email notifications are not configured. Do not advertise email notifications until SMTP/mail delivery is added and tested.

After verifying the import, remove temporary transfer files or move them into a secure backup outside the public application directory. Set up recurring backups of PostgreSQL, uploads and `/etc/earg.env`. Keep the old deployment/data available until cutover has been checked.

## Search Console and existing indexed pages

Keep the same public domain and the original non-www canonical hostname when restoring the site. The Django compatibility routes preserve old About-page paths, and the dynamic sitemap is available at `https://earesearch.org/sitemap.xml`. Existing publication/opportunity slugs must also be imported from the actual content database; a routing rule cannot restore missing records.

After the public site is reachable:

1. Keep existing Google Search Console verification. If verification uses a DNS TXT record, preserve that record when changing hosting DNS; do not delete unrelated mail or verification records.
2. Confirm the sitemap returns 200 and contains the intended published pages, then submit or refresh `/sitemap.xml` in the existing Search Console property.
3. Check representative previously indexed URLs, including `/views/About/who-we-are.php`, `/views/About/founder-story.php` and existing publication URLs. Verify their final destination shows the intended content rather than a missing-page response.
4. Use URL Inspection to check the restored homepage and important pages, request indexing where appropriate, and monitor indexing and 404 reports after Google recrawls.

Restoring the same domain, real content and URL continuity helps Google rediscover the site, but does not guarantee immediate indexing or restored rankings. Do not start a Search Console Change of Address merely for a server change on the same domain.

## Later updates — preserve runtime data

Run these steps yourself from a root SSH shell. Keep `/etc/earg.env`, the PostgreSQL database and upload folders. Do not rerun the first-install secret/database generation, use `git clean -fdx`, replace `/srv/earg` with a new empty folder, or use `rsync --delete` across runtime directories.

Before downtime, inspect the intended update:

```bash
sudo -i
set -e
umask 077
cd /srv/earg
git status --short
git diff --quiet
git diff --cached --quiet
git fetch origin
git log --oneline HEAD..origin/main
```

If there are unexpected local edits or the history has diverged, stop and resolve that situation first. Then stop writes briefly and make a backup:

```bash
systemctl stop earg
BACKUP_DIR="/var/backups/earg/$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/code-commit.txt"
cp -p /etc/earg.env "$BACKUP_DIR/earg.env"
runuser -u postgres -- pg_dump -Fc earg > "$BACKUP_DIR/database.dump"
tar -C /srv/earg -czf "$BACKUP_DIR/media.tar.gz" media
for folder in static/assets/uploads static/assets/documents; do
    if [ -d "/srv/earg/$folder" ]; then
        tar -C /srv/earg -czf "$BACKUP_DIR/$(basename "$folder").tar.gz" "$folder"
    fi
done
```

Apply the fast-forward update and database migrations:

```bash
cd /srv/earg
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.lock
set -a
. /etc/earg.env
set +a
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py migrate
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py seed_site
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py collectstatic --noinput
runuser -u earg -g www-data -- /srv/earg/.venv/bin/python manage.py check --deploy
systemctl start earg
systemctl status earg --no-pager
```

Recheck the website and live submissions. `seed_site` preserves later content edits. Review any changes to `deploy/` separately instead of overwriting your customized domain/configuration; reload Nginx or systemd only when their actual installed configuration changes.

If a step fails after stopping the service, inspect the error and resolve it before proceeding. The database and uploads remain backed up. A rollback involving migrations requires assessing database compatibility or restoring the matching database backup; do not blindly check out older code against a migrated schema.

For the detailed old-URL and indexing checks, see [INDEXING.md](INDEXING.md).

References: [Ubuntu certificate setup](https://ubuntu.com/server/docs/how-to/security/obtain-tls-certificates/), [Certbot installation options](https://github.com/certbot/certbot/blob/main/certbot/docs/install.rst).
