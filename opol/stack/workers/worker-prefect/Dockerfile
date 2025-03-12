FROM prefecthq/prefect:3-python3.12


WORKDIR /app

ENV UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y curl git

RUN pip install uv

# Copy the requirements.txt file
COPY flows/requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt