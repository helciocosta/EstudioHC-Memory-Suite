FROM python:3.12-slim

# Instala curl (necessário p/ instalar a CLI opencode) e remove-o após o build
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Usuário não-root
RUN useradd --create-home --uid 1000 sandbox && mkdir -p /work && chown sandbox:sandbox /work

USER sandbox
WORKDIR /work

# Instala a CLI opencode (binário standalone); falhas de instalação não abortam o build
ARG OPENCODE_VERSION=latest
RUN curl -fsSL https://opencode.ai/install | bash || true

ENV PATH="/home/sandbox/.opencode/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["opencode", "run", "--format", "json"]