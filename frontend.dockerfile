# Dockerfile for frontend
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install dependencies
RUN npm install -g pnpm && pnpm install

# Copy frontend code
COPY frontend/ .

# Expose port
EXPOSE 5173

# Command to run the application
CMD ["pnpm", "run", "dev"]