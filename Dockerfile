FROM python:2.7
# supper code
WORKDIR /app

RUN   pip install requests
RUN   pip install baker
RUN   pip install websocket-client

ENTRYPOINT ["/app/gaucho"]
COPY services.py /app/gaucho
RUN chmod +x /app/gaucho