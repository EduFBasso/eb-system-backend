# Render ENV VARS Checklist - Backend Clinico

Use este checklist no Web Service do backend na Render. O deploy deve sair da branch `main`; esta branch de feature deve ser mergeada antes de apontar producao.

## Runtime Django

- [ ] `DJANGO_SETTINGS_MODULE=clinic_project.settings.production`
- [ ] `DJANGO_SECRET_KEY=<secret forte gerado para producao>`
- [ ] `DEBUG=False`
- [ ] `APP_VERSION=<hash, tag ou versao do deploy>`
- [ ] `TIME_ZONE=America/Sao_Paulo`
- [ ] `SERVE_MEDIA_FILES=False`

Observacao: use `SERVE_MEDIA_FILES=True` apenas se o deploy inicial precisar servir arquivos locais pelo Django. Na Render, arquivos de media exigem Persistent Disk ou storage externo para sobreviver a redeploys.

## Banco Postgres

- [ ] `DATABASE_URL=<Internal Database URL do Postgres da Render>`
- [ ] `DB_CONN_MAX_AGE=60`

O arquivo `production.py` exige `DATABASE_URL` e falha no boot se essa variavel estiver ausente ou se nao apontar para `postgres://` ou `postgresql://`.

## Hosts, CORS e CSRF

- [ ] `DJANGO_ALLOWED_HOSTS=<backend>.onrender.com,<dominio-api-futuro>`
- [ ] `CORS_ALLOWED_ORIGINS=https://<frontend-clinico>.vercel.app,https://<dominio-frontend-futuro>`
- [ ] `CORS_ALLOWED_ORIGIN_REGEXES=`
- [ ] `CORS_ALLOW_CREDENTIALS=False`
- [ ] `CSRF_TRUSTED_ORIGINS=https://<backend>.onrender.com,https://<frontend-clinico>.vercel.app`

Nao use `CORS_ALLOW_ALL_ORIGINS=True` em producao. O `production.py` forca `CORS_ALLOW_ALL_ORIGINS=False`.

## HTTPS e Cookies

Nao precisa preencher variaveis para estes itens; `production.py` fixa os valores abaixo:

- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')`
- `SECURE_HSTS_SECONDS=31536000`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- `SECURE_HSTS_PRELOAD=True`

## JWT, TOTP, WebAuthn e sessoes

- [ ] `ALLOW_OTP_FALLBACK=False`
- [ ] `OTP_FALLBACK_CODE=`
- [ ] `MAX_ACTIVE_DEVICE_SESSIONS=2`
- [ ] `TOTP_ISSUER=ClinicSystem`
- [ ] `TOTP_VALID_WINDOW=4`
- [ ] `WEBAUTHN_RP_ID=<dominio do frontend sem https>`
- [ ] `WEBAUTHN_RP_NAME=ClinicSystem`
- [ ] `WEBAUTHN_ORIGINS=https://<frontend-clinico>.vercel.app`

O login API usa JWT via header `Authorization: Bearer <token>`. Mantenha `CORS_ALLOW_CREDENTIALS=False` enquanto nao houver autenticação cross-site por cookies.

## E-mail SMTP

- [ ] `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- [ ] `DEFAULT_FROM_EMAIL=<email remetente validado>`
- [ ] `EMAIL_HOST=<smtp host>`
- [ ] `EMAIL_PORT=587`
- [ ] `EMAIL_USE_TLS=True`
- [ ] `EMAIL_HOST_USER=<usuario smtp>`
- [ ] `EMAIL_HOST_PASSWORD=<senha smtp ou app password>`

Para Apple/iCloud, normalmente use:

- `EMAIL_HOST=smtp.mail.me.com`
- `EMAIL_PORT=587`
- `EMAIL_USE_TLS=True`
- `EMAIL_HOST_USER=<seu email iCloud>`
- `EMAIL_HOST_PASSWORD=<app-specific password da Apple>`

Smoke test depois do deploy:

```bash
cd backend
python manage.py sendtestemail seu-email@exemplo.com
```

## Telegram e lembretes

- [ ] `APPOINTMENT_REMINDERS_ENABLED=False` no primeiro boot, ate validar o bot e os vinculos
- [ ] `TELEGRAM_BOT_TOKEN=<token do BotFather>`
- [ ] `TELEGRAM_BOT_API_BASE=https://api.telegram.org`
- [ ] `TELEGRAM_BOT_TIMEOUT_SECONDS=10`

Validacao do bot no Render Shell:

```bash
cd backend
python manage.py shell -c "from apps.reminders.services.telegram import TelegramBotClient; print(TelegramBotClient().get_me())"
```

Vinculo manual profissional-chat, se necessario:

```bash
cd backend
python manage.py telegram_link_professional --email profissional@exemplo.com --chat-id 123456789 --username usuario_telegram
```

Cron job Render, depois de validar token e vinculos:

- Schedule: `*/5 * * * *`
- Command: `cd backend && python manage.py send_reminders`

Depois de validar o cron, ajuste:

- [ ] `APPOINTMENT_REMINDERS_ENABLED=True`

## Multi-Tenant e Backfill

O comando `python manage.py migrate` executa a data migration `tenancy.0002_backfill_existing_tenants`. Ela e conservadora: so preenche `tenant` quando um profissional tem exatamente um `TenantMembership` ativo em um `Tenant` ativo.

Ordem segura em producao:

1. Fazer backup/snapshot do Postgres Render.
2. Deployar a `main` com as ENV VARS acima.
3. Rodar migrations.
4. Criar ou conferir `Tenant` e `TenantMembership` no Django Admin.
5. Rodar explicitamente:

```bash
cd backend
python manage.py backfill_tenants
```

6. Conferir se os registros criticos esperados ficaram com `tenant` preenchido.

## Protecao Operacional Opcional

Para smoke online inicial sem permitir alteracoes destrutivas:

- [ ] `ONLINE_MUTATION_LOCK_ENABLED=True`
- [ ] `ONLINE_MUTATION_LOCK_METHODS=PUT,PATCH,DELETE`

Desative essa trava quando o ambiente estiver homologado para uso real.

## One-Off Admin

Use apenas se precisar criar um superuser temporario no primeiro boot:

- [ ] `ONE_OFF_ADMIN={"email":"admin@exemplo.com","password":"senha-forte","first_name":"Admin","last_name":"Clinic"}`

Remova `ONE_OFF_ADMIN` depois que o admin estiver criado.

## Comandos Render Recomendados

Build command:

```bash
pip install -r backend/requirements.txt && cd backend && python manage.py collectstatic --noinput
```

Start command inicial:

```bash
cd backend && python manage.py migrate --noinput && gunicorn clinic_project.wsgi --bind 0.0.0.0:$PORT --workers 2
```

Smoke URLs:

- `https://<backend>.onrender.com/health`
- `https://<backend>.onrender.com/health/full`