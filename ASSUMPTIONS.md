# Assumptions and Design Decisions

Este documento detalla todas las decisiones arquitectónicas, asunciones y trade-offs realizados durante la implementación del desafío técnico de Streaver.

## Contexto General

### Restricciones del Challenge

1. **No hay acceso a ambiente AWS real**: Todo el desarrollo y validación se realizó localmente
2. **Dual IaC requirement**: Implementación tanto en CDK como en Terraform
3. **Timeline limitado**: Priorización de features core sobre optimizaciones avanzadas
4. **Demo/Portfolio purpose**: Balance entre simplicidad y best practices

### Herramientas de Desarrollo

**IDE y Entorno**:
- **Visual Studio Code** con extensión Claude Code integrada
- **Desarrollo local**: Todo el código, infraestructura y tests fueron desarrollados y validados localmente en Windows
- **Testing local-first**: Se priorizó la validación local antes de cada commit (Docker builds, unit tests, CDK synth, Terraform validate)

**Asistencia de IA**:

Durante la implementación se utilizó **Claude Code** (modelo: Claude Sonnet 4.5) como herramienta de aceleración en las siguientes áreas:

- **Escritura de código**: Generación rápida de código base para aplicación e infraestructura
- **Tests automatizados**: Creación de test suites (unit, security, load tests)
- **Documentación técnica**: Generación de READMEs y documentación de configuración
- **Debugging**: Resolución de issues técnicos (deprecation warnings, errores de sintaxis)

---

## Decisiones Arquitectónicas

### 1. Servicio de Compute: ECS Fargate

**Decisión**: Usar ECS Fargate en lugar de EC2, EKS o Lambda

**Razones**:
- **Serverless**: No hay gestión de instancias EC2
- **Simplicidad**: Menos complejidad operacional que EKS
- **Cost-effective**: Pay-per-use, ideal para workloads variables
- **Security**: Aislamiento a nivel de task
- **Scaling**: Auto-scaling nativo con CloudWatch metrics

**Trade-offs**:
- Más caro que EC2 para workloads 24/7 constantes
- Cold start leve vs EC2 (no relevante para este caso)
- Menos control sobre el host que con EC2

**Alternativas consideradas**:
- **EC2 + Auto Scaling Groups**: Más económico a gran escala, pero requiere gestión de OS, patching, etc.
- **EKS (Kubernetes)**: Overkill para una aplicación simple, mayor complejidad
- **Lambda**: No adecuado para API long-running, límites de timeout

### 2. Load Balancer: Application Load Balancer (ALB)

**Decisión**: ALB en lugar de NLB o CLB

**Razones**:
- **Layer 7**: Routing basado en path, host, headers
- **Health checks**: HTTP health checks inteligentes
- **Integración**: Nativa con ECS targets
- **Metrics**: Métricas detalladas en CloudWatch
- **TLS termination**: Gestión de certificados con ACM

**Trade-offs**:
- Ligeramente más caro que NLB para tráfico puro TCP
- Menor throughput que NLB (no crítico para este caso)

### 3. Networking: VPC Multi-AZ con Private Subnets

**Decisión**: Tasks ECS en private subnets, ALB en public subnets

**Razones**:
- **Security**: Tasks no tienen IPs públicas
- **Compliance**: Alineado con security frameworks (CIS, NIST)
- **Defense in depth**: Múltiples capas de seguridad
- **High Availability**: Multi-AZ para redundancia

**Configuración por ambiente**:

| Ambiente | VPC CIDR | AZs | Public Subnets | Private Subnets | NAT Gateways |
|----------|----------|-----|----------------|-----------------|--------------|
| **dev** | 10.0.0.0/16 | 2 | 2 (/24) | 2 (/24) | 1 |
| **cert** | 10.1.0.0/16 | 2 | 2 (/24) | 2 (/24) | 1 |
| **prod** | 10.2.0.0/16 | 3 | 3 (/24) | 3 (/24) | 3 |

**NAT Gateway Strategy**:

- **Dev/Cert**: 1 NAT Gateway (ahorro de costos)
  - Costo: ~$32/mes
  - Riesgo: Single point of failure para salida a internet
  - Mitigación: Acceptable para ambientes no-prod

- **Prod**: 3 NAT Gateways (uno por AZ)
  - Costo: ~$96/mes
  - Beneficio: Alta disponibilidad, sin SPOF
  - Best practice: Recomendado por AWS

**Trade-off importante**:
- NAT Gateway es costoso (~$32/mes + data transfer)
- Alternativa explorada: VPC Endpoints para S3, ECR, CloudWatch (ahorro de costos)
- Mejora futura: Implementar VPC Endpoints para reducir tráfico por NAT

### 4. Container Registry: Amazon ECR

**Decisión**: ECR en lugar de Docker Hub o registries privados

**Razones**:
- **Integración nativa**: Con ECS, IAM, y CI/CD
- **Security scanning**: Integrado con Amazon Inspector
- **Lifecycle policies**: Retention automático de imágenes
- **Private**: No hay riesgo de exposición pública
- **IAM-based auth**: Sin gestión de credentials separadas

**Configuración**:
- Image tag mutability: MUTABLE (permite latest tag)
- Scan on push: Enabled
- Lifecycle: Retener últimas 10 imágenes

### 5. Logging: CloudWatch Logs con JSON Estructurado

**Decisión**: Logs estructurados en formato JSON a CloudWatch

**Razones**:
- **Queryable**: CloudWatch Insights permite queries complejas
- **Structured**: Fácil parsing y análisis
- **Standardized**: Schema consistente
- **Integration**: Fácil export a S3, OpenSearch, etc.

**Log schema**:
```json
{
  "timestamp": "2026-03-03T12:34:56.789Z",
  "level": "INFO|ERROR|WARNING",
  "message": "Human-readable message",
  "service": "streaver-helloworld",
  "method": "GET",
  "path": "/endpoint",
  "status": 200,
  "duration_ms": 15.23,
  "error": "Error details if applicable"
}
```

**Retention por ambiente**:
- Dev: 7 días (ahorro de costos)
- Cert: 14 días
- Prod: 30 días (compliance y debugging)

**Mejora futura**: Export a S3 con Athena para análisis histórico

### 6. Monitoring: CloudWatch Metrics, Alarms y Dashboards

**Decisión**: CloudWatch nativo en lugar de third-party (Datadog, New Relic)

**Razones**:
- **Cost**: Incluido en AWS, sin costos adicionales
- **Integration**: Nativo con ECS, ALB, SNS
- **Simplicidad**: No requiere agents ni configuración compleja
- **Sufficient**: Para el scope del challenge

**Alarmas configuradas**:

| Alarma | Threshold | Evaluation Period | Action |
|--------|-----------|-------------------|--------|
| High CPU | >80% | 2 de 2 datapoints (5 min) | SNS |
| High Memory | >80% | 2 de 2 datapoints (5 min) | SNS |
| 5XX Errors | >10 errors | 1 de 1 datapoint (5 min) | SNS |
| High Latency | p99 >1s | 2 de 2 datapoints (5 min) | SNS |
| Unhealthy Targets | <2 healthy | 1 de 1 datapoint (1 min) | SNS |

**SNS Topic**: Email notifications (configurable por ambiente)

**Trade-offs**:
- Menos features que Datadog/New Relic (APM, distributed tracing)
- CloudWatch Insights no es tan potente como Splunk/ELK
- Suficiente para el 80% de casos de uso
- Mejora futura: AWS X-Ray para distributed tracing

### 7. Auto-Scaling: CPU y Memory-based

**Decisión**: Auto-scaling basado en métricas de CloudWatch

**Configuración por ambiente**:

| Ambiente | Min Tasks | Max Tasks | Target CPU | Target Memory | Scale-in Cooldown | Scale-out Cooldown |
|----------|-----------|-----------|------------|---------------|-------------------|-------------------|
| **dev** | 1 | 2 | 70% | 70% | 300s | 60s |
| **cert** | 2 | 4 | 70% | 70% | 300s | 60s |
| **prod** | 3 | 10 | 60% | 60% | 300s | 60s |

**Razones**:
- **Responsive**: Scale-out rápido (60s) para picos de tráfico
- **Conservative scale-in**: 300s para evitar flapping
- **Headroom**: Target 60-70% permite absorber picos
- **Multi-metric**: CPU y memoria para cobertura completa

**Trade-off**:
- No hay scaling basado en request rate o custom metrics
- Mejora futura: Target tracking con ALB RequestCountPerTarget

### 8. Multi-Environment Strategy: Separate AWS Accounts

**Decisión**: 3 cuentas AWS separadas (dev, cert, prod)

**Razones**:
- **Security**: Blast radius limitado por cuenta
- **Compliance**: Controles IAM/SCPs independientes
- **Billing**: Cost allocation clara por ambiente
- **Isolation**: No hay riesgo de impacto cross-environment
- **Best practice**: Recomendado por AWS Well-Architected

**Estructura asumida**:
```
AWS Organization
├── Management Account (root)
├── Dev Account (111111111111)
├── Cert Account (222222222222)
└── Prod Account (333333333333)
```

**Alternativas**:
- Single account con tags: Menos seguro, blast radius mayor
- Workspaces separados en Terraform: Aislamiento lógico pero misma cuenta

### 9. IaC Dual: CDK + Terraform

**Decisión**: Implementar AMBOS CDK y Terraform (requirement del challenge)

**CDK (AWS Cloud Development Kit)**:
- **Type safety**: Python con type hints
- **Abstractions**: L2/L3 constructs de alto nivel
- **AWS-native**: Primera clase de soporte para nuevos servicios
- **Testing**: Unit tests con CDK assertions

**Terraform**:
- **Multi-cloud**: Agnóstico de proveedor
- **Mature ecosystem**: Abundancia de módulos y examples
- **State management**: Backend S3 + DynamoDB lock
- **Plan preview**: Terraform plan para cambios

**Estructura modular**:

Ambas implementaciones siguen el mismo patrón de 3 módulos/stacks:

1. **Networking**: VPC, subnets, NAT, IGW, route tables
2. **ECS**: Cluster, service, task definition, ALB, auto-scaling
3. **Monitoring**: CloudWatch alarms, dashboard, SNS topic

**Trade-off**:
- Mantenimiento duplicado de dos codebases
- Potencial drift entre CDK y Terraform
- Demuestra versatilidad y conocimiento de ambas herramientas
- En producción real, se elegiría UNA herramienta

### 10. CI/CD: GitHub Actions con OIDC

**Decisión**: GitHub Actions en lugar de Jenkins, CircleCI, GitLab CI

**Razones**:
- **Native**: Integrado con GitHub (donde está el código)
- **Free tier**: Generoso para proyectos públicos
- **Matrix builds**: Fácil paralelización de jobs
- **Marketplace**: Amplia selección de actions reusables
- **OIDC**: Autenticación sin long-lived credentials

**OIDC vs IAM Access Keys**:
- **Security**: No hay credentials hardcoded en secrets
- **Short-lived**: Tokens expiran automáticamente
- **Auditable**: CloudTrail muestra el subject del token
- **Best practice**: Recomendado por GitHub y AWS

**Pipeline strategy**:

- **CI (ci.yml)**: 8 jobs paralelos en cada push/PR
  - Lint, Test, Security, Docker, CDK, Terraform, IaC-Security, Summary
  - Tiempo estimado: ~8-10 minutos

- **CD Dev (cd-dev.yml)**: Auto-deploy en merge a main
  - Build → Push ECR → Deploy CDK/Terraform → Smoke tests

- **CD Cert (cd-cert.yml)**: Manual trigger con approval
  - Promoción de imagen desde dev ECR
  - Requiere approval de DevOps lead

- **CD Prod (cd-prod.yml)**: Strict manual con multi-approval
  - Requiere image tag explícito (no latest)
  - Requiere aprobación de 2+ reviewers
  - Pre-deployment validation checks

**Nota importante**:
- Todos los jobs de deploy están deshabilitados (`if: false`) porque no hay AWS disponible
- Se incluyen placeholder jobs con instrucciones de setup
- En un ambiente real, se habilitarían tras configurar OIDC + secrets

---

## Decisiones de Seguridad

### 1. Multi-Stage Docker Build

**Decisión**: Build multi-stage con non-root user

```dockerfile
# Stage 1: Builder (con gcc, herramientas de build)
FROM python:3.11-slim as builder
...

# Stage 2: Runtime (solo runtime, sin build tools)
FROM python:3.11-slim
...
USER appuser  # Non-root!
```

**Razones**:
- **Smaller image**: Runtime image ~150MB vs ~500MB monolítico
- **Security**: Sin herramientas de build en imagen final
- **Non-root**: Principio de least privilege
- **Attack surface**: Menor superficie de ataque

### 2. Security Scanning Multi-Layer

**Decisión**: 4 herramientas de scanning complementarias

| Tool | Scope | Execution |
|------|-------|-----------|
| **Bandit** | Python code (SAST) | CI pipeline |
| **Safety** | Python dependencies (SCA) | CI pipeline |
| **Checkov** | IaC (CDK/Terraform) | CI pipeline |
| **Trivy** | Container vulnerabilities | CI pipeline |

**Razones**:
- **Defense in depth**: Múltiples capas de detección
- **Shift-left**: Detectar issues antes de deploy
- **Compliance**: Alineado con DevSecOps practices
- **SARIF export**: Integración con GitHub Security tab

**Configuración**:
- Bandit: Exclude tests, skip low-severity binds
- Checkov: Skip checks para dev environment shortcuts
- Trivy: Scan OS + app dependencies

### 3. Secrets Management

**Decisión**: AWS Secrets Manager (en implementación futura)

**Razones**:
- **Rotation**: Rotación automática programable
- **Audit**: CloudTrail logging de accesos
- **Encryption**: KMS encryption at rest
- **IAM integration**: Fine-grained access control

**Nota**: En este challenge no hay secrets reales, pero la estructura está preparada para:

```python
# Example future implementation
secret_arn = secretsmanager.Secret(self, "AppSecret", ...)
task_definition.add_secret(
    secret_name="DB_PASSWORD",
    secret=ecs.Secret.from_secrets_manager(secret_arn)
)
```

### 4. Network Security

**Decisión**: Defense in depth con múltiples capas

**Security Groups**:

- **ALB SG**:
  - Inbound: 80/443 desde 0.0.0.0/0 (internet)
  - Outbound: Ephemeral ports a ECS SG

- **ECS SG**:
  - Inbound: 5000 solo desde ALB SG
  - Outbound: 443 a internet (para pulls de ECR, CloudWatch)

**NACLs**: Default (no custom, SGs son suficientes)

**Razones**:
- **Least privilege**: Solo puertos necesarios
- **Source restriction**: ECS solo accesible desde ALB
- **Stateful**: SGs manejan return traffic automáticamente

### 5. IAM Roles: Least Privilege

**Decisión**: Separate roles para ECS Task y Task Execution

**ECS Task Role** (runtime de la app):
- Permissions: CloudWatch Logs, CloudWatch Metrics
- NO permissions para: ECR, Secrets Manager (aún)

**ECS Task Execution Role** (ECS agent):
- Permissions: ECR pull, CloudWatch Logs create stream
- Managed policy: AmazonECSTaskExecutionRolePolicy

**Razones**:
- **Separation of concerns**: Runtime vs infrastructure
- **Least privilege**: Solo permisos necesarios
- **Audit**: Fácil rastrear qué role hizo qué acción

---

## Decisiones de Testing

### 1. Unit Tests: Pytest con 100% Coverage de Endpoints

**Decisión**: 32 tests comprehensivos para la app Flask

**Cobertura**:
- Todos los endpoints (/, /health, /error, /metrics)
- Error handling y status codes
- Metrics tracking (increment, retrieval)
- Structured logging format
- JSON response validation

**Razones**:
- **Confidence**: Alta confianza en funcionalidad core
- **Regression**: Detectar breaking changes
- **Documentation**: Tests como spec ejecutable

### 2. CDK Tests: Unit Tests de Infraestructura

**Decisión**: 16 tests con CDK assertions

**Cobertura**:
- VPC con subnets públicas y privadas
- ECS cluster, service, task definition
- ALB, target group, listeners
- Auto-scaling policies
- CloudWatch alarms y dashboard

**Razones**:
- **Prevent regressions**: Detectar cambios no intencionados
- **Fast feedback**: Tests ejecutan en ~5s
- **Documentation**: Tests describen la arquitectura

**Trade-off**:
- No hay integration tests (requieren AWS real)
- Mejora futura: LocalStack para integration tests

### 3. Load Tests: K6 con Two-Phase Approach

**Decisión**: Smoke test (30s) + Load test (8 min)

**Smoke test**:
- 10 VUs, 30 segundos
- Quick validation de endpoints
- Thresholds relajados

**Load test**:
- Stage 1: Ramp-up a 50 VUs (2 min)
- Stage 2: Sustained 100 VUs (4 min)
- Stage 3: Ramp-down a 0 VUs (2 min)
- Thresholds: p95 <500ms, p99 <1s

**Razones**:
- **Realistic**: Simula tráfico real con ramp-up/down
- **Scalability validation**: Verifica auto-scaling
- **Performance SLOs**: Define thresholds claros

**Trade-off**:
- Requiere app corriendo (no se puede ejecutar sin AWS)
- Mejora futura: Incluir en CD pipeline con ambiente efímero

### 4. Security Scanning: Multiple Tools, Different Scopes

**Decisión**: Ver sección de Seguridad arriba

### 5. IaC Validation: Synth/Validate + Plan

**Decisión**: Scripts de validación para CDK y Terraform

**CDK validation**:
```bash
cdk synth --all -c environment=dev
pytest infrastructure/cdk/tests/
```

**Terraform validation**:
```bash
terraform init
terraform validate
terraform fmt -check
terraform plan -var-file=environments/dev.tfvars
```

**Razones**:
- **Syntax validation**: Detectar errores básicos
- **Type checking**: CDK tiene ventaja aquí (Python types)
- **Plan preview**: Terraform plan muestra cambios exactos

**Limitación**:
- Sin AWS, no se puede hacer `cdk deploy` o `terraform apply`
- Validación sintáctica y lógica es suficiente para challenge

---

## Decisiones de Cost Optimization

### 1. NAT Gateway: Single for Dev/Cert, Multi for Prod

**Ahorro anual**: ~$768 en dev + cert

| Ambiente | NAT Gateways | Costo mensual | Costo anual |
|----------|--------------|---------------|-------------|
| Dev | 1 | $32 | $384 |
| Cert | 1 | $32 | $384 |
| Prod | 3 | $96 | $1,152 |

**Mejora futura**: VPC Endpoints (S3, ECR, CloudWatch)
- Costo: ~$7/mes por endpoint
- Ahorro: Reduce data transfer por NAT (~50-70%)
- ROI: Positivo en ambientes con alto tráfico

### 2. Fargate Spot: Considerado pero NO Implementado

**Decisión**: NO usar Fargate Spot (aún)

**Razones**:
- **Simplicity first**: Fargate on-demand es predecible
- Spot puede interrumpir tasks sin aviso (2 min warning)
- Requiere graceful shutdown handling

**Mejora futura**: Mix 70% On-demand + 30% Spot
- Ahorro: ~30% en compute costs
- Riesgo: Mitigado con circuit breakers y health checks

### 3. CloudWatch Logs: Retention Policy por Ambiente

**Ahorro**: Variable según tráfico

| Ambiente | Retention | Cost Impact |
|----------|-----------|-------------|
| Dev | 7 días | Bajo (pocas requests) |
| Cert | 14 días | Medio |
| Prod | 30 días | Justificado (compliance) |

**Mejora futura**: Export a S3 + Athena
- Costo S3: ~$0.023/GB/mes (vs $0.50/GB CloudWatch)
- Ahorro: ~95% para logs históricos

### 4. ECR Lifecycle: Retener Solo Últimas 10 Imágenes

**Ahorro**: Previene acumulación ilimitada

**Policy**:
```json
{
  "rules": [{
    "rulePriority": 1,
    "description": "Keep last 10 images",
    "selection": {
      "tagStatus": "any",
      "countType": "imageCountMoreThan",
      "countNumber": 10
    },
    "action": { "type": "expire" }
  }]
}
```

**Razones**:
- **Sufficient**: 10 imágenes cubren 2+ semanas de deploys
- **Automatic**: No requiere manual cleanup
- **Cost**: Evita costos de storage innecesarios

### 5. Right-Sizing: Task Resources por Ambiente

| Ambiente | vCPU | Memory | Costo/hora | Justificación |
|----------|------|--------|------------|---------------|
| Dev | 0.25 | 512 MB | $0.012 | Tráfico bajo |
| Cert | 0.5 | 1024 MB | $0.024 | Testing realista |
| Prod | 1 | 2048 MB | $0.073 | Performance + headroom |

**Mejora futura**: CloudWatch Container Insights
- Analizar utilización real
- Right-size basado en datos históricos
- Potencial ahorro: 20-30%

---

## Decisiones de CI/CD

### 1. Pipeline Strategy: CI Every Push, CD Manual (Mostly)

**CI Pipeline (ci.yml)**:
- Trigger: Every push + PR
- Duration: ~8-10 minutos
- Jobs: 8 paralelos (lint, test, security, docker, cdk, terraform, iac-security, summary)

**CD Pipelines**:
- **Dev**: Auto en merge a main (if: false por ahora)
- **Cert**: Manual trigger con approval
- **Prod**: Manual trigger con multi-approval + explicit tag

**Razones**:
- **Fast feedback**: CI rápido detecta issues early
- **Control**: CD manual evita deploys accidentales
- **Safety**: Producción requiere múltiples approvals

### 2. Image Promotion: Build Once, Deploy Many

**Decisión**: Build en dev, promocionar misma imagen a cert/prod

**Flow**:
```
main branch
  ↓
Build + Push → dev-ecr/app:git-abc123
  ↓
[Tests pass]
  ↓
Tag → cert-ecr/app:git-abc123  (copy)
  ↓
[Approval + Validation]
  ↓
Tag → prod-ecr/app:git-abc123  (copy)
```

**Razones**:
- **Immutability**: Misma imagen en todos los ambientes
- **Speed**: No rebuild, solo copy/retag
- **Confidence**: Lo que se testea en dev/cert va a prod
- **Traceability**: Git SHA en tag

### 3. OIDC Authentication: No Long-Lived Credentials

**Setup asumido**:

```yaml
# En GitHub Actions
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::111111111111:role/GitHubActionsRole
    aws-region: us-east-1
```

**IAM Trust Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:sub": "repo:pcaamano182/streaver-helloworld:ref:refs/heads/main"
      }
    }
  }]
}
```

**Razones**:
- **Security**: No hay AWS_ACCESS_KEY_ID/SECRET en GitHub secrets
- **Audit**: CloudTrail muestra el repo/branch en cada call
- **Rotation**: No hay credentials para rotar
- **Best practice**: Recomendado por GitHub y AWS

### 4. Rollback Strategy: Blue/Green con Circuit Breaker

**Decisión**: Deployment circuit breaker habilitado

```python
deployment_configuration=ecs.DeploymentConfiguration(
    maximum_percent=200,  # Blue/Green: ambos task sets activos
    minimum_healthy_percent=100,  # No downtime
    deployment_circuit_breaker=ecs.DeploymentCircuitBreaker(
        enable=True,
        rollback=True  # Auto-rollback en failure
    )
)
```

**Razones**:
- **Zero downtime**: 100% healthy durante deploy
- **Auto-rollback**: Detecta fallos y vuelve atrás
- **Safety net**: Evita deploys broken en producción

**Mejora futura**: Canary deployments con CodeDeploy
- 10% → 50% → 100% traffic shift
- Automated rollback basado en CloudWatch alarms

---

## Mejoras Futuras (Con Más Tiempo)

### Infraestructura

#### 1. Multi-Region Active-Active

**Implementación**:
- Route 53 con health checks y failover
- DynamoDB global tables
- S3 cross-region replication
- CloudFront con múltiples origins

**Beneficios**:
- Disaster recovery (RTO < 5 min, RPO < 1 min)
- Latency reduction para usuarios globales
- Compliance con data residency requirements

**Costo estimado**: +150% (2.5x debido a duplicación + networking)

#### 2. AWS WAF + Shield

**Implementación**:
- WAF en ALB con managed rule groups
- Rate limiting por IP
- Geo-blocking para países de alto riesgo
- Shield Standard (incluido) o Advanced ($3k/mes)

**Beneficios**:
- Protección contra OWASP Top 10
- DDoS mitigation
- Bot detection

**Costo estimado**: $5-10/mes (WAF) o $3k/mes (Shield Advanced)

#### 3. Service Mesh (AWS App Mesh o Istio)

**Implementación**:
- Sidecar proxies (Envoy)
- mTLS entre servicios
- Traffic shaping (circuit breakers, retries, timeouts)
- Distributed tracing integration

**Beneficios**:
- Zero trust networking
- Advanced traffic management
- Observability mejorada

**Trade-off**: Complejidad operacional +40%

#### 4. Database Layer

**Opción 1: RDS PostgreSQL**
- Multi-AZ para HA
- Read replicas para scale-out
- Automated backups (PITR 35 días)

**Opción 2: DynamoDB**
- Serverless, auto-scaling
- Global tables para multi-region
- DynamoDB Streams para CDC

**Decisión**: Depende de workload (relacional vs NoSQL)

#### 5. Caching Layer (ElastiCache)

**Implementación**:
- Redis cluster mode
- 3 nodos (Multi-AZ)
- Cache-aside pattern

**Beneficios**:
- Reduce latencia (sub-millisecond)
- Reduce carga en database
- Session storage para múltiples tasks

**Costo estimado**: $50-100/mes (cache.t3.micro)

### Observabilidad

#### 1. Distributed Tracing (AWS X-Ray)

**Implementación**:
```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

xray_recorder.configure(service='streaver-helloworld')
XRayMiddleware(app, xray_recorder)
```

**Beneficios**:
- Request flow visualization
- Latency breakdown (ALB → ECS → downstream services)
- Error root cause analysis

**Costo**: ~$5/million traces (primeros 100k free)

#### 2. Synthetic Monitoring (CloudWatch Synthetics)

**Implementación**:
- Canaries ejecutando cada 5 minutos
- Multi-region probes
- Assertions sobre response time, status, content

**Beneficios**:
- Proactive monitoring (detecta issues antes que usuarios)
- SLA validation
- Third-party endpoint monitoring

**Costo**: ~$0.001/run (~$8/mes por canary)

#### 3. Log Aggregation (OpenSearch)

**Implementación**:
- CloudWatch Logs → Lambda → OpenSearch
- Kibana dashboards
- Alerting rules

**Beneficios**:
- Advanced queries (vs CloudWatch Insights)
- Visualizaciones custom
- Correlation cross-service

**Costo**: $50-200/mes (t3.small.search)

**Alternativa**: Managed Grafana + Loki (más económico)

#### 4. SLIs/SLOs/Error Budgets

**Definición**:
```yaml
SLOs:
  - name: Availability
    target: 99.9%
    window: 30d
    SLI: successful_requests / total_requests

  - name: Latency
    target: 95% < 500ms
    window: 7d
    SLI: p95_latency
```

**Beneficios**:
- Objetive reliability targets
- Error budget como guía para velocity vs stability
- Stakeholder alignment

**Herramientas**: Prometheus + Grafana + sloth, o herramienta custom

### Seguridad

#### 1. SIEM (Security Information and Event Management)

**Implementación**:
- AWS Security Hub (aggregator)
- GuardDuty (threat detection)
- Config Rules (compliance)
- CloudTrail (audit logs)

**Beneficios**:
- Centralized security posture
- Threat detection automático
- Compliance reporting (PCI, HIPAA, etc.)

**Costo**: $5-20/mes (depende de volume)

#### 2. Runtime Security (Falco o AWS GuardDuty Runtime Monitoring)

**Implementación**:
- Sidecar en ECS tasks
- Detección de comportamiento anómalo
- Alertas en tiempo real

**Beneficios**:
- Detect container escape attempts
- Unauthorized process execution
- Network anomalies

**Costo**: $10-30/task/mes

#### 3. Secrets Rotation Automática

**Implementación**:
```python
secret = secretsmanager.Secret(
    self, "DBPassword",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        secret_string_template='{"username":"admin"}',
        generate_string_key="password"
    )
)

# Lambda para rotación cada 30 días
secret.add_rotation_schedule(
    "RotationSchedule",
    automatically_after=Duration.days(30),
    rotation_lambda=rotation_function
)
```

**Beneficios**:
- Reduce risk de credential compromise
- Compliance con security policies
- Zero-touch automation

#### 4. Network Segmentation (PrivateLink)

**Implementación**:
- VPC Endpoints para servicios AWS (S3, ECR, Secrets Manager)
- PrivateLink para servicios internos
- No traffic por internet

**Beneficios**:
- Data exfiltration prevention
- Reduce attack surface
- Ahorro en NAT Gateway costs

**Costo**: $7/mes por endpoint + $0.01/GB

### CI/CD

#### 1. GitOps con ArgoCD o Flux

**Implementación**:
- Git como single source of truth
- Automatic sync cada 3 minutos
- Drift detection y remediation

**Beneficios**:
- Declarative deployments
- Audit trail (Git history)
- Easy rollback (git revert)

**Trade-off**: Requiere Kubernetes (no compatible con ECS)

#### 2. Feature Flags (AWS AppConfig o LaunchDarkly)

**Implementación**:
```python
from appconfig import AppConfigClient

client = AppConfigClient()
if client.get_flag('new-feature-enabled'):
    # New code path
else:
    # Old code path
```

**Beneficios**:
- Deploy code != enable feature
- Progressive rollout (10% → 50% → 100%)
- Kill switch para features problemáticas

**Costo**: $0 (AppConfig) o $10-100/mes (LaunchDarkly)

#### 3. Canary Deployments con AWS CodeDeploy

**Implementación**:
```yaml
deployment_config:
  type: Canary10Percent5Minutes
  # 10% traffic → wait 5 min → 100%
  # Auto-rollback si CloudWatch alarm se dispara
```

**Beneficios**:
- Reduce blast radius de bugs
- Automated rollback
- Real traffic validation

**Mejora sobre**: Blue/Green (más granular)

#### 4. Performance Testing en Pipeline

**Implementación**:
```yaml
- name: Load Test
  run: |
    k6 run --vus 100 --duration 5m tests/load/k6-load-test.js
    # Fail build si p95 > 500ms
```

**Beneficios**:
- Detect performance regressions
- SLO validation pre-production
- Capacity planning data

**Trade-off**: Requiere ambiente efímero o long-running staging

---

## Lecciones Aprendidas

### 1. Deprecation Warnings Matter

**Issue**: CDK tenía 4 deprecation warnings inicialmente

**Fix**:
- `datetime.utcnow()` → `datetime.now(timezone.utc)`
- `alb.metric_*()` → `alb.metrics.*`
- `RetentionDays` integer → enum mapping

**Lesson**: Resolver warnings early evita breaking changes futuros

### 2. Terraform Syntax Is Strict

**Issue**: `deployment_configuration` block inválido

```terraform
# ❌ Incorrecto
deployment_configuration {
  deployment_circuit_breaker {
    enable = true
    rollback = true
  }
}

# ✅ Correcto
deployment_circuit_breaker {
  enable = true
  rollback = true
}
```

**Lesson**: Consultar docs oficiales, no asumir sintaxis

### 3. Security Scanning Needs Tuning

**Issue**: Bandit reportó 80 LOW warnings (ruido)

**Fix**: Config file `.bandit` con excludes:
```yaml
exclude_dirs:
  - '/tests/'
  - '/.venv/'
```

**Lesson**: Security tools requieren tuning para evitar alert fatigue

### 4. Test Validation Before Commit

**Issue**: User preguntó "pudiste correr estos tests?" en Phase 4

**Lesson**: SIEMPRE validar tests localmente antes de commit, no asumir que pasan

### 5. Documentation Is As Important As Code

**Effort distribution**:
- Code: ~60%
- Tests: ~20%
- Documentation: ~20%

**Lesson**: README comprehensivo es crítico para onboarding y mantenibilidad

---

## Conclusión

Este proyecto demuestra una implementación production-ready siguiendo best practices de:

- **Infrastructure as Code**: Modular, testeable, reproducible
- **Security**: Defense in depth, least privilege, automated scanning
- **Observability**: Structured logs, metrics, alarms, dashboards
- **Reliability**: Multi-AZ, auto-scaling, health checks, circuit breakers
- **CI/CD**: Automated testing, security scanning, deployment pipelines
- **Cost Optimization**: Right-sizing, lifecycle policies, retention tuning

Las mejoras futuras listadas arriba transformarían este proyecto de un "good enough" MVP a un sistema enterprise-grade capaz de manejar millones de requests con alta disponibilidad y compliance estricto.

---

**Desarrollado para el desafío técnico de Streaver - Senior DevOps Engineer**
