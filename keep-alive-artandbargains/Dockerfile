FROM alpine:3.19

# Install curl for making HTTP requests
RUN apk --no-cache add curl

# Create a directory for our script
WORKDIR /app

# Copy our ping script into the container
COPY ping.sh .

# Make the script executable
RUN chmod +x /app/ping.sh

# Run the script
CMD ["/app/ping.sh"]
