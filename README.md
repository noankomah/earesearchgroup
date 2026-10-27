# EA Research Group — Django Website

This repository contains the Django website, editable administration and restricted team workspace for EA Research Group. It runs independently of the archived PHP site. The existing public design is retained, with the requested presentation corrections. Django handles page rendering, contact messages, newsletter subscriptions and survey responses.

Uses [Django 5.2 LTS](https://www.djangoproject.com/download/). Python 3.12 is recommended. SQLite is used locally; the supplied OVH configuration uses PostgreSQL, Gunicorn and Nginx.

## Run locally

From this folder:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
export DJANGO_DEBUG=1
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_site
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Administration is at `/admin/`; the team login is at `/team/login/`. No accounts or passwords are shipped. A fresh checkout does not include a virtual environment, local database or administrator account. Follow the commands above to prepare them. The seed command adds the original website content without replacing later admin edits.

The `.env.example` file documents configuration. Django does **not** automatically read `.env`; export values in your shell or use the supplied systemd `EnvironmentFile` on OVH. `DJANGO_DEBUG=0` is the default and requires a secret key. Keep local debug mode off on the server.

## What administrators can change

| Admin section | Editable content |
| --- | --- |
| Content blocks | Existing page headings, paragraphs, button labels, links, logos, contact email, address and footer text. Filter by page or search the existing wording. The `contact` entries update both the About page and footer. Image slots support uploads. Keys and slot types are fixed to protect template wiring. |
| Hero slides | Upload or replace images, change their order, image position, accessible description, and visibility. |
| Team members | Add or remove board, advisory and executive members; change names, roles, photos, biographies, links, order and visibility. |
| Navigation links | Add, remove, reorder or enable header, footer and social links. A header item with children becomes a dropdown. Existing inactive program/event links stay inactive until enabled. |
| Publications | Blogs, newsletters and reports, including drafts, dates, authors, formatted content, cover images, gallery uploads and document links. |
| Opportunities | Descriptions, categories, dates, status, country, host, application links, publication and featured flags. |
| Founder story | Name, role, photo, ordered sections and formatted story content. |
| Events | Event text, date, place, image and registration link. The original empty page stays empty until events are published. |
| Surveys | Survey title and introduction, questions, options, required flags and scales. Responses preserve a snapshot of question wording. |
| Contact messages / subscribers / survey responses | View and manage submissions; export selected records as CSV. Contact messages support read/archive flags. Survey responses have a date-filtered statistics page with charts and a CSV column per question. |

Content blocks edit the existing layout's slots. Adding a new type of section or changing its structure still requires a template change. Adding people, slides, menu links, publications, opportunities, events, story sections and survey questions does not.

## Team accounts and access

In **Users**, create a normal active user. Leave **staff status** and **superuser status** unchecked for team members. Assign one or more groups:

| Group | Access |
| --- | --- |
| Team authors | Create publication/opportunity drafts and edit assigned publications/opportunities. |
| Team profiles | Edit an assigned person's name, photo, biography and profile link. Role, section and visibility stay under administrator control. |
| Assigned page editors | Edit only assigned page text/link/image slots and assigned hero images. Cannot add, reorder or enable sections/slides. |
| Event editors | Create event drafts and edit assigned events. |
| Content publishers | Additional ability to publish assigned publications, opportunities and events. Combine with the relevant editing group. |

For each record, set **Owner** to an individual or **Editor group** to a group. A model permission alone does not reveal other people's records. New team-created records belong to their creator. Unassigned existing/imported content remains administrator-only.

Administrators are active staff superusers. The `/admin/` area is restricted to them, including if someone accidentally marks a normal team account as staff. Team members cannot change permissions, user accounts, content ownership, global menus or unrelated content by sending extra form fields or guessing record URLs. The My content page includes an exact word/phrase search across permitted titles and content, with excerpts and direct Edit links. They can change their password in their workspace; administrators can reset passwords through Users.

Without publishing permission, saving a publication/opportunity/event always makes it a draft, including previously published records. The editing screen explains this before saving. The administrator then reviews and republishes it. Live and pending copies are not stored separately.

## Bring across the current database and uploads

The current production database and private PHP configuration are not in this checkout. The initial seed includes the content visible in the tracked HTML and the hero image manifest; it cannot invent existing publications, founder story content, messages or responses.

For an optional legacy import, the export helper remains with the old checkout at `earg-site/django/tools/export_legacy.php`; it is not part of this Django repository or its runtime. Copy that helper outside the web root on the **old PHP host**, then run it against the existing database helper:

```bash
umask 077
php export_legacy.php /home/earesearch/public_html/admin/includes/db.php > /private/path/legacy-export.json
```

Transfer that file privately to the new host. Run `seed_site` first, then:

```bash
.venv/bin/python manage.py import_legacy /private/path/legacy-export.json --dry-run
.venv/bin/python manage.py import_legacy /private/path/legacy-export.json
```

The importer is transactional, retains original slugs and timestamps, maps message statuses, imports gallery and founder sections, and supports re-running by legacy ID without duplicate records. A repeated import updates imported records from the export, so finish the final import before editing migrated records. Conflicting slugs or invalid values abort the import. Keep a backup before importing into a database already containing work.

Copy **all** original `assets/uploads/` and `assets/documents/` files from the old host into `static/assets/uploads/` and `static/assets/documents/`. These directories are ignored by Git, as they were in the PHP project. Legacy `assets/...` references are translated to Django's `/static/assets/...` URL. Run `collectstatic` after copying. New Django uploads go into `media/` and must be backed up separately. Delete or archive the private JSON export securely after verifying the migration.

Existing public `.php` page and API URLs remain available, including publication/opportunity query-string slugs. Clean URLs are also supported. Django never executes PHP; all these routes are served by Python.

## OVH deployment

Use [the complete Ubuntu 24.04 commands](deploy/OVH_DEPLOY.md) for the first deployment and later updates. For preserving old URLs and Search Console, see [the indexing guide](deploy/INDEXING.md).

The files in `deploy/` target a Linux OVH VPS or dedicated server with Python 3.12, PostgreSQL, Nginx and systemd. Adapt paths and domain names to your server. No deployment or domain change has been performed.

1. Create an `earg` service user, a PostgreSQL database and database user. Place this repository directly at `/srv/earg`, so that `/srv/earg/manage.py` exists. Create its virtual environment and install `requirements.lock`.
2. Create `/etc/earg.env` from `.env.example`. Supply your domain names, HTTPS origins, PostgreSQL credentials, `DJANGO_DEBUG=0`, and a random secret generated with `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'`. Restrict this file's access; keep secrets out of Git.
3. Load the environment in a privileged deployment shell (`set -a`, `. /etc/earg.env`, `set +a`). From the repository root, run `manage.py migrate`, `manage.py seed_site`, the legacy import, `manage.py createsuperuser`, `manage.py collectstatic --noinput` and `manage.py check --deploy` using `.venv/bin/python`.
4. Create `media/` with ownership `earg:www-data` and permissions `2750`. Give Nginx read/traverse access to `staticfiles/` and `media/`. Keep the source code and virtual environment writable only by the deployment account; the service requires write access to `media/` only when using PostgreSQL.
5. Install `deploy/earg.service` under `/etc/systemd/system/`. Adjust paths if needed, then run `systemctl daemon-reload` and `systemctl enable --now earg`.
6. Obtain a TLS certificate for your domain. Adapt `deploy/nginx.conf` with that domain and certificate paths. Enable it in Nginx, run `nginx -t`, and reload Nginx. Gunicorn listens only on localhost; Nginx replaces the proxy headers Django trusts. Enable `DJANGO_TRUST_PROXY_IP=1` only with this setup. Apply normal host firewall rules for SSH, HTTP and HTTPS.
7. Verify public pages, uploads, admin/team sign-in and each account's assigned content on the OVH host before pointing the live domain at it. For the final transfer, pause editing on the PHP site, take a fresh export and upload copy, import, verify counts and switch DNS. Keep the PHP deployment and its database backup available for rollback.

Back up PostgreSQL and `media/`, retain legacy uploaded files, and monitor `journalctl -u earg` and Nginx logs. Public submission and team login throttles use shared database counters; the Nginx configuration also limits both login routes.

## Verification

```bash
export DJANGO_DEBUG=1
.venv/bin/python manage.py check
.venv/bin/python manage.py test website
```

Contact form submissions go to `/contact/send/` and appear under Contact messages in the admin. Email notifications are not configured yet; development uses Django’s console email backend.

The tests cover page rendering, editable content, draft visibility, assignment and group isolation, publishing restrictions, profile restrictions, CSRF, form validation, upload/link validation, request throttling, and transactional/idempotent imports. The existing CSS layout is retained with the requested founder-story spacing, contact visibility and survey control contrast corrections. Footer links use the company LinkedIn address, a non-clickable Facebook placeholder and the original YouTube URL. Browser comparison and a real production database import still need to be performed before cutover.
