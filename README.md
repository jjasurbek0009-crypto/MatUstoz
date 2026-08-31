# MatUstoz — Telegram matematika repetitori boti

O'zbek tilida, noldan matematika o'rgatadigan shaxsiy repetitor bot.
Claude (`claude-opus-5`) + python-telegram-bot + PostgreSQL.

Bot har bir o'quvchining maqsadi, muddati, darajasi, o'quv rejasi va o'tilgan
mavzularini bazada saqlaydi — suhbat uzilib qolsa ham hammasi joyida qoladi.

---

## O'rnatish

### 1. Kalitlarni oling

- **Telegram token** — Telegramda [@BotFather](https://t.me/BotFather) ga `/newbot` yozing.
- **Anthropic API kaliti** — [console.anthropic.com](https://console.anthropic.com) → API Keys.

### 2. Bazani yarating

```bash
psql -U postgres -c "CREATE DATABASE matustoz;"
```

Jadvallar bot birinchi ishga tushganda avtomatik yaratiladi (`schema.sql`).

### 3. Sozlang

```bash
cp .env.example .env
```

`.env` ichiga tokenlarni va `DATABASE_URL` ni yozing.

### 4. Kutubxonalarni o'rnating va ishga tushiring

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m bot.main
```

Telegramda botingizga `/start` deb yozing.

---

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/start` | Boshlash yoki qaytib kelish |
| `/reja` | Tuzilgan o'quv rejani ko'rsatish |
| `/progress` | O'tilgan mavzular va foiz |
| `/reset` | Tarix, reja va progressni tozalash (tasdiq so'raladi) |
| `/help` | Buyruqlar ro'yxati |

---

## Loyiha tuzilishi

```
prompts/system_prompt.md   Ustozning tizim prompti — botning xulq-atvori shu yerda
schema.sql                 PostgreSQL jadvallari
bot/config.py              .env va prompt yuklanishi
bot/db.py                  asyncpg qatlami (o'quvchi, xabarlar, mavzular)
bot/tutor.py               Claude bilan ishlash: javob oqimi + profilni yangilash
bot/handlers.py            Telegram handlerlari, oqimli javob yozish
bot/main.py                Ishga tushirish nuqtasi
```

### Ishlash tartibi

1. O'quvchi xabar yozadi.
2. Bazadan oxirgi 40 ta xabar va o'quvchi profili olinadi.
3. Claude ga so'rov ketadi:
   - **system** — `prompts/system_prompt.md` (o'zgarmaydi, keshlanadi),
   - **messages** — suhbat tarixi + yangi xabar,
   - eng oxirida **`role: "system"`** bloki — o'quvchining hozirgi holati
     (maqsad, daraja, reja, mavzular). U oxirida turgani uchun kesh buzilmaydi.
4. Javob oqim (streaming) bilan keladi va Telegram xabari real vaqtda tahrirlanadi.
5. Javobdan keyin ikkinchi, arzon so'rov profilni yangilaydi: maqsad, muddat,
   daraja, reja, hozirgi mavzu va mavzular holati (`structured outputs` orqali JSON).

Profil tanishuv tugamaguncha har xabarda, keyin har 4-xabarda yangilanadi
(`MATUSTOZ_PROFILE_REFRESH_EVERY`).

---

## Sozlamalar (`.env`)

| O'zgaruvchi | Standart | Izoh |
|---|---|---|
| `MATUSTOZ_MODEL` | `claude-opus-5` | Model. Matematika aniqlik talab qilgani uchun Opus tavsiya etiladi |
| `MATUSTOZ_EFFORT` | `high` | `low` / `medium` / `high` / `xhigh` / `max` — chuqurroq o'ylash, ko'proq token |
| `MATUSTOZ_MAX_TOKENS` | `16000` | Bitta javobdagi maksimal token |
| `MATUSTOZ_HISTORY_LIMIT` | `40` | Modelga uzatiladigan oxirgi xabarlar soni |
| `MATUSTOZ_PROFILE_REFRESH_EVERY` | `4` | Profil har necha xabarda yangilansin |

---

## Xarajat haqida

`claude-opus-5` narxi: 1M kirish tokeni uchun $5, 1M chiqish tokeni uchun $25.

Xarajatni kamaytiradigan narsalar allaqachon yoqilgan:

- **Prompt caching** — tizim prompti keshlanadi, takroriy so'rovlarda o'sha qism
  ~90% arzon tushadi. Tekshirish: `usage.cache_read_input_tokens` noldan katta bo'lishi kerak.
- **O'zgaruvchan ma'lumot oxirida** — o'quvchi holati `role: "system"` xabari
  sifatida eng oxirga qo'yiladi, shuning uchun kesh prefiksi buzilmaydi.
- **Tarix chegarasi** — butun suhbat emas, oxirgi 40 ta xabar yuboriladi.
- **Profil ajratish `effort: "low"` da** — yordamchi so'rov arzon rejimda ishlaydi.

Yanada arzonlashtirish kerak bo'lsa: `MATUSTOZ_EFFORT=medium` qiling yoki
`MATUSTOZ_PROFILE_REFRESH_EVERY` ni oshiring. Modelni almashtirishdan oldin
javob sifatini tekshirib ko'ring — matematikada xato javob eng qimmat narsa.

---

## Texnik eslatmalar

- **Markdown yo'q.** Telegramga javoblar oddiy matn ko'rinishida yuboriladi
  (`parse_mode` ishlatilmaydi), chunki formulalardagi `*` va `_` belgilari
  Markdown ni buzadi. Tizim prompti ham modelga Markdown yozmaslikni aytadi.
- **Uzun javoblar** avtomatik ravishda 3800 belgilik bo'laklarga bo'linadi.
- **Bir o'quvchi — bir so'rov.** Har bir foydalanuvchi uchun qulf (lock) bor,
  ketma-ket yuborilgan xabarlar aralashib ketmaydi.
- **Model moslashuvi.** Agar tanlangan model `role: "system"` xabarini yoki
  server tomonidagi `fallbacks` beta'sini qo'llamasa, bot birinchi xatodan keyin
  o'sha imkoniyatni o'chirib, ishlashda davom etadi.
- **Rasm/ovoz** hozircha qo'llab-quvvatlanmaydi — bot matn so'raydi.

---

## Botning xulqini o'zgartirish

Deyarli hamma narsa `prompts/system_prompt.md` da. Uni tahrirlab botni qayta
ishga tushirsangiz kifoya — kodga tegish shart emas. Faylning 11-bo'limi
(Telegram muhiti) texnik cheklovlarni tavsiflaydi, uni o'chirmang.
