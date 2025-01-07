#!/bin/bash

# Update package index and install dependencies
sudo apt-get update
sudo apt-get install -y \
    apache2 ghostscript libapache2-mod-php php8.3 \
    php8.3-bcmath php8.3-curl php8.3-imagick php8.3-intl \
    php8.3-mbstring php8.3-mysql php8.3-xml php8.3-zip

# Set ownership for the web root directory
sudo mkdir -p /var/www/html
sudo chown www-data: /var/www/html

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

# Restart Apache to apply changes
sudo systemctl restart apache2