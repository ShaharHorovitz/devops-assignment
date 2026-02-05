# Nginx image based on Ubuntu (required by the assignment)
FROM ubuntu:24.04

LABEL maintainer="Shahar Horovitz"

# Install nginx and openssl in a single RUN to keep the image small.
# openssl is needed for generating the self-signed TLS cert.
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx openssl && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/* /usr/share/doc/* /usr/share/man/*

# Generate self-signed certificate for HTTPS (port 8443)
RUN mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/nginx/ssl/selfsigned.key \
        -out /etc/nginx/ssl/selfsigned.crt \
        -subj "/C=IL/ST=Tel-Aviv/L=Tel-Aviv/O=DevOps-Assignment/CN=localhost"

# Copy configs
COPY nginx.conf /etc/nginx/nginx.conf
COPY sites/custom-html.conf /etc/nginx/sites-enabled/custom-html.conf
COPY sites/error-response.conf /etc/nginx/sites-enabled/error-response.conf
COPY sites/https-html.conf /etc/nginx/sites-enabled/https-html.conf

# Remove Ubuntu's default site config
RUN rm -f /etc/nginx/sites-enabled/default

COPY html/index.html /var/www/html/index.html

EXPOSE 8080 8081 8443

# Run in foreground so Docker can track the process
CMD ["nginx", "-g", "daemon off;"]
