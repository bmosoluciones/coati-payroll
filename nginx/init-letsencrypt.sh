#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 BMO Soluciones, S.A.

# =============================================================================
# Let's Encrypt SSL Certificate Initialization Script
# =============================================================================
# This script obtains SSL certificates from Let's Encrypt for nginx
#
# Usage:
#   ./init-letsencrypt.sh your-domain.com your-email@example.com
# =============================================================================

set -e

if [[ "$#" -ne 2 ]]; then
    echo "Usage: $0 <domain> <email>" >&2
    echo "Example: $0 payroll.example.com admin@example.com" >&2
    exit 1
fi

DOMAIN=$1
EMAIL=$2

echo "==================================================================="
echo "Let's Encrypt SSL Certificate Setup for Coati Payroll"
echo "==================================================================="
echo "Domain: $DOMAIN"
echo "Email:  $EMAIL"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "ERROR: docker-compose is not installed or not in PATH" >&2
    exit 1
fi

# Create directories for certbot
echo "Creating directories..."
mkdir -p ./certbot/conf
mkdir -p ./certbot/www

# Create a temporary nginx configuration for the initial certificate request
echo "Creating temporary nginx configuration..."
cat > nginx/nginx-certbot-init.conf << NGINX_CONF
upstream coati_backend {
    server web:5000;
}

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
NGINX_CONF

# Backup original nginx.conf
if [[ -f nginx/nginx.conf ]]; then
    echo "Backing up original nginx.conf..."
    cp nginx/nginx.conf nginx/nginx.conf.backup
fi

# Use temporary configuration
echo "Applying temporary nginx configuration..."
cp nginx/nginx-certbot-init.conf nginx/nginx.conf

# Start nginx with temporary configuration
echo "Starting nginx..."
docker-compose up -d nginx

# Wait for nginx to be ready
echo "Waiting for nginx to be ready..."
sleep 5

# Request certificate from Let's Encrypt
echo ""
echo "Requesting certificate from Let's Encrypt..."
echo "This may take a few minutes..."
docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

if [[ $? -eq 0 ]]; then
    echo ""
    echo "SUCCESS! Certificate obtained successfully."
    echo ""
    echo "Next steps:"
    echo "1. Restore the original nginx.conf:"
    echo "   cp nginx/nginx.conf.backup nginx/nginx.conf"
    echo ""
    echo "2. Edit nginx/nginx.conf and update 'your-domain.com' to '$DOMAIN'"
    echo ""
    echo "3. Uncomment the HTTPS server block in nginx/nginx.conf"
    echo ""
    echo "4. Restart nginx:"
    echo "   docker-compose restart nginx"
    echo ""
    
    # Restore original configuration
    if [[ -f nginx/nginx.conf.backup ]]; then
        echo "Restoring original nginx.conf..."
        mv nginx/nginx.conf.backup nginx/nginx.conf
    fi
    
    # Update domain in nginx.conf
    echo "Updating domain in nginx.conf..."
    sed -i "s/your-domain.com/$DOMAIN/g" nginx/nginx.conf
    
    echo ""
    echo "Configuration updated! Now uncomment the HTTPS server block and restart nginx."
else
    echo ""
    echo "ERROR: Failed to obtain certificate." >&2
    echo "Please check:" >&2
    echo "- Domain $DOMAIN points to this server's IP address" >&2
    echo "- Port 80 is accessible from the internet" >&2
    echo "- You have not exceeded Let's Encrypt rate limits" >&2
    echo "" >&2
    
    # Restore original configuration
    if [[ -f nginx/nginx.conf.backup ]]; then
        echo "Restoring original nginx.conf..."
        mv nginx/nginx.conf.backup nginx/nginx.conf
    fi
    
    exit 1
fi
