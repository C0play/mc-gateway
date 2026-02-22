FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    wakeonlan \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


RUN mkdir -p /root/.ssh \
    && chmod 700 /root/.ssh \
    && echo "Host *" > /root/.ssh/config \
    && echo "    StrictHostKeyChecking no" >> /root/.ssh/config \
    && echo "    UserKnownHostsFile=/dev/null" >> /root/.ssh/config \
    && chmod 600 /root/.ssh/config

COPY src ./src

EXPOSE 25567 25566

ENTRYPOINT ["python", "-m", "src.gateway.main"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-m", "src.gateway.cli", "status"]