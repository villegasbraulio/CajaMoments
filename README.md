# Caja Moments

Sistema operativo para salon de eventos: caja diaria, cuentas, movimientos,
proveedores, personal eventual, impuestos, recordatorios, eventos, presupuestos,
cobranzas online con Mercado Pago, venta publica de tarjetas de egresados y
reportes.

## Stack

- Backend: Django 4.2, Django REST Framework, django-filter.
- Frontend: React 18 + Vite.
- Base local: SQLite.
- Base produccion: PostgreSQL via `DATABASE_URL`.
- Estilos: Bootstrap 5 + CSS propio.
- Dinero: `DecimalField`, nunca `FloatField`.
- Zona horaria: `America/Argentina/Mendoza`.
- Autenticacion: token DRF.

## Casos de uso

### Acceso y permisos

- Iniciar sesion desde el frontend con usuario Django.
- Consultar datos con cualquier usuario autenticado.
- Crear, editar, anular y ejecutar operaciones solo con usuarios `is_staff`.
- Usar `/api/health/` sin autenticacion para healthchecks.

### Dashboard operativo

- Ver saldos actuales por cuenta y moneda.
- Ver ingresos y egresos del dia.
- Ver recordatorios pendientes.
- Ver cierres pendientes o diferencias del dia.
- Ver proveedores con saldo a favor, personal pendiente y movimientos anulados.

### Caja diaria

- Cargar ingresos, egresos y ajustes.
- Asociar movimientos a cuenta, codigo, proveedor, empleado, evento o impuesto.
- Filtrar movimientos por fecha, cuenta, tipo, codigo, proveedor, empleado,
  evento, impuesto y estado.
- Ver detalle completo, editar movimientos abiertos y descargar recibo o
  comprobante PDF para movimientos confirmados.
- Exportar el cierre por cuenta con todos los movimientos del dia: ingresos,
  egresos, ajustes y transferencias.
- Anular movimientos sin borrarlos fisicamente.
- Bloquear cambios cuando la cuenta ya esta cerrada para ese dia.

### Cuentas y ajustes

- Administrar cuentas/billeteras en ARS o USD.
- Clasificar cuentas como efectivo, banco, billetera virtual, inversion, moneda
  extranjera u otro.
- Consultar saldo calculado.
- Ajustar saldo declarado creando un movimiento `AJUSTE_CAJA` solo si hay
  diferencia.

### Transferencias

- Transferir entre cuentas de la misma moneda.
- Registrar comision de transferencia como egreso separado.
- Crear automaticamente los movimientos `TRANSFER_OUT` y `TRANSFER_IN`.
- Anular transferencias por estado, preservando trazabilidad.

### Cierres diarios

- Cerrar una cuenta para una fecha con saldo declarado.
- Cerrar todas las cuentas activas del dia en un grupo de cierre.
- Guardar saldo inicial, ingresos, egresos, transferencias, ajustes, saldo
  calculado, saldo declarado y diferencia.
- Consultar cierres historicos.

### Proveedores

- Crear proveedores con categoria, CUIT, telefono, email, direccion y notas.
- Registrar deudas, pagos y ajustes en el ledger del proveedor.
- Pagar proveedor desde caja y generar el movimiento asociado.
- Asociar deudas o pagos a eventos.
- Consultar saldo del proveedor; saldo negativo significa pago adelantado o
  saldo a favor.

### Personal eventual

- Crear empleados y roles.
- Guardar email y alias bancario del empleado.
- Asignar empleados a eventos con rol, fecha, importe base, extra, total y
  estado.
- Registrar pagos parciales o totales al personal desde una cuenta.
- Generar el movimiento de caja de cada pago.
- Consultar pagado y pendiente por asignacion.

### Clientes y eventos

- Crear clientes con contacto y notas.
- Crear eventos con cliente opcional, contacto alternativo, tipo, fecha, hora,
  salon, invitados de cena/brindis, mesa principal, manteleria/vajilla,
  protocolo, bebidas, adicionales, estado interno, notas operativas y estado.
- Buscar y filtrar eventos por texto, estado, cliente, tipo, estado interno y
  rango de fechas.
- Ver resumen del evento con datos operativos, presupuesto, cobranzas,
  movimientos, proveedores y personal asociado.
- Mantener cronograma, croquis adjunto y funciones operativas del evento.

### Presupuestos de eventos

- Crear o consultar el presupuesto de un evento.
- Cambiar estado del presupuesto: borrador, enviado, aprobado o cancelado.
- Cargar items con servicio, categoria, cantidad, unidad, precio unitario,
  total calculado, orden, opcionalidad y notas.
- Separar subtotal obligatorio, total opcional y total general.
- Editar o borrar items del presupuesto.
- Cargar opcionales rapidos desde la ficha del evento.
- Registrar cobros por item, manuales o por Mercado Pago, con su movimiento de
  caja asociado.

### Cobranzas online con Mercado Pago

- Crear una preferencia de pago para un presupuesto con total mayor a cero.
- Abrir checkout productivo o sandbox segun el link devuelto por Mercado Pago.
- Registrar intentos de pago con idempotency key, preference id, payment id,
  estado, metodo, tipo, cuotas, importe y moneda.
- Recibir webhooks de Mercado Pago con deduplicacion y validacion de firma
  cuando `MERCADOPAGO_WEBHOOK_SECRET` esta configurado.
- Aprobar automaticamente el presupuesto cuando el pago aprobado coincide con
  importe, moneda y referencia esperada.
- Crear una sola cobranza en caja para pagos aprobados, en la cuenta
  `MERCADOPAGO_ACCOUNT_NAME` o `MERCADO PAGO`.
- Crear una sola reversa de egreso cuando Mercado Pago informa refund o
  chargeback y ya existia una cobranza asociada.
- Consultar intentos de pago y la cuenta/fecha del movimiento asociado.

### Egresados y venta de tarjetas

- Crear un link publico por evento de egresados, con precio por tarjeta y cupo
  opcional.
- Definir historial mensual de precios y maximo acumulado de tarjetas por
  egresado.
- Precargar egresados para que el comprador busque su nombre sin login.
- Pedir cantidad y email, enviar resumen por email y abrir Checkout Pro.
- Marcar compras pagadas por webhook Mercado Pago y crear el ingreso en caja.
- Registrar pagos manuales de tarjetas por staff, generando caja.
- Cerrar la lista final y exportarla en CSV.
- Crear una reversa de caja ante refund o chargeback informado por Mercado Pago.

### Pagos y auditoria

- Registrar pagos desde un modulo con pestanas para proveedores, empleados,
  servicios y egresados.
- Crear tipos de servicio al vuelo y pagar servicios con descripcion libre.
- Consultar auditoria central de acciones por usuario, accion, modelo, objeto y
  fecha.

### Impuestos y recordatorios

- Crear tipos de impuesto.
- Registrar pagos de impuestos desde caja.
- Generar recordatorio proximo con recurrencia mensual, bimestral, trimestral,
  anual o por cantidad custom de dias.
- Crear recordatorios manuales relacionados con impuesto, evento o proveedor.
- Marcar recordatorios como hechos.

### Reportes

- Resumen de caja diaria.
- Cierre por cuenta/billetera.
- Saldos por cuenta/billetera.
- Ingresos vs egresos por periodo.
- Egresos por codigo.
- Gastos y saldos por proveedor.
- Proveedores con saldo a favor.
- Personal por evento.
- Pagos al personal por periodo.
- Impuestos pagados y proximos a vencer.
- Movimientos anulados.
- Transferencias entre cuentas.
- Resultado basico por evento.
- Exportacion CSV desde el frontend para tablas de reportes.

## Modelo de datos

### Entidades principales

| Modelo | Proposito | Campos principales |
|---|---|---|
| `Account` | Cuenta, caja o billetera | `name`, `type`, `currency`, `active`, `initial_balance`, `notes` |
| `MovementCode` | Codigo contable/operativo | `code`, `name`, `movement_type`, `category`, flags `requires_*`, `active` |
| `CashMovement` | Libro mayor de caja | fechas, descripcion, comprobante, tipo, importe, cuenta, codigo, proveedor, empleado, evento, impuesto, transferencia, metodo, estado, auditoria y anulacion |
| `AccountTransfer` | Transferencia entre cuentas | fecha, cuenta origen, cuenta destino, importe, comision, descripcion, estado |
| `DailyCashCloseGroup` | Cierre diario general | fecha unica, estado, fecha de cierre, notas |
| `DailyAccountClose` | Cierre de una cuenta en un dia | grupo, cuenta, saldo inicial, totales, saldo calculado, declarado, diferencia, cierre |
| `Provider` | Proveedor | nombre, categoria, CUIT, telefono, email, direccion, activo, notas |
| `ProviderLedgerEntry` | Cuenta corriente proveedor | proveedor, evento, fecha, tipo, descripcion, documento, importe, movimiento asociado, notas |
| `EmployeeRole` | Rol eventual | nombre, activo |
| `Employee` | Persona eventual | nombre, apellido, alias bancario, telefono, documento, email, activo, notas |
| `EmployeePayment` | Pago a empleado | empleado, evento, asignacion, movimiento asociado, importe, fecha, notas |
| `Client` | Cliente de evento | nombre, telefono, email, notas |
| `Event` | Ficha operativa del evento | cliente, nombre, tipo, fecha, hora, salon, invitados, contacto, notas de servicio, cronograma, croquis, funciones, estado interno, estado |
| `EventBudget` | Presupuesto del evento | evento, estado, notas comerciales, comentarios opcionales, notas internas |
| `EventBudgetItem` | Item de presupuesto | presupuesto, servicio, categoria, cantidad, unidad, precio, total, orden, opcional, notas |
| `EventBudgetPayment` | Intento/cobranza Mercado Pago o cobro manual por item | presupuesto, item opcional, idempotencia, preference/payment ids, estado MP, metodo, cuotas, importe, moneda, movimiento de caja |
| `EventBudgetPaymentWebhookLog` | Registro de webhook MP | notification id, clave de deduplicacion, topic, payload, procesado, error, fecha |
| `EventStaffAssignment` | Asignacion de personal a evento | evento, empleado, rol, fecha, base, extra, total, estado, notas |
| `GraduationEvent` | Venta publica de tarjetas | evento base, precio inicial, cupo, maximo por egresado, token publico, cierre, activo, notas |
| `GraduationTicketPrice` | Historial de precios | evento de egresados, precio, vigente desde, notas |
| `Graduate` | Egresado precargado | evento de egresados, nombre, apellido, notas |
| `TicketPurchase` | Compra de tarjetas | evento, egresado, cantidad, total, email, estado, IDs MP, medio, fecha, usuario staff, movimiento de caja |
| `TicketPurchaseWebhookLog` | Registro de webhook de tarjetas | notification id, clave de deduplicacion, topic, payload, procesado, error, fecha |
| `ServiceType` | Catalogo de servicios | nombre, activo, descripcion |
| `AuditLogEntry` | Auditoria central | usuario, accion, modelo, id de objeto, detalle, fecha |
| `TaxType` | Tipo de impuesto | nombre, activo, descripcion |
| `TaxPayment` | Pago de impuesto | tipo, periodo, fecha, importe, cuenta, movimiento asociado, notas |
| `Reminder` | Recordatorio | titulo, descripcion, vencimiento, aviso previo, recurrencia, estado, impuesto/evento/proveedor asociado |

### Relaciones y reglas

- `Event` puede tener un `Client`; si no, usa contacto alternativo.
- `Event` tiene un solo `EventBudget`.
- `EventBudget` tiene muchos `EventBudgetItem` y muchos `EventBudgetPayment`.
- `EventBudgetPayment` puede tener un solo `CashMovement` de cobranza.
- `EventBudgetPayment` puede apuntar a un `EventBudgetItem` cuando el cobro es
  por item.
- El costo del evento se calcula desde `EventBudget.total()`, no desde un campo
  duplicado en `Event`.
- `GraduationEvent` reusa un `Event` existente para que las ventas de tarjetas
  impacten en la misma caja y reportes del evento.
- El precio vigente de tarjetas sale de `GraduationTicketPrice`: se usa el
  ultimo `vigente_desde` menor o igual a la fecha.
- El cierre final de egresados bloquea nuevos egresados y compras/asignaciones.
- `AuditLogEntry` registra acciones operativas; no guarda diffs completos.
- `CashMovement` es el registro canonico de dinero real; proveedores, empleados,
  impuestos, transferencias y cobranzas online apuntan a movimientos de caja.
- `CashMovement` no se borra: se anula con estado `VOIDED` y motivo.
- Solo movimientos `CONFIRMED` afectan saldos.
- `DailyAccountClose` bloquea nuevos cambios para esa cuenta y fecha.
- `AccountTransfer` no permite origen y destino iguales ni monedas distintas.
- `EventStaffAssignment.total_amount` se calcula como base + extra.
- `EventStaffAssignment` calcula pagado y pendiente desde `EmployeePayment`.
- `EventBudgetItem.total` se calcula como cantidad * precio unitario.
- `Provider.balance()` suma deudas y ajustes, y resta pagos.
- `Account.current_balance()` parte del saldo inicial y suma/resta movimientos
  confirmados.

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
/api/accounts/{id}/balance/
/api/accounts/{id}/adjust-balance/
/api/movement-codes/
/api/cash-movements/
/api/cash-movements/{id}/void/
/api/cash-movements/{id}/receipt/
/api/account-transfers/
/api/daily-cash-closes/
/api/daily-cash-closes/close-account/
/api/daily-account-closes/
/api/daily-account-closes/{id}/export/
/api/providers/
/api/providers/{id}/ledger/
/api/providers/{id}/pay/
/api/provider-ledger/
/api/employees/
/api/employee-roles/
/api/clients/
/api/events/
/api/events/{id}/overview/
/api/events/{id}/budget/
/api/event-budgets/
/api/event-budget-items/
/api/event-budget-items/{id}/pay-manual/
/api/event-budget-payments/
/api/event-budget-payments/create-preference/
/api/event-budget-payments/webhook/
/api/event-staff-assignments/
/api/employee-payments/
/api/graduation-events/
/api/graduation-events/{id}/graduates/
/api/graduation-events/{id}/ticket-price/
/api/graduation-events/{id}/close/
/api/graduation-events/{id}/export/
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
/api/reminders/{id}/complete/
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

## Estructura

```text
backend/
  config/              Configuracion Django
  cashflow/            Dominio de caja, eventos, pagos, API, admin y tests
  build.sh             Build para Render
  start.sh             Arranque Render: migraciones, seeds y admin opcional
render.yaml            Blueprint Render: API, DB y static site React
frontend/
  src/                 SPA React
docs/
  adr/                 Decisiones tecnicas
  worklog/             Bitacora de trabajo
  PROJECT_STATE.md     Estado actual resumido
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

Crear usuario:

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

Tests:

```bash
cd backend
../.venv/bin/python manage.py test
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

Build:

```bash
npm run build
```

## Variables de entorno

Ejemplos:

- [backend/.env.example](/Users/braulio/CajaMoments/backend/.env.example)
- [frontend/.env.example](/Users/braulio/CajaMoments/frontend/.env.example)

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

`seed_initial_data --skip-examples` carga maestros:

- Cuentas: EFECTIVO, BNA, MERCADO PAGO, NARANJA, PLAZO FIJO, FRASCOS, USD.
- Codigos: COBRO_EVENTO, SEÑA_EVENTO, PAGO_PROVEEDOR, PERSONAL_EVENTUAL,
  COCINA, LIMPIEZA, CABINA, IMPUESTOS, SERVICIOS, TRANSFERENCIA_INTERNA,
  INVERSION_PLAZO_FIJO, INVERSION_FRASCO, RENDIMIENTO_INVERSION, AJUSTE_CAJA,
  OTRO_INGRESO, OTRO_EGRESO.
- Impuestos: Servicios, Monotributo, IVA, Ingresos Brutos, Autonomos,
  Municipal.
- Roles: Mozo, Cocina, Cabina, Limpieza anterior, Limpieza posterior, Armado,
  Produccion, Barra, Otro.

Sin `--skip-examples`, tambien carga proveedores, empleados, cliente y evento de
ejemplo.

## Decisiones tecnicas

- El nucleo es `CashMovement`; todo movimiento real de dinero pasa por caja.
- Los saldos no se editan historicamente: se calculan desde saldo inicial +
  movimientos confirmados.
- Los movimientos anulados no impactan saldos y no se borran.
- Las correcciones de saldo se registran con `AJUSTE_CAJA`.
- Los cierres son por fecha + cuenta y bloquean cambios posteriores.
- Las transferencias crean movimientos espejo, mas un egreso por comision si
  corresponde.
- Los pagos a proveedores, empleados e impuestos generan movimientos de caja.
- Las cobranzas Mercado Pago aprobadas generan una unica cobranza de caja.
- Los refunds/chargebacks generan una unica reversa si habia cobranza previa.
- Los recibos/comprobantes PDF son documentos simples generados sin dependencia
  externa.
- Las tarjetas de egresados usan link publico, lista cerrada de egresados y el
  mismo patron de Mercado Pago + caja que los presupuestos.
- Los precios de tarjetas se cargan por mes; no hay cron de actualizacion.
- La auditoria usa un log central resumido en vez de columnas repetidas en todos
  los modelos.
- USD es una cuenta separada y no se convierte a ARS.
- La logica de negocio vive en `cashflow/services.py`.
- La API requiere autenticacion por token salvo login, logout y healthcheck.
- Las mutaciones operativas requieren `is_staff`.

## Deploy en Render

El repo incluye:

- [render.yaml](/Users/braulio/CajaMoments/render.yaml)
- [backend/build.sh](/Users/braulio/CajaMoments/backend/build.sh)
- [backend/start.sh](/Users/braulio/CajaMoments/backend/start.sh)

Blueprint:

- `caja-moments-db`: PostgreSQL.
- `caja-moments-api`: Django + Gunicorn.
- `caja-moments-web`: static site React.

En cada arranque del backend, `start.sh`:

- corre migraciones;
- carga seeds maestros;
- crea o actualiza admin solo si existe `ADMIN_PASSWORD`.

Para operar datos reales:

- usar plan con backups;
- definir `ADMIN_PASSWORD` seguro;
- configurar dominio/HTTPS;
- configurar variables Mercado Pago;
- validar checkout, webhook y refund en sandbox antes de usar live.

## Deploy en Vercel

Vercel esta preparado como opcion separada:

- backend Django desde `backend/`;
- frontend React desde `frontend/`;
- PostgreSQL externo, por ejemplo Neon.

Archivos incluidos:

- [backend/vercel.json](/Users/braulio/CajaMoments/backend/vercel.json)
- [backend/api/index.py](/Users/braulio/CajaMoments/backend/api/index.py)
- [frontend/vercel.json](/Users/braulio/CajaMoments/frontend/vercel.json)

Render sigue siendo la opcion mas simple para operar API, DB y frontend juntos.
