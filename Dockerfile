FROM python:3.11-alpine

# Set the working directory
WORKDIR /app

# Copy requirements.txt
COPY requirements.txt .

# RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
#     && pip install --no-cache-dir -r requirements.txt \
#     && apk del .build-deps

RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app

COPY . .

ENTRYPOINT [ "python", "export.py" ]