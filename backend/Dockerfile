FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY ./animereloaded_mal_auth_server.py /app/animereloaded_mal_auth_server.py
COPY ./providers/__init__.py /app/providers/__init__.py
COPY ./providers/mal_client.py /app/providers/mal_client.py

RUN mkdir -p /data

EXPOSE 18787

CMD ["python3", "/app/animereloaded_mal_auth_server.py"]
