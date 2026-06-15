# ⚠ DELIBERATE BROWNFIELD DEBT — Item 11
FROM node:latest AS build
WORKDIR /workspace

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ⚠ Item 11 — nginx:latest also
FROM nginx:latest
# SPA routing — fall back to index.html so deep-link refreshes don't 404.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/dist/acquire-gov-frontend/browser /usr/share/nginx/html
EXPOSE 80
