# MatUstoz — serverga joylash

> ⚠️ **Muhim:** Telegram bitta botni bir vaqtda faqat bitta joydan ishlatishga ruxsat
> beradi. Serverga qo'yishdan oldin kompyuterdagi botni to'xtating, aks holda ikkalasi
> ham `Conflict: terminated by other getUpdates request` xatosi bilan uziladi.

---

## Variant 1 — VPS + Docker (tavsiya etiladi)

Bot va PostgreSQL bitta buyruq bilan ko'tariladi. Ubuntu 22.04/24.04 uchun.

### 1. Serverga ulaning va Docker o'rnating

```bash
ssh root@SERVER_IP
curl -fsSL https://get.docker.com | sh
```

### 2. Loyihani serverga tashlang

Git orqali (tavsiya):

```bash
git clone <repo-manzili> /opt/matustoz && cd /opt/matustoz
```

Yoki kompyuterdan to'g'ridan-to'g'ri (Windows PowerShell da, loyiha papkasida):

```powershell
scp -r bot prompts schema.sql requirements.txt Dockerfile docker-compose.yml .dockerignore root@SERVER_IP:/opt/matustoz/
```

### 3. `.env` faylini yarating

```bash
cd /opt/matustoz
nano .env
```

Ichiga:

```
TELEGRAM_BOT_TOKEN=...
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_PASSWORD=uzun-tasodifiy-parol
MATUSTOZ_MODEL=claude-opus-5
MATUSTOZ_EFFORT=high
```

`DATABASE_URL` yozish shart emas — docker-compose uni o'zi beradi.

```bash
chmod 600 .env
```

### 4. Ishga tushiring

```bash
docker compose up -d --build
docker compose logs -f bot        # loglarni ko'rish (Ctrl+C chiqish)
```

Server qayta yuklansa ham bot o'zi ko'tariladi (`restart: unless-stopped`).

### Kundalik buyruqlar

```bash
docker compose ps                 # holat
docker compose logs -f bot        # loglar
docker compose restart bot        # qayta ishga tushirish
docker compose down               # to'xtatish
docker compose up -d --build      # kod yangilangandan keyin
```

### Bazani zaxiralash

```bash
docker compose exec db pg_dump -U matustoz matustoz > backup-$(date +%F).sql
```

Tiklash:

```bash
cat backup-2026-09-01.sql | docker compose exec -T db psql -U matustoz -d matustoz
```

---

## Variant 2 — VPS, Docker'siz (systemd)

PostgreSQL server allaqachon bor bo'lsa qulay.

```bash
apt update && apt install -y python3.12-venv postgresql
sudo -u postgres psql -c "CREATE DATABASE matustoz;"
sudo -u postgres psql -c "CREATE USER matustoz WITH PASSWORD 'parol';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE matustoz TO matustoz;"

useradd --system --create-home --home-dir /opt/matustoz matustoz
# kodni /opt/matustoz ga ko'chiring, keyin:
cd /opt/matustoz
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
nano .env                          # kalitlarni yozing (DATABASE_URL ham kerak)
chown -R matustoz:matustoz /opt/matustoz && chmod 600 .env

cp deploy/matustoz.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now matustoz
systemctl status matustoz
journalctl -u matustoz -f          # loglar
```

---

## Variant 3 — Railway (server boshqarish shart emas)

1. Kodni GitHub ga yuklang.
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub repo.
3. Loyihaga **PostgreSQL** qo'shing (New → Database → PostgreSQL).
4. Bot servisining Variables bo'limiga qo'shing:
   - `TELEGRAM_BOT_TOKEN`
   - `ANTHROPIC_API_KEY`
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
5. Railway `Dockerfile` ni o'zi topib build qiladi.

Chet el karta kerak (~$5/oy). Linux bilan ishlashni istamasangiz — eng oson yo'l.

---

## Qaysi server?

| Variant | Narx | Kimga |
|---|---|---|
| Hetzner CX22 (Germaniya) | ~€4/oy | Eng arzon va barqaror, chet el kartasi kerak |
| DigitalOcean / Vultr | $6/oy | Ko'p hujjat, oson panel, chet el kartasi kerak |
| O'zbekiston hostinglari (ahost.uz, uzinfocom) | ~50–100 ming so'm/oy | Humo/Uzcard bilan to'lanadi, ping past |
| Railway | ~$5/oy | Server sozlashni xohlamaganlarga |

Botga kuchli server kerak emas — **1 CPU, 1–2 GB RAM** yetarli. Asosiy xarajat
serverda emas, Anthropic API da bo'ladi.
