const alertBox = document.getElementById("office-alert");
const dialog = document.getElementById("hold-dialog");
const form = document.getElementById("hold-form");
const reasonField = document.getElementById("hold-reason");
const studentField = document.getElementById("hold-student");
const studentLabel = document.getElementById("hold-student-label");
const holdError = document.getElementById("hold-error");
let officeStudents = [];
let statusFilter = "all";
let page = 1;
const pageSize = 10;

function csrfToken() {
  return document.querySelector('input[name="csrf_token"]')?.value || "";
}

function showAlert(message) {
  if (!alertBox) {
    return;
  }
  alertBox.textContent = message;
  alertBox.classList.toggle("hidden", !message);
}

function badge(status) {
  const element = document.createElement("span");
  element.className = `badge badge-${String(status || "pending").toLowerCase()}`;
  element.textContent = status || "PENDING";
  return element;
}

function cell(value, className) {
  const element = document.createElement("td");
  if (className) {
    element.className = className;
  }
  element.textContent = value || "";
  return element;
}

function render(payload) {
  document.getElementById("count-hold").textContent = payload.counts.HOLD ?? 0;
  document.getElementById("count-pending").textContent = payload.counts.PENDING ?? 0;
  document.getElementById("count-cleared").textContent = payload.counts.CLEARED ?? 0;
  officeStudents = payload.students || [];
  drawRows();
}

function matchingStudents() {
  const query = (document.getElementById("student-search")?.value || "").trim().toLowerCase();
  return officeStudents.filter((student) => {
    const statusMatches = statusFilter === "all" || student.status === statusFilter;
    const haystack = `${student.student_number} ${student.display_name || ""}`.toLowerCase();
    return statusMatches && (!query || haystack.includes(query));
  });
}

function updatePager(total, start, shown) {
  const status = document.getElementById("student-page-status");
  const previous = document.getElementById("student-page-prev");
  const next = document.getElementById("student-page-next");
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  if (status) {
    status.textContent = total
      ? `Showing ${start + 1}–${start + shown} of ${total}`
      : "Showing 0 students";
  }
  if (previous) {
    previous.disabled = page <= 1;
  }
  if (next) {
    next.disabled = page >= pageCount || total === 0;
  }
}

function drawRows() {
  const students = matchingStudents();
  const pageCount = Math.max(1, Math.ceil(students.length / pageSize));
  if (page > pageCount) {
    page = pageCount;
  }
  const start = (page - 1) * pageSize;
  const visible = students.slice(start, start + pageSize);
  const body = document.getElementById("student-body");
  body.replaceChildren();
  updatePager(students.length, start, visible.length);
  if (!visible.length) {
    const row = document.createElement("tr");
    const empty = document.createElement("td");
    empty.colSpan = 5;
    empty.textContent = officeStudents.length
      ? "No students match this search."
      : "No students are available for this office yet.";
    row.append(empty);
    body.append(row);
    return;
  }
  visible.forEach((student) => {
    const row = document.createElement("tr");
    row.append(cell(student.student_number, "cell-id"), cell(student.display_name, "cell-name"));
    const statusCell = document.createElement("td");
    statusCell.append(badge(student.status));
    const actionCell = document.createElement("td");
    const actions = document.createElement("div");
    actions.className = "row-actions";
    const holdButton = document.createElement("button");
    holdButton.className = "btn btn-secondary";
    holdButton.type = "button";
    holdButton.textContent = "Place on hold";
    holdButton.addEventListener("click", () => openHold(student));
    const signButton = document.createElement("button");
    signButton.className = "btn btn-primary";
    signButton.type = "button";
    signButton.textContent = "Sign off";
    signButton.disabled = student.blocking;
    signButton.title = student.blocking ? "A blocking record must be cleared first." : "";
    signButton.addEventListener("click", () => signOff(student.student_number));
    actions.append(holdButton, signButton);
    actionCell.append(actions);
    row.append(statusCell, cell(student.reason || "", "cell-reason"), actionCell);
    body.append(row);
  });
}

function openHold(student) {
  studentField.value = student.student_number;
  studentLabel.textContent = `${student.display_name} (${student.student_number}). This hold applies only to your office.`;
  reasonField.value = "";
  holdError.classList.add("hidden");
  dialog.showModal();
  reasonField.focus();
}

async function loadQueue() {
  const response = await fetch("/api/staff/clearance", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error("The office list could not be loaded.");
  }
  render(await response.json());
}

async function signOff(studentNumber) {
  showAlert("");
  const response = await fetch(`/api/staff/clearance/${studentNumber}/signoff`, {
    method: "POST",
    headers: { Accept: "application/json", "X-CSRF-Token": csrfToken() },
  });
  const payload = await response.json();
  if (!response.ok) {
    showAlert(payload.error || "Sign-off was not saved.");
    return;
  }
  await loadQueue();
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  holdError.classList.add("hidden");
  const response = await fetch(`/api/staff/clearance/${studentField.value}/hold`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken(),
    },
    body: JSON.stringify({ reason: reasonField.value }),
  });
  const payload = await response.json();
  if (!response.ok) {
    holdError.textContent = payload.error || "The hold was not saved.";
    holdError.classList.remove("hidden");
    return;
  }
  dialog.close();
  await loadQueue();
});

document.querySelector("[data-close-dialog]")?.addEventListener("click", () => dialog.close());

document.getElementById("student-search")?.addEventListener("input", () => {
  page = 1;
  drawRows();
});
document.querySelectorAll("[data-status-filter]").forEach((chip) => {
  chip.addEventListener("click", () => {
    statusFilter = chip.dataset.statusFilter || "all";
    page = 1;
    document.querySelectorAll("[data-status-filter]").forEach((item) => {
      item.classList.toggle("is-selected", item === chip);
    });
    drawRows();
  });
});
document.getElementById("student-page-prev")?.addEventListener("click", () => {
  if (page > 1) {
    page -= 1;
    drawRows();
  }
});
document.getElementById("student-page-next")?.addEventListener("click", () => {
  page += 1;
  drawRows();
});

loadQueue().catch((error) => showAlert(error.message));
