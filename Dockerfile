FROM node:20-bookworm-slim

WORKDIR /workspace

ENV npm_config_update_notifier=false
ENV npm_config_fund=false
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        python3 \
        python3-pip \
        python3-venv \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv

COPY docker/entrypoint.sh /usr/local/bin/project-entrypoint
RUN chmod +x /usr/local/bin/project-entrypoint

ENTRYPOINT ["project-entrypoint"]
CMD ["bash"]
