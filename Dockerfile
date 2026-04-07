# ── Build stage ───────────────────────────────────────────────────────────────
FROM golang:1.21-alpine AS builder

WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .

ARG VERSION=dev
RUN CGO_ENABLED=0 go build \
    -ldflags "-X main.version=${VERSION} -s -w" \
    -o /claude-stats \
    ./cmd/claude-stats

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM alpine:3.19

RUN apk add --no-cache tzdata ca-certificates

COPY --from=builder /claude-stats /usr/local/bin/claude-stats

# Mount your ~/.claude at /root/.claude when running:
#   docker run --rm -it -v "$HOME/.claude:/root/.claude:ro" claude-stats
VOLUME ["/root/.claude"]

ENTRYPOINT ["claude-stats"]
CMD ["--help"]
