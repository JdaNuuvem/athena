FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json tsconfig.json prisma.config.ts ./
COPY prisma/ ./prisma/
RUN npm install --production=false # ponytail: use install not ci; lock file was out of sync with package.json, if reproducibility matters rebuild lock from scratch
COPY src/ ./src/
RUN npx prisma generate
RUN npm run build
RUN npm prune --production

FROM node:22-alpine AS runner

RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/prisma ./prisma
COPY prisma.config.ts ./

ENV NODE_ENV=production
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:3000/api/health || exit 1

CMD ["node", "dist/bootstrap/startup.js"]
