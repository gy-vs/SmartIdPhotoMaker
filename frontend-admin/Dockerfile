FROM nginx:1.25-alpine

# Install font for Pillow text rendering
RUN apk add --no-cache dejavu-fonts

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY layout.html /usr/share/nginx/html/layout.html
COPY layout.js /usr/share/nginx/html/layout.js

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
