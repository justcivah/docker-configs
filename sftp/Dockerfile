# Base image
FROM debian:latest

# Install necessary packages and clean apt cache
RUN apt-get update && \
    apt-get -y install openssh-server && \
    apt-get install netcat-traditional && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the scripts into the container
COPY sshd_config /etc/ssh/sshd_config
COPY .env /app/.env
COPY sftp-users.sh /app/sftp-users.sh
COPY init.sh /app/init.sh

# Make the scripts executables
RUN chmod +x sftp-users.sh
RUN chmod +x init.sh

# Create additional required directories
RUN mkdir -p /var/run/sshd /etc/sftp_users /sftp

# Expose the SFTP port
EXPOSE 22

# Add a health check
HEALTHCHECK CMD nc -zv localhost 22 || exit 1

# Create users
RUN /app/init.sh
# Start sshd in foreground
CMD ["/usr/sbin/sshd", "-D", "-e"]
