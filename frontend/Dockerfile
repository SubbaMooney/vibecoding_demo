# Frontend React PWA Dockerfile
FROM node:18-alpine as base

# Set working directory
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# =============================================================================
# Development Stage
# =============================================================================
FROM base as development

# Install all dependencies including dev
RUN npm ci

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev"]

# =============================================================================
# Build Stage
# =============================================================================
FROM base as build

# Install all dependencies
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# =============================================================================
# Production Stage
# =============================================================================
FROM nginx:alpine as production

# Copy built application
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

# =============================================================================
# Build Target Selection
# =============================================================================
ARG BUILD_TARGET=development
FROM (${BUILD_TARGET}) as final