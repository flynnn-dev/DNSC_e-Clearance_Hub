const sidebar = document.getElementById("sidebar");
const backdrop = document.getElementById("nav-backdrop");
const openButton = document.querySelector("[data-open-nav]");
const closeButton = document.querySelector("[data-close-nav]");

function setNavOpen(isOpen) {
  if (!sidebar || !openButton) {
    return;
  }
  sidebar.classList.toggle("is-open", isOpen);
  backdrop?.classList.toggle("hidden", !isOpen);
  openButton.setAttribute("aria-expanded", String(isOpen));
  document.body.classList.toggle("overflow-hidden", isOpen);
}

openButton?.addEventListener("click", () => setNavOpen(true));
closeButton?.addEventListener("click", () => setNavOpen(false));
backdrop?.addEventListener("click", () => setNavOpen(false));

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    setNavOpen(false);
    document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
  }
});

window.addEventListener("resize", () => {
  if (window.matchMedia("(min-width: 768px)").matches) {
    setNavOpen(false);
  }
});

const navLinks = [...document.querySelectorAll(".nav-link, .tab-link")].filter((link) =>
  (link.getAttribute("href") || "").startsWith("#"),
);
const navSections = navLinks
  .map((link) => document.querySelector(link.getAttribute("href")))
  .filter((section) => section instanceof HTMLElement);

function markCurrentSection(activeId) {
  navLinks.forEach((link) => {
    const current = link.getAttribute("href") === `#${activeId}`;
    if (current) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

if (navSections.length) {
  markCurrentSection(navSections[0].id);
  const seen = new Map();
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => seen.set(entry.target.id, entry.isIntersecting));
    const active = navSections.find((section) => seen.get(section.id));
    if (active) {
      markCurrentSection(active.id);
    }
  }, { rootMargin: "-20% 0px -55% 0px", threshold: 0.1 });
  navSections.forEach((section) => sectionObserver.observe(section));
}

document.querySelectorAll("[data-open-dialog]").forEach((button) => {
  button.addEventListener("click", () => {
    const dialog = document.getElementById(button.getAttribute("data-open-dialog"));
    if (dialog && typeof dialog.showModal === "function") {
      dialog.showModal();
    }
  });
});
