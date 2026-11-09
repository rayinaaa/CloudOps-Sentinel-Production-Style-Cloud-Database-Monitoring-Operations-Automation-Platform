# ==============================================================================
# CloudOps Sentinel - Frontend Production Dockerfile
# Multi-stage build with Nginx Alpine runtime
# ==============================================================================

FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Runtime Stage
FROM nginx:alpine-slim

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

