FROM golang:1.24.8-alpine AS build

ARG MINIO_VERSION
ARG MINIO_COMMIT

RUN apk add --no-cache ca-certificates git

WORKDIR /src
RUN git clone --depth 1 --branch "${MINIO_VERSION}" https://github.com/minio/minio.git . \
    && test "$(git rev-parse HEAD)" = "${MINIO_COMMIT}"

# Match MinIO's official release build flags so the binary reports the correct
# release metadata. The source is pinned to the immutable release commit above.
RUN release_timestamp="${MINIO_VERSION#RELEASE.}" \
    && ldflags="$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${release_timestamp}")" \
    && CGO_ENABLED=0 go build -tags kqueue -trimpath -ldflags "${ldflags}" -o /out/minio .

FROM alpine:3.22

RUN apk add --no-cache ca-certificates tzdata \
    && addgroup -S minio \
    && adduser -S -G minio minio \
    && mkdir -p /data \
    && chown minio:minio /data

COPY --from=build /out/minio /usr/local/bin/minio

USER minio
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["minio"]
