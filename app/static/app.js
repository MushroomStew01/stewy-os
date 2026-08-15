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
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[ch]);
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
    const source = ({movies: "Movies", calories: "Nutrition", lexus: "Lexus", system: "HomeLab"})[item.source] || item.source;
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
