FROM python:3.10-bullseye

WORKDIR /app
ADD requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
ADD bot.py bot.py
CMD ["python", "bot.py"]

