FROM python:3.13.0-slim

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "discord_bot.py"]
