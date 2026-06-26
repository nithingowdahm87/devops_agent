
# syntax=docker/dockerfile:1.6

# ─── Dependencies Stage ─────────────────────────────────
FROM node:20-alpine AS deps
RUN apk add --no-cache tini=0.19.0-r1
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
RUN npm audit --audit-level=moderate || true

# ─── Production Stage ────────────────────────────────────
FROM node:20-alpine AS production
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /sbin/tini /sbin/tini
COPY package*.json ./
COPY .env.example .env.example
COPY server.js ./
ENV NODE_ENV=production
ENV PORT=3000
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3   CMD wget -qO- http://localhost:3000/health || exit 1
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
LABEL org.opencontainers.image.source="https://github.com/OWNER/REPO"
LABEL org.opencontainers.image.description="Node.js Express API"

