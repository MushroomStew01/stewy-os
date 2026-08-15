const initial = document.getElementById("initial-data");

function fmt(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return `${Number.isInteger(value) ? value : value.toFixed(1)}${suffix}`;
  return `${value}${suffix}`;
}

function setMetric(card, key, value, suffix = "") {
  const el = card.querySelector(`[data-metric="${key}"]`);
  if (el) el.textContent = fmt(value, suffix);
}

function renderCard(name, data) {
  const card = document.querySelector(`[data-card="${name}"]`);
  if (!card || !data) return;
  const status = card.querySelector('[data-field="status"]');
  if (status) {
    status.textContent = String(data.status || "unknown").replaceAll("_", " ").toUpperCase();
    status.className = `status ${data.status || "neutral"}`;
  }
  const headline = card.querySelector('[data-field="headline"]');
  if (headline && data.detail) headline.textContent = data.detail;
  const m = data.metrics || {};
  if (name === "lexus") {
    setMetric(card, "ready", m.ready === true ? "YES" : m.ready === false ? "NO" : null);
    setMetric(card, "fuel_percent", m.fuel_percent, "%");
    setMetric(card, "range_km", m.range_km, " km");
    setMetric(card, "odometer_km", m.odometer_km, " km");
  } else if (name === "calories") {
    setMetric(card, "calories", m.calories);
    setMetric(card, "calorie_goal", m.calorie_goal);
    setMetric(card, "calories_remaining", m.calories_remaining, " kcal");
    setMetric(card, "protein_g", m.protein_g, " g");
    setMetric(card, "meal_count", m.meal_count);
    const progress = card.querySelector("[data-progress]");
    if (progress) progress.style.width = `${Math.max(0, Math.min(100, m.progress_percent || 0))}%`;
  } else if (name === "system") {
    setMetric(card, "cpu_percent", m.cpu_percent, "%");
    setMetric(card, "memory_percent", m.memory_percent, "%");
    setMetric(card, "disk_percent", m.disk_percent, "%");
    setMetric(card, "temperature_c", m.temperature_c, "°C");
  } else if (name === "movies") {
    setMetric(card, "ticket_available", m.ticket_available === true ? "YES" : m.ticket_available === false ? "NO" : null);
    const theatreValue = m.monitored_theatres ? `${m.theatres_found || 0}/${m.monitored_theatres}` : m.theatres_found;
    setMetric(card, "theatres_found", theatreValue);
    setMetric(card, "showtime_count", m.showtime_count);
    setMetric(card, "format_count", m.format_count);
  } else if (name === "home_assistant") {
    const peopleValue = m.people_total ? `${m.people_home || 0}/${m.people_total}` : "NOT SET";
    setMetric(card, "people_home", peopleValue);
    setMetric(card, "temperature_count", m.temperature_count);
    setMetric(card, "selected_count", m.selected_count);
    setMetric(card, "entity_count", m.entity_count);
    renderEntityList(card.querySelector("[data-home-presence]"), m.presence, "presence");
    renderEntityList(card.querySelector("[data-home-temperatures]"), m.temperatures, "temperature");
    renderEntityList(card.querySelector("[data-home-selected]"), m.selected, "state");
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[ch]);
}

function renderEntityList(root, items, kind) {
  if (!root) return;
  if (!Array.isArray(items) || items.length === 0) {
    const empty = {
      presence: "No usable presence detected.",
      temperature: "No room temperature sensors.",
      state: "No selected entities."
    }[kind] || "None configured or discovered.";
    root.innerHTML = `<span class="muted">${escapeHtml(empty)}</span>`;
    return;
  }
  root.innerHTML = items.map(item => {
    let value = item.state ?? "—";
    if (kind === "presence") {
      value = item.state === "home" ? "HOME" : item.state === "not_home" ? "AWAY" : String(item.state || "—").toUpperCase();
    } else if (kind === "temperature") {
      const suffix = item.unit ? ` ${item.unit}` : "";
      value = `${fmt(item.value)}${suffix}`;
    } else if (item.unit) {
      value = `${item.state ?? "—"} ${item.unit}`;
    }
    return `<div class="entity-row"><span>${escapeHtml(item.name || item.entity_id || "Entity")}</span><strong>${escapeHtml(value)}</strong></div>`;
  }).join("");
}

function renderActivity(items) {
  const root = document.getElementById("activity-list");
  if (!root) return;
  if (!items || items.length === 0) {
    root.innerHTML = '<p class="muted">No activity events yet. New meals, movie changes, and integration health changes will appear here.</p>';
    return;
  }
  root.innerHTML = items.map(item => {
    const when = new Date(item.occurred_at);
    const time = Number.isNaN(when.getTime()) ? "—" : when.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    const source = ({movies: "Movies", calories: "Nutrition", lexus: "Lexus", home_assistant: "Home", system: "HomeLab"})[item.source] || item.source;
    return `<div class="activity-row"><time>${escapeHtml(time)}</time><span class="source">${escapeHtml(source)}</span><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail || "")}</p></div></div>`;
  }).join("");
}

function render(payload) {
  Object.entries(payload.integrations || {}).forEach(([name, data]) => renderCard(name, data));
  renderActivity(payload.activity || []);
  const stamp = document.getElementById("last-updated");
  if (stamp) stamp.textContent = `Updated ${new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}`;
}

function greeting() {
  const hour = new Date().getHours();
  const word = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const el = document.getElementById("greeting");
  if (el) el.textContent = `${word}, Andy. Your systems are in one place.`;
}

async function refresh() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) return;
    render(await response.json());
  } catch (_) {}
}

greeting();
if (initial) {
  try { render(JSON.parse(initial.textContent)); } catch (_) {}
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/sw.js").catch(() => {});
setInterval(refresh, Math.max(10, Number(window.STEWY_REFRESH_SECONDS || 30)) * 1000);
