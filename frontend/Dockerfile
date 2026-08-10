# ATECH NOC Commander - Frontend Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Build stage
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files
COPY package.json yarn.lock ./

# Copy Electron
COPY electron-builder.json ./


# Install dependencies
RUN yarn install --frozen-lockfile

# Copy source code
COPY . .

# Build arguments
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Build the application
RUN yarn build

# Stage 2: Production stage with Nginx
FROM nginx:alpine as production

# Copy custom nginx configuration
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built application
COPY --from=builder /app/build /usr/share/nginx/html

# Create non-root user
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:3000/health || exit 1

# Expose port
EXPOSE 3000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
