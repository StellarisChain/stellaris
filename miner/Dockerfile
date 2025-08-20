FROM python:3.12-slim

WORKDIR /app
COPY ../requirements.txt .
COPY . .

RUN apt-get update -y && apt-get upgrade -y 
RUN apt-get install -y libgmp3-dev gcc

RUN pip install -r requirements.txt

CMD ["python", "miner.py", "DWMVFcRTZ8UMaWr2vsb7XkTmh7zaA57BQaDRGiAKB6qX6", "4", "https://stellaris-node.connor33341.dev/"]