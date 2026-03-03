# Streaver Hello World - DevOps Challenge

## Descripción del Proyecto

Este proyecto es una solución completa para el desafío técnico de DevOps/SRE Senior en Streaver. Implementa una aplicación web containerizada en Flask con infraestructura como código (IaC) utilizando tanto AWS CDK como Terraform, siguiendo las mejores prácticas de la industria para seguridad, escalabilidad y observabilidad.

### Características Principales

- **Aplicación Flask** con endpoints de health, error y metrics
- **Infraestructura como Código** dual: AWS CDK (Python) y Terraform
- **Multi-ambiente**: configuraciones separadas para dev, cert y prod
- **Testing comprehensivo**: unit tests, load tests, security scanning
- **CI/CD con GitHub Actions**: pipelines automatizados de integración y despliegue
- **Observabilidad**: logging estructurado, métricas CloudWatch, alarmas y dashboards
- **Seguridad**: escaneo con Bandit, Safety, Checkov y Trivy
- **Alta disponibilidad**: Auto-scaling, health checks, circuit breakers

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                          Internet                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ Application    │
              │ Load Balancer  │
              └───────┬────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  ECS Fargate  │           │  ECS Fargate  │
│   Task 1      │           │   Task 2      │
│  (Container)  │           │  (Container)  │
└───────────────┘           └───────────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
                      ▼
              ┌────────────────┐
              │   CloudWatch   │
              │ Logs + Metrics │
              └────────────────┘
```

### Stack Tecnológico

- **Aplicación**: Python 3.11, Flask, Gunicorn
- **Containerización**: Docker multi-stage
- **IaC**: AWS CDK (Python), Terraform
- **Servicios AWS**: ECS Fargate, ECR, ALB, VPC, CloudWatch, SNS
- **Testing**: pytest, k6, Bandit, Safety, Checkov, Trivy
- **CI/CD**: GitHub Actions con OIDC

## Quick Start

### Prerrequisitos

```bash
# Software requerido
- Python 3.11+
- Docker
- Node.js 18+ (para CDK)
- Terraform 1.5+
- AWS CLI configurado
- Git
```

### 1. Clonar el Repositorio

```bash
git clone https://github.com/pcaamano182/streaver-helloworld.git
cd streaver-helloworld
```

### 2. Ejecutar Localmente con Docker

```bash
# Build de la imagen
docker build -t streaver-helloworld:latest .

# Ejecutar el container
docker run -d -p 5000:5000 --name streaver-app streaver-helloworld:latest

# Probar endpoints
curl http://localhost:5000/
curl http://localhost:5000/health
curl http://localhost:5000/metrics
curl http://localhost:5000/error  # Devuelve 500 intencionalmente

# Ver logs
docker logs -f streaver-app

# Detener y limpiar
docker stop streaver-app
docker rm streaver-app
```

### 3. Ejecutar Tests Locales

```bash
# Crear ambiente virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Unit tests (32 tests)
pytest app/tests/ -v

# Security scan con Bandit
bandit -r app/ -c tests/security/.bandit

# Dependency scan con Safety
safety check -r requirements.txt

# Load tests con k6 (requiere Docker corriendo)
docker run --rm -i grafana/k6 run --vus 10 --duration 30s - < tests/load/k6-smoke-test.js
```

## 🔧 Despliegue con AWS CDK

### Setup Inicial

```bash
cd infrastructure/cdk

# Instalar dependencias de CDK
pip install -r requirements.txt
npm install -g aws-cdk

# Bootstrap CDK (primera vez por ambiente/región)
export AWS_PROFILE=dev
cdk bootstrap aws://ACCOUNT-ID/us-east-1

# Validar síntesis de stacks
cdk synth -c environment=dev
```

### Deploy a Desarrollo

```bash
# Configurar credenciales AWS para dev
export AWS_PROFILE=dev

# Deploy todas las stacks
cdk deploy --all -c environment=dev --require-approval never

# Deploy stack específico
cdk deploy StreamerHelloWorldNetwork-dev -c environment=dev
cdk deploy StreamerHelloWorldEcs-dev -c environment=dev
cdk deploy StreamerHelloWorldMonitoring-dev -c environment=dev

# Ver outputs (ALB URL, etc.)
cdk outputs --all -c environment=dev
```

### Deploy a Certificación

```bash
export AWS_PROFILE=cert
cdk deploy --all -c environment=cert
```

### Deploy a Producción

```bash
export AWS_PROFILE=prod
cdk deploy --all -c environment=prod
```

### Destroy (Cleanup)

```bash
# CUIDADO: Esto elimina toda la infraestructura
cdk destroy --all -c environment=dev

# Eliminar en orden inverso (recomendado)
cdk destroy StreamerHelloWorldMonitoring-dev -c environment=dev
cdk destroy StreamerHelloWorldEcs-dev -c environment=dev
cdk destroy StreamerHelloWorldNetwork-dev -c environment=dev
```

## 🔧 Despliegue con Terraform

### Setup Inicial

```bash
cd infrastructure/terraform

# Inicializar Terraform
terraform init

# Validar configuración
terraform validate

# Formatear archivos
terraform fmt -recursive
```

### Deploy a Desarrollo

```bash
# Plan (revisar cambios)
terraform plan -var-file=environments/dev.tfvars

# Apply (ejecutar cambios)
terraform apply -var-file=environments/dev.tfvars

# Ver outputs (ALB URL, etc.)
terraform output
```

### Deploy a Certificación

```bash
terraform apply -var-file=environments/cert.tfvars
```

### Deploy a Producción

```bash
terraform apply -var-file=environments/prod.tfvars
```

### Destroy (Cleanup)

```bash
# CUIDADO: Esto elimina toda la infraestructura
terraform destroy -var-file=environments/dev.tfvars
```

## Monitoreo y Observabilidad

### CloudWatch Alarms

El stack de monitoring crea automáticamente las siguientes alarmas:

- **CPU alta**: >80% durante 5 minutos → notificación SNS
- **Memoria alta**: >80% durante 5 minutos → notificación SNS
- **5XX Errors**: >10 errores en 5 minutos → notificación SNS
- **Response Time**: p99 >1s durante 5 minutos → notificación SNS
- **Unhealthy Targets**: <2 targets healthy → notificación SNS

### CloudWatch Dashboard

Acceder al dashboard desde la consola de AWS CloudWatch para ver:

- Request count y response times
- CPU y memoria utilization
- Error rates (4xx, 5xx)
- Healthy/unhealthy target count
- Auto-scaling metrics

### Logs Estructurados

Todos los logs se envían a CloudWatch Logs en formato JSON:

```json
{
  "timestamp": "2026-03-03T12:34:56.789Z",
  "level": "INFO",
  "message": "Request processed",
  "service": "streaver-helloworld",
  "method": "GET",
  "path": "/",
  "status": 200,
  "duration_ms": 15.23
}
```

### Métricas Disponibles

- `request_count`: Total de requests
- `error_count`: Total de errores
- `start_time`: Timestamp de inicio de la aplicación

## Seguridad

### Análisis Estático

```bash
# Python security (Bandit)
bandit -r app/ -c tests/security/.bandit -f json -o reports/bandit.json

# Dependency vulnerabilities (Safety)
safety check -r requirements.txt --json > reports/safety.json

# IaC security (Checkov)
checkov -d infrastructure/cdk --framework cloudformation --output json
checkov -d infrastructure/terraform --framework terraform --output json

# Container vulnerabilities (Trivy)
trivy image streaver-helloworld:latest --format json
```

### Mejores Prácticas Implementadas

- Multi-stage Docker builds con non-root user
- Private subnets para ECS tasks (sin IPs públicas)
- Security groups con least-privilege
- IAM roles con políticas mínimas necesarias
- Secrets en AWS Secrets Manager (no hardcoded)
- Escaneo automático de vulnerabilidades en CI/CD
- HTTPS/TLS en ALB (certificados ACM)
- VPC Flow Logs habilitados

## CI/CD Pipelines

### Continuous Integration (ci.yml)

Ejecuta en cada push y PR:

1. **Lint**: Flake8, Black, isort
2. **Test**: 32 unit tests con pytest
3. **Security**: Bandit + Safety
4. **Docker**: Build y scan con Trivy
5. **CDK**: Synth y tests (16 tests)
6. **Terraform**: Validate, fmt, plan
7. **IaC Security**: Checkov scan
8. **Summary**: Reporte consolidado

### Continuous Deployment

- **cd-dev.yml**: Auto-deploy a dev en merge a main
- **cd-cert.yml**: Deploy manual a cert con approval
- **cd-prod.yml**: Deploy manual a prod con multi-approval

**NOTA**: Los workflows de CD están deshabilitados por defecto (`if: false`) ya que no hay ambiente AWS disponible para este challenge. Ver [.github/workflows/README.md](.github/workflows/README.md) para instrucciones de configuración.

## Estructura del Proyecto

```
streaver-helloworld/
├── app/
│   ├── main.py                    # Aplicación Flask
│   └── tests/
│       └── test_unit.py           # 32 unit tests
├── infrastructure/
│   ├── cdk/
│   │   ├── app.py                 # CDK app entry point
│   │   ├── stacks/
│   │   │   ├── network_stack.py   # VPC, subnets, NAT
│   │   │   ├── ecs_stack.py       # ECS, ALB, auto-scaling
│   │   │   └── monitoring_stack.py # CloudWatch, SNS
│   │   ├── config/                # dev/cert/prod configs
│   │   └── tests/
│   │       └── test_stacks.py     # 16 CDK tests
│   └── terraform/
│       ├── main.tf                # Root module
│       ├── modules/
│       │   ├── networking/        # VPC module
│       │   ├── ecs/               # ECS module
│       │   └── monitoring/        # CloudWatch module
│       └── environments/          # dev/cert/prod tfvars
├── tests/
│   ├── load/
│   │   ├── k6-load-test.js        # Load test (8 min)
│   │   └── k6-smoke-test.js       # Smoke test (30s)
│   ├── security/
│   │   ├── .bandit                # Bandit config
│   │   ├── checkov.yml            # Checkov config
│   │   └── trivy.yml              # Trivy config
│   └── integration/
│       ├── validate-cdk.sh        # CDK validation
│       └── validate-terraform.sh  # Terraform validation
├── .github/
│   └── workflows/
│       ├── ci.yml                 # CI pipeline
│       ├── cd-dev.yml             # Dev deployment
│       ├── cd-cert.yml            # Cert deployment
│       └── cd-prod.yml            # Prod deployment
├── Dockerfile                     # Multi-stage build
├── requirements.txt               # App dependencies
├── requirements-dev.txt           # Dev dependencies
├── README.md                      # Este archivo
└── ASSUMPTIONS.md                 # Decisiones y trade-offs
```

## Testing

### Cobertura de Tests

- **Unit Tests**: 32 tests (100% passing)
  - Endpoints: /, /health, /error, /metrics
  - Error handling y logging
  - Metrics tracking

- **CDK Tests**: 16 tests (100% passing)
  - VPC y networking resources
  - ECS cluster, service, task definition
  - ALB, target groups, security groups
  - Auto-scaling policies
  - CloudWatch alarms y dashboard

- **Load Tests**: k6
  - Smoke test: 10 VUs, 30s
  - Load test: 100 VUs, 8min, 3 stages

- **Security Tests**:
  - Bandit: Python code scanning
  - Safety: Dependency vulnerabilities
  - Checkov: IaC security
  - Trivy: Container vulnerabilities

- **IaC Validation**:
  - CDK synth + tests
  - Terraform validate + fmt + plan

### Ejecutar Suite Completa

```bash
# Desde la raíz del proyecto
bash tests/integration/validate-all.sh
```

## Multi-Ambiente

El proyecto soporta 3 ambientes con configuraciones separadas:

| Ambiente | AWS Account | Region | Fargate Tasks | NAT Gateways | Auto-scaling |
|----------|-------------|--------|---------------|--------------|--------------|
| **dev** | 111111111111 | us-east-1 | 1 (min) - 2 (max) | 1 | Sí (CPU 70%) |
| **cert** | 222222222222 | us-east-1 | 2 (min) - 4 (max) | 1 | Sí (CPU 70%) |
| **prod** | 333333333333 | us-east-1 | 3 (min) - 10 (max) | 3 (HA) | Sí (CPU 60%) |

### Estrategia Multi-Cuenta

Se asume una arquitectura de cuentas AWS separadas por ambiente:

- **Seguridad**: Aislamiento completo entre ambientes
- **Compliance**: Controles IAM y SCPs independientes
- **Billing**: Cost allocation tags por ambiente
- **Blast radius**: Limitar impacto de cambios

Ver [ASSUMPTIONS.md](ASSUMPTIONS.md) para más detalles sobre decisiones arquitectónicas.

## Mejoras Futuras

Con más tiempo, se implementarían las siguientes mejoras:

### Infraestructura

- [ ] **Multi-región**: Despliegue activo-activo o activo-pasivo
- [ ] **WAF**: AWS WAF para protección contra ataques
- [ ] **CDN**: CloudFront para cache y distribución global
- [ ] **RDS/DynamoDB**: Base de datos para persistencia
- [ ] **ElastiCache**: Redis/Memcached para caching
- [ ] **Service Mesh**: AWS App Mesh o Istio
- [ ] **Secrets Rotation**: Rotación automática con Lambda
- [ ] **Backup**: AWS Backup para disaster recovery

### Observabilidad

- [ ] **Distributed Tracing**: AWS X-Ray o Datadog APM
- [ ] **Synthetic Monitoring**: CloudWatch Synthetics canaries
- [ ] **Log Aggregation**: OpenSearch o ELK stack
- [ ] **Custom Metrics**: Métricas de negocio con EMF
- [ ] **Anomaly Detection**: CloudWatch Anomaly Detection
- [ ] **SLIs/SLOs**: Service Level Indicators y Objectives
- [ ] **Runbooks**: Documentación de respuesta a incidentes

### CI/CD

- [ ] **GitOps**: ArgoCD o Flux para deployments
- [ ] **Feature Flags**: LaunchDarkly o AWS AppConfig
- [ ] **Canary Deployments**: Traffic shifting gradual
- [ ] **Blue/Green Testing**: Smoke tests pre-cutover
- [ ] **Rollback Automático**: En caso de health checks fallidos
- [ ] **Deployment Approvals**: Integraciones con Slack/Teams
- [ ] **Performance Testing**: K6 en pipeline con thresholds

### Seguridad

- [ ] **SIEM**: AWS Security Hub + GuardDuty
- [ ] **Compliance**: AWS Config rules
- [ ] **Penetration Testing**: Tests automatizados
- [ ] **Network Segmentation**: PrivateLink para servicios
- [ ] **Encryption**: KMS keys customer-managed
- [ ] **Certificate Management**: Renovación automática ACM
- [ ] **IAM Access Analyzer**: Análisis de permisos

### Aplicación

- [ ] **API Versioning**: /v1/, /v2/ endpoints
- [ ] **Rate Limiting**: Throttling por cliente/IP
- [ ] **Caching**: HTTP caching headers
- [ ] **Compression**: Gzip/Brotli responses
- [ ] **GraphQL**: Alternativa a REST
- [ ] **WebSockets**: Para real-time updates
- [ ] **Async Processing**: SQS + Lambda para background jobs

## Desarrollo

Este proyecto fue desarrollado como solución al desafío técnico de Streaver. Se utilizó **Claude Code** (modelo: Claude Sonnet 4.5) como herramienta de aceleración para la escritura de código, generación de tests automatizados y documentación técnica, permitiendo reducir significativamente los tiempos de implementación.

### Commits Incrementales

El historial de commits muestra el progreso iterativo:

1. `feat: add containerized Flask application with health and metrics endpoints`
2. `feat: add AWS CDK infrastructure with networking, ECS, and monitoring stacks`
3. `feat: add Terraform infrastructure with modular design`
4. `feat: add comprehensive testing suite (unit, load, security, IaC validation)`
5. `feat: add comprehensive CI/CD pipelines with GitHub Actions`
6. `docs: add final documentation (README and ASSUMPTIONS)`

## Licencia

Este proyecto es parte de un desafío técnico y no tiene licencia de uso comercial.

## Contacto

Para consultas sobre el desafío:
- **Empresa**: Streaver
- **Repositorio**: https://github.com/pcaamano182/streaver-helloworld
- **Posición**: Senior DevOps Engineer

---

**Nota**: Este README asume que no hay acceso a ambientes AWS reales para el challenge. Todas las instrucciones de deployment son teóricas pero siguen las mejores prácticas de la industria.
