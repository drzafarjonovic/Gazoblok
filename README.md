# Manufacturing ERP Telegram Bot

**v2.0** — A Telegram-based ERP/MRP system for manufacturing companies. Fully **dynamic and multi-product**: you define your own products, block types, templates, formulas and prices directly inside the bot — nothing is hard-coded.

> v1.x supported a single product (gas concrete blocks). v2.0 generalizes the whole system to any number of products. Existing data is migrated automatically (see [Migration](#migration)).

## Overview

This bot is a production management platform that helps manufacturers track raw materials, production, inventory, finished goods, sales, costing and reports — all through Telegram. It is designed for small and medium-sized manufacturers that need a simple, mobile-first solution. Any product line (e.g. gas concrete blocks, polystyrene blocks, paving tiles, …) is configured at runtime by an admin.

## Features

### Dynamic Product Management
- Create / rename / archive products from within the bot (⚙️ Settings → 🏭 Product management)
- **Block types** per product (code, name, size, and "units per mould" used for costing)
- **Templates** per product with fully dynamic output — each template defines which blocks and how many come out of one mould (e.g. `30×P`, or `11×A + 2×B`)
- **Mould formula** per product (which raw materials and how much per mould), drawn from one shared warehouse

### Raw Material Management
- Shared warehouse with unit conversion (kg, tonna, litr, m³, meshok, …)
- Material receiving and stock updates
- Per-production material consumption logging
- Minimum-threshold warnings

### Production
- Product → template selection, dynamic per-block output
- Atomic, transactional entry (row-locked, race-condition safe): material deduction + finished-goods increment + logging in one transaction
- Production history and "undo last entry" (restores materials and finished goods)

### Finished Goods & Sales
- Per-product, per-block finished-goods inventory
- Sales recording with stock checks (oversell protected) and sale-price snapshot
- Initial-balance entry

### Finance & Costing
- Per-product prices: sale price, worker wage and overhead per mould, plus optional per-block cost override (💵 Prices → 🏷 Product prices)
- **Automatic cost**: `mould cost = Σ(formula material × price) + wage + overhead`; `cost per block = mould cost ÷ units-per-mould` (or manual override)
- Financial report: revenue, COGS, net profit, raw-material and finished-goods valuation
- Multi-currency display (UZS, USD, EUR, RUB, GBP, CNY, TRY, SAR) with online rates (cached, manual fallback); stored internally in UZS

### Inventory Control
- Per-product inventory audits and stock reconciliation, difference reporting and history

### Reporting
- Product filter: **All** or a specific product
- Summary / detailed / finance / workers / material-usage / comparison reports
- Excel, CSV and PDF export, charts
- Scheduled automatic daily / weekly / monthly reports
- Audit log of all actions

### Security
- Role-based access control (Super Admin, Director, Warehouse, Worker, Seller, Accountant) with per-role and per-user permissions
- **PIN lock** via an inline numeric keypad — the PIN is never typed into the chat; entered digits are masked, and any text typed while locked is auto-deleted

### Performance
- In-memory caches (user, settings, permissions, product/block/template definitions, cost map) drastically reduce per-message database round-trips
- Activity-timestamp writes are throttled
- N+1 queries eliminated; report queries run in parallel
- Database indexes on date/product columns

### Multilingual
- 7 languages: Uzbek, English, Russian, Arabic, Turkish, Chinese, German
- Buttons and messages translated per user; translations cached (in-memory + database) with pre-warming

## Technology Stack

- Python 3.11
- aiogram 3.7 (Telegram Bot API, async)
- PostgreSQL via asyncpg (e.g. Supabase)
- openpyxl (Excel), matplotlib (charts), deep-translator (i18n)

Timezone is fixed to GMT+5 (Asia/Tashkent).

## Project Structure

```
.
├── bot.py            # Entry point, dispatcher, middleware, PIN keypad, scheduler
├── database.py       # PostgreSQL access layer (asyncpg) + caching + migration
├── translation.py    # i18n: translation, cache, pre-warm, helpers
├── valyuta.py        # Multi-currency conversion and rates
├── charts.py         # Chart / PDF generation (optional, degrades gracefully)
├── handlers/
│   ├── production.py
│   ├── sales.py
│   ├── warehouse.py
│   ├── finished_goods.py
│   ├── inventory.py
│   ├── prices.py
│   ├── reports.py
│   ├── users.py
│   ├── permissions.py
│   └── settings.py   # incl. dynamic Product management
├── requirements.txt
├── Dockerfile
├── CHANGELOG.md
└── .env.example
```

## Installation

### 1. Clone

```
git clone https://github.com/drzafarjonovic/Gazoblok.git
cd Gazoblok
```

### 2. Virtual environment

```
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
```

### 3. Dependencies

```
pip install -r requirements.txt
```

### 4. Configure environment

```
cp .env.example .env
```

Required variables:

```
BOT_TOKEN=your_telegram_bot_token     # from @BotFather
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

> The first user to run `/start` becomes the Super Admin and is set as the admin chat for notifications and scheduled reports.

### 5. Run

```
python bot.py
```

On first start the database schema, indexes and data migration are applied automatically.

### Docker (optional)

```
docker build -t erpbot .
docker run -e BOT_TOKEN=... -e DATABASE_URL=... erpbot
```

## Getting Started (after first run)

1. ⚙️ Settings → ➕ Add materials (shared warehouse)
2. ⚙️ Settings → 🏭 Product management → ➕ Add a product
   - 🧱 Add block types (code, name, size, units per mould)
   - 📦 Add templates (which blocks and how many per mould)
   - 📋 Define the mould formula (materials per mould)
3. 💵 Prices → 🏷 Product prices → set sale price, wage, overhead
4. Start recording production and sales

## Commands

- `/start` — register / open menu
- `/til` — change language
- `/version` — show bot version

## Migration

When upgrading from v1.x, the existing single-product data (A/B blocks, the three mould templates, prices and full history) is migrated automatically into a product named **"Gazoblok"** on first start. The migration is idempotent and non-destructive — nothing is lost, and you can keep editing that product like any other.

## License

MIT License

## Author

Developed for manufacturing automation and digital transformation in the construction-materials industry.
