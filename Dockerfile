# Multi-stage build para React Dashboard
FROM node:18-alpine AS builder

WORKDIR /app

COPY dashboard/package*.json ./
RUN npm install

COPY dashboard/ ./
RUN npm run build

# Stage de produção
FROM node:18-alpine

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/vite.config.js ./

# Instalar serve para servir os arquivos estáticos
RUN npm install -g serve

# Expor porta
EXPOSE 5173

# Iniciar
CMD ["serve", "-s", "dist", "-l", "5173"]