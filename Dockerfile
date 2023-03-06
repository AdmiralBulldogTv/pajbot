FROM python:3.10

WORKDIR /app

COPY requirements.txt .
COPY scripts/venvinstall.sh scripts/venvinstall.sh

RUN ./scripts/venvinstall.sh

COPY . .

RUN chmod +x /app/docker_entrypoint.sh

CMD ["/app/docker_entrypoint.sh"]
