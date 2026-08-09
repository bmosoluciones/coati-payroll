# Background Queue System

Sistema de colas para ejecutar tareas en segundo plano sin bloquear la aplicación principal.

## Características principales

- ✅ **Backend soportado**: Dramatiq + Redis
- ✅ **Selección automática**: el sistema usa Dramatiq cuando Redis está disponible
- ✅ **Degradación segura**: si Redis no está disponible, usa `NoopQueueDriver` (sin background)
- ✅ **Feedback en tiempo real**: seguimiento de progreso para planillas grandes
- ✅ **Idempotencia**: bloqueo por nómina y `job_id` para evitar doble procesamiento

## Inicio rápido

### 1) Instalación

```bash
pip install -r requirements.txt
```

### 2) Configuración

```bash
export QUEUE_ENABLED=1
export REDIS_URL=redis://localhost:6379/0
export BACKGROUND_PAYROLL_THRESHOLD=100
```

### 3) Worker Dramatiq

```bash
dramatiq coati_payroll.queue.tasks --threads 8 --processes 4
```

### 4) Compose para nóminas grandes y pequeñas

La imagen tiene dos modos operativos: `PROCESS_ROLE=web` para la aplicación
HTTP y `PROCESS_ROLE=worker` para consumir trabajos desde Redis. Para escalar
consumidores:

```bash
docker compose up -d --scale worker=3
```

Las nóminas que superan `BACKGROUND_PAYROLL_THRESHOLD` se publican en la cola
`default` y las procesa Dramatiq en PostgreSQL. Las nóminas pequeñas se
calculan directamente en el proceso web. El perfil aislado valida ambos modos:

```bash
docker compose --profile loadtest run --rm loadtest-runner
docker compose --profile loadtest run --rm \
  -e PAYROLL_EMPLOYEE_COUNT=10 -e EXPECT_BACKGROUND=0 loadtest-runner
```

## Selección de backend

`get_queue_driver()` aplica esta lógica:

1. Entorno de test → `NoopQueueDriver`
2. Redis disponible + Dramatiq inicializa → `DramatiqDriver`
3. Si no → `NoopQueueDriver`

No existe fallback a Huey.

## Estructura del módulo

```text
coati_payroll/queue/
├── __init__.py
├── driver.py
├── selector.py
├── tasks.py
└── drivers/
    ├── dramatiq_driver.py
    ├── noop_driver.py
```

## Troubleshooting

### Redis no disponible

1. Verifique `REDIS_URL`
2. Verifique que Redis responda
3. Reinicie workers Dramatiq

### Tareas no se procesan

1. Verifique workers en ejecución
2. Revise logs de app y workers
3. Verifique `queue.get_stats()` y estado del driver
