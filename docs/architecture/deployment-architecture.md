# Deployment Architecture

## 1. Kubernetes Deployment

```yaml
# Deployment Configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-rag-server
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
      - name: api-gateway
        image: mcp-rag/api:latest
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## 2. Edge Deployment for Mobile

```yaml
# CloudFlare Workers Configuration
edge_workers:
  - name: mobile-preprocessor
    routes:
      - pattern: /api/mobile/*
    script: |
      addEventListener('fetch', event => {
        event.respondWith(handleMobileRequest(event.request))
      })
      
      async function handleMobileRequest(request) {
        // Lightweight processing at edge
        const simplified = await simplifyForMobile(request)
        return fetch(origin, simplified)
      }
```

## 3. Multi-Region Architecture

```mermaid
graph TB
    subgraph "US-EAST"
        US_LB[Load Balancer]
        US_API[API Servers]
        US_DB[(PostgreSQL Primary)]
        US_QDRANT[(Qdrant Cluster)]
    end
    
    subgraph "EU-WEST"
        EU_LB[Load Balancer]
        EU_API[API Servers]
        EU_DB[(PostgreSQL Replica)]
        EU_QDRANT[(Qdrant Cluster)]
    end
    
    subgraph "APAC"
        AP_LB[Load Balancer]
        AP_API[API Servers]
        AP_DB[(PostgreSQL Replica)]
        AP_QDRANT[(Qdrant Cluster)]
    end
    
    CDN[Global CDN] --> US_LB
    CDN --> EU_LB
    CDN --> AP_LB
    
    US_DB -.->|Replication| EU_DB
    US_DB -.->|Replication| AP_DB
    
    US_QDRANT -.->|Sync| EU_QDRANT
    US_QDRANT -.->|Sync| AP_QDRANT
```

---
