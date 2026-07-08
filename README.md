# Caja Moments

Sistema operativo para salones de eventos: caja diaria, cuentas, cierres,
proveedores, personal eventual, impuestos, recordatorios, eventos, presupuestos,
cobranzas por Mercado Pago, venta publica de tarjetas de egresados y reportes.

## Estado auditado

Auditoria local ejecutada el **2026-07-08** sobre `main` en el commit
`15920cc`.

| Area | Estado |
|---|---|
| Backend | Django/DRF funcional; 34 tests pasan. |
| Frontend | React/Vite compila para produccion. |
| Base de datos | Migraciones al dia; SQLite local y PostgreSQL por `DATABASE_URL`. |
| Seguridad prod | `manage.py check --deploy` pasa con variables productivas. |
| Seguridad deps | `npm audit --omit=dev` falla por Vite/esbuild dev-server advisories. |
| Integraciones | Mercado Pago esta implementado, pero falta validacion end-to-end en sandbox/live. |

### Que falta

- CI basico: correr tests backend, migration check, build frontend y audit de
  dependencias en cada pull request.
- Pruebas frontend: hoy no hay unit tests, accesibilidad automatizada ni smoke
  E2E autenticado.
- Rate limiting o proteccion equivalente en endpoints publicos de pago.
- Validacion real de Mercado Pago sandbox/live: checkout, webhook, refund y
  chargeback.
- Definicion legal/fiscal de recibos: los PDF actuales son comprobantes internos.
- Backup/restore documentado y probado para produccion.
- OpenAPI/Swagger o contrato API generado para integraciones externas.
- Eliminacion del CDN de Bootstrap cuando las grillas restantes migren a MUI.

### Donde falla o tiene deuda

- `npm audit --omit=dev` reporta 2 vulnerabilidades en la cadena Vite/esbuild;
  `npm audit fix --force` propone salto mayor a Vite 8, asi que no conviene
  aplicarlo a ciegas.
- La venv local usa Python 3.9 con LibreSSL; `urllib3` avisa que espera OpenSSL
  1.1.1+. No rompe tests, pero conviene mover el entorno local a Python 3.11+
  con OpenSSL moderno.
- El cierre de evento congela totales, pero no bloquea todas las ediciones
  relacionadas de presupuesto/proveedores/personal/caja.
- La auditoria registra resumen de acciones, no diffs completos antes/despues.
- `frontend/src/App.jsx`, `backend/cashflow/services.py`,
  `backend/cashflow/views.py`, `backend/cashflow/models.py` y
  `backend/cashflow/tests.py` concentran casi todo el sistema; funciona, pero
  ya limita mantenimiento.
- El deploy de desarrollo sin variables productivas muestra warnings esperables
  de Django (`DEBUG`, `SECRET_KEY`, cookies seguras, HSTS). En produccion debe
  usarse la configuracion segura documentada.

## Stack

- **Backend:** Django 4.2, Django REST Framework, django-filter.
- **Frontend:** React 18 + Vite, Material UI, CSS propio.
- **Compatibilidad UI pendiente:** Bootstrap 5 por CDN para grillas heredadas.
- **Base local:** SQLite.
- **Base produccion:** PostgreSQL via `DATABASE_URL`.
- **Autenticacion:** token DRF y sesion Django.
- **Dinero:** `DecimalField`; no se usa `FloatField`.
- **Zona horaria:** `America/Argentina/Mendoza`.

## Arquitectura

```text
backend/
  config/              Configuracion Django
  cashflow/            Dominio, API, servicios, admin, migraciones y tests
  build.sh             Build para Render
  start.sh             Migraciones, seeds y Gunicorn en Render
frontend/
  src/App.jsx          SPA operativa
  src/styles.css       Estilos propios
docs/
  adr/                 Decisiones tecnicas
  worklog/             Bitacora de cambios
  PROJECT_STATE.md     Estado actual del proyecto
render.yaml            Blueprint Render: API, DB y frontend estatico
```

## Modulos funcionales

- Acceso, permisos y healthcheck.
- Dashboard operativo con saldos, flujo diario, pendientes y alertas.
- Caja diaria con ingresos, egresos, ajustes, anulacion y PDF de comprobante.
- Cuentas, billeteras, transferencias y cierres diarios por cuenta.
- Proveedores, ledger, deudas, pagos y saldos a favor.
- Personal eventual, roles, asignaciones, pagos y pendientes.
- Clientes, eventos, Evento 360, presupuestos, items opcionales y cierre.
- Cobranzas online de eventos por Mercado Pago.
- Venta publica de tarjetas de egresados por Mercado Pago.
- Impuestos, recordatorios, pagos recurrentes y reportes.
- Auditoria central resumida.

## Reglas de negocio clave

- `CashMovement` es el libro canonico de dinero real.
- Solo movimientos `CONFIRMED` impactan saldos.
- Los movimientos no se borran; se anulan con estado `VOIDED`.
- El cierre diario por cuenta bloquea nuevos movimientos en esa cuenta/fecha.
- Las transferencias crean movimientos espejo `TRANSFER_OUT` y `TRANSFER_IN`.
- Proveedores, empleados, impuestos, eventos y Mercado Pago terminan en caja.
- Un pago aprobado de Mercado Pago crea una sola cobranza de caja.
- Refunds y chargebacks crean una sola reversa cuando existe cobranza previa.
- El total de un evento sale del presupuesto: item base `Evento` + opcionales.
- Los links publicos exponen solo contexto de pago; la operatoria staff requiere
  autenticacion y `is_staff`.
- USD se maneja como cuenta separada; no hay conversion automatica a ARS.

## Modelo de datos resumido

| Area | Modelos principales |
|---|---|
| Caja | `Account`, `MovementCode`, `CashMovement`, `AccountTransfer`, `DailyCashCloseGroup`, `DailyAccountClose` |
| Proveedores | `Provider`, `ProviderLedgerEntry` |
| Personal | `Employee`, `EmployeeRole`, `EventStaffAssignment`, `EmployeePayment` |
| Eventos | `Client`, `Event`, `EventBudget`, `EventBudgetItem`, `EventBudgetPayment` |
| Mercado Pago | `EventBudgetPaymentWebhookLog`, `TicketPurchaseWebhookLog` |
| Egresados | `GraduationEvent`, `GraduationTicketPrice`, `Graduate`, `TicketPurchase` |
| Operacion | `ServiceType`, `TaxType`, `TaxPayment`, `Reminder`, `AuditLogEntry` |

## API

Base local:

```text
http://localhost:8000/api/
```

Endpoints principales:

```text
/api/auth/login/
/api/auth/me/
/api/auth/logout/
/api/health/
/api/dashboard/
/api/accounts/
/api/cash-movements/
/api/account-transfers/
/api/daily-cash-closes/
/api/daily-account-closes/
/api/providers/
/api/provider-ledger/
/api/employees/
/api/employee-roles/
/api/clients/
/api/events/
/api/event-budgets/
/api/event-budget-items/
/api/event-budget-payments/
/api/event-budget-payments/create-preference/
/api/event-budget-payments/webhook/
/api/event-payments/{token}/public/
/api/event-payments/{token}/create-preference/
/api/graduation-events/
/api/graduation-events/{token}/public/
/api/graduation-events/{token}/graduates/search/
/api/graduation-ticket-prices/
/api/graduates/
/api/ticket-purchases/
/api/ticket-purchases/create-preference/
/api/ticket-purchases/manual/
/api/ticket-purchases/webhook/
/api/service-types/
/api/service-payments/
/api/tax-types/
/api/tax-payments/
/api/reminders/
/api/reports/
/api/audit-log/
```

Reportes:

```text
/api/reports/daily-cash-summary/
/api/reports/account-balances/
/api/reports/income-vs-expense/
/api/reports/expense-by-code/
/api/reports/provider-expenses/
/api/reports/provider-balances/
/api/reports/providers-with-credit/
/api/reports/staff-by-event/
/api/reports/taxes-paid/
/api/reports/employee-payments/
/api/reports/taxes-due/
/api/reports/voided-movements/
/api/reports/transfers/
/api/reports/event-summary/
```

## Backend local

Crear entorno e instalar dependencias:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Migrar y cargar datos maestros:

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py seed_initial_data --skip-examples
```

Crear usuario admin:

```bash
../.venv/bin/python manage.py createsuperuser
```

O crear/actualizar uno por comando:

```bash
../.venv/bin/python manage.py ensure_admin_user --username admin --password 'CAMBIAR_ESTO' --email admin@cajamoments.local
```

Correr backend:

```bash
../.venv/bin/python manage.py runserver 0.0.0.0:8000
```

Admin:

```text
http://localhost:8000/admin/
```

## Frontend local

Instalar dependencias y correr:

```bash
cd frontend
npm install
npm run dev
```

Abrir:

```text
http://localhost:5173
```

Si la API corre en otra URL:

```bash
VITE_API_BASE_URL=http://localhost:8000/api npm run dev
```

## Comandos de verificacion

Backend:

```bash
cd backend
../.venv/bin/python manage.py test
../.venv/bin/python manage.py makemigrations --check --dry-run
```

Frontend:

```bash
cd frontend
npm run build
npm audit --omit=dev
```

Deploy settings check:

```bash
cd backend
env DEBUG=False SECRET_KEY=prod-like-secret-key-with-enough-length-for-django-checks ALLOWED_HOSTS=caja-moments-api.onrender.com CORS_ALLOWED_ORIGINS=https://caja-moments-web.onrender.com CSRF_TRUSTED_ORIGINS=https://caja-moments-web.onrender.com SECURE_SSL_REDIRECT=True ../.venv/bin/python manage.py check --deploy
```

## Variables de entorno

Ejemplos:

- `backend/.env.example`
- `frontend/.env.example`

Backend:

- `SECRET_KEY`
- `DEBUG`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `SECURE_SSL_REDIRECT`
- `BACKEND_URL`
- `FRONTEND_URL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_EMAIL`
- `MERCADOPAGO_ACCESS_TOKEN`
- `MERCADOPAGO_WEBHOOK_SECRET`
- `MERCADOPAGO_WEBHOOK_SIGNATURE_REQUIRED`
- `MERCADOPAGO_COLLECTOR_ID`
- `MERCADOPAGO_ACCOUNT_NAME`
- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`

Frontend:

- `VITE_API_BASE_URL`

## Seeds

`seed_initial_data --skip-examples` carga:

- Cuentas: EFECTIVO, BNA, MERCADO PAGO, NARANJA, PLAZO FIJO, FRASCOS, USD.
- Codigos: COBRO_EVENTO, SEÑA_EVENTO, PAGO_PROVEEDOR, PERSONAL_EVENTUAL,
  COCINA, LIMPIEZA, CABINA, IMPUESTOS, SERVICIOS, TRANSFERENCIA_INTERNA,
  INVERSION_PLAZO_FIJO, INVERSION_FRASCO, RENDIMIENTO_INVERSION, AJUSTE_CAJA,
  OTRO_INGRESO, OTRO_EGRESO.
- Impuestos: Servicios, Monotributo, IVA, Ingresos Brutos, Autonomos,
  Municipal.
- Roles: Mozo, Cocina, Cabina, Limpieza anterior, Limpieza posterior, Armado,
  Produccion, Barra, Otro.
- Servicios: servicios operativos iniciales.

Sin `--skip-examples`, tambien carga datos de ejemplo.

## Deploy en Render

El repo incluye `render.yaml`, `backend/build.sh` y `backend/start.sh`.

Blueprint:

- `caja-moments-db`: PostgreSQL.
- `caja-moments-api`: Django + Gunicorn.
- `caja-moments-web`: static site React.

En cada arranque del backend, `start.sh`:

- corre migraciones;
- carga seeds maestros;
- crea o actualiza admin solo si existe `ADMIN_PASSWORD`;
- inicia Gunicorn.

Para operar datos reales:

- usar plan con backups;
- definir `SECRET_KEY` y `ADMIN_PASSWORD` seguros;
- configurar dominio/HTTPS;
- configurar variables de Mercado Pago;
- validar checkout, webhook, refund y chargeback en sandbox antes de usar live;
- configurar SMTP real si se necesitan emails fuera de consola.

## Deploy en Vercel

Vercel esta preparado como opcion separada:

- backend Django desde `backend/`;
- frontend React desde `frontend/`;
- PostgreSQL externo, por ejemplo Neon.

Archivos incluidos:

- `backend/vercel.json`
- `backend/api/index.py`
- `frontend/vercel.json`

Render sigue siendo la opcion mas simple para operar API, DB y frontend juntos.
