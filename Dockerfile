FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN apt-get update -y && apt-get upgrade -y 
RUN apt-get install -y libgmp3-dev gcc

RUN pip install -r requirements.txt

CMD ["python", "run_node.py"]