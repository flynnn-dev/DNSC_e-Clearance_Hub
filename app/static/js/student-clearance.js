const alertBox = document.getElementById("clearance-alert");
const issueButton = document.getElementById("issue-slip");
const exportButton = document.getElementById("export-holds");
const RING = 2 * Math.PI * 52;

const STATUS_LABEL = {
  CLEARED: "Cleared",
  HOLD: "On Hold",
  PENDING: "Pending",
};

const OFFICE_LABELS = {
  library: "Library",
  accounting: "Accounting",
};

let latestOffices = [];

function showAlert(message) {
  if (!alertBox) {
    return;
  }
  alertBox.textContent = message;
  alertBox.classList.remove("hidden");
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = value;
  }
}

function setBadge(element, status) {
  if (!element) {
    return;
  }
  const key = String(status || "PENDING").toUpperCase();
  element.textContent = STATUS_LABEL[key] || status || "No record";
  const tone = key === "CLEARED" || key === "HOLD" || key === "PENDING" ? key.toLowerCase() : "pending";
  element.className = `badge badge-${tone}`;
}

function officeCopy(record, titles) {
  if (!record) {
    return "No office record yet.";
  }
  if (record.reason) {
    return record.reason;
  }
  if (titles.length) {
    return titles.join(". ");
  }
  if (record.status === "CLEARED") {
    return "Signed off. No blocking record.";
  }
  return "No blocking record and no sign-off yet.";
}

function officeLabel(code) {
  if (OFFICE_LABELS[code]) {
    return OFFICE_LABELS[code];
  }
  return String(code || "Office")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function officeTitles(code, payload) {
  if (code === "library") {
    return payload.library_records || [];
  }
  if (code === "accounting") {
    return payload.accounting_records || [];
  }
  return [];
}

function iconSvg(paths) {
  return `<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

function officeIcon(code) {
  if (code === "library") {
    return iconSvg('<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>');
  }
  if (code === "accounting") {
    return iconSvg('<rect width="20" height="14" x="2" y="5" rx="2"/><path d="M2 10h20"/>');
  }
  return iconSvg('<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>');
}

function formatDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function firstName(displayName) {
  const name = String(displayName || "").trim();
  if (!name) {
    return "";
  }
  return name.split(/\s+/)[0];
}

function renderSlip(payload) {
  const copy = document.getElementById("slip-copy");
  if (!issueButton || !copy) {
    return;
  }
  const cleared = Boolean(payload.linked) && payload.overall_status === "CLEARED";
  issueButton.disabled = !cleared;
  if (!payload.linked) {
    copy.textContent = "Link this account to a student number before a slip can be issued.";
    return;
  }
  if (cleared) {
    copy.textContent = "Library and Accounting are cleared. Issue a signed slip. The QR code opens a public check with a masked student number.";
    return;
  }
  copy.textContent = "A signed slip can be issued when Library and Accounting are both cleared.";
}

function renderHistory(history) {
  const body = document.getElementById("history-body");
  if (!body) {
    return;
  }
  body.replaceChildren();
  if (!history.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No clearance history yet.";
    row.append(cell);
    body.append(row);
    return;
  }
  history.forEach((item) => {
    const row = document.createElement("tr");
    [new Date(item.at).toLocaleString(), item.office || "", item.action || "", item.reason || ""].forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 0) {
        cell.className = "cell-id";
      }
      if (index === 3) {
        cell.className = "cell-reason";
      }
      row.append(cell);
    });
    body.append(row);
  });
}

function renderDeadline(payload) {
  const line = document.getElementById("clearance-deadline");
  const stamp = document.getElementById("announcement-date");
  const completion = document.getElementById("stat-completion");
  if (payload.deadline) {
    const shortDate = formatDate(payload.deadline);
    if (line) {
      line.textContent = `The clearance deadline is ${shortDate}. Complete every office requirement before that date.`;
    }
    if (stamp) {
      stamp.textContent = shortDate;
    }
    if (completion) {
      completion.textContent = shortDate;
    }
    return;
  }
  const message = payload.deadline_error || "The clearance deadline is unavailable because the holiday list could not be loaded.";
  if (line) {
    line.textContent = message;
  }
  if (stamp) {
    stamp.textContent = "";
  }
  if (completion) {
    completion.textContent = "Unavailable";
  }
}

function renderProgress(cleared, total) {
  const ring = document.getElementById("progress-ring");
  const ratio = total ? cleared / total : 0;
  const percent = Math.round(ratio * 100);
  if (ring) {
    ring.style.strokeDasharray = String(RING);
    ring.style.strokeDashoffset = String(RING * (1 - ratio));
  }
  setText("progress-percent", `${percent}%`);
  setText("progress-caption", total ? `${cleared} of ${total} offices cleared` : "No offices linked yet");
}

function renderOffices(payload) {
  const list = document.getElementById("office-list");
  if (!list) {
    return;
  }
  list.replaceChildren();
  const offices = payload.offices || [];
  if (!offices.length) {
    const item = document.createElement("li");
    item.className = "py-3 text-sm text-slate-500";
    item.textContent = payload.linked ? "No office records yet." : "No offices to show until this login is linked.";
    list.append(item);
    return;
  }
  const base = list.dataset.officeBase || "/student/clearance";
  offices.forEach((office, index) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.className = "flex items-center gap-3 rounded-lg py-3 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-700";
    link.href = `${base}/${encodeURIComponent(office.office)}`;
    const descriptionId = `office-desc-${index}`;
    link.setAttribute("aria-describedby", descriptionId);

    const iconWrap = document.createElement("span");
    iconWrap.className = "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-green-50 text-green-700";
    iconWrap.innerHTML = officeIcon(office.office);

    const text = document.createElement("div");
    text.className = "min-w-0 flex-1";
    const name = document.createElement("p");
    name.className = "text-sm font-medium text-green-900";
    name.textContent = officeLabel(office.office);
    const description = document.createElement("p");
    description.id = descriptionId;
    description.className = "sr-only";
    description.textContent = officeCopy(office, officeTitles(office.office, payload));
    text.append(name, description);

    const badge = document.createElement("span");
    setBadge(badge, office.status);

    const chevron = document.createElement("span");
    chevron.className = "text-slate-300";
    chevron.innerHTML = iconSvg('<path d="m9 18 6-6-6-6"/>');

    link.append(iconWrap, text, badge, chevron);
    item.append(link);
    list.append(item);
  });
}

function renderOfficeDetail(payload) {
  const detail = document.getElementById("office-detail");
  if (!detail) {
    return;
  }
  const code = detail.dataset.office || "";
  const offices = payload.offices || [];
  const office = offices.find((item) => item.office === code);
  setText("office-title", officeLabel(code));
  const badge = document.getElementById("office-badge");
  if (!payload.linked) {
    setBadge(badge, "PENDING");
    setText("office-reason", "Ask for this login to be linked to a student number before this office can be shown.");
    return;
  }
  if (!office) {
    setBadge(badge, "PENDING");
    setText("office-reason", "This office is not part of your clearance.");
    return;
  }
  setBadge(badge, office.status);
  setText("office-reason", officeCopy(office, officeTitles(code, payload)));
  const records = document.getElementById("office-records");
  if (!records) {
    return;
  }
  records.replaceChildren();
  officeTitles(code, payload).forEach((title) => {
    const item = document.createElement("li");
    item.textContent = title;
    records.append(item);
  });
}

function renderIdentity(payload) {
  const name = payload.display_name || payload.student_number || "";
  const given = firstName(payload.display_name);
  setText("greeting", given ? `Good day, ${given}!` : "Good day!");
  if (name) {
    setText("shell-display-name", name);
    const initial = name.trim().charAt(0).toUpperCase();
    setText("shell-avatar", initial);
    setText("header-avatar", initial);
  }
  setText("profile-number", payload.student_number || "Not linked yet");
  setText("profile-name", payload.display_name || payload.student_number || "Not linked yet");
  setText("profile-program", payload.program || "Not in the Registrar record");
}

function renderStats(offices) {
  const total = offices.length;
  const cleared = offices.filter((office) => office.status === "CLEARED").length;
  const holds = offices.filter((office) => office.status === "HOLD").length;
  setText("stat-cleared", `${cleared} / ${total}`);
  setText("stat-hold", String(holds));
  setText("stat-requirements", String(total));
  renderProgress(cleared, total);
}

function render(payload) {
  latestOffices = payload.offices || [];
  renderSlip(payload);
  renderDeadline(payload);
  const note = document.getElementById("link-note");
  if (!payload.linked) {
    if (note) {
      note.textContent = "Ask for this login to be linked to a student number before clearance can be shown.";
      note.classList.remove("hidden");
    }
    setText("greeting", "Good day!");
    renderStats([]);
    renderOffices(payload);
    renderOfficeDetail(payload);
    renderHistory([]);
    return;
  }
  note?.classList.add("hidden");
  renderIdentity(payload);
  renderStats(latestOffices);
  renderOffices(payload);
  renderOfficeDetail(payload);
  renderHistory(payload.history || []);
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function exportHolds() {
  const holds = latestOffices.filter((office) => office.status === "HOLD");
  const lines = ["office,status,reason", ...holds.map((office) => [office.office, office.status, office.reason || ""].map(csvCell).join(","))];
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "hold-summary.csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function showSlip(payload) {
  const result = document.getElementById("slip-result");
  const qr = document.getElementById("slip-qr");
  const expiry = document.getElementById("slip-expiry");
  const link = document.getElementById("slip-link");
  if (!result || !qr || !expiry || !link) {
    return;
  }
  result.classList.remove("hidden");
  qr.replaceChildren();
  const parsed = new DOMParser().parseFromString(payload.qr_svg || "", "image/svg+xml");
  const svg = parsed.documentElement;
  if (svg && svg.tagName.toLowerCase() === "svg") {
    qr.append(document.importNode(svg, true));
  }
  expiry.textContent = payload.expires_at ? `Expires ${new Date(payload.expires_at).toLocaleString()}` : "";
  link.href = payload.verify_path || "#slip";
}

function issueSlip() {
  const csrf = document.querySelector('input[name="csrf_token"]');
  issueButton.disabled = true;
  fetch("/api/me/slip", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "X-CSRF-Token": csrf ? csrf.value : "",
    },
  })
    .then((response) => response.json().then((payload) => ({ ok: response.ok, payload })))
    .then(({ ok, payload }) => {
      if (!ok) {
        throw new Error(payload.error || "The slip could not be issued.");
      }
      showSlip(payload);
      return fetch("/api/me/clearance", { headers: { Accept: "application/json" } });
    })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Clearance could not be loaded.");
      }
      return response.json();
    })
    .then(render)
    .catch((error) => {
      showAlert(error.message);
      return fetch("/api/me/clearance", { headers: { Accept: "application/json" } })
        .then((response) => response.json())
        .then(render)
        .catch(() => {
          issueButton.disabled = false;
        });
    });
}

if (issueButton) {
  issueButton.addEventListener("click", issueSlip);
}

if (exportButton) {
  exportButton.addEventListener("click", exportHolds);
}

fetch("/api/me/clearance", { headers: { Accept: "application/json" } })
  .then((response) => {
    if (!response.ok) {
      throw new Error("Clearance could not be loaded.");
    }
    return response.json();
  })
  .then(render)
  .catch((error) => showAlert(error.message));
