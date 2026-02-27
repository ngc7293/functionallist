# syntax=docker/dockerfile:1.10

FROM ghcr.io/astral-sh/uv:0.10.6-debian-slim AS build-backend

WORKDIR /build

COPY pyproject.toml /build/pyproject.toml
COPY uv.lock        /build/uv.lock

RUN uv sync --locked --no-dev --no-cache --compile-bytecode

FROM build-backend AS gather-libs

RUN mkdir /libs && \
    find /build/.venv -name '*.so*' \
        | xargs ldd 2>/dev/null \
        | awk '/=> \// { print $3 }' \
        | grep -v '/build/.venv' \
        | sort -u \
        | xargs cp -t /libs/

FROM node:25.6.1-alpine AS build-frontend

WORKDIR /build

COPY package.json       /build/package.json
COPY package-lock.json  /build/package-lock.json

RUN npm install

COPY vite.config.ts /build/vite.config.ts
COPY tsconfig.json  /build/tsconfig.json
COPY index.html     /build/index.html
COPY app/           /build/app/

RUN npm run build

# Google's distroless images don't have release tags other than :latest
# hadolint ignore=DL3007
FROM gcr.io/distroless/cc-debian13:latest AS runtime

WORKDIR /opt

# UV installs Python in /root/.local. In the distroless image, it includes
# nothing else so we can copy the whole directory.
COPY --from=build-backend /root        /root
COPY --from=build-backend /build       /opt
COPY --from=gather-libs   /libs        /usr/lib
COPY --from=build-frontend /build/dist /opt/dist

COPY /server /opt/server

EXPOSE 8000/tcp
ENTRYPOINT ["/opt/.venv/bin/python", "-m", "server"]
