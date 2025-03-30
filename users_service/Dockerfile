FROM python:3.11

# Встановлення робочої директорії
WORKDIR /app

# Копіюємо залежності
COPY requirements.txt .

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код у контейнер
COPY . .

# Відкриваємо порт для застосунку
EXPOSE 8000

# Запускаємо FastAPI за допомогою Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
