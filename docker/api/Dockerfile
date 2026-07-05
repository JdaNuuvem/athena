FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json tsconfig.json ./
RUN npm install

COPY src/ ./src/
COPY prisma/ ./prisma/

RUN npx prisma generate
RUN npm run build

EXPOSE 3000
CMD ["node", "dist/bootstrap/startup.js"]
