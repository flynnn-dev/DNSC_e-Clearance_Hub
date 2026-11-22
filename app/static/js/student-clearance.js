const alertBox = document.getElementById("clearance-alert");
const issueButton = document.getElementById("issue-slip");

function showAlert(message) {
  if (!alertBox) {
    return;
  }
  alertBox.textContent = message;
  alertBox.classList.remove("hidden");
}

function setBadge(element, status) {
  if (!element) {
    return;
  }
  const label = status || "No record";
  element.textContent = label;
  element.className = `badge badge-${String(label).toLowerCase()}`;
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
  if (!line) {
    return;
  }
  if (payload.deadline) {
    const [year, month, day] = payload.deadline.split("-").map(Number);
    const formatted = new Date(year, month - 1, day).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    line.textContent = `Clearance deadline: ${formatted}`;
    return;
  }
  line.textContent = payload.deadline_error || "The clearance deadline is unavailable because the holiday list could not be loaded.";
}

function render(payload) {
  renderSlip(payload);
  renderDeadline(payload);
  if (!payload.linked) {
    setBadge(document.getElementById("overall-badge"), "PENDING");
    document.getElementById("overall-title").textContent = "No Registrar student is linked to this account";
    document.getElementById("overall-copy").textContent = "Ask for this login to be linked to a student number before clearance can be shown.";
    return;
  }
  const overall = payload.overall_status || "PENDING";
  setBadge(document.getElementById("overall-badge"), overall);
  const titles = {
    HOLD: "Clearance is on hold",
    PENDING: "Clearance is still pending",
    CLEARED: "Every required office has signed off",
  };
  document.getElementById("overall-title").textContent = titles[overall] || overall;
  document.getElementById("overall-copy").textContent = "Library and Accounting are both shown below.";
  document.getElementById("profile-number").textContent = payload.student_number;
  document.getElementById("profile-name").textContent = payload.display_name || payload.student_number;
  document.getElementById("profile-program").textContent = payload.program || "Not in the Registrar record";
  const byOffice = Object.fromEntries((payload.offices || []).map((office) => [office.office, office]));
  const library = byOffice.library;
  const accounting = byOffice.accounting;
  setBadge(document.getElementById("library-badge"), library ? library.status : "PENDING");
  setBadge(document.getElementById("accounting-badge"), accounting ? accounting.status : "PENDING");
  document.getElementById("library-copy").textContent = officeCopy(library, payload.library_records || []);
  document.getElementById("accounting-copy").textContent = officeCopy(accounting, payload.accounting_records || []);
  renderHistory(payload.history || []);
}

function showSlip(payload) {
  const result = document.getElementById("slip-result");
  const qr = document.getElementById("slip-qr");
  const expiry = document.getElementById("slip-expiry");
  const link = document.getElementById("slip-link");
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

fetch("/api/me/clearance", { headers: { Accept: "application/json" } })
  .then((response) => {
    if (!response.ok) {
      throw new Error("Clearance could not be loaded.");
    }
    return response.json();
  })
  .then(render)
  .catch((error) => showAlert(error.message));
