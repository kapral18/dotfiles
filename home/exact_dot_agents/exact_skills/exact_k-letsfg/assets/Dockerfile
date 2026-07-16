FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Install xvfb for headless execution and curl for uv installation
RUN apt-get update && apt-get install -y xvfb curl && rm -rf /var/lib/apt/lists/*

# Install uv (fast python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL=/usr/local/bin sh

# Install letsfg globally
RUN /usr/local/bin/uv tool install letsfg

# Execute letsfg with a virtual display
ENTRYPOINT ["/usr/bin/env", "bash", "-c", "Xvfb :99 -screen 0 1280x1024x24 & sleep 1; export DISPLAY=:99; exec /root/.local/bin/letsfg \"$@\"", "--"]