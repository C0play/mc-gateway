FROM python:3.14-alpine

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY src ./src

EXPOSE 25567 25566

ENTRYPOINT ["python", "-m", "src.gateway.main"]
