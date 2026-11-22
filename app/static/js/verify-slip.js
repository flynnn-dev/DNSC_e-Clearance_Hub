const main = document.getElementById("main");
const message = document.getElementById("verify-message");
const badge = document.getElementById("verify-badge");
const number = document.getElementById("verify-number");
const expiry = document.getElementById("verify-expiry");

function show(payload) {
  message.textContent = payload.message || "This slip could not be verified.";
  const status = payload.verified ? payload.status || "PENDING" : "not verified";
  const label = status === "CLEARED" ? "Cleared" : status === "revoked" ? "Revoked" : status === "expired" ? "Expired" : status === "HOLD" ? "Hold" : status === "PENDING" ? "Pending" : "Not verified";
  badge.textContent = label;
  const tone = status === "CLEARED" ? "cleared" : status === "PENDING" || status === "not verified" ? "pending" : "hold";
  badge.className = `badge badge-${tone}`;
  number.textContent = payload.student_number || "—";
  expiry.textContent = payload.expires_at ? new Date(payload.expires_at).toLocaleString() : "—";
}

const token = main ? main.dataset.token || "" : "";
if (!token || token.length > 400) {
  show({ verified: false, message: "This slip could not be verified." });
} else {
  fetch(`/api/verify/${encodeURIComponent(token)}`, { headers: { Accept: "application/json" } })
    .then((response) => response.json())
    .then(show)
    .catch(() => show({ verified: false, message: "This slip could not be verified." }));
}
