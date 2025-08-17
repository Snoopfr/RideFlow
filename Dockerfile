# RideFlow Dockerfile
FROM php:8.2-apache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libzip-dev \
    zip \
    unzip \
    libxml2-dev \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
RUN docker-php-ext-install \
    zip \
    xml \
    simplexml \
    curl

# Enable Apache modules
RUN a2enmod rewrite headers

# Configure Apache
COPY ./docker/apache.conf /etc/apache2/sites-available/000-default.conf
RUN a2dissite 000-default.conf && a2ensite 000-default.conf

# Set working directory
WORKDIR /var/www/html

# Copy application files (This must be done before setting permissions)
COPY . /var/www/html/

# Create necessary directories and set permissions in one block
RUN mkdir -p /var/www/html/tmp && \
    chown -R www-data:www-data /var/www/html && \
    chmod -R 755 /var/www/html && \
    chmod -R 777 /var/www/html/uploads && \
    chmod -R 777 /var/www/html/cache && \
    chmod -R 777 /var/www/html/tmp && \
    chmod -R 777 /var/www/html/logs

# Configure PHP settings in one go
RUN echo "upload_max_filesize = 50M" >> /usr/local/etc/php/conf.d/uploads.ini && \
    echo "post_max_size = 50M" >> /usr/local/etc/php/conf.d/uploads.ini && \
    echo "upload_tmp_dir = /var/www/html/tmp" >> /usr/local/etc/php/conf.d/uploads.ini && \
    echo "max_execution_time = 300" >> /usr/local/etc/php/conf.d/uploads.ini && \
    echo "memory_limit = 1024M" >> /usr/local/etc/php/conf.d/uploads.ini && \
    echo "allow_url_fopen = On" >> /usr/local/etc/php/conf.d/uploads.ini

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Expose port
EXPOSE 80

# Start Apache
CMD ["apache2-foreground"]