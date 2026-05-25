# Production build for React Record Manager UI
FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY src ./src
COPY public ./public

RUN npm run build

# Serve with Nginx
FROM nginx:alpine

COPY --from=builder /app/build /usr/share/nginx/html

RUN echo 'server { \
  listen 80; \
  resolver 127.0.0.11 valid=10s; \
  resolver_timeout 5s; \
  set $upstream http://fastapi:8000; \
  root /usr/share/nginx/html; \
  location ~ ^/static/ { \
    expires 1y; \
    add_header Cache-Control "public, immutable"; \
  } \
  location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ { \
    expires 1y; \
    add_header Cache-Control "public, immutable"; \
  } \
  location / { \
    try_files $uri /index.html =404; \
  } \
  location /api { \
    proxy_pass $upstream; \
  } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
