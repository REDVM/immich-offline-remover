FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv


WORKDIR /app

COPY src/pyproject.toml src/uv.lock ./
RUN /uvbin/uv sync --frozen --no-dev

COPY src/*.py ./

CMD ["/uvbin/uv", "run", "--no-sync", "python", "main.py"]