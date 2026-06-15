FROM python:3.11-slim

WORKDIR /app

# Bog'liqliklarni alohida qatlamda o'rnatamiz (cache uchun)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Root bo'lmagan foydalanuvchi (xavfsizlik)
RUN useradd --create-home appuser
USER appuser

# Quyidagi muhit o'zgaruvchilari ishga tushirishda berilishi SHART:
#   BOT_TOKEN     - Telegram bot tokeni
#   DATABASE_URL  - PostgreSQL/Supabase ulanish satri
# Misol:
#   docker run -e BOT_TOKEN=... -e DATABASE_URL=... gazobot

CMD ["python", "bot.py"]
