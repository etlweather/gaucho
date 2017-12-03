FROM python:2.7
# supper code
WORKDIR /app

RUN pip install \
        requests==2.18.4 \
        baker==1.3 \
        websocket-client==0.44.0

COPY services.py /app/gaucho
RUN chmod +x /app/gaucho

ENTRYPOINT ["/app/gaucho"]
