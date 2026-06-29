import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
const TOKEN_STORAGE_KEY = "cajaMomentsAuthToken";

const navItems = [
  ["dashboard", "Dashboard"],
  ["cash", "Caja diaria"],
  ["accounts", "Cuentas y ajustes"],
  ["transfers", "Transferencias"],
  ["closes", "Cierres"],
  ["providers", "Proveedores"],
  ["people", "Personal eventual"],
  ["events", "Eventos basicos"],
  ["taxes", "Impuestos y recordatorios"],
  ["reports", "Reportes"],
];

const eventStatusOptions = [
  { id: "DRAFT", name: "Borrador" },
  { id: "CONFIRMED", name: "Confirmado" },
  { id: "DONE", name: "Realizado" },
  { id: "CANCELLED", name: "Cancelado" },
];

const budgetStatusOptions = [
  { id: "DRAFT", name: "Borrador" },
  { id: "SENT", name: "Enviado" },
  { id: "APPROVED", name: "Aprobado" },
  { id: "CANCELLED", name: "Cancelado" },
];

function todayISO() {
  return new Date().toLocaleDateString("sv-SE");
}

function unwrap(data) {
  return Array.isArray(data) ? data : data?.results || [];
}

async function api(path, options = {}) {
  const token = options.token ?? localStorage.getItem(TOKEN_STORAGE_KEY);
  const url = String(path).startsWith("http") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401) {
    throw new Error("AUTH_REQUIRED");
  }
  const rawBody = response.status === 204 ? "" : await response.text();
  if (!response.ok) {
    let detail = "Error al comunicarse con la API";
    if (rawBody) {
      try {
        detail = JSON.stringify(JSON.parse(rawBody));
      } catch {
        detail = rawBody;
      }
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  if (!rawBody) return null;
  try {
    return JSON.parse(rawBody);
  } catch {
    return rawBody;
  }
}

async function apiList(path) {
  const rows = [];
  let next = path;
  while (next) {
    const data = await api(next);
    rows.push(...unwrap(data));
    next = Array.isArray(data) ? null : data?.next || null;
  }
  return rows;
}

function money(value, currency = "ARS") {
  const number = Number(value || 0);
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(number);
}

function statusLabel(type) {
  const labels = {
    INCOME: "Ingreso",
    EXPENSE: "Egreso",
    TRANSFER_IN: "Transf. entra",
    TRANSFER_OUT: "Transf. sale",
    ADJUSTMENT: "Ajuste",
    CONFIRMED: "Confirmado",
    VOIDED: "Anulado",
    DRAFT: "Borrador",
    CLOSED: "Cerrado",
    OPEN: "Abierto",
    SENT: "Enviado",
    APPROVED: "Aprobado",
    DEBT: "Deuda",
    PAYMENT: "Pago",
    DONE: "Hecho",
    PENDING: "Pendiente",
    pending: "Pendiente",
    approved: "Aprobado",
    rejected: "Rechazado",
    cancelled: "Cancelado",
    refunded: "Reembolsado",
    in_process: "En proceso",
  };
  return labels[type] || type;
}

function Field({ label, children }) {
  return (
    <label className="form-label w-100">
      <span className="small fw-bold text-uppercase text-muted">{label}</span>
      {children}
    </label>
  );
}

function TextInput({ label, value, onChange, type = "text", required = false, placeholder = "" }) {
  return (
    <Field label={label}>
      <input
        className="form-control"
        type={type}
        value={value}
        required={required}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

function TextAreaInput({ label, value, onChange, rows = 3, placeholder = "" }) {
  return (
    <Field label={label}>
      <textarea
        className="form-control"
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

function SelectInput({ label, value, onChange, options, labelFor, required = false, empty = "Seleccionar" }) {
  return (
    <Field label={label}>
      <select className="form-select" value={value || ""} required={required} onChange={(event) => onChange(event.target.value)}>
        <option value="">{empty}</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {labelFor(option)}
          </option>
        ))}
      </select>
    </Field>
  );
}

function AlertLine({ status }) {
  if (!status) return null;
  return <div className={`alert ${status.type === "error" ? "alert-danger" : "alert-success"} shadow-sm`}>{status.message}</div>;
}

function prettifyErrorMessage(message) {
  if (!message) return "Ocurrio un error inesperado.";
  if (message === "AUTH_REQUIRED") return "La sesion vencio. Volve a ingresar.";
  try {
    const parsed = JSON.parse(message);
    if (typeof parsed === "string") return parsed;
    if (Array.isArray(parsed)) return parsed.join(" ");
    if (parsed.detail) {
      return Array.isArray(parsed.detail) ? parsed.detail.join(" ") : parsed.detail;
    }
    return Object.entries(parsed)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(" ") : value}`)
      .join(" | ");
  } catch {
    return message;
  }
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(`${value}T00:00:00`).toLocaleDateString("es-AR");
}

function formatTime(value) {
  if (!value) return "-";
  return String(value).slice(0, 5);
}

function csvCell(value) {
  const safeValue = value ?? "";
  const normalized = String(safeValue).replace(/"/g, '""');
  return `"${normalized}"`;
}

function downloadCsv(filename, columns, rows) {
  const header = columns.map((column) => csvCell(column.label)).join(",");
  const body = rows
    .map((row) =>
      columns
        .map((column) => {
          const raw = typeof column.value === "function" ? column.value(row) : row[column.value];
          return csvCell(raw);
        })
        .join(","),
    )
    .join("\n");
  const blob = new Blob([`${header}\n${body}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportRows(filename, columns, rows) {
  if (!rows.length) {
    window.alert("No hay datos para exportar.");
    return;
  }
  downloadCsv(filename, columns, rows);
}

function emptyEventForm() {
  return {
    client: "",
    name: "",
    event_type: "",
    event_date: todayISO(),
    event_time: "",
    venue_space: "",
    guest_count_dinner: "",
    guest_count_toast: "",
    main_table_notes: "",
    tableware_notes: "",
    protocol_notes: "",
    beverage_notes: "",
    additional_notes: "",
    operational_notes: "",
    internal_status: "",
    contact_name: "",
    contact_phone: "",
    contact_email: "",
    status: "CONFIRMED",
    notes: "",
  };
}

function normalizeEventForForm(event) {
  if (!event) return emptyEventForm();
  return {
    client: event.client || "",
    name: event.name || "",
    event_type: event.event_type || "",
    event_date: event.event_date || todayISO(),
    event_time: event.event_time ? String(event.event_time).slice(0, 5) : "",
    venue_space: event.venue_space || "",
    guest_count_dinner: event.guest_count_dinner ?? "",
    guest_count_toast: event.guest_count_toast ?? "",
    main_table_notes: event.main_table_notes || "",
    tableware_notes: event.tableware_notes || "",
    protocol_notes: event.protocol_notes || "",
    beverage_notes: event.beverage_notes || "",
    additional_notes: event.additional_notes || "",
    operational_notes: event.operational_notes || "",
    internal_status: event.internal_status || "",
    contact_name: event.contact_name || "",
    contact_phone: event.contact_phone || "",
    contact_email: event.contact_email || "",
    status: event.status || "CONFIRMED",
    notes: event.notes || "",
  };
}

function buildEventPayload(form) {
  return {
    ...form,
    client: form.client || null,
    event_date: form.event_date || null,
    event_time: form.event_time || null,
    guest_count_dinner: form.guest_count_dinner === "" ? null : Number(form.guest_count_dinner),
    guest_count_toast: form.guest_count_toast === "" ? null : Number(form.guest_count_toast),
  };
}

function emptyBudgetItemForm() {
  return {
    service_name: "",
    category: "",
    quantity: "1.00",
    unit_label: "",
    unit_price: "",
    sort_order: "1",
    is_optional: false,
    notes: "",
  };
}

function App() {
  const [active, setActive] = useState("dashboard");
  const [authToken, setAuthToken] = useState(() => localStorage.getItem(TOKEN_STORAGE_KEY));
  const [currentUser, setCurrentUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [refs, setRefs] = useState({
    accounts: [],
    movementCodes: [],
    providers: [],
    employees: [],
    roles: [],
    clients: [],
    events: [],
    eventBudgetPayments: [],
    assignments: [],
    taxTypes: [],
  });
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState(null);

  async function loadSession(token = authToken) {
    if (!token) {
      setCurrentUser(null);
      setBooting(false);
      return;
    }
    try {
      const data = await api("/auth/me/", { token });
      setCurrentUser(data.user);
    } catch (error) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      setAuthToken(null);
      setCurrentUser(null);
      if (error.message !== "AUTH_REQUIRED") {
        setStatus({ type: "error", message: prettifyErrorMessage(error.message) });
      }
    } finally {
      setBooting(false);
    }
  }

  async function loadRefs() {
    const [accounts, movementCodes, providers, employees, roles, clients, events, eventBudgetPayments, assignments, taxTypes] = await Promise.all([
      apiList("/accounts/"),
      apiList("/movement-codes/"),
      apiList("/providers/"),
      apiList("/employees/"),
      apiList("/employee-roles/"),
      apiList("/clients/"),
      apiList("/events/"),
      apiList("/event-budget-payments/"),
      apiList("/event-staff-assignments/"),
      apiList("/tax-types/"),
    ]);
    setRefs({
      accounts,
      movementCodes,
      providers,
      employees,
      roles,
      clients,
      events,
      eventBudgetPayments,
      assignments,
      taxTypes,
    });
  }

  useEffect(() => {
    loadSession();
  }, []);

  useEffect(() => {
    if (!authToken) {
      setRefs({
        accounts: [],
        movementCodes: [],
        providers: [],
        employees: [],
        roles: [],
        clients: [],
        events: [],
        eventBudgetPayments: [],
        assignments: [],
        taxTypes: [],
      });
      return;
    }
    loadRefs().catch((error) => {
      if (error.message === "AUTH_REQUIRED") {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setAuthToken(null);
        setCurrentUser(null);
        setStatus({ type: "error", message: "La sesion vencio. Volve a ingresar." });
        return;
      }
      setStatus({ type: "error", message: prettifyErrorMessage(error.message) });
    });
  }, [authToken, reloadKey]);

  async function mutate(action, successMessage = "Operacion realizada") {
    try {
      await action();
      setStatus({ type: "success", message: successMessage });
      setReloadKey((value) => value + 1);
    } catch (error) {
      if (error.message === "AUTH_REQUIRED") {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setAuthToken(null);
        setCurrentUser(null);
        setStatus({ type: "error", message: "La sesion vencio. Volve a ingresar." });
        return;
      }
      setStatus({ type: "error", message: prettifyErrorMessage(error.message) });
    }
  }

  const context = { refs, mutate, reloadKey };
  const screens = {
    dashboard: <Dashboard reloadKey={reloadKey} />,
    cash: <DailyCash {...context} />,
    accounts: <AccountsScreen {...context} />,
    transfers: <TransfersScreen {...context} />,
    closes: <ClosesScreen {...context} />,
    providers: <ProvidersScreen {...context} />,
    people: <PeopleScreen {...context} />,
    events: <EventsScreen {...context} />,
    taxes: <TaxesScreen {...context} />,
    reports: <ReportsScreen refs={refs} />,
  };

  async function handleLogin(credentials) {
    try {
      const data = await api("/auth/login/", {
        method: "POST",
        body: JSON.stringify(credentials),
        token: "",
      });
      localStorage.setItem(TOKEN_STORAGE_KEY, data.token);
      setAuthToken(data.token);
      setCurrentUser(data.user);
      setStatus({ type: "success", message: `Sesion iniciada como ${data.user.username}` });
      setReloadKey((value) => value + 1);
    } catch (error) {
      setStatus({ type: "error", message: prettifyErrorMessage(error.message) });
      throw error;
    }
  }

  async function handleLogout() {
    await mutate(
      async () => {
        if (authToken) {
          await api("/auth/logout/", {
            method: "POST",
            body: JSON.stringify({}),
            token: authToken,
          });
        }
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setAuthToken(null);
        setCurrentUser(null);
      },
      "Sesion cerrada",
    );
  }

  if (booting) {
    return (
      <div className="app-shell">
        <main className="main-stage">
          <section className="hero-card">
            <div className="pill mb-3">Iniciando</div>
            <h2 className="mb-2">Caja Moments</h2>
            <p className="text-muted mb-0">Chequeando sesion y preparando la app.</p>
          </section>
        </main>
      </div>
    );
  }

  if (!currentUser) {
    return <LoginScreen onLogin={handleLogin} status={status} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark mb-4">
          <div className="pill mb-3">Fase 1</div>
          <h1>Caja Moments</h1>
          <p className="mb-0 opacity-75">Caja diaria, billeteras, proveedores, personal e impuestos.</p>
        </div>
        <div className="mb-4">
          <div className="small text-uppercase opacity-50">Sesion</div>
          <div className="fw-semibold">{currentUser.username}</div>
          <button className="btn btn-sm btn-outline-light mt-2" onClick={handleLogout}>Cerrar sesion</button>
        </div>
        <nav>
          {navItems.map(([key, label]) => (
            <button key={key} className={`nav-button ${active === key ? "active" : ""}`} onClick={() => setActive(key)}>
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="main-stage">
        <AlertLine status={status} />
        {screens[active]}
      </main>
    </div>
  );
}

function LoginScreen({ onLogin, status }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onLogin(form);
    } catch {
      return;
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="app-shell login-shell">
      <main className="main-stage d-flex align-items-center justify-content-center">
        <div className="work-card login-card">
          <div className="pill mb-3">Acceso</div>
          <h2 className="section-title mb-2">Caja Moments</h2>
          <p className="text-muted">Ingresa con el usuario Django que vas a crear en Render o localmente.</p>
          <AlertLine status={status} />
          <form onSubmit={submit}>
            <TextInput label="Usuario" value={form.username} onChange={(value) => setForm({ ...form, username: value })} required />
            <TextInput label="Contrasena" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} required />
            <button className="btn btn-earth w-100 mt-2" disabled={submitting}>
              {submitting ? "Ingresando..." : "Entrar"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

function PageHeader({ title, kicker, children }) {
  return (
    <section className="hero-card">
      <div className="row g-3 align-items-end">
        <div className="col-lg">
          <div className="pill mb-3">{kicker}</div>
          <h2 className="mb-2">{title}</h2>
          <p className="text-muted mb-0">{children}</p>
        </div>
      </div>
    </section>
  );
}

function Dashboard({ reloadKey }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    api("/dashboard/")
      .then(setSummary)
      .catch(() => setSummary(null));
  }, [reloadKey]);

  return (
    <>
      <PageHeader title="Tablero operativo" kicker="Hoy">
        Vista ejecutiva del dia: saldos por moneda, pendientes de cierre, diferencias, proveedores con saldo a favor y alertas operativas.
      </PageHeader>
      <div className="row g-3 mb-3">
        {(summary?.balances_by_currency || []).map((item) => (
          <div className="col-md-4" key={item.currency}>
            <div className="metric-card h-100">
              <span className="text-muted small">Saldo total por moneda</span>
              <h5 className="mt-2 mb-1">{item.currency}</h5>
              <strong>{money(item.balance, item.currency)}</strong>
            </div>
          </div>
        ))}
      </div>
      <div className="row g-3 mt-1">
        <div className="col-md-3">
          <div className="metric-card">
            <span className="text-muted small">Ingresos de hoy</span>
            <strong className="d-block">{money(summary?.today_income)}</strong>
          </div>
        </div>
        <div className="col-md-3">
          <div className="metric-card">
            <span className="text-muted small">Egresos de hoy</span>
            <strong className="d-block">{money(summary?.today_expense)}</strong>
          </div>
        </div>
        <div className="col-md-3">
          <div className="metric-card">
            <span className="text-muted small">Cierres pendientes</span>
            <strong className="d-block">{summary?.pending_account_closes?.length || 0}</strong>
          </div>
        </div>
        <div className="col-md-3">
          <div className="metric-card">
            <span className="text-muted small">Movimientos anulados</span>
            <strong className="d-block">{summary?.voided_count || 0}</strong>
          </div>
        </div>
      </div>
      <div className="row g-3 mt-1">
        <div className="col-lg-7">
          <div className="work-card h-100">
            <h4 className="section-title">Saldos por cuenta</h4>
            <SimpleTable
              rows={summary?.accounts || []}
              columns={[
                ["name", "Cuenta"],
                ["type", "Tipo"],
                ["currency", "Moneda"],
                [(row) => money(row.balance, row.currency), "Saldo"],
              ]}
            />
          </div>
        </div>
        <div className="col-lg-5">
          <div className="work-card h-100">
            <h4 className="section-title">Cierres pendientes del dia</h4>
            <SimpleTable
              rows={summary?.pending_account_closes || []}
              columns={[
                ["account_name", "Cuenta"],
                ["currency", "Moneda"],
                [(row) => money(row.balance, row.currency), "Saldo actual"],
              ]}
            />
          </div>
        </div>
      </div>
      <div className="row g-3 mt-1">
        <div className="col-lg-6">
          <div className="work-card h-100">
            <h4 className="section-title">Diferencias de caja del dia</h4>
            <SimpleTable
              rows={summary?.today_close_differences || []}
              columns={[
                ["account_name", "Cuenta"],
                [(row) => money(row.calculated_balance, row.currency), "Calculado"],
                [(row) => money(row.declared_balance, row.currency), "Declarado"],
                [(row) => money(row.difference, row.currency), "Diferencia"],
              ]}
            />
          </div>
        </div>
        <div className="col-lg-6">
          <div className="work-card h-100">
            <h4 className="section-title">Recordatorios de impuestos y vencimientos</h4>
            <SimpleTable
              rows={summary?.pending_reminders || []}
              columns={[
                [(row) => formatDate(row.due_date), "Vence"],
                ["title", "Titulo"],
                ["tax_type_name", "Impuesto"],
                ["status", "Estado"],
              ]}
            />
          </div>
        </div>
      </div>
      <div className="row g-3 mt-1">
        <div className="col-lg-6">
          <div className="work-card h-100">
            <h4 className="section-title">Proveedores con saldo a favor</h4>
            <SimpleTable
              rows={summary?.providers_with_credit || []}
              columns={[
                ["provider_name", "Proveedor"],
                [(row) => money(row.balance), "Saldo a favor"],
              ]}
            />
          </div>
        </div>
        <div className="col-lg-6">
          <div className="work-card h-100">
            <h4 className="section-title">Personal pendiente de pago</h4>
            <SimpleTable
              rows={summary?.employee_pending || []}
              columns={[
                ["employee_name", "Empleado"],
                ["event_name", "Evento"],
                ["role_name", "Rol"],
                [(row) => money(row.pending_amount), "Pendiente"],
              ]}
            />
          </div>
        </div>
      </div>
    </>
  );
}

function DailyCash({ refs, mutate, reloadKey }) {
  const [form, setForm] = useState({
    date_payment: todayISO(),
    account: "",
    code: "",
    movement_type: "INCOME",
    amount: "",
    description: "",
    voucher_number: "",
    provider: "",
    employee: "",
    event: "",
    payment_method: "",
    notes: "",
    status: "CONFIRMED",
  });
  const [filters, setFilters] = useState({
    date_from: todayISO(),
    date_to: todayISO(),
    account: "",
    status: "CONFIRMED",
    movement_type: "",
    code: "",
    provider: "",
    employee: "",
  });
  const [movements, setMovements] = useState([]);

  const selectedCode = refs.movementCodes.find((code) => String(code.id) === String(form.code));
  const selectedAccount = refs.accounts.find((account) => String(account.id) === String(form.account));

  function updateForm(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function onCodeChange(value) {
    const code = refs.movementCodes.find((item) => String(item.id) === String(value));
    const mappedType = {
      INCOME: "INCOME",
      EXPENSE: "EXPENSE",
      ADJUSTMENT: "ADJUSTMENT",
      TRANSFER: "TRANSFER_OUT",
    }[code?.movement_type || "INCOME"];
    setForm((current) => ({ ...current, code: value, movement_type: mappedType }));
  }

  function loadMovements() {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    api(`/cash-movements/?${params}`).then((data) => setMovements(unwrap(data)));
  }

  useEffect(() => {
    loadMovements();
  }, [reloadKey]);

  async function submit(event) {
    event.preventDefault();
    if (!form.account || !form.code || !form.amount || !form.description) {
      window.alert("Completa cuenta, codigo, importe y descripcion.");
      return;
    }
    const payload = {
      ...form,
      provider: selectedCode?.requires_provider ? form.provider : form.provider || null,
      employee: selectedCode?.requires_employee ? form.employee : form.employee || null,
      event: selectedCode?.requires_event ? form.event : form.event || null,
    };
    await mutate(async () => api("/cash-movements/", { method: "POST", body: JSON.stringify(payload) }), "Movimiento cargado");
    loadMovements();
    setForm((current) => ({ ...current, amount: "", description: "", voucher_number: "", notes: "" }));
  }

  const filteredIncome = movements
    .filter((row) => row.movement_type === "INCOME" && row.status === "CONFIRMED")
    .reduce((total, row) => total + Number(row.amount || 0), 0);
  const filteredExpense = movements
    .filter((row) => row.movement_type === "EXPENSE" && row.status === "CONFIRMED")
    .reduce((total, row) => total + Number(row.amount || 0), 0);

  async function voidMovement(row) {
    if (!window.confirm(`Vas a anular el movimiento "${row.description}" por ${money(row.amount)}. Continuar?`)) {
      return;
    }
    const reason = window.prompt("Motivo de anulacion:", "Carga incorrecta");
    if (reason === null) {
      return;
    }
    await mutate(
      () => api(`/cash-movements/${row.id}/void/`, { method: "POST", body: JSON.stringify({ reason }) }),
      "Movimiento anulado",
    );
    loadMovements();
  }

  return (
    <>
      <PageHeader title="Caja diaria" kicker="Libro mayor">
        Carga ingresos y egresos reales, revisa rapido el resumen filtrado y exporta el movimiento diario cuando necesites compartirlo.
      </PageHeader>
      <div className="row g-3">
        <div className="col-xl-4">
          <form className="work-card" onSubmit={submit}>
            <h4 className="section-title">Nuevo movimiento</h4>
            <div className="row g-2">
              <div className="col-6"><TextInput label="Fecha pago" type="date" value={form.date_payment} onChange={(v) => updateForm("date_payment", v)} required /></div>
              <div className="col-6"><TextInput label="Importe" type="number" value={form.amount} onChange={(v) => updateForm("amount", v)} required /></div>
              <div className="col-12"><SelectInput label="Cuenta" value={form.account} onChange={(v) => updateForm("account", v)} options={refs.accounts} labelFor={(a) => `${a.name} (${a.currency})`} required /></div>
              {selectedAccount && <div className="col-12"><div className="pill">Saldo actual: {money(selectedAccount.current_balance, selectedAccount.currency)}</div></div>}
              <div className="col-12"><SelectInput label="Codigo" value={form.code} onChange={onCodeChange} options={refs.movementCodes} labelFor={(c) => `${c.code} - ${c.name}`} required /></div>
              <div className="col-12"><SelectInput label="Tipo" value={form.movement_type} onChange={(v) => updateForm("movement_type", v)} options={[
                { id: "INCOME", name: "Ingreso" },
                { id: "EXPENSE", name: "Egreso" },
                { id: "ADJUSTMENT", name: "Ajuste +" },
              ]} labelFor={(x) => x.name} required /></div>
              <div className="col-12"><TextInput label="Descripcion" value={form.description} onChange={(v) => updateForm("description", v)} required /></div>
              <div className="col-6"><TextInput label="Comprobante" value={form.voucher_number} onChange={(v) => updateForm("voucher_number", v)} /></div>
              <div className="col-6"><TextInput label="Metodo" value={form.payment_method} onChange={(v) => updateForm("payment_method", v)} /></div>
              {selectedCode?.requires_provider && <div className="col-12"><SelectInput label="Proveedor" value={form.provider} onChange={(v) => updateForm("provider", v)} options={refs.providers} labelFor={(p) => p.name} required /></div>}
              {selectedCode?.requires_employee && <div className="col-12"><SelectInput label="Empleado" value={form.employee} onChange={(v) => updateForm("employee", v)} options={refs.employees} labelFor={(e) => e.display_name || `${e.first_name} ${e.last_name}`} required /></div>}
              {(selectedCode?.requires_event || form.event) && <div className="col-12"><SelectInput label="Evento" value={form.event} onChange={(v) => updateForm("event", v)} options={refs.events} labelFor={(e) => e.name} required={selectedCode?.requires_event} /></div>}
              {selectedCode?.code === "IMPUESTOS" && <div className="col-12"><div className="alert alert-warning py-2 mb-0">Para guardar tipo de impuesto y recordatorio, usa la pantalla Impuestos.</div></div>}
            </div>
            <button className="btn btn-earth w-100 mt-3" type="submit">Guardar movimiento</button>
          </form>
        </div>
        <div className="col-xl-8">
          <div className="work-card">
            <div className="d-flex flex-wrap justify-content-between gap-2 mb-3">
              <h4 className="section-title mb-0">Movimientos</h4>
              <div className="d-flex gap-2">
                <button className="btn btn-outline-dark btn-sm" onClick={() => setFilters({ date_from: todayISO(), date_to: todayISO(), account: "", status: "CONFIRMED", movement_type: "", code: "", provider: "", employee: "" })}>Limpiar</button>
                <button className="btn btn-outline-dark btn-sm" onClick={loadMovements}>Aplicar filtros</button>
                <button
                  className="btn btn-earth btn-sm"
                  onClick={() =>
                    exportRows(
                      `movimientos-caja-${filters.date_from || "desde"}-${filters.date_to || "hasta"}.csv`,
                      [
                        { label: "Fecha", value: "date_payment" },
                        { label: "Cuenta", value: "account_name" },
                        { label: "Codigo", value: "code_code" },
                        { label: "Tipo", value: (row) => statusLabel(row.movement_type) },
                        { label: "Importe", value: "amount" },
                        { label: "Descripcion", value: "description" },
                        { label: "Estado", value: "status" },
                      ],
                      movements,
                    )
                  }
                >
                  Exportar CSV
                </button>
              </div>
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-6">
                <div className="metric-card">
                  <span className="text-muted small">Ingresos filtrados</span>
                  <strong className="d-block">{money(filteredIncome)}</strong>
                </div>
              </div>
              <div className="col-md-6">
                <div className="metric-card">
                  <span className="text-muted small">Egresos filtrados</span>
                  <strong className="d-block">{money(filteredExpense)}</strong>
                </div>
              </div>
            </div>
            <div className="row g-2 mb-3">
              <div className="col-md-3"><TextInput label="Desde" type="date" value={filters.date_from} onChange={(v) => setFilters({ ...filters, date_from: v })} /></div>
              <div className="col-md-3"><TextInput label="Hasta" type="date" value={filters.date_to} onChange={(v) => setFilters({ ...filters, date_to: v })} /></div>
              <div className="col-md-3"><SelectInput label="Cuenta" value={filters.account} onChange={(v) => setFilters({ ...filters, account: v })} options={refs.accounts} labelFor={(a) => a.name} empty="Todas" /></div>
              <div className="col-md-3"><SelectInput label="Estado" value={filters.status} onChange={(v) => setFilters({ ...filters, status: v })} options={[{ id: "CONFIRMED", name: "Confirmados" }, { id: "VOIDED", name: "Anulados" }, { id: "DRAFT", name: "Borradores" }]} labelFor={(x) => x.name} empty="Todos" /></div>
              <div className="col-md-3"><SelectInput label="Tipo" value={filters.movement_type} onChange={(v) => setFilters({ ...filters, movement_type: v })} options={[{ id: "INCOME", name: "Ingreso" }, { id: "EXPENSE", name: "Egreso" }, { id: "ADJUSTMENT", name: "Ajuste" }, { id: "TRANSFER_IN", name: "Transferencia +" }, { id: "TRANSFER_OUT", name: "Transferencia -" }]} labelFor={(x) => x.name} empty="Todos" /></div>
              <div className="col-md-3"><SelectInput label="Codigo" value={filters.code} onChange={(v) => setFilters({ ...filters, code: v })} options={refs.movementCodes} labelFor={(c) => c.code} empty="Todos" /></div>
              <div className="col-md-3"><SelectInput label="Proveedor" value={filters.provider} onChange={(v) => setFilters({ ...filters, provider: v })} options={refs.providers} labelFor={(p) => p.name} empty="Todos" /></div>
              <div className="col-md-3"><SelectInput label="Empleado" value={filters.employee} onChange={(v) => setFilters({ ...filters, employee: v })} options={refs.employees} labelFor={(e) => e.display_name || `${e.first_name} ${e.last_name}`} empty="Todos" /></div>
            </div>
            <SimpleTable
              rows={movements}
              columns={[
                [(row) => formatDate(row.date_payment), "Fecha"],
                ["account_name", "Cuenta"],
                ["code_code", "Codigo"],
                [(row) => statusLabel(row.movement_type), "Tipo"],
                [(row) => money(row.amount), "Importe"],
                ["provider_name", "Proveedor"],
                ["employee_name", "Empleado"],
                ["description", "Descripcion"],
                [(row) => statusLabel(row.status), "Estado"],
                [(row) =>
                  row.status === "CONFIRMED" ? (
                    <button className="btn btn-sm btn-outline-danger" onClick={() => voidMovement(row)}>Anular</button>
                  ) : (
                    "-"
                  ), ""],
              ]}
            />
          </div>
        </div>
      </div>
    </>
  );
}

function AccountsScreen({ refs, mutate }) {
  const [account, setAccount] = useState({ name: "", type: "CASH", currency: "ARS", initial_balance: "0.00", notes: "" });
  const [adjust, setAdjust] = useState({ account: "", date: todayISO(), declared_balance: "", description: "" });

  return (
    <>
      <PageHeader title="Cuentas y ajustes" kicker="Billeteras">
        El saldo inicial vive en la cuenta. Las correcciones posteriores se hacen con movimientos de ajuste.
      </PageHeader>
      <div className="row g-3">
        <div className="col-lg-4">
          <form className="work-card" onSubmit={(e) => {
            e.preventDefault();
            if (!window.confirm(`Crear la cuenta ${account.name}?`)) {
              return;
            }
            mutate(() => api("/accounts/", { method: "POST", body: JSON.stringify(account) }), "Cuenta creada");
          }}>
            <h4 className="section-title">Nueva cuenta</h4>
            <TextInput label="Nombre" value={account.name} onChange={(v) => setAccount({ ...account, name: v })} required />
            <SelectInput label="Tipo" value={account.type} onChange={(v) => setAccount({ ...account, type: v })} options={["CASH", "BANK", "WALLET", "INVESTMENT", "FOREIGN_CURRENCY", "OTHER"].map((id) => ({ id }))} labelFor={(x) => x.id} />
            <SelectInput label="Moneda" value={account.currency} onChange={(v) => setAccount({ ...account, currency: v })} options={[{ id: "ARS" }, { id: "USD" }]} labelFor={(x) => x.id} />
            <TextInput label="Saldo inicial" type="number" value={account.initial_balance} onChange={(v) => setAccount({ ...account, initial_balance: v })} />
            <button className="btn btn-olive w-100 mt-2">Crear</button>
          </form>
          <form className="work-card mt-3" onSubmit={(e) => {
            e.preventDefault();
            if (!window.confirm(`Registrar ajuste de saldo para la cuenta seleccionada?`)) {
              return;
            }
            mutate(() => api(`/accounts/${adjust.account}/adjust-balance/`, { method: "POST", body: JSON.stringify(adjust) }), "Ajuste registrado");
          }}>
            <h4 className="section-title">Ajuste de saldo</h4>
            <SelectInput label="Cuenta" value={adjust.account} onChange={(v) => setAdjust({ ...adjust, account: v })} options={refs.accounts} labelFor={(a) => `${a.name} (${money(a.current_balance, a.currency)})`} required />
            <TextInput label="Fecha" type="date" value={adjust.date} onChange={(v) => setAdjust({ ...adjust, date: v })} required />
            <TextInput label="Saldo declarado" type="number" value={adjust.declared_balance} onChange={(v) => setAdjust({ ...adjust, declared_balance: v })} required />
            <TextInput label="Descripcion" value={adjust.description} onChange={(v) => setAdjust({ ...adjust, description: v })} />
            <button className="btn btn-earth w-100 mt-2">Crear ajuste</button>
          </form>
        </div>
        <div className="col-lg-8">
          <div className="work-card">
            <h4 className="section-title">Saldos actuales</h4>
            <SimpleTable rows={refs.accounts} columns={[
              ["name", "Cuenta"],
              ["type", "Tipo"],
              ["currency", "Moneda"],
              [(row) => money(row.initial_balance, row.currency), "Inicial"],
              [(row) => money(row.current_balance, row.currency), "Actual"],
              [(row) => (row.active ? "Activa" : "Inactiva"), "Estado"],
            ]} />
          </div>
        </div>
      </div>
    </>
  );
}

function TransfersScreen({ refs, mutate, reloadKey }) {
  const [form, setForm] = useState({ date: todayISO(), from_account: "", to_account: "", amount: "", fee_amount: "0.00", description: "" });
  const [transfers, setTransfers] = useState([]);

  useEffect(() => {
    api("/account-transfers/").then((data) => setTransfers(unwrap(data)));
  }, [reloadKey]);

  return (
    <>
      <PageHeader title="Transferencias internas" kicker="Entre cuentas">
        Una transferencia crea salida en origen y entrada en destino. La comision se registra como egreso separado.
      </PageHeader>
      <div className="row g-3">
        <div className="col-lg-4">
          <form className="work-card" onSubmit={(e) => {
            e.preventDefault();
            if (!window.confirm(`Crear transferencia por ${money(form.amount || 0)}?`)) {
              return;
            }
            mutate(() => api("/account-transfers/", { method: "POST", body: JSON.stringify(form) }), "Transferencia creada");
          }}>
            <SelectInput label="Desde" value={form.from_account} onChange={(v) => setForm({ ...form, from_account: v })} options={refs.accounts} labelFor={(a) => `${a.name} (${a.currency})`} required />
            <SelectInput label="Hacia" value={form.to_account} onChange={(v) => setForm({ ...form, to_account: v })} options={refs.accounts} labelFor={(a) => `${a.name} (${a.currency})`} required />
            <TextInput label="Fecha" type="date" value={form.date} onChange={(v) => setForm({ ...form, date: v })} required />
            <TextInput label="Importe" type="number" value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} required />
            <TextInput label="Comision" type="number" value={form.fee_amount} onChange={(v) => setForm({ ...form, fee_amount: v })} />
            <TextInput label="Descripcion" value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
            <button className="btn btn-earth w-100 mt-2">Transferir</button>
          </form>
        </div>
        <div className="col-lg-8">
          <div className="work-card">
            <h4 className="section-title">Ultimas transferencias</h4>
            <SimpleTable rows={transfers} columns={[
              ["date", "Fecha"],
              ["from_account_name", "Desde"],
              ["to_account_name", "Hacia"],
              [(row) => money(row.amount), "Importe"],
              [(row) => money(row.fee_amount), "Comision"],
              ["status", "Estado"],
            ]} />
          </div>
        </div>
      </div>
    </>
  );
}

function ClosesScreen({ refs, mutate, reloadKey }) {
  const [date, setDate] = useState(todayISO());
  const [declared, setDeclared] = useState({});
  const [closes, setCloses] = useState([]);
  const [dailySummary, setDailySummary] = useState({ account_closes: [] });
  const [balancesForDate, setBalancesForDate] = useState([]);

  useEffect(() => {
    api("/daily-cash-closes/").then((data) => setCloses(unwrap(data)));
  }, [reloadKey]);

  useEffect(() => {
    api(`/reports/daily-cash-summary/?date=${date}`)
      .then(setDailySummary)
      .catch(() => setDailySummary({ account_closes: [] }));
  }, [date, reloadKey]);

  useEffect(() => {
    api(`/reports/account-balances/?date=${date}`)
      .then(setBalancesForDate)
      .catch(() => setBalancesForDate([]));
  }, [date, reloadKey]);

  function declaredBalances() {
    return Object.fromEntries(
      refs.accounts.map((account) => {
        const datedBalance = balancesForDate.find((item) => item.id === account.id)?.balance ?? account.current_balance;
        return [String(account.id), declared[account.id] || datedBalance || "0.00"];
      }),
    );
  }

  async function closeFullDay() {
    if (!window.confirm(`Vas a cerrar el dia ${formatDate(date)} para todas las cuentas activas. Continuar?`)) {
      return;
    }
    await mutate(() => api("/daily-cash-closes/", { method: "POST", body: JSON.stringify({ date, declared_balances: declaredBalances() }) }), "Cierre general realizado");
  }

  async function closeOneAccount(row) {
    if (!window.confirm(`Vas a cerrar ${row.name} para ${formatDate(date)}. Continuar?`)) {
      return;
    }
    await mutate(
      () => api("/daily-cash-closes/close-account/", { method: "POST", body: JSON.stringify({ date, account: row.id, declared_balance: declared[row.id] ?? row.current_balance }) }),
      `Cierre de ${row.name} realizado`,
    );
  }

  return (
    <>
      <PageHeader title="Cierre diario" kicker="Por cuenta">
        Declara saldos, compara contra el calculado, exporta el cierre y deja bloqueado ese dia/cuenta para evitar cambios silenciosos.
      </PageHeader>
      <div className="work-card mb-3">
        <div className="d-flex flex-wrap align-items-end gap-2 mb-3">
          <div style={{ minWidth: 220 }}><TextInput label="Fecha de cierre" type="date" value={date} onChange={setDate} /></div>
          <button className="btn btn-earth mb-2" onClick={closeFullDay}>Cerrar dia completo</button>
          <button
            className="btn btn-outline-dark mb-2"
            onClick={() =>
              exportRows(
                `cierre-diario-${date}.csv`,
                [
                  { label: "Cuenta", value: "account_name" },
                  { label: "Moneda", value: "currency" },
                  { label: "Apertura", value: "opening_balance" },
                  { label: "Ingresos", value: "total_income" },
                  { label: "Egresos", value: "total_expense" },
                  { label: "Transferencias +", value: "total_transfer_in" },
                  { label: "Transferencias -", value: "total_transfer_out" },
                  { label: "Ajustes", value: "total_adjustments" },
                  { label: "Calculado", value: "calculated_balance" },
                  { label: "Declarado", value: "declared_balance" },
                  { label: "Diferencia", value: "difference" },
                ],
                dailySummary.account_closes || [],
              )
            }
          >
            Exportar cierre
          </button>
        </div>
        <SimpleTable rows={refs.accounts} columns={[
          ["name", "Cuenta"],
          ["currency", "Moneda"],
          [(row) => {
            const datedBalance = balancesForDate.find((item) => item.id === row.id)?.balance ?? row.current_balance;
            return money(datedBalance, row.currency);
          }, "Calculado fecha"],
          [(row) => (
            <input
              className="form-control"
              type="number"
              value={declared[row.id] ?? balancesForDate.find((item) => item.id === row.id)?.balance ?? row.current_balance ?? ""}
              onChange={(event) => setDeclared({ ...declared, [row.id]: event.target.value })}
            />
          ), "Saldo declarado"],
          [(row) => (
            <button className="btn btn-sm btn-outline-dark" onClick={() => closeOneAccount(row)}>
              Cerrar cuenta
            </button>
          ), ""],
        ]} />
      </div>
      <div className="work-card mb-3">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h4 className="section-title mb-0">Resumen del cierre seleccionado</h4>
          <div className="pill">{formatDate(date)}</div>
        </div>
        <SimpleTable rows={dailySummary.account_closes || []} columns={[
          ["account_name", "Cuenta"],
          ["currency", "Moneda"],
          [(row) => money(row.calculated_balance, row.currency), "Calculado"],
          [(row) => money(row.declared_balance, row.currency), "Declarado"],
          [(row) => money(row.difference, row.currency), "Diferencia"],
        ]} />
      </div>
      <div className="work-card">
        <h4 className="section-title">Cierres anteriores</h4>
        <SimpleTable rows={closes} columns={[
          [(row) => formatDate(row.date), "Fecha"],
          ["status", "Estado"],
          ["closed_at", "Cerrado"],
          [(row) => row.account_closes?.length || 0, "Cuentas"],
        ]} />
      </div>
    </>
  );
}

function ProvidersScreen({ refs, mutate, reloadKey }) {
  const [providerForm, setProviderForm] = useState({ name: "", category: "", phone: "", email: "", cuit: "" });
  const [selectedProvider, setSelectedProvider] = useState("");
  const [ledger, setLedger] = useState([]);
  const [debt, setDebt] = useState({ date: todayISO(), description: "", document_number: "", amount: "", event: "" });
  const [payment, setPayment] = useState({ date: todayISO(), account: "", amount: "", description: "", event: "", document_number: "" });

  useEffect(() => {
    if (selectedProvider) api(`/providers/${selectedProvider}/ledger/`).then(setLedger);
  }, [selectedProvider, reloadKey]);

  const selected = refs.providers.find((provider) => String(provider.id) === String(selectedProvider));
  const ledgerWithRunningBalance = [...ledger]
    .sort((left, right) => `${left.date}-${left.id}`.localeCompare(`${right.date}-${right.id}`))
    .reduce((accumulator, entry) => {
      const previous = accumulator.length ? accumulator[accumulator.length - 1].running_balance : 0;
      const delta =
        entry.entry_type === "DEBT" ? Number(entry.amount || 0) :
        entry.entry_type === "PAYMENT" ? -Number(entry.amount || 0) :
        Number(entry.amount || 0);
      accumulator.push({ ...entry, running_balance: previous + delta });
      return accumulator;
    }, []);

  return (
    <>
      <PageHeader title="Proveedores" kicker="Cuenta corriente">
        Podes cargar deuda sin mover caja o pagar directo. La cuenta corriente ahora muestra saldo acumulado y se puede exportar para compartir.
      </PageHeader>
      <div className="row g-3">
        <div className="col-lg-4">
          <form className="work-card" onSubmit={(e) => {
            e.preventDefault();
            mutate(() => api("/providers/", { method: "POST", body: JSON.stringify(providerForm) }), "Proveedor creado");
          }}>
            <h4 className="section-title">Nuevo proveedor</h4>
            <TextInput label="Nombre" value={providerForm.name} onChange={(v) => setProviderForm({ ...providerForm, name: v })} required />
            <TextInput label="Categoria" value={providerForm.category} onChange={(v) => setProviderForm({ ...providerForm, category: v })} />
            <TextInput label="CUIT" value={providerForm.cuit} onChange={(v) => setProviderForm({ ...providerForm, cuit: v })} />
            <TextInput label="Telefono" value={providerForm.phone} onChange={(v) => setProviderForm({ ...providerForm, phone: v })} />
            <button className="btn btn-olive w-100 mt-2">Crear proveedor</button>
          </form>
          <div className="work-card mt-3">
            <SelectInput label="Proveedor" value={selectedProvider} onChange={setSelectedProvider} options={refs.providers} labelFor={(p) => `${p.name} (${money(p.balance)})`} />
            {selected && <div className="metric-card mt-2"><span className="text-muted small">Saldo</span><strong className="d-block">{money(selected.balance)}</strong></div>}
          </div>
        </div>
        <div className="col-lg-8">
          {selectedProvider && (
            <div className="row g-3">
              <div className="col-md-6">
                <form className="work-card" onSubmit={(e) => {
                  e.preventDefault();
                  mutate(() => api("/provider-ledger/", { method: "POST", body: JSON.stringify({ ...debt, event: debt.event || null, provider: selectedProvider, entry_type: "DEBT" }) }), "Deuda de proveedor cargada");
                }}>
                  <h4 className="section-title">Cargar deuda/remito</h4>
                  <TextInput label="Fecha" type="date" value={debt.date} onChange={(v) => setDebt({ ...debt, date: v })} />
                  <TextInput label="Descripcion" value={debt.description} onChange={(v) => setDebt({ ...debt, description: v })} required />
                  <TextInput label="Documento" value={debt.document_number} onChange={(v) => setDebt({ ...debt, document_number: v })} />
                  <TextInput label="Importe" type="number" value={debt.amount} onChange={(v) => setDebt({ ...debt, amount: v })} required />
                  <button className="btn btn-outline-dark w-100 mt-2">Registrar deuda</button>
                </form>
              </div>
              <div className="col-md-6">
                <form className="work-card" onSubmit={(e) => {
                  e.preventDefault();
                  if (!window.confirm(`Registrar pago a ${selected?.name || "proveedor"} por ${money(payment.amount || 0)}?`)) {
                    return;
                  }
                  mutate(() => api(`/providers/${selectedProvider}/pay/`, { method: "POST", body: JSON.stringify(payment) }), "Pago a proveedor registrado");
                }}>
                  <h4 className="section-title">Pago directo</h4>
                  <SelectInput label="Cuenta" value={payment.account} onChange={(v) => setPayment({ ...payment, account: v })} options={refs.accounts} labelFor={(a) => a.name} required />
                  <TextInput label="Fecha" type="date" value={payment.date} onChange={(v) => setPayment({ ...payment, date: v })} />
                  <TextInput label="Importe" type="number" value={payment.amount} onChange={(v) => setPayment({ ...payment, amount: v })} required />
                  <TextInput label="Descripcion" value={payment.description} onChange={(v) => setPayment({ ...payment, description: v })} />
                  <button className="btn btn-earth w-100 mt-2">Pagar proveedor</button>
                </form>
              </div>
              <div className="col-12">
                <div className="work-card">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h4 className="section-title mb-0">Cuenta corriente</h4>
                    <button
                      className="btn btn-earth btn-sm"
                      onClick={() =>
                        exportRows(
                          `proveedor-${selected?.name || "cuenta-corriente"}.csv`,
                          [
                            { label: "Fecha", value: (row) => row.date },
                            { label: "Tipo", value: "entry_type" },
                            { label: "Descripcion", value: "description" },
                            { label: "Documento", value: "document_number" },
                            { label: "Importe", value: "amount" },
                            { label: "Saldo acumulado", value: "running_balance" },
                          ],
                          ledgerWithRunningBalance,
                        )
                      }
                    >
                      Exportar cuenta corriente
                    </button>
                  </div>
                  <SimpleTable rows={ledgerWithRunningBalance} columns={[
                    [(row) => formatDate(row.date), "Fecha"],
                    ["entry_type", "Tipo"],
                    ["description", "Descripcion"],
                    [(row) => money(row.amount), "Importe"],
                    ["document_number", "Documento"],
                    [(row) => money(row.running_balance), "Saldo"],
                  ]} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function PeopleScreen({ refs, mutate }) {
  const [employee, setEmployee] = useState({ first_name: "", last_name: "", alias: "", phone: "", document_number: "" });
  const [roleName, setRoleName] = useState("");
  const [assignment, setAssignment] = useState({ event: "", employee: "", role: "", work_date: todayISO(), base_amount: "", extra_amount: "0.00", status: "WORKED" });
  const [payment, setPayment] = useState({ employee: "", assignment: "", account: "", amount: "", payment_date: todayISO(), notes: "" });

  return (
    <>
      <PageHeader title="Personal eventual" kicker="Por evento">
        Asigna personas a eventos y paga parcial o totalmente sin perder el saldo pendiente.
      </PageHeader>
      <div className="row g-3">
        <div className="col-lg-4">
          <form className="work-card" onSubmit={(e) => {
            e.preventDefault();
            mutate(() => api("/employees/", { method: "POST", body: JSON.stringify(employee) }), "Empleado creado");
          }}>
            <h4 className="section-title">Empleado</h4>
            <TextInput label="Nombre" value={employee.first_name} onChange={(v) => setEmployee({ ...employee, first_name: v })} required />
            <TextInput label="Apellido" value={employee.last_name} onChange={(v) => setEmployee({ ...employee, last_name: v })} required />
            <TextInput label="Alias" value={employee.alias} onChange={(v) => setEmployee({ ...employee, alias: v })} />
            <TextInput label="Telefono" value={employee.phone} onChange={(v) => setEmployee({ ...employee, phone: v })} />
            <button className="btn btn-olive w-100 mt-2">Crear empleado</button>
          </form>
          <form className="work-card mt-3" onSubmit={(e) => {
            e.preventDefault();
            mutate(() => api("/employee-roles/", { method: "POST", body: JSON.stringify({ name: roleName }) }), "Rol creado");
          }}>
            <h4 className="section-title">Rol</h4>
            <TextInput label="Nombre del rol" value={roleName} onChange={setRoleName} required />
            <button className="btn btn-outline-dark w-100 mt-2">Crear rol</button>
          </form>
        </div>
        <div className="col-lg-8">
          <div className="row g-3">
            <div className="col-md-6">
              <form className="work-card" onSubmit={(e) => {
                e.preventDefault();
                mutate(() => api("/event-staff-assignments/", { method: "POST", body: JSON.stringify(assignment) }), "Asignacion creada");
              }}>
                <h4 className="section-title">Asignar a evento</h4>
                <SelectInput label="Evento" value={assignment.event} onChange={(v) => setAssignment({ ...assignment, event: v })} options={refs.events} labelFor={(e) => e.name} required />
                <SelectInput label="Empleado" value={assignment.employee} onChange={(v) => setAssignment({ ...assignment, employee: v })} options={refs.employees} labelFor={(e) => e.display_name || `${e.first_name} ${e.last_name}`} required />
                <SelectInput label="Rol" value={assignment.role} onChange={(v) => setAssignment({ ...assignment, role: v })} options={refs.roles} labelFor={(r) => r.name} required />
                <TextInput label="Fecha trabajo" type="date" value={assignment.work_date} onChange={(v) => setAssignment({ ...assignment, work_date: v })} />
                <TextInput label="Base" type="number" value={assignment.base_amount} onChange={(v) => setAssignment({ ...assignment, base_amount: v })} required />
                <TextInput label="Extra" type="number" value={assignment.extra_amount} onChange={(v) => setAssignment({ ...assignment, extra_amount: v })} />
                <button className="btn btn-olive w-100 mt-2">Asignar</button>
              </form>
            </div>
            <div className="col-md-6">
              <form className="work-card" onSubmit={(e) => {
                e.preventDefault();
                const selectedAssignment = refs.assignments.find((item) => String(item.id) === String(payment.assignment));
                mutate(() => api("/employee-payments/", { method: "POST", body: JSON.stringify({ ...payment, employee: payment.employee || selectedAssignment?.employee }) }), "Pago a empleado registrado");
              }}>
                <h4 className="section-title">Pago parcial/total</h4>
                <SelectInput label="Empleado" value={payment.employee} onChange={(v) => setPayment({ ...payment, employee: v })} options={refs.employees} labelFor={(e) => e.display_name || `${e.first_name} ${e.last_name}`} required />
                <SelectInput label="Asignacion" value={payment.assignment} onChange={(v) => {
                  const selected = refs.assignments.find((item) => String(item.id) === String(v));
                  setPayment({ ...payment, assignment: v, employee: selected?.employee || payment.employee });
                }} options={refs.assignments} labelFor={(a) => `${a.event_name} - ${a.employee_name} - pendiente ${money(a.pending_amount)}`} empty="Pago sin asignacion" />
                <SelectInput label="Cuenta" value={payment.account} onChange={(v) => setPayment({ ...payment, account: v })} options={refs.accounts} labelFor={(a) => a.name} required />
                <TextInput label="Fecha pago" type="date" value={payment.payment_date} onChange={(v) => setPayment({ ...payment, payment_date: v })} />
                <TextInput label="Importe" type="number" value={payment.amount} onChange={(v) => setPayment({ ...payment, amount: v })} required />
                <TextInput label="Notas" value={payment.notes} onChange={(v) => setPayment({ ...payment, notes: v })} />
                <button className="btn btn-earth w-100 mt-2">Registrar pago</button>
              </form>
            </div>
          </div>
          <div className="work-card mt-3">
            <h4 className="section-title">Empleados</h4>
            <SimpleTable rows={refs.employees} columns={[
              [(row) => row.display_name || `${row.first_name} ${row.last_name}`, "Nombre"],
              ["phone", "Telefono"],
              ["document_number", "Documento"],
              [(row) => (row.active ? "Activo" : "Inactivo"), "Estado"],
            ]} />
          </div>
          <div className="work-card mt-3">
            <h4 className="section-title">Asignaciones</h4>
            <SimpleTable rows={refs.assignments} columns={[
              ["event_name", "Evento"],
              ["employee_name", "Empleado"],
              ["role_name", "Rol"],
              ["work_date", "Fecha"],
              [(row) => money(row.total_amount), "Total"],
              [(row) => money(row.pending_amount), "Pendiente"],
              ["status", "Estado"],
            ]} />
          </div>
        </div>
      </div>
    </>
  );
}

function EventsScreen({ refs, mutate, reloadKey }) {
  const [client, setClient] = useState({ name: "", phone: "", email: "", notes: "" });
  const [newEvent, setNewEvent] = useState(emptyEventForm());
  const [selectedEventId, setSelectedEventId] = useState("");
  const [editingEvent, setEditingEvent] = useState(emptyEventForm());
  const [budget, setBudget] = useState(null);
  const [budgetForm, setBudgetForm] = useState({ status: "DRAFT", notes: "", optional_comments: "", internal_notes: "" });
  const [budgetItem, setBudgetItem] = useState(emptyBudgetItemForm());
  const [checkoutPreference, setCheckoutPreference] = useState(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [filters, setFilters] = useState({ search: "", status: "", client: "", event_type: "", internal_status: "", date_from: "", date_to: "" });
  const [overview, setOverview] = useState(null);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingBudget, setLoadingBudget] = useState(false);

  const filteredEvents = refs.events.filter((row) => {
    const haystack = [row.name, row.client_name, row.event_type, row.venue_space, row.internal_status]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const matchesSearch = !filters.search || haystack.includes(filters.search.toLowerCase());
    const matchesStatus = !filters.status || row.status === filters.status;
    const matchesClient = !filters.client || String(row.client) === String(filters.client);
    const matchesType = !filters.event_type || (row.event_type || "").toLowerCase().includes(filters.event_type.toLowerCase());
    const matchesInternal = !filters.internal_status || (row.internal_status || "").toLowerCase().includes(filters.internal_status.toLowerCase());
    const matchesFrom = !filters.date_from || (row.event_date && row.event_date >= filters.date_from);
    const matchesTo = !filters.date_to || (row.event_date && row.event_date <= filters.date_to);
    return matchesSearch && matchesStatus && matchesClient && matchesType && matchesInternal && matchesFrom && matchesTo;
  });

  useEffect(() => {
    if (!filteredEvents.length) {
      setSelectedEventId("");
      return;
    }
    const currentExists = filteredEvents.some((event) => String(event.id) === String(selectedEventId));
    if (!currentExists) {
      setSelectedEventId(String(filteredEvents[0].id));
    }
  }, [filteredEvents, selectedEventId]);

  useEffect(() => {
    const selected = refs.events.find((event) => String(event.id) === String(selectedEventId));
    setEditingEvent(normalizeEventForForm(selected));
  }, [selectedEventId, refs.events]);

  useEffect(() => {
    if (!selectedEventId) {
      setOverview(null);
      return;
    }
    setLoadingOverview(true);
    api(`/events/${selectedEventId}/overview/`)
      .then(setOverview)
      .catch(() => setOverview(null))
      .finally(() => setLoadingOverview(false));
  }, [selectedEventId, reloadKey]);

  useEffect(() => {
    if (!selectedEventId) {
      setBudget(null);
      setCheckoutPreference(null);
      return;
    }
    setLoadingBudget(true);
    api(`/events/${selectedEventId}/budget/`)
      .then((data) => {
        setBudget(data);
        setCheckoutPreference(null);
        setBudgetForm({
          status: data.status || "DRAFT",
          notes: data.notes || "",
          optional_comments: data.optional_comments || "",
          internal_notes: data.internal_notes || "",
        });
      })
      .catch(() => setBudget(null))
      .finally(() => setLoadingBudget(false));
  }, [selectedEventId, reloadKey]);

  const selectedEvent = refs.events.find((event) => String(event.id) === String(selectedEventId));
  const latestPayment = checkoutPreference || budget?.latest_payment;
  const checkoutUrl = latestPayment?.init_point || latestPayment?.preference_init_point || latestPayment?.sandbox_init_point || latestPayment?.preference_sandbox_init_point || null;
  const selectedBudgetPayments = refs.eventBudgetPayments.filter((payment) => String(payment.event_id) === String(selectedEventId));

  return (
    <>
      <PageHeader title="Ficha de eventos" kicker="Etapa 1">
        Alta completa, filtros por fecha y cliente, y una ficha editable con contexto operativo sin romper la integracion actual con caja, proveedores y personal.
      </PageHeader>
      <div className="row g-3">
        <div className="col-xl-4">
          <form
            className="work-card"
            onSubmit={(e) => {
              e.preventDefault();
              mutate(async () => {
                await api("/clients/", { method: "POST", body: JSON.stringify(client) });
                setClient({ name: "", phone: "", email: "", notes: "" });
              }, "Cliente creado");
            }}
          >
            <h4 className="section-title">Cliente rapido</h4>
            <TextInput label="Nombre" value={client.name} onChange={(v) => setClient({ ...client, name: v })} required />
            <TextInput label="Telefono" value={client.phone} onChange={(v) => setClient({ ...client, phone: v })} />
            <TextInput label="Email" value={client.email} onChange={(v) => setClient({ ...client, email: v })} />
            <TextAreaInput label="Notas" value={client.notes} onChange={(v) => setClient({ ...client, notes: v })} rows={2} />
            <button className="btn btn-olive w-100 mt-2">Crear cliente</button>
          </form>

          <form
            className="work-card mt-3"
            onSubmit={(e) => {
              e.preventDefault();
              mutate(async () => {
                const created = await api("/events/", { method: "POST", body: JSON.stringify(buildEventPayload(newEvent)) });
                setNewEvent(emptyEventForm());
                setSelectedEventId(String(created.id));
              }, "Evento creado");
            }}
          >
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h4 className="section-title mb-0">Nuevo evento</h4>
              <span className="text-muted small">Alta comercial y operativa</span>
            </div>
            <SelectInput label="Cliente" value={newEvent.client} onChange={(v) => setNewEvent({ ...newEvent, client: v })} options={refs.clients} labelFor={(c) => c.name} empty="Sin cliente asociado" />
            <TextInput label="Nombre del evento" value={newEvent.name} onChange={(v) => setNewEvent({ ...newEvent, name: v })} required />
            <div className="row g-2">
              <div className="col-md-6"><TextInput label="Tipo" value={newEvent.event_type} onChange={(v) => setNewEvent({ ...newEvent, event_type: v })} /></div>
              <div className="col-md-6"><TextInput label="Espacio / salon" value={newEvent.venue_space} onChange={(v) => setNewEvent({ ...newEvent, venue_space: v })} /></div>
              <div className="col-md-6"><TextInput label="Fecha" type="date" value={newEvent.event_date} onChange={(v) => setNewEvent({ ...newEvent, event_date: v })} /></div>
              <div className="col-md-6"><TextInput label="Hora" type="time" value={newEvent.event_time} onChange={(v) => setNewEvent({ ...newEvent, event_time: v })} /></div>
            </div>
            <div className="row g-2">
              <div className="col-md-6"><TextInput label="Personas cena" type="number" value={newEvent.guest_count_dinner} onChange={(v) => setNewEvent({ ...newEvent, guest_count_dinner: v })} /></div>
              <div className="col-md-6"><TextInput label="Personas brindis" type="number" value={newEvent.guest_count_toast} onChange={(v) => setNewEvent({ ...newEvent, guest_count_toast: v })} /></div>
            </div>
            <TextInput label="Mesa principal" value={newEvent.main_table_notes} onChange={(v) => setNewEvent({ ...newEvent, main_table_notes: v })} />
            <button className="btn btn-earth w-100 mt-2">Crear evento</button>
          </form>

          <div className="work-card mt-3">
            <h4 className="section-title">Filtros</h4>
            <TextInput label="Buscar" value={filters.search} onChange={(v) => setFilters({ ...filters, search: v })} placeholder="Evento, cliente, salon o contacto" />
            <div className="row g-2">
              <div className="col-md-6">
                <SelectInput label="Estado" value={filters.status} onChange={(v) => setFilters({ ...filters, status: v })} options={eventStatusOptions} labelFor={(option) => option.name} empty="Todos" />
              </div>
              <div className="col-md-6">
                <SelectInput label="Cliente" value={filters.client} onChange={(v) => setFilters({ ...filters, client: v })} options={refs.clients} labelFor={(c) => c.name} empty="Todos" />
              </div>
              <div className="col-md-6"><TextInput label="Tipo" value={filters.event_type} onChange={(v) => setFilters({ ...filters, event_type: v })} placeholder="Cumple, boda, empresa" /></div>
              <div className="col-md-6"><TextInput label="Estado interno" value={filters.internal_status} onChange={(v) => setFilters({ ...filters, internal_status: v })} placeholder="Presupuesto, menu, listo..." /></div>
              <div className="col-md-6"><TextInput label="Desde" type="date" value={filters.date_from} onChange={(v) => setFilters({ ...filters, date_from: v })} /></div>
              <div className="col-md-6"><TextInput label="Hasta" type="date" value={filters.date_to} onChange={(v) => setFilters({ ...filters, date_to: v })} /></div>
            </div>
          </div>
        </div>

        <div className="col-xl-8">
          <div className="work-card mb-3">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h4 className="section-title mb-0">Agenda de eventos</h4>
              <span className="text-muted small">{filteredEvents.length} evento(s)</span>
            </div>
            <div className="row g-2">
              {filteredEvents.length === 0 && <div className="text-muted text-center py-4">No hay eventos para los filtros elegidos.</div>}
              {filteredEvents.map((item) => (
                <div className="col-md-6" key={item.id}>
                  <button
                    type="button"
                    className={`w-100 text-start border rounded-4 p-3 bg-white ${String(selectedEventId) === String(item.id) ? "border-dark shadow-sm" : "border-light-subtle"}`}
                    onClick={() => setSelectedEventId(String(item.id))}
                  >
                    <div className="d-flex justify-content-between gap-3">
                      <div>
                        <div className="fw-semibold">{item.name}</div>
                        <div className="text-muted small">{item.client_name || item.contact_name || "Sin cliente asociado"}</div>
                      </div>
                      <div className="text-end small">
                        <div>{formatDate(item.event_date)}</div>
                        <div>{formatTime(item.event_time)}</div>
                      </div>
                    </div>
                    <div className="small text-muted mt-2">
                      {(item.event_type || "Sin tipo")} {item.venue_space ? `· ${item.venue_space}` : ""} {item.internal_status ? `· ${item.internal_status}` : ""}
                    </div>
                  </button>
                </div>
              ))}
            </div>
          </div>

          {selectedEvent ? (
            <>
              <div className="row g-3 mb-3">
                <div className="col-md-3">
                  <div className="metric-card h-100">
                    <span className="text-muted small">Invitados referencia</span>
                    <strong className="d-block">{overview?.event?.guest_count_total || 0}</strong>
                  </div>
                </div>
                <div className="col-md-3">
                  <div className="metric-card h-100">
                    <span className="text-muted small">Movimientos vinculados</span>
                    <strong className="d-block">{overview?.linked_counts?.movements || 0}</strong>
                  </div>
                </div>
                <div className="col-md-3">
                  <div className="metric-card h-100">
                    <span className="text-muted small">Personal asignado</span>
                    <strong className="d-block">{overview?.linked_counts?.assignments || 0}</strong>
                  </div>
                </div>
                  <div className="col-md-3">
                    <div className="metric-card h-100">
                      <span className="text-muted small">Total presupuestado</span>
                      <strong className="d-block">{money(overview?.budget_summary?.grand_total || 0)}</strong>
                    </div>
                  </div>
              </div>

              <div className="work-card mb-3">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h4 className="section-title mb-0">Ficha del evento</h4>
                  <span className="text-muted small">{loadingOverview ? "Actualizando resumen..." : "Detalle editable"}</span>
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    mutate(
                      () => api(`/events/${selectedEventId}/`, { method: "PUT", body: JSON.stringify(buildEventPayload(editingEvent)) }),
                      "Evento actualizado",
                    );
                  }}
                >
                  <div className="row g-2">
                    <div className="col-md-6">
                      <SelectInput label="Cliente" value={editingEvent.client} onChange={(v) => setEditingEvent({ ...editingEvent, client: v })} options={refs.clients} labelFor={(c) => c.name} empty="Sin cliente asociado" />
                    </div>
                    <div className="col-md-6">
                      <SelectInput label="Estado" value={editingEvent.status} onChange={(v) => setEditingEvent({ ...editingEvent, status: v })} options={eventStatusOptions} labelFor={(option) => option.name} required />
                    </div>
                    <div className="col-md-6"><TextInput label="Nombre del evento" value={editingEvent.name} onChange={(v) => setEditingEvent({ ...editingEvent, name: v })} required /></div>
                    <div className="col-md-3"><TextInput label="Tipo" value={editingEvent.event_type} onChange={(v) => setEditingEvent({ ...editingEvent, event_type: v })} /></div>
                    <div className="col-md-3"><TextInput label="Espacio / salon" value={editingEvent.venue_space} onChange={(v) => setEditingEvent({ ...editingEvent, venue_space: v })} /></div>
                    <div className="col-md-3"><TextInput label="Fecha" type="date" value={editingEvent.event_date} onChange={(v) => setEditingEvent({ ...editingEvent, event_date: v })} /></div>
                    <div className="col-md-3"><TextInput label="Hora" type="time" value={editingEvent.event_time} onChange={(v) => setEditingEvent({ ...editingEvent, event_time: v })} /></div>
                    <div className="col-md-3"><TextInput label="Personas cena" type="number" value={editingEvent.guest_count_dinner} onChange={(v) => setEditingEvent({ ...editingEvent, guest_count_dinner: v })} /></div>
                    <div className="col-md-3"><TextInput label="Personas brindis" type="number" value={editingEvent.guest_count_toast} onChange={(v) => setEditingEvent({ ...editingEvent, guest_count_toast: v })} /></div>
                    <div className="col-md-6"><TextInput label="Estado interno" value={editingEvent.internal_status} onChange={(v) => setEditingEvent({ ...editingEvent, internal_status: v })} placeholder="Presupuesto, menu, listo para operar..." /></div>
                    <div className="col-md-6"><TextInput label="Mesa principal" value={editingEvent.main_table_notes} onChange={(v) => setEditingEvent({ ...editingEvent, main_table_notes: v })} /></div>
                    <div className="col-md-6"><TextInput label="Contacto alternativo" value={editingEvent.contact_name} onChange={(v) => setEditingEvent({ ...editingEvent, contact_name: v })} /></div>
                    <div className="col-md-3"><TextInput label="Telefono contacto" value={editingEvent.contact_phone} onChange={(v) => setEditingEvent({ ...editingEvent, contact_phone: v })} /></div>
                    <div className="col-md-3"><TextInput label="Email contacto" type="email" value={editingEvent.contact_email} onChange={(v) => setEditingEvent({ ...editingEvent, contact_email: v })} /></div>
                  </div>
                  <div className="row g-2 mt-1">
                    <div className="col-md-6"><TextAreaInput label="Manteleria / vajilla" value={editingEvent.tableware_notes} onChange={(v) => setEditingEvent({ ...editingEvent, tableware_notes: v })} rows={2} /></div>
                    <div className="col-md-6"><TextAreaInput label="Protocolo y ceremonia" value={editingEvent.protocol_notes} onChange={(v) => setEditingEvent({ ...editingEvent, protocol_notes: v })} rows={2} /></div>
                    <div className="col-md-6"><TextAreaInput label="Bebidas / barra" value={editingEvent.beverage_notes} onChange={(v) => setEditingEvent({ ...editingEvent, beverage_notes: v })} rows={2} /></div>
                    <div className="col-md-6"><TextAreaInput label="Adicionales" value={editingEvent.additional_notes} onChange={(v) => setEditingEvent({ ...editingEvent, additional_notes: v })} rows={2} /></div>
                    <div className="col-md-6"><TextAreaInput label="Observaciones generales" value={editingEvent.notes} onChange={(v) => setEditingEvent({ ...editingEvent, notes: v })} rows={3} /></div>
                    <div className="col-md-6"><TextAreaInput label="Observaciones operativas" value={editingEvent.operational_notes} onChange={(v) => setEditingEvent({ ...editingEvent, operational_notes: v })} rows={3} /></div>
                  </div>
                  <div className="d-flex justify-content-end mt-3">
                    <button className="btn btn-earth">Guardar cambios</button>
                  </div>
                </form>
              </div>

              <div className="row g-3">
                <div className="col-lg-6">
                  <div className="work-card h-100">
                    <h4 className="section-title">Resumen del cliente y servicio</h4>
                    <SimpleTable
                      rows={[
                        {
                          client: overview?.event?.client_name || selectedEvent.client_name || "-",
                          phone: overview?.event?.client_phone || "-",
                          email: overview?.event?.client_email || selectedEvent.contact_email || "-",
                          venue: overview?.event?.venue_space || "-",
                          dinner: overview?.event?.guest_count_dinner || 0,
                          toast: overview?.event?.guest_count_toast || 0,
                          status: overview?.event?.status || "-",
                        },
                      ]}
                      columns={[
                        ["client", "Cliente"],
                        ["phone", "Telefono"],
                        ["email", "Email"],
                        ["venue", "Salon"],
                        ["dinner", "Cena"],
                        ["toast", "Brindis"],
                        ["status", "Estado"],
                      ]}
                    />
                  </div>
                </div>
                <div className="col-lg-6">
                  <div className="work-card h-100">
                    <h4 className="section-title">Vinculos actuales</h4>
                    <SimpleTable
                      rows={[
                        {
                          movements: overview?.linked_counts?.movements || 0,
                          providers: overview?.linked_counts?.providers || 0,
                          assignments: overview?.linked_counts?.assignments || 0,
                          payments: overview?.linked_counts?.employee_payments || 0,
                          budgetItems: overview?.budget_summary?.item_count || 0,
                          providerDebt: money(overview?.financial?.provider_debt || 0),
                          quoted: money(overview?.budget_summary?.grand_total || 0),
                          staffingPending: money(overview?.financial?.staffing_pending || 0),
                        },
                      ]}
                      columns={[
                        ["movements", "Mov. caja"],
                        ["providers", "Prov."],
                        ["assignments", "Personal"],
                        ["payments", "Pagos personal"],
                        ["budgetItems", "Items pres."],
                        ["providerDebt", "Deuda prov."],
                        ["quoted", "Presupuesto"],
                        ["staffingPending", "Pendiente personal"],
                      ]}
                    />
                  </div>
                </div>
              </div>

              <div className="work-card mt-3">
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div>
                    <h4 className="section-title mb-0">Presupuesto comercial</h4>
                    <div className="text-muted small">Servicios, opcionales y total del evento.</div>
                  </div>
                  <span className="text-muted small">{loadingBudget ? "Cargando presupuesto..." : `${budget?.item_count || 0} item(s)`}</span>
                </div>
                <div className="row g-3 mb-3">
                  <div className="col-md-3">
                    <div className="metric-card h-100">
                      <span className="text-muted small">Base</span>
                      <strong className="d-block">{money(budget?.subtotal || 0)}</strong>
                    </div>
                  </div>
                  <div className="col-md-3">
                    <div className="metric-card h-100">
                      <span className="text-muted small">Opcionales</span>
                      <strong className="d-block">{money(budget?.optional_total || 0)}</strong>
                    </div>
                  </div>
                  <div className="col-md-3">
                    <div className="metric-card h-100">
                      <span className="text-muted small">Total</span>
                      <strong className="d-block">{money(budget?.grand_total || 0)}</strong>
                    </div>
                  </div>
                  <div className="col-md-3">
                    <div className="metric-card h-100">
                      <span className="text-muted small">Estado presupuesto</span>
                      <strong className="d-block">{statusLabel(budget?.status || "DRAFT")}</strong>
                    </div>
                  </div>
                </div>

                <div className="border rounded-4 p-3 mb-3">
                  <div className="d-flex flex-wrap justify-content-between align-items-center gap-2">
                    <div>
                      <h4 className="section-title mb-1">Pago online</h4>
                      <div className="text-muted small">
                        {latestPayment ? `Estado: ${statusLabel(latestPayment.status)} · ${money(latestPayment.amount || budget?.grand_total || 0)}` : "Sin preferencia generada para este presupuesto."}
                      </div>
                    </div>
                    <div className="d-flex flex-wrap gap-2">
                      {checkoutUrl ? (
                        <a className="btn btn-outline-dark" href={checkoutUrl} target="_blank" rel="noreferrer">
                          Abrir checkout
                        </a>
                      ) : null}
                      <button
                        type="button"
                        className="btn btn-earth"
                        disabled={!budget?.id || paymentLoading || Number(budget?.grand_total || 0) <= 0}
                        onClick={() => {
                          if (!budget?.id) return;
                          setPaymentLoading(true);
                          mutate(
                            async () => {
                              const preference = await api("/event-budget-payments/create-preference/", {
                                method: "POST",
                                body: JSON.stringify({ budget: budget.id }),
                              });
                              setCheckoutPreference(preference);
                              const url = preference.init_point || preference.sandbox_init_point;
                              if (url) window.open(url, "_blank", "noreferrer");
                            },
                            "Preferencia de Mercado Pago preparada",
                          ).finally(() => setPaymentLoading(false));
                        }}
                      >
                        {paymentLoading ? "Preparando..." : "Preparar pago"}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="border rounded-4 p-3 mb-3">
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <h4 className="section-title mb-0">Cobranzas online</h4>
                    <span className="text-muted small">{selectedBudgetPayments.length} intento(s)</span>
                  </div>
                  {selectedBudgetPayments.length ? (
                    <SimpleTable
                      rows={selectedBudgetPayments}
                      columns={[
                        [(row) => statusLabel(row.status), "Estado"],
                        [(row) => money(row.amount, row.currency), "Importe"],
                        ["mp_payment_id", "Pago MP"],
                        ["cash_movement_account", "Cuenta"],
                        [(row) => formatDate(row.cash_movement_date), "Fecha caja"],
                      ]}
                    />
                  ) : (
                    <div className="text-muted small">Todavia no hay intentos de pago para este evento.</div>
                  )}
                </div>

                <div className="row g-3">
                  <div className="col-lg-5">
                    <form
                      className="work-card"
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (!budget?.id) return;
                        mutate(
                          () => api(`/event-budgets/${budget.id}/`, { method: "PUT", body: JSON.stringify({ ...budget, ...budgetForm, event: selectedEventId }) }),
                          "Presupuesto actualizado",
                        );
                      }}
                    >
                      <h4 className="section-title">Cabecera del presupuesto</h4>
                      <SelectInput label="Estado" value={budgetForm.status} onChange={(v) => setBudgetForm({ ...budgetForm, status: v })} options={budgetStatusOptions} labelFor={(option) => option.name} required />
                      <TextAreaInput label="Notas comerciales" value={budgetForm.notes} onChange={(v) => setBudgetForm({ ...budgetForm, notes: v })} rows={3} />
                      <TextAreaInput label="Comentarios opcionales" value={budgetForm.optional_comments} onChange={(v) => setBudgetForm({ ...budgetForm, optional_comments: v })} rows={3} />
                      <TextAreaInput label="Notas internas" value={budgetForm.internal_notes} onChange={(v) => setBudgetForm({ ...budgetForm, internal_notes: v })} rows={3} />
                      <button className="btn btn-outline-dark w-100 mt-2" disabled={!budget?.id}>Guardar cabecera</button>
                    </form>

                    <form
                      className="work-card mt-3"
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (!budget?.id) return;
                        mutate(
                          async () => {
                            await api("/event-budget-items/", {
                              method: "POST",
                              body: JSON.stringify({
                                ...budgetItem,
                                budget: budget.id,
                                quantity: Number(budgetItem.quantity || 0),
                                unit_price: Number(budgetItem.unit_price || 0),
                                sort_order: Number(budgetItem.sort_order || 0),
                              }),
                            });
                            setBudgetItem(emptyBudgetItemForm());
                          },
                          "Item de presupuesto agregado",
                        );
                      }}
                    >
                      <h4 className="section-title">Nuevo item</h4>
                      <TextInput label="Servicio" value={budgetItem.service_name} onChange={(v) => setBudgetItem({ ...budgetItem, service_name: v })} required />
                      <div className="row g-2">
                        <div className="col-md-6"><TextInput label="Categoria" value={budgetItem.category} onChange={(v) => setBudgetItem({ ...budgetItem, category: v })} /></div>
                        <div className="col-md-6"><TextInput label="Unidad" value={budgetItem.unit_label} onChange={(v) => setBudgetItem({ ...budgetItem, unit_label: v })} placeholder="personas, fijo, horas..." /></div>
                        <div className="col-md-4"><TextInput label="Cantidad" type="number" value={budgetItem.quantity} onChange={(v) => setBudgetItem({ ...budgetItem, quantity: v })} required /></div>
                        <div className="col-md-4"><TextInput label="Precio unitario" type="number" value={budgetItem.unit_price} onChange={(v) => setBudgetItem({ ...budgetItem, unit_price: v })} required /></div>
                        <div className="col-md-4"><TextInput label="Orden" type="number" value={budgetItem.sort_order} onChange={(v) => setBudgetItem({ ...budgetItem, sort_order: v })} /></div>
                      </div>
                      <div className="form-check mt-2">
                        <input className="form-check-input" id="budget-item-optional" type="checkbox" checked={budgetItem.is_optional} onChange={(e) => setBudgetItem({ ...budgetItem, is_optional: e.target.checked })} />
                        <label className="form-check-label" htmlFor="budget-item-optional">Es opcional</label>
                      </div>
                      <TextAreaInput label="Notas" value={budgetItem.notes} onChange={(v) => setBudgetItem({ ...budgetItem, notes: v })} rows={2} />
                      <button className="btn btn-earth w-100 mt-2" disabled={!budget?.id}>Agregar item</button>
                    </form>
                  </div>

                  <div className="col-lg-7">
                    <div className="work-card h-100">
                      <div className="d-flex justify-content-between align-items-center mb-3">
                        <h4 className="section-title mb-0">Items del presupuesto</h4>
                        <span className="text-muted small">Edicion inline y borrado con trazabilidad simple.</span>
                      </div>
                      {!budget?.items?.length ? (
                        <div className="text-muted text-center py-4">Todavia no hay items cargados para este evento.</div>
                      ) : (
                        <div className="d-flex flex-column gap-3">
                          {budget.items.map((item) => (
                            <form
                              key={item.id}
                              className="border rounded-4 p-3"
                              onSubmit={(e) => {
                                e.preventDefault();
                                mutate(
                                  () =>
                                    api(`/event-budget-items/${item.id}/`, {
                                      method: "PUT",
                                      body: JSON.stringify({
                                        ...item,
                                        quantity: Number(item.quantity || 0),
                                        unit_price: Number(item.unit_price || 0),
                                        sort_order: Number(item.sort_order || 0),
                                      }),
                                    }),
                                  "Item actualizado",
                                );
                              }}
                            >
                              <div className="row g-2">
                                <div className="col-md-5">
                                  <TextInput
                                    label="Servicio"
                                    value={item.service_name}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, service_name: v } : row)),
                                      })
                                    }
                                    required
                                  />
                                </div>
                                <div className="col-md-3">
                                  <TextInput
                                    label="Categoria"
                                    value={item.category || ""}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, category: v } : row)),
                                      })
                                    }
                                  />
                                </div>
                                <div className="col-md-2">
                                  <TextInput
                                    label="Cantidad"
                                    type="number"
                                    value={item.quantity}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, quantity: v } : row)),
                                      })
                                    }
                                    required
                                  />
                                </div>
                                <div className="col-md-2">
                                  <TextInput
                                    label="P. unit."
                                    type="number"
                                    value={item.unit_price}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, unit_price: v } : row)),
                                      })
                                    }
                                    required
                                  />
                                </div>
                                <div className="col-md-3">
                                  <TextInput
                                    label="Unidad"
                                    value={item.unit_label || ""}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, unit_label: v } : row)),
                                      })
                                    }
                                  />
                                </div>
                                <div className="col-md-2">
                                  <TextInput
                                    label="Orden"
                                    type="number"
                                    value={item.sort_order}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, sort_order: v } : row)),
                                      })
                                    }
                                  />
                                </div>
                                <div className="col-md-3 d-flex align-items-end">
                                  <div className="form-check mb-2">
                                    <input
                                      className="form-check-input"
                                      id={`item-optional-${item.id}`}
                                      type="checkbox"
                                      checked={Boolean(item.is_optional)}
                                      onChange={(e) =>
                                        setBudget({
                                          ...budget,
                                          items: budget.items.map((row) => (row.id === item.id ? { ...row, is_optional: e.target.checked } : row)),
                                        })
                                      }
                                    />
                                    <label className="form-check-label" htmlFor={`item-optional-${item.id}`}>Opcional</label>
                                  </div>
                                </div>
                                <div className="col-md-4 d-flex align-items-end">
                                  <div className="small text-muted">Total calculado: <strong>{money(item.total || 0)}</strong></div>
                                </div>
                                <div className="col-12">
                                  <TextAreaInput
                                    label="Notas"
                                    value={item.notes || ""}
                                    onChange={(v) =>
                                      setBudget({
                                        ...budget,
                                        items: budget.items.map((row) => (row.id === item.id ? { ...row, notes: v } : row)),
                                      })
                                    }
                                    rows={2}
                                  />
                                </div>
                              </div>
                              <div className="d-flex gap-2 justify-content-end mt-2">
                                <button className="btn btn-sm btn-outline-dark" type="submit">Guardar item</button>
                                <button
                                  className="btn btn-sm btn-outline-danger"
                                  type="button"
                                  onClick={() => {
                                    if (!window.confirm(`Eliminar "${item.service_name}" del presupuesto?`)) return;
                                    mutate(() => api(`/event-budget-items/${item.id}/`, { method: "DELETE" }), "Item eliminado");
                                  }}
                                >
                                  Eliminar
                                </button>
                              </div>
                            </form>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="work-card">
              <h4 className="section-title">Sin evento seleccionado</h4>
              <p className="text-muted mb-0">Crea un evento o elegi uno de la agenda para completar su ficha.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function TaxesScreen({ refs, mutate, reloadKey }) {
  const [payment, setPayment] = useState({
    tax_type: "",
    account: "",
    payment_date: todayISO(),
    amount: "",
    period: "",
    notes: "",
    recurrence_type: "NONE",
    reminder_due_date: "",
    remind_before_days: 0,
  });
  const [reminders, setReminders] = useState([]);

  useEffect(() => {
    api("/reminders/?status=PENDING").then((data) => setReminders(unwrap(data)));
  }, [reloadKey]);

  return (
    <>
      <PageHeader title="Impuestos y recordatorios" kicker="Vencimientos">
        Un pago de impuesto genera movimiento de caja y, si queres, el proximo recordatorio.
      </PageHeader>
      <div className="row g-3">
        <div className="col-lg-4">
          <form className="work-card" onSubmit={(e) => {
            e.preventDefault();
            mutate(() => api("/tax-payments/", { method: "POST", body: JSON.stringify(payment) }), "Pago de impuesto registrado");
          }}>
            <h4 className="section-title">Pago de impuesto</h4>
            <SelectInput label="Tipo" value={payment.tax_type} onChange={(v) => setPayment({ ...payment, tax_type: v })} options={refs.taxTypes} labelFor={(t) => t.name} required />
            <SelectInput label="Cuenta" value={payment.account} onChange={(v) => setPayment({ ...payment, account: v })} options={refs.accounts} labelFor={(a) => a.name} required />
            <TextInput label="Fecha pago" type="date" value={payment.payment_date} onChange={(v) => setPayment({ ...payment, payment_date: v })} />
            <TextInput label="Periodo" value={payment.period} onChange={(v) => setPayment({ ...payment, period: v })} />
            <TextInput label="Importe" type="number" value={payment.amount} onChange={(v) => setPayment({ ...payment, amount: v })} required />
            <SelectInput label="Recurrencia" value={payment.recurrence_type} onChange={(v) => setPayment({ ...payment, recurrence_type: v })} options={["NONE", "MONTHLY", "BIMONTHLY", "QUARTERLY", "YEARLY", "CUSTOM_DAYS"].map((id) => ({ id }))} labelFor={(x) => x.id} />
            <TextInput label="Vencimiento manual" type="date" value={payment.reminder_due_date} onChange={(v) => setPayment({ ...payment, reminder_due_date: v })} />
            <button className="btn btn-earth w-100 mt-2">Registrar impuesto</button>
          </form>
        </div>
        <div className="col-lg-8">
          <div className="work-card">
            <h4 className="section-title">Recordatorios pendientes</h4>
            <SimpleTable rows={reminders} columns={[
              [(row) => formatDate(row.due_date), "Vence"],
              ["title", "Titulo"],
              ["description", "Descripcion"],
              [(row) => statusLabel(row.status), "Estado"],
              [(row) => <button className="btn btn-sm btn-outline-dark" onClick={() => {
                if (!window.confirm(`Marcar "${row.title}" como completado?`)) {
                  return;
                }
                mutate(() => api(`/reminders/${row.id}/complete/`, { method: "POST", body: JSON.stringify({}) }), "Recordatorio completado");
              }}>Completar</button>, ""],
            ]} />
          </div>
        </div>
      </div>
    </>
  );
}

function ReportsScreen({ refs }) {
  const [dateFrom, setDateFrom] = useState(todayISO().slice(0, 8) + "01");
  const [dateTo, setDateTo] = useState(todayISO());
  const [eventId, setEventId] = useState("");
  const [report, setReport] = useState({ title: "Todavia no corriste ningun reporte.", rows: [], columns: [], summary: [] });
  const [loading, setLoading] = useState(false);

  async function run(kind) {
    setLoading(true);
    try {
      const period = `date_from=${dateFrom}&date_to=${dateTo}`;
      if (kind === "daily-close") {
        const data = await api(`/reports/daily-cash-summary/?date=${dateTo}`);
        setReport({
          title: `Cierre diario ${formatDate(dateTo)}`,
          rows: data.account_closes || [],
          columns: [
            ["account_name", "Cuenta"],
            ["currency", "Moneda"],
            [(row) => money(row.total_income, row.currency), "Ingresos"],
            [(row) => money(row.total_expense, row.currency), "Egresos"],
            [(row) => money(row.calculated_balance, row.currency), "Calculado"],
            [(row) => money(row.declared_balance, row.currency), "Declarado"],
            [(row) => money(row.difference, row.currency), "Diferencia"],
          ],
          exportColumns: [
            { label: "Cuenta", value: "account_name" },
            { label: "Moneda", value: "currency" },
            { label: "Ingresos", value: "total_income" },
            { label: "Egresos", value: "total_expense" },
            { label: "Calculado", value: "calculated_balance" },
            { label: "Declarado", value: "declared_balance" },
            { label: "Diferencia", value: "difference" },
          ],
          summary: [
            { label: "Ingresos del dia", value: money(data.income) },
            { label: "Egresos del dia", value: money(data.expense) },
          ],
        });
        return;
      }
      if (kind === "income-vs-expense") {
        const data = await api(`/reports/income-vs-expense/?${period}`);
        setReport({
          title: "Ingresos vs egresos",
          rows: [
            { concept: "Ingresos", amount: data.income },
            { concept: "Egresos", amount: data.expense },
            { concept: "Resultado", amount: Number(data.income || 0) - Number(data.expense || 0) },
          ],
          columns: [
            ["concept", "Concepto"],
            [(row) => money(row.amount), "Importe"],
          ],
          exportColumns: [
            { label: "Concepto", value: "concept" },
            { label: "Importe", value: "amount" },
          ],
          summary: [
            { label: "Desde", value: formatDate(data.date_from) },
            { label: "Hasta", value: formatDate(data.date_to) },
          ],
        });
        return;
      }

      const definitions = {
        "account-balances": {
          path: "/reports/account-balances/",
          title: "Saldo por cuenta",
          columns: [["name", "Cuenta"], ["type", "Tipo"], ["currency", "Moneda"], [(row) => money(row.balance, row.currency), "Saldo"]],
          exportColumns: [
            { label: "Cuenta", value: "name" },
            { label: "Tipo", value: "type" },
            { label: "Moneda", value: "currency" },
            { label: "Saldo", value: "balance" },
          ],
        },
        "expense-by-code": {
          path: `/reports/expense-by-code/?${period}`,
          title: "Egresos por codigo",
          columns: [["code__code", "Codigo"], ["code__name", "Nombre"], [(row) => money(row.total), "Total"]],
          exportColumns: [
            { label: "Codigo", value: "code__code" },
            { label: "Nombre", value: "code__name" },
            { label: "Total", value: "total" },
          ],
        },
        "provider-expenses": {
          path: `/reports/provider-expenses/?${period}`,
          title: "Gastos por proveedor",
          columns: [["provider__name", "Proveedor"], [(row) => money(row.total), "Total"]],
          exportColumns: [
            { label: "Proveedor", value: "provider__name" },
            { label: "Total", value: "total" },
          ],
        },
        "provider-balances": {
          path: "/reports/provider-balances/",
          title: "Saldo por proveedor",
          columns: [["name", "Proveedor"], [(row) => money(row.balance), "Saldo"]],
          exportColumns: [
            { label: "Proveedor", value: "name" },
            { label: "Saldo", value: "balance" },
          ],
        },
        "providers-with-credit": {
          path: "/reports/providers-with-credit/",
          title: "Proveedores con saldo a favor",
          columns: [["name", "Proveedor"], [(row) => money(row.balance), "Saldo a favor"]],
          exportColumns: [
            { label: "Proveedor", value: "name" },
            { label: "Saldo a favor", value: "balance" },
          ],
        },
        "employee-payments": {
          path: `/reports/employee-payments/?${period}`,
          title: "Pagos a empleados",
          columns: [
            [(row) => formatDate(row.payment_date), "Fecha"],
            ["employee_name", "Empleado"],
            ["event_name", "Evento"],
            [(row) => money(row.amount), "Importe"],
          ],
          exportColumns: [
            { label: "Fecha", value: "payment_date" },
            { label: "Empleado", value: "employee_name" },
            { label: "Evento", value: "event_name" },
            { label: "Importe", value: "amount" },
          ],
        },
        "taxes-paid": {
          path: `/reports/taxes-paid/?${period}`,
          title: "Impuestos pagados",
          columns: [
            [(row) => formatDate(row.payment_date), "Fecha"],
            ["tax_type_name", "Impuesto"],
            ["period", "Periodo"],
            ["account_name", "Cuenta"],
            [(row) => money(row.amount), "Importe"],
          ],
          exportColumns: [
            { label: "Fecha", value: "payment_date" },
            { label: "Impuesto", value: "tax_type_name" },
            { label: "Periodo", value: "period" },
            { label: "Cuenta", value: "account_name" },
            { label: "Importe", value: "amount" },
          ],
        },
        "taxes-due": {
          path: "/reports/taxes-due/",
          title: "Impuestos proximos a vencer",
          columns: [[(row) => formatDate(row.due_date), "Vence"], ["tax_type_name", "Impuesto"], ["title", "Titulo"], ["status", "Estado"]],
          exportColumns: [
            { label: "Vence", value: "due_date" },
            { label: "Impuesto", value: "tax_type_name" },
            { label: "Titulo", value: "title" },
            { label: "Estado", value: "status" },
          ],
        },
        "voided-movements": {
          path: "/reports/voided-movements/",
          title: "Movimientos anulados",
          columns: [[(row) => formatDate(row.date_payment), "Fecha"], ["account_name", "Cuenta"], ["code_code", "Codigo"], [(row) => money(row.amount), "Importe"], ["void_reason", "Motivo"]],
          exportColumns: [
            { label: "Fecha", value: "date_payment" },
            { label: "Cuenta", value: "account_name" },
            { label: "Codigo", value: "code_code" },
            { label: "Importe", value: "amount" },
            { label: "Motivo", value: "void_reason" },
          ],
        },
        transfers: {
          path: `/reports/transfers/?${period}`,
          title: "Transferencias entre cuentas",
          columns: [[(row) => formatDate(row.date), "Fecha"], ["from_account_name", "Desde"], ["to_account_name", "Hacia"], [(row) => money(row.amount), "Importe"], [(row) => money(row.fee_amount), "Comision"]],
          exportColumns: [
            { label: "Fecha", value: "date" },
            { label: "Desde", value: "from_account_name" },
            { label: "Hacia", value: "to_account_name" },
            { label: "Importe", value: "amount" },
            { label: "Comision", value: "fee_amount" },
          ],
        },
      };

      if (kind === "event-summary") {
        const data = await api(`/reports/event-summary/?event=${eventId}`);
        setReport({
          title: `Resumen del evento ${data.event.name}`,
          rows: [
            { concept: "Cobros", amount: data.income },
            { concept: "Egresos", amount: data.expense },
            { concept: "Resultado", amount: data.result },
          ],
          columns: [["concept", "Concepto"], [(row) => money(row.amount), "Importe"]],
          exportColumns: [
            { label: "Concepto", value: "concept" },
            { label: "Importe", value: "amount" },
          ],
          summary: [
            { label: "Fecha", value: data.event.event_date ? formatDate(data.event.event_date) : "-" },
            { label: "Cliente", value: data.event.client_name || "-" },
          ],
        });
        return;
      }

      const definition = definitions[kind];
      const data = await api(definition.path);
      setReport({
        title: definition.title,
        rows: Array.isArray(data) ? data : unwrap(data),
        columns: definition.columns,
        exportColumns: definition.exportColumns,
        summary: [
          { label: "Desde", value: formatDate(dateFrom) },
          { label: "Hasta", value: formatDate(dateTo) },
        ],
      });
    } catch (error) {
      setReport({
        title: "No se pudo generar el reporte",
        rows: [{ message: prettifyErrorMessage(error.message) }],
        columns: [["message", "Detalle"]],
        exportColumns: [{ label: "Detalle", value: "message" }],
        summary: [],
      });
      window.alert(prettifyErrorMessage(error.message));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader title="Reportes basicos" kicker="Lecturas utiles">
        Reportes listos para mostrar, exportar y abrir en Excel. Menos JSON crudo, mas lecturas operativas claras.
      </PageHeader>
      <div className="work-card mb-3">
        <div className="row g-2 align-items-end">
          <div className="col-md-3"><TextInput label="Desde" type="date" value={dateFrom} onChange={setDateFrom} /></div>
          <div className="col-md-3"><TextInput label="Hasta" type="date" value={dateTo} onChange={setDateTo} /></div>
          <div className="col-md-4"><SelectInput label="Evento" value={eventId} onChange={setEventId} options={refs.events} labelFor={(e) => e.name} empty="Para resumen por evento" /></div>
        </div>
        <div className="d-flex flex-wrap gap-2 mt-3">
          <button className="btn btn-outline-dark" onClick={() => run("daily-close")}>Cierre diario</button>
          <button className="btn btn-outline-dark" onClick={() => run("account-balances")}>Saldo por cuenta</button>
          <button className="btn btn-outline-dark" onClick={() => run("income-vs-expense")}>Ingresos vs egresos</button>
          <button className="btn btn-outline-dark" onClick={() => run("expense-by-code")}>Egresos por codigo</button>
          <button className="btn btn-outline-dark" onClick={() => run("provider-expenses")}>Gastos por proveedor</button>
          <button className="btn btn-outline-dark" onClick={() => run("provider-balances")}>Saldo proveedores</button>
          <button className="btn btn-outline-dark" onClick={() => run("providers-with-credit")}>Saldos a favor</button>
          <button className="btn btn-outline-dark" onClick={() => run("employee-payments")}>Pagos a empleados</button>
          <button className="btn btn-outline-dark" onClick={() => run("taxes-paid")}>Impuestos pagados</button>
          <button className="btn btn-outline-dark" onClick={() => run("taxes-due")}>Impuestos a vencer</button>
          <button className="btn btn-outline-dark" onClick={() => run("voided-movements")}>Anulados</button>
          <button className="btn btn-outline-dark" onClick={() => run("transfers")}>Transferencias</button>
          <button className="btn btn-earth" disabled={!eventId} onClick={() => run("event-summary")}>Resumen evento</button>
        </div>
      </div>
      <div className="work-card">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h4 className="section-title mb-0">{report.title}</h4>
          <button
            className="btn btn-earth btn-sm"
            onClick={() => exportRows(`reporte-${report.title.toLowerCase().replace(/\s+/g, "-")}.csv`, report.exportColumns || [], report.rows || [])}
          >
            Exportar CSV
          </button>
        </div>
        {report.summary?.length > 0 && (
          <div className="row g-3 mb-3">
            {report.summary.map((item) => (
              <div className="col-md-4" key={item.label}>
                <div className="metric-card">
                  <span className="text-muted small">{item.label}</span>
                  <strong className="d-block">{item.value}</strong>
                </div>
              </div>
            ))}
          </div>
        )}
        {loading ? <p>Cargando...</p> : <SimpleTable rows={report.rows || []} columns={report.columns || []} />}
      </div>
    </>
  );
}

function SimpleTable({ rows, columns }) {
  if (!columns.length) {
    return <div className="text-muted py-4 text-center">Elegi un reporte para ver los datos.</div>;
  }
  return (
    <div className="table-responsive soft-table">
      <table className="table table-hover align-middle mb-0">
        <thead>
          <tr>
            {columns.map(([, label], index) => <th key={index}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="text-center text-muted py-4">Sin datos todavia</td>
            </tr>
          )}
          {rows.map((row, rowIndex) => (
            <tr key={row.id || rowIndex}>
              {columns.map(([accessor], columnIndex) => (
                <td key={columnIndex}>{typeof accessor === "function" ? accessor(row) : row[accessor]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;
