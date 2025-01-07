#!/bin/bash

# Update package index and install dependencies
sudo apt-get update
sudo apt-get install -y \
    apache2 ghostscript libapache2-mod-php php8.3 \
    php8.3-bcmath php8.3-curl php8.3-imagick php8.3-intl \
    php8.3-mbstring php8.3-mysql php8.3-xml php8.3-zip \
    unzip curl

# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify AWS CLI installation
if ! command -v aws &> /dev/null; then
    echo "AWS CLI installation failed. Exiting."
    exit 1
fi

# Fetch credentials from AWS SSM Parameter Store
export DB_USER=$(aws ssm get-parameter --name "/DB_USER" --with-decryption --query "Parameter.Value" --output text || echo "error")
export DB_PASSWORD=$(aws ssm get-parameter --name "/DB_PASSWORD" --with-decryption --query "Parameter.Value" --output text || echo "error")
export DB_HOST=$(aws ssm get-parameter --name "/DB_HOST" --with-decryption --query "Parameter.Value" --output text || echo "error")
export DB_NAME=$(aws ssm get-parameter --name "/DB_NAME" --with-decryption --query "Parameter.Value" --output text || echo "error")

# Validate SSM parameter retrieval
if [ "$DB_USER" == "error" ] || [ "$DB_PASSWORD" == "error" ] || [ "$DB_HOST" == "error" ] || [ "$DB_NAME" == "error" ]; then
    echo "Failed to fetch one or more database parameters. Exiting."
    exit 1
fi

# Set ownership for the web root directory
sudo mkdir -p /var/www/html
sudo chown -R www-data:www-data /var/www/html

# Download and extract WordPress
curl https://wordpress.org/latest.tar.gz | sudo -u www-data tar zx -C /var/www/html

# Configure Apache for WordPress
sudo touch /etc/apache2/sites-available/wordpress.conf
sudo tee /etc/apache2/sites-available/wordpress.conf << EOF
<VirtualHost *:80>
    DocumentRoot /var/www/html/wordpress
    <Directory /var/www/html/wordpress>
        Options FollowSymLinks
        AllowOverride Limit Options FileInfo
        DirectoryIndex index.php
        Require all granted
    </Directory>
    <Directory /var/www/html/wordpress/wp-content>
        Options FollowSymLinks
        Require all granted
    </Directory>
</VirtualHost>
EOF

# Enable the WordPress site and required modules
sudo a2ensite wordpress
sudo a2dissite 000-default
sudo a2enmod rewrite

# Copy and prepare WordPress configuration file
sudo -u www-data cp /var/www/html/wordpress/wp-config-sample.php /var/www/html/wordpress/wp-config.php

# Secure WordPress directory
sudo chmod -R 755 /var/www/html/wordpress
sudo -u www-data mkdir -p /var/www/html/wordpress/wp-content/uploads
sudo chmod -R 775 /var/www/html/wordpress/wp-content/uploads

# Test Apache configuration and restart
if apache2ctl configtest; then
    sudo systemctl restart apache2
else
    echo "Apache configuration test failed. Exiting."
    exit 1
fi