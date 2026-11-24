const notifyButton = document.getElementById("notify-button");
const notifyPanel = document.getElementById("notify-panel");
const notifyList = document.getElementById("notify-list");
const notifyDot = document.getElementById("notify-dot");

const OFFICE_LABELS = {
  library: "Library",
  accounting: "Accounting",
};

function officeLabel(code) {
  if (OFFICE_LABELS[code]) {
    return OFFICE_LABELS[code];
  }
  return String(code || "Office")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(isoDate) {
  const [year, month, day] = String(isoDate).split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function weekdayDistance(isoDate) {
  const [year, month, day] = String(isoDate).split("-").map(Number);
  const target = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (Number.isNaN(target.getTime())) {
    return null;
  }
  if (target < today) {
    return -1;
  }
  let count = 0;
  const cursor = new Date(today);
  while (cursor < target) {
    cursor.setDate(cursor.getDate() + 1);
    const weekday = cursor.getDay();
    if (weekday !== 0 && weekday !== 6) {
      count += 1;
    }
  }
  return count;
}

function item(title, body, href, actionable) {
  return { title, body, href, actionable };
}

function buildStudentItems(payload, links) {
  if (!payload.linked) {
    return [
      item(
        "Account not linked",
        "Ask for this login to be linked to a student number.",
        links.help,
        true,
      ),
    ];
  }
  const items = [];
  const offices = payload.offices || [];
  offices
    .filter((office) => office.status === "HOLD")
    .forEach((office) => {
      items.push(
        item(
          `${officeLabel(office.office)} is on hold`,
          office.reason || "This office still has a hold.",
          `${links.clearance}/${encodeURIComponent(office.office)}`,
          true,
        ),
      );
    });
  if (payload.deadline) {
    const distance = weekdayDistance(payload.deadline);
    const date = formatDate(payload.deadline);
    if (distance !== null && distance <= 3) {
      const title =
        distance < 0 ? "Clearance deadline passed" : distance === 0 ? "Clearance deadline is today" : "Clearance deadline is soon";
      const body = distance < 0 ? `The deadline was ${date}.` : `The deadline is ${date}.`;
      items.push(item(title, body, links.announcements, true));
    }
  }
  const history = payload.history || [];
  const slipIssued = history.some((event) => event.action === "slip_issued");
  if (payload.overall_status === "CLEARED" && !slipIssued) {
    items.push(
      item(
        "Clearance slip is ready",
        "Library and Accounting are cleared. Download the signed slip.",
        links.documents,
        true,
      ),
    );
  }
  const cleared = new Set(offices.filter((office) => office.status === "CLEARED").map((office) => office.office));
  const seen = new Set();
  history.forEach((event) => {
    if (event.action !== "signoff" || !event.office || !cleared.has(event.office) || seen.has(event.office)) {
      return;
    }
    seen.add(event.office);
    items.push(item(`${officeLabel(event.office)} signed off`, "This office is cleared.", links.clearance, false));
  });
  return items;
}

function countLabel(count, singular, plural) {
  return count === 1 ? `1 student is ${singular}` : `${count} students are ${plural}`;
}

function buildStaffItems(payload, links) {
  const counts = payload.counts || {};
  const hold = counts.HOLD || 0;
  const pending = counts.PENDING || 0;
  const items = [];
  if (hold > 0) {
    items.push(item(countLabel(hold, "on hold", "on hold"), "Open the hold list for this office.", `${links.students}?status=HOLD`, true));
  }
  if (pending > 0) {
    items.push(
      item(countLabel(pending, "still pending", "still pending"), "Open the pending list for this office.", `${links.students}?status=PENDING`, true),
    );
  }
  return items;
}

function renderItems(items) {
  if (!notifyList || !notifyDot || !notifyButton) {
    return;
  }
  notifyList.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("li");
    empty.className = "px-2 py-3 text-sm text-slate-600";
    empty.textContent = "Nothing needs attention.";
    notifyList.append(empty);
  } else {
    items.forEach((entry) => {
      const row = document.createElement("li");
      const link = document.createElement("a");
      link.className =
        "block rounded-lg px-2 py-2 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-700";
      link.href = entry.href;
      const title = document.createElement("span");
      title.className = "block text-sm font-medium text-green-900";
      title.textContent = entry.title;
      const body = document.createElement("span");
      body.className = "mt-1 block text-sm text-slate-600";
      body.textContent = entry.body;
      link.append(title, body);
      row.append(link);
      notifyList.append(row);
    });
  }
  const actionable = items.some((entry) => entry.actionable);
  notifyDot.classList.toggle("hidden", !actionable);
  notifyButton.setAttribute("aria-label", actionable ? "Notifications, items need attention" : "Notifications");
}

function setOpen(open) {
  if (!notifyPanel || !notifyButton) {
    return;
  }
  notifyPanel.classList.toggle("hidden", !open);
  notifyButton.setAttribute("aria-expanded", open ? "true" : "false");
}

function linksFromButton() {
  return {
    clearance: notifyButton.dataset.clearance || "/student/clearance",
    announcements: notifyButton.dataset.announcements || "/student/announcements",
    documents: notifyButton.dataset.documents || "/student/documents",
    help: notifyButton.dataset.help || "/student/help",
    students: notifyButton.dataset.students || "/staff/students",
  };
}

function loadNotifications() {
  const role = notifyButton.dataset.role;
  const links = linksFromButton();
  const endpoint = role === "staff" ? "/api/staff/clearance" : "/api/me/clearance";
  fetch(endpoint, { headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Notifications could not be loaded.");
      }
      return response.json();
    })
    .then((payload) => renderItems(role === "staff" ? buildStaffItems(payload, links) : buildStudentItems(payload, links)))
    .catch((error) => {
      notifyList.replaceChildren();
      const row = document.createElement("li");
      row.className = "px-2 py-3 text-sm text-slate-600";
      row.textContent = error.message;
      notifyList.append(row);
      notifyDot.classList.add("hidden");
    });
}

if (notifyButton && notifyPanel && notifyList && notifyDot) {
  notifyButton.addEventListener("click", () => {
    setOpen(notifyPanel.classList.contains("hidden"));
  });
  document.addEventListener("click", (event) => {
    if (!notifyButton.parentElement.contains(event.target)) {
      setOpen(false);
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
  });
  loadNotifications();
}
