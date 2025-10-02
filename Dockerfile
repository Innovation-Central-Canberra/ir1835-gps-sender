FROM arm64v8/alpine:latest

# Install required packages
RUN apk add --no-cache python3 py3-pip

# Install pyserial using --break-system-packages to bypas PEP 668
RUN pip3 install --break-system-packages --no-cache-dir pyserial requests

# Copy application
COPY gpssender.py /app/gpssender.py
WORKDIR /app

# Make script executable
RUN chmod +x gpssender.py

# Run the GPS reader
CMD ["python3", "gpssender.py"]
