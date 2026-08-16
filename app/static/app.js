const initial = document.getElementById("initial-data");

function fmt(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    return `${Number.isInteger(value) ? value : value.toFixed(1)}${suffix}`;
  }
  return `${value}${suffix}`;
}

function fmtDuration(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function setMetric(card, key, value, suffix = "") {
  const el = card.querySelector(`[data-metric="${key}"]`);
  if (el) el.textContent = fmt(value, suffix);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;"
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
      value = item.state === "home"
        ? "HOME"
        : item.state === "not_home"
          ? "AWAY"
          : String(item.state || "—").toUpperCase();
    } else if (kind === "temperature") {
      const suffix = item.unit ? ` ${item.unit}` : "";
      value = `${fmt(item.value)}${suffix}`;
    } else if (item.unit) {
      value = `${item.state ?? "—"} ${item.unit}`;
    }
    return `<div class="entity-row"><span>${escapeHtml(item.name || item.entity_id || "Entity")}</span><strong>${escapeHtml(value)}</strong></div>`;
  }).join("");
}

function stateClass(state) {
  if (state === "success" || state === "running" || state === "healthy") return "state-good";
  if (state === "failure" || state === "error" || state === "unhealthy") return "state-bad";
  return "state-warn";
}

function renderGitHubRepos(root, items) {
  if (!root) return;
  if (!Array.isArray(items) || items.length === 0) {
    root.innerHTML = '<span class="muted">No GitHub repositories configured.</span>';
    return;
  }
  const labels = {
    success: "PASS",
    failure: "FAIL",
    running: "RUNNING",
    neutral: "NEUTRAL",
    no_runs: "NO RUNS",
    error: "ERROR",
    unknown: "UNKNOWN"
  };
  root.innerHTML = items.map(item => {
    const state = String(item.state || "unknown");
    const label = labels[state] || state.toUpperCase();
    const detail = item.workflow
      ? `${item.name} · ${item.workflow}`
      : item.name || item.repo || "Repository";
    return `<div class="entity-row"><span>${escapeHtml(detail)}</span><strong class="${stateClass(state)}">${escapeHtml(label)}</strong></div>`;
  }).join("");
}

function renderDockerContainers(root, items) {
  if (!root) return;
  if (!Array.isArray(items) || items.length === 0) {
    root.innerHTML = '<span class="muted">No Docker containers found.</span>';
    return;
  }
  root.innerHTML = items.map(item => {
    const state = String(item.state || "unknown");
    const health = String(item.health || "");
    const effective = health === "unhealthy" ? "unhealthy" : state;
    const label = health === "unhealthy"
      ? "UNHEALTHY"
      : state === "running"
        ? "RUNNING"
        : state.toUpperCase();
    return `<div class="entity-row"><span>${escapeHtml(item.name || "container")}</span><strong class="${stateClass(effective)}">${escapeHtml(label)}</strong></div>`;
  }).join("");
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
    if (progress) {
      progress.style.width = `${Math.max(0, Math.min(100, m.progress_percent || 0))}%`;
    }
  } else if (name === "system") {
    setMetric(card, "cpu_percent", m.cpu_percent, "%");
    setMetric(card, "memory_percent", m.memory_percent, "%");
    setMetric(card, "disk_percent", m.disk_percent, "%");
    setMetric(card, "temperature_c", m.temperature_c, "°C");
    setMetric(card, "uptime_seconds", fmtDuration(m.uptime_seconds));
  } else if (name === "movies") {
    setMetric(
      card,
      "ticket_available",
      m.ticket_available === true ? "YES" : m.ticket_available === false ? "NO" : null
    );
    const theatreValue = m.monitored_theatres
      ? `${m.theatres_found || 0}/${m.monitored_theatres}`
      : m.theatres_found;
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
    renderEntityList(
      card.querySelector("[data-home-temperatures]"),
      m.temperatures,
      "temperature"
    );
    renderEntityList(card.querySelector("[data-home-selected]"), m.selected, "state");
  } else if (name === "github") {
    setMetric(card, "repo_count", m.repo_count);
    setMetric(card, "success_count", m.success_count);
    setMetric(card, "failing_count", m.failing_count);
    setMetric(card, "running_count", m.running_count);
    renderGitHubRepos(card.querySelector("[data-github-repos]"), m.repos);
  } else if (name === "docker") {
    setMetric(card, "running_count", m.running_count);
    setMetric(card, "unhealthy_count", m.unhealthy_count);
    setMetric(card, "stopped_count", m.stopped_count);
    setMetric(card, "engine_version", m.engine_version || "—");
    renderDockerContainers(card.querySelector("[data-docker-containers]"), m.containers);
  } else if (name === "notifications") {
    setMetric(card, "sent_count", m.sent_count);
    setMetric(card, "failed_count", m.failed_count);
    setMetric(card, "suppressed_count", m.suppressed_count);
    setMetric(card, "min_severity", String(m.min_severity || "warning").toUpperCase());
    setMetric(card, "quiet_hours", m.quiet_hours);
    const note = card.querySelector("[data-notification-note]");
    if (note) {
      if (!data.enabled) {
        note.textContent = "Central delivery is disabled. Existing source alerts are unchanged.";
      } else if (!data.configured) {
        note.textContent = "Set DISCORD_WEBHOOK_URL to activate central delivery.";
      } else if (m.last_status) {
        note.textContent = `Last delivery state: ${String(m.last_status).replaceAll("_", " ")}.`;
      } else {
        note.textContent = "Ready. New qualifying activity will be delivered to Discord.";
      }
    }
  }
}

function renderActivity(items) {
  const root = document.getElementById("activity-list");
  if (!root) return;
  if (!items || items.length === 0) {
    root.innerHTML = '<p class="muted">No activity events yet. Changes across your services will appear here.</p>';
    return;
  }
  root.innerHTML = items.map(item => {
    const when = new Date(item.occurred_at);
    const time = Number.isNaN(when.getTime())
      ? "—"
      : when.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    const source = ({
      movies: "Movies",
      calories: "Nutrition",
      lexus: "Lexus",
      home_assistant: "Home",
      system: "HomeLab",
      github: "GitHub",
      docker: "Docker"
    })[item.source] || item.source;
    return `<div class="activity-row"><time>${escapeHtml(time)}</time><span class="source">${escapeHtml(source)}</span><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail || "")}</p></div></div>`;
  }).join("");
}

function render(payload) {
  Object.entries(payload.integrations || {}).forEach(([name, data]) => renderCard(name, data));
  renderCard("notifications", payload.notifications);
  renderActivity(payload.activity || []);
  const stamp = document.getElementById("last-updated");
  if (stamp) {
    stamp.textContent = `Updated ${new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}`;
  }
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
  try {
    render(JSON.parse(initial.textContent));
  } catch (_) {}
}
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}
setInterval(refresh, Math.max(10, Number(window.STEWY_REFRESH_SECONDS || 30)) * 1000);
