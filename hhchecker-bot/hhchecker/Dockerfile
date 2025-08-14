# Используем лёгкий образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Открываем порт для API (если понадобится)
EXPOSE 8000

# По умолчанию запускаем бота
CMD ["python3", "-m", "app.bot"]
