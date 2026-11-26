FROM docker.io/library/alpine:3.24 AS fetch
ARG UPSTREAM_REPO=https://github.com/mgoltzsche/podman-static
ARG UPSTREAM_REF=c55c0fbb9ede2937f71536a394d5cccc5efafcfe
RUN apk add --no-cache git \
 && git init -q /src \
 && git -C /src remote add origin "$UPSTREAM_REPO" \
 && git -C /src fetch --depth=1 origin "$UPSTREAM_REF" \
 && git -C /src checkout -q FETCH_HEAD \
 && git -C /src rev-parse HEAD > /src/.pinned-rev \
 && rm -rf /src/.git

FROM scratch AS export
COPY --from=fetch /src/ /
