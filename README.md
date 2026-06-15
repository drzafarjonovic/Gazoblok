# Gazoblock ERP Telegram Bot

A Telegram-based ERP/MRP system for gas concrete block (gazoblock) manufacturing companies.

## Overview

Gazoblock ERP Bot is a production management platform that helps manufacturers track raw materials, production processes, inventory, finished goods, sales, and operational reports directly through Telegram. It is designed for small and medium-sized manufacturers that need a simple, mobile-first solution.

## Features

### Raw Material Management
- Raw material inventory tracking (with unit conversion: kg, tonna, litr, m³, etc.)
- Material receiving and stock updates
- Material consumption logging per production
- Warehouse balance monitoring with minimum-threshold warnings

### Production Management
- Template-based production (3 mould templates)
- Atomic, transactional production entry (row-locked, race-condition safe)
- Automatic material deduction and finished-goods increment
- Production history and "undo last entry"

### Finished Product & Sales
- Finished goods inventory (A / B blocks)
- Sales recording with stock checks (oversell protected)
- Initial-balance entry

### Inventory Control
- Inventory audits and stock reconciliation
- Difference reporting and historical records

### Reporting
- Daily / weekly / monthly reports
- Detailed report and Excel export (7 sheets)
- Automatic scheduled daily report
- Audit logs

### User Management
- Role-based access control (Super Admin, Director, Warehouse, Worker, Seller, Accountant)
- Per-role and per-user individual permissions

### Multilingual
- 7 languages: Uzbek, English, Russian, Arabic, Turkish, Chinese, German
- Buttons and messages translated per user
- Translations cached (in-memory + database) with pre-warming for speed

## Technology Stack

- Python 3.11
- aiogram 3.7 (Telegram Bot API, async)
- PostgreSQL via asyncpg (e.g. Supabase)
- openpyxl (Excel reports)
- deep-translator (multilingual)

Timezone is fixed to GMT+5 (Asia/Tashkent).

## Project Structure

```
.
├── bot.py            # Entry point, dispatcher, middleware, scheduler
├── database.py       # PostgreSQL access layer (asyncpg)
├── translation.py    # i18n: translation, cache, pre-warm, helpers
├── handlers/
│   ├── production.py
│   ├── sales.py
│   ├── warehouse.py
│   ├── finished_goods.py
│   ├── inventory.py
│   ├── reports.py
│   ├── users.py
│   ├── permissions.py
│   └── settings.py
├── requirements.txt
├── Dockerfile
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

Copy the example file and fill in your values:

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

### Docker (optional)

```
docker build -t gazobot .
docker run -e BOT_TOKEN=... -e DATABASE_URL=... gazobot
```

## License

MIT License

## Author

Developed for manufacturing automation and digital transformation in the construction materials industry.
