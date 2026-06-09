const sections = window.__SPA_SECTIONS__ || {};
const appState = window.__APP_STATE__ || { authed: false };
const screen = document.getElementById("screen");
const navButtons = Array.from(document.querySelectorAll("[data-view]"));
const menuBtn = document.querySelector("[data-action='toggle-nav']");
const appShell = document.querySelector(".app-shell");

const protectedViews = new Set(["vendors", "vendor_detail", "quotes", "groups", "group_detail", "leaderboard", "profile"]);

const sampleVendorDetails = {
  name: "SolarBright Energy",
  category: "Solar Installation",
  rating: "4.5",
  reviews: 32,
  services: "Solar Installation, Maintenance",
  areas: "Whitefield, Sarjapur, Marathahalli",
  experience: "8+ Years",
  usage: "Used by 32 residents",
  avgQuote: "₹2.15L for 5kW setup",
  contact: "+91 98765 43210",
};

const quotes = [
  { title: "Solar Installation - 5kW", vendor: "SolarBright Energy", price: "₹2,15,000", date: "10 Jun 2026" },
  { title: "Modular Kitchen", vendor: "Home Interior Studio", price: "₹1,45,000", date: "08 Jun 2026" },
  { title: "Water Softener", vendor: "AquaPure Water", price: "₹24,500", date: "05 Jun 2026" },
  { title: "CCTV Setup", vendor: "SecureEye CCTV", price: "₹42,000", date: "03 Jun 2026" },
];

const groups = [
  { title: "5kW Solar Installation", target: "20 Members", joined: "12 Joined", ends: "Ends in 10 days" },
  { title: "Modular Kitchen Setup", target: "15 Members", joined: "8 Joined", ends: "Ends in 7 days" },
  { title: "Water Softener Group Buy", target: "10 Members", joined: "5 Joined", ends: "Ends in 5 days" },
  { title: "CCTV Package", target: "12 Members", joined: "4 Joined", ends: "Ends in 12 days" },
];

function isAuthed() {
  return Boolean(appState.authed);
}

function setActive(view) {
  navButtons.forEach((btn) => btn.classList.toggle("is-active", btn.dataset.view === view));
}

function viewToPath(view) {
  if (view === "home") return "/";
  if (view === "group_detail") return "/group-detail";
  if (view === "vendor_detail") return "/vendor-detail";
  return `/${view}`;
}

function routeTo(path) {
  history.replaceState(null, "", path);
}

function renderAuthGate(view) {
  screen.innerHTML = `
    <section class="gate">
      <div class="gate-card">
        <div class="kicker">Protected Area</div>
        <h1>Google login required</h1>
        <p>${view} is available after sign in. Home stays public so people can preview the app first.</p>
        <a class="primary-big primary-big--inline" href="/login/google?next=${encodeURIComponent(location.pathname || "/")}">Continue with Google</a>
      </div>
    </section>
  `;
}

function renderHome() {
  const data = sections.home;
  screen.innerHTML = `
    <section class="dashboard">
      <div class="hero-row">
        <div><h1>${data.title}</h1></div>
        <div class="badge-pill">${data.badge}</div>
      </div>
      <p class="hero-banner">${data.hero}</p>
      <div class="stats-grid">
        ${data.stats
          .map(
            (item) => `
              <article class="stat-card">
                <div class="stat-value">${item.value}</div>
                <div class="stat-label">${item.label}</div>
              </article>`,
          )
          .join("")}
      </div>
      <div class="section-head">
        <h2>Top Vendors</h2>
        <button class="link-btn" data-go="vendors">View all</button>
      </div>
      <div class="vendor-list">
        ${data.vendors
          .map(
            (vendor) => `
              <article class="vendor-card">
                <div class="vendor-icon">⌂</div>
                <div class="vendor-info">
                  <div class="vendor-name">${vendor.name}</div>
                  <div class="vendor-category">${vendor.category}</div>
                </div>
                <div class="vendor-meta">
                  <div class="vendor-rating">${vendor.rating} ★</div>
                  <div class="vendor-uses">${vendor.uses}</div>
                </div>
              </article>`,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderVendors() {
  screen.innerHTML = `
    <section class="vendor-page">
      <div class="search-bar"><span>⌕</span><input value="" placeholder="Search vendors..." /></div>
      <div class="category-row">
        ${["All", "Solar", "Interior", "Water", "CCTV"].map((item, index) => `<button class="chip ${index === 0 ? "is-selected" : ""}">${item}</button>`).join("")}
      </div>
      <div class="section-head"><h2>Top Vendors</h2></div>
      <div class="vendor-list">
        ${sections.home.vendors
          .concat([{ name: "SecureEye CCTV", category: "CCTV Installation", rating: "4.1", uses: "10 used" }])
          .map(
            (vendor) => `
              <article class="vendor-card vendor-card--clickable" data-go="vendor_detail">
                <div class="vendor-icon">⌂</div>
                <div class="vendor-info">
                  <div class="vendor-name">${vendor.name}</div>
                  <div class="vendor-category">${vendor.category}</div>
                </div>
                <div class="vendor-meta">
                  <div class="vendor-rating">${vendor.rating} ★</div>
                  <div class="vendor-uses">${vendor.uses}</div>
                </div>
              </article>`,
          )
          .join("")}
      </div>
      <button class="primary-big">+ Add Vendor</button>
    </section>
  `;
}

function renderVendorDetail() {
  const v = sampleVendorDetails;
  screen.innerHTML = `
    <section class="detail-page">
      <div class="detail-top">
        <button class="icon-btn" data-go="vendors">←</button>
        <button class="icon-btn">♡</button>
      </div>
      <div class="vendor-hero">
        <div class="vendor-hero__icon">⌂</div>
        <div>
          <h1>${v.name}</h1>
          <div class="vendor-category">${v.category}</div>
          <div class="vendor-rating vendor-rating--detail">${v.rating} ★ (${v.reviews} Reviews)</div>
        </div>
      </div>
      <div class="tab-row">
        <button class="tab is-active">Overview</button>
        <button class="tab">Reviews (${v.reviews})</button>
        <button class="tab">Quotes (6)</button>
      </div>
      <article class="info-card">
        <div class="info-row"><span>Services</span><strong>${v.services}</strong></div>
        <div class="info-row"><span>Areas</span><strong>${v.areas}</strong></div>
        <div class="info-row"><span>Experience</span><strong>${v.experience}</strong></div>
        <div class="info-row"><span>Community Usage</span><strong>${v.usage}</strong></div>
        <div class="info-row"><span>Avg Quote</span><strong>${v.avgQuote}</strong></div>
        <div class="info-row"><span>Contact</span><strong>${v.contact}</strong></div>
      </article>
      <button class="primary-big">Contact Vendor</button>
    </section>
  `;
}

function renderQuotes() {
  screen.innerHTML = `
    <section class="list-page">
      <div class="tab-row tab-row--spaced">
        <button class="tab is-active">Browse Quotes</button>
        <button class="tab">My Quotes</button>
      </div>
      <div class="search-row">
        <div class="search-bar search-bar--compact"><span>⌕</span><input placeholder="Search quotes..." /></div>
        <button class="filter-btn">⎇</button>
      </div>
      <div class="vendor-list">
        ${quotes
          .map(
            (quote) => `
              <article class="quote-card">
                <div class="quote-icon"></div>
                <div class="vendor-info">
                  <div class="vendor-name">${quote.title}</div>
                  <div class="vendor-category">${quote.vendor}</div>
                  <div class="quote-price">${quote.price}</div>
                </div>
                <div class="quote-date">${quote.date}</div>
              </article>`,
          )
          .join("")}
      </div>
      <button class="primary-big">Upload Quote</button>
    </section>
  `;
}

function renderGroups() {
  screen.innerHTML = `
    <section class="list-page">
      <div class="tab-row tab-row--spaced">
        <button class="tab is-active">Active</button>
        <button class="tab">Joined</button>
        <button class="tab">Created</button>
      </div>
      <div class="vendor-list">
        ${groups
          .map(
            (group) => `
              <article class="group-card">
                <div class="vendor-name">${group.title}</div>
                <div class="vendor-category">Target: ${group.target}</div>
                <div class="group-bottom">
                  <div>${group.joined}</div>
                  <div class="group-ending">${group.ends}</div>
                </div>
              </article>`,
          )
          .join("")}
      </div>
      <button class="primary-big">+ Create Group Buy</button>
    </section>
  `;
}

function renderGroupDetail() {
  screen.innerHTML = `
    <section class="detail-page">
      <div class="detail-top">
        <button class="icon-btn" data-go="groups">←</button>
        <button class="icon-btn">↗</button>
      </div>
      <div class="vendor-hero">
        <div>
          <h1>5kW Solar Installation</h1>
          <p>Let's install solar together and negotiate the best price.</p>
        </div>
        <span class="status-pill">Active</span>
      </div>
      <div class="progress-block">
        <div class="progress-meta">12 / 20 Joined</div>
        <div class="progress-bar"><span style="width: 60%"></span></div>
      </div>
      <article class="info-card">
        <div class="info-row"><span>Category</span><strong>Solar Installation</strong></div>
        <div class="info-row"><span>Target Members</span><strong>20</strong></div>
        <div class="info-row"><span>Ends On</span><strong>20 Jun 2026</strong></div>
        <div class="info-row"><span>Created By</span><strong>Aniket Pathak</strong></div>
        <div class="info-row"><span>Vendor Proposals</span><strong>3 received</strong></div>
      </article>
      <button class="primary-big">Join Group Buy</button>
      <button class="secondary-big">View Proposals (3)</button>
    </section>
  `;
}

function renderLeaderboard() {
  screen.innerHTML = `
    <section class="leaderboard-page">
      <div class="points-card">
        <div>
          <div class="points-label">Your Points</div>
          <div class="points-value">2,450</div>
        </div>
        <div class="badge-gold">★<small>Gold Member</small></div>
      </div>
      <div class="selector">How to earn points? <span>⌄</span></div>
      <div class="tab-row tab-row--center">
        <button class="tab is-active">Leaderboard</button>
        <button class="tab">My Activity</button>
      </div>
      <div class="leader-list">
        ${[
          ["Rajesh Kumar", "3,850", "Platinum"],
          ["Priya Sharma", "2,980", "Gold"],
          ["Aniket Pathak", "2,450", "Gold"],
          ["Neha Iyer", "1,950", "Silver"],
          ["Saurabh Singh", "1,600", "Silver"],
        ]
          .map(
            (row, index) => `
              <article class="leader-card ${index === 2 ? "is-highlighted" : ""}">
                <div class="leader-rank">${index + 1}</div>
                <div class="leader-avatar"></div>
                <div class="leader-info">
                  <div class="vendor-name">${row[0]}</div>
                  <div class="vendor-category">${row[1]}</div>
                </div>
                <div class="leader-badge">${row[2]}</div>
              </article>`,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderProfile() {
  screen.innerHTML = `
    <section class="profile-page">
      <div class="profile-hero">
        <div class="profile-avatar">A</div>
        <h1>Aniket Pathak</h1>
        <div class="profile-badge">Gold Member</div>
      </div>
      <div class="profile-metrics">
        <div><strong>2,450</strong><span>Points</span></div>
        <div><strong>24</strong><span>Reviews</span></div>
        <div><strong>15</strong><span>Quotes</span></div>
        <div><strong>3</strong><span>Group Buys</span></div>
      </div>
      <div class="menu-list">
        ${["My Activity", "My Quotes", "My Reviews", "My Group Buys", "Settings", "Logout"]
          .map((item) => `<button class="menu-item">${item}<span>›</span></button>`)
          .join("")}
      </div>
    </section>
  `;
}

function renderRequirements() {
  const data = sections.requirements;
  screen.innerHTML = `
    <section class="requirements">
      <div class="requirements-header">
        <div><div class="kicker">Requirements</div><h1>${data.title}</h1><p>${data.subtitle}</p></div>
      </div>
      <div class="requirements-grid">
        <article class="req-card">
          <h3>Public</h3>
          <p>Home and requirements remain visible without login.</p>
        </article>
        <article class="req-card">
          <h3>Protected</h3>
          <p>Vendors, quotes, groups, leaderboard, and profile require Google login.</p>
        </article>
      </div>
    </section>
  `;
}

function renderView(view) {
  if (protectedViews.has(view) && !isAuthed()) {
    renderAuthGate(view);
    return;
  }
  if (view === "home") renderHome();
  else if (view === "vendors") renderVendors();
  else if (view === "vendor_detail") renderVendorDetail();
  else if (view === "quotes") renderQuotes();
  else if (view === "groups") renderGroups();
  else if (view === "group_detail") renderGroupDetail();
  else if (view === "leaderboard") renderLeaderboard();
  else if (view === "profile") renderProfile();
  else renderRequirements();
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const view = btn.dataset.view;
    setActive(view);
    routeTo(viewToPath(view));
    renderView(view);
  });
});

screen.addEventListener("click", (event) => {
  const go = event.target.closest("[data-go]")?.dataset.go;
  if (!go) return;
  setActive(go);
  routeTo(viewToPath(go));
  renderView(go);
});

menuBtn?.addEventListener("click", () => {
  appShell.classList.toggle("nav-open");
});

const initial = location.pathname.replace(/^\/+/, "") || "home";
renderView(initial);
setActive(initial === "" ? "home" : initial);
