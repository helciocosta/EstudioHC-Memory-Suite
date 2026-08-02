FROM python:3.12-slim

# Usuário não-root
RUN useradd --create-home --uid 1000 sandbox && mkdir -p /work && chown sandbox:sandbox /work

USER sandbox
WORKDIR /work

# Instala a CLI opencode (binário standalone); falhas de instalação não abortam o build
ARG OPENCODE_VERSION=latest
RUN curl -fsSL https://opencode.ai/install | bash || true

ENV PATH="/home/sandbox/.opencode/bin:${PATH}"
ENV OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["opencode", "run", "--format", "json"]