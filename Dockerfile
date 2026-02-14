FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install INDI (indiserver + simulator drivers)
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    apt-add-repository -y ppa:mutlaqja/ppa && \
    apt-get update && \
    apt-get install -y indi-bin && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install multiple Python versions (3.9, 3.10, 3.11, 3.12) and tox
# Ubuntu 22.04 has python3.10; deadsnakes provides 3.9, 3.11, 3.12
RUN apt-get update && \
    apt-add-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
        python3.9 python3.9-venv python3.9-dev \
        python3.10 python3.10-venv python3.10-dev \
        python3.11 python3.11-venv python3.11-dev \
        python3.12 python3.12-venv python3.12-dev \
        python3-pip && \
    pip install --no-cache-dir tox && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project
COPY . .

CMD ["tox", "run", "-e", "py39,py310,py311,py312"]
