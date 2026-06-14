Gazoblock ERP Telegram Bot

A comprehensive Telegram-based ERP/MRP system designed for gas concrete block (gazoblock) manufacturing companies.

Overview

Gazoblock ERP Bot is a production management platform that helps manufacturers track raw materials, production processes, inventory levels, finished products, and operational reports directly through Telegram.

The system is designed for small and medium-sized manufacturing businesses that need a simple, mobile-first solution without deploying expensive enterprise software.

Features

Raw Material Management

- Raw material inventory tracking
- Material receiving and stock updates
- Material consumption logging
- Warehouse balance monitoring

Production Management

- Production order registration
- Template-based production workflows
- Automatic material deduction
- Production history tracking

Finished Product Management

- Finished goods inventory
- Automatic stock updates after production
- Shipment and sales recording
- Balance verification

Inventory Control

- Inventory audits
- Stock reconciliation
- Difference reporting
- Historical inventory records

Reporting

- Production reports
- Material consumption reports
- Warehouse balance reports
- Finished goods reports
- Audit logs

User Management

- Role-based access control
- Individual permissions
- Administrator management
- Secure access restrictions

Technology Stack

- Python
- Telegram Bot API
- SQLite / PostgreSQL
- Async Architecture

Project Structure

project/
├── bot.py
├── database.py
├── handlers/
├── keyboards/
├── services/
├── reports/
├── utils/
└── config.py

Installation

Clone Repository

git clone https://github.com/yourusername/gazoblock-erp-bot.git
cd gazoblock-erp-bot

Create Virtual Environment

python -m venv venv

Activate Environment

Linux/macOS:

source venv/bin/activate

Windows:

venv\Scripts\activate

Install Dependencies

pip install -r requirements.txt

Configure Environment

Create ".env" file:

BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_ID=YOUR_TELEGRAM_ID

Run

python bot.py

Main Modules

Module| Description
Warehouse| Raw material management
Production| Manufacturing operations
Inventory| Stock control
Reports| Analytics and reporting
Users| Roles and permissions
Audit Logs| Change tracking

Roadmap

- Web dashboard
- Telegram Mini App
- Barcode integration
- QR code support
- Multi-factory support
- Advanced analytics
- Cloud synchronization

License

MIT License

Author

Developed for manufacturing automation and digital transformation in the construction materials industry.
