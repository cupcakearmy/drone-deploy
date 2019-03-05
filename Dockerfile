FROM python:3-alpine as builder
RUN apk add --no-cache alpine-sdk libffi-dev openssl-dev python3-dev
COPY requirements.txt .
RUN pip install -r requirements.txt


FROM python:3-alpine
WORKDIR /plugin
COPY --from=builder /root/.cache /root/.cache
COPY --from=builder requirements.txt .
RUN pip install -r requirements.txt && rm -rf /root/.cache

COPY main.py ./

WORKDIR /drone/src

CMD ["python", "/plugin/main.py"]