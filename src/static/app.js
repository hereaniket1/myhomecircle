const sections = window.__SPA_SECTIONS__ || {};
const appState = window.__APP_STATE__ || { authed: false };
const screen = document.getElementById("screen");
const navButtons = Array.from(document.querySelectorAll("[data-view]"));
const appShell = document.querySelector(".app-shell");
const mobileMenu = document.getElementById("mobileMenu");
const loginModal = document.getElementById("loginModal");
const authError = document.getElementById("authError");
let otpCountdownTimer = null;
let otpCountdownRemaining = 20;

const protectedViews = new Set(["vendors", "vendor_detail", "quotes", "groups", "group_detail", "leaderboard", "profile"]);
const recentActivity = [
  { title: "Villa 300 uploaded a Solar Installation quote", time: "2h ago", points: "+50 points", icon: "▣" },
  { title: "Solar Group Buy reached 15 members", time: "3h ago", points: "", icon: "👥" },
  { title: "Interior Vendor received a 5-star review", time: "5h ago", points: "+20 points", icon: "★" },
  { title: "Water Softener Group Buy saved ₹3.2L for 12 members", time: "1d ago", points: "", icon: "💧" },
];
const groupBuys = [
  { title: "Solar Installation", members: "18 members joined", goal: "Goal: 25 members", closing: "Closing in 5 days", width: "62%" },
  { title: "Interior Package", members: "9 members joined", goal: "Goal: 15 members", closing: "Closing in 7 days", width: "54%" },
  { title: "Water Purifier", members: "7 members joined", goal: "Goal: 12 members", closing: "Closing in 4 days", width: "48%" },
];
const bestDeals = [
  { title: "Solar Installation", low: "₹2.05L", high: "₹2.62L", save: "₹57,000", img: "☀" },
  { title: "Interior Package", low: "₹4.10L", high: "₹4.75L", save: "₹65,000", img: "⌂" },
];
const contributors = [
  { name: "Villa 300", points: "1,250 pts", badge: "Gold Badge" },
  { name: "Villa 112", points: "980 pts", badge: "Silver Badge" },
  { name: "Villa 215", points: "820 pts", badge: "Silver Badge" },
];
let communitySearchTimer = null;

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

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setActive(view) {
  navButtons.forEach((btn) => btn.classList.toggle("is-active", btn.dataset.view === view));
}

function setAuthError(message = "") {
  if (!authError) return;
  if (!message) {
    authError.textContent = "";
    authError.classList.add("hidden");
    return;
  }
  authError.textContent = message;
  authError.classList.remove("hidden");
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

function setMobileMenu(open) {
  if (!mobileMenu || !appShell) return;
  appShell.classList.toggle("nav-open", open);
  mobileMenu.classList.toggle("is-open", open);
  document.body.classList.toggle("mobile-menu-open", open);
  if (open) {
    mobileMenu.removeAttribute("hidden");
    return;
  }
  mobileMenu.setAttribute("hidden", "");
}

function toggleMobileMenu() {
  setMobileMenu(!mobileMenu?.classList.contains("is-open"));
}

function renderAuthGate(view) {
  screen.innerHTML = `
    <section class="gate">
      <div class="gate-card">
        <div class="kicker">Protected Area</div>
        <h1>Google login required</h1>
        <p>${view} is available after sign in. Home stays public so people can preview the app first.</p>
        <button class="primary-big primary-big--inline" type="button" data-action="open-login">Continue with Google</button>
      </div>
    </section>
  `;
}

function renderHome() {
  const data = sections.home;
  const user = appState.currentUser;
  const userName = user?.full_name || user?.name || user?.email || "User";
  const firstNameSource = userName.includes("@") ? userName.split("@")[0] : userName;
  const firstName = firstNameSource.trim().split(/\s+/)[0] || "User";
  const title = isAuthed() && user ? `Welcome ${escapeHtml(firstName)}` : "Welcome to HomeCircle";
  const userInitial = userName.trim().charAt(0).toUpperCase() || "U";
  const safeUserName = escapeHtml(userName);
  const authAction = isAuthed()
    ? `
      <button class="dashboard-notification" type="button" aria-label="Notifications">
        <span>🔔</span>
        <b>3</b>
      </button>
      <div class="dashboard-user-chip" title="${safeUserName}">
        <span>${escapeHtml(userInitial)}</span>
        <strong>${safeUserName}</strong>
      </div>
      <a class="dashboard-auth-btn dashboard-auth-btn--ghost" href="/logout">Logout</a>
    `
    : `<button class="dashboard-auth-btn" type="button" data-action="open-login">Signup/Login</button>`;
  screen.innerHTML = `
    <section class="dashboard-grid">
      <header class="dashboard-hero">
        <div>
          <h1>${title} 👋</h1>
          <p>${isAuthed() ? "Avani Abode • Villa 300" : "Browse the public HomeCircle dashboard"}</p>
        </div>
        <div class="dashboard-hero__actions">
          <div class="dashboard-hero__search">
            <span>⌕</span>
            <input type="text" value="" placeholder="Search vendors, quotes, group buys..." />
          </div>
          ${authAction}
        </div>
      </header>

      <section class="summary-card">
        <div class="summary-card__main">
          <div class="summary-card__kicker">Community Savings This Month</div>
          <div class="summary-card__value">₹14.8L</div>
          <div class="summary-card__sub">Saved through group buys</div>
        </div>
        <div class="summary-card__stats">
          <article><strong>126</strong><span>Verified Quotes</span></article>
          <article><strong>82</strong><span>Active Residents</span></article>
          <article><strong>48</strong><span>Vendors</span></article>
          <article><strong>1,250</strong><span>My Points</span></article>
        </div>
        <div class="summary-card__art"></div>
      </section>

      <section class="quick-actions">
        ${[
          ["Upload Quote", "Get community insights", "☁"],
          ["Start Group Buy", "Save more together", "👥"],
          ["Add Vendor", "Share trusted vendor", "⌂"],
          ["Write Review", "Help your community", "★"],
        ].map(([title, subtitle, icon]) => `
          <button class="quick-action" type="button">
            <span class="quick-action__icon">${icon}</span>
            <strong>${title}</strong>
            <small>${subtitle}</small>
          </button>
        `).join("")}
      </section>

      <section class="content-grid">
        <article class="panel panel--main panel--active">
          <div class="panel__head"><h2>Active Group Buys</h2><button class="link-btn" data-go="groups">View all</button></div>
          <div class="group-list">
            ${groupBuys.map((group) => `
              <div class="group-row">
                <div class="group-row__thumb"></div>
                <div class="group-row__body">
                  <strong>${group.title}</strong>
                  <span>${group.members}</span>
                  <div class="group-row__meta">
                    <div class="group-progress"><span style="width:${group.width}"></span></div>
                    <small>${group.goal}</small>
                    <small class="danger">${group.closing}</small>
                  </div>
                </div>
                <button class="join-btn" type="button">Join</button>
              </div>
            `).join("")}
          </div>
        </article>

        <article class="panel panel--right panel--contributors">
          <div class="panel__head"><h2>Top Contributors</h2><button class="link-btn" data-go="leaderboard">View all</button></div>
          <div class="contributors">
            ${contributors.map((person, index) => `
              <div class="contributor-row">
                <div class="contributor-row__rank">${index + 1}</div>
                <div class="contributor-row__avatar"></div>
                <div class="contributor-row__meta">
                  <strong>${person.name}</strong>
                  <span>${person.badge}</span>
                </div>
                <div class="contributor-row__points">${person.points}</div>
              </div>
            `).join("")}
          </div>
        </article>

        <article class="panel panel--main panel--activity">
          <div class="panel__head"><h2>Recent Activity</h2><button class="link-btn">View all</button></div>
          <div class="activity-list">
            ${recentActivity.map((item) => `
              <div class="activity-row">
                <div class="activity-row__icon">${item.icon}</div>
                <div class="activity-row__body">
                  <strong>${item.title}</strong>
                  <span>${item.time}</span>
                </div>
                <div class="activity-row__points">${item.points}</div>
              </div>
            `).join("")}
          </div>
        </article>

        <article class="panel panel--right panel--deals">
          <div class="panel__head"><h2>Best Deals Right Now 🔥</h2><button class="link-btn" data-go="quotes">View all</button></div>
          <div class="deals-row">
            ${bestDeals.map((deal) => `
              <div class="deal-card">
                <div class="deal-card__img">${deal.img}</div>
                <div class="deal-card__body">
                  <strong>${deal.title}</strong>
                  <div><span>Lowest Quote</span><b class="green">${deal.low}</b></div>
                  <div><span>Highest Quote</span><b class="red">${deal.high}</b></div>
                  <div><span>You Save</span><b class="green">${deal.save}</b></div>
                </div>
              </div>
            `).join("")}
          </div>
          <div class="deal-footer">
            <div class="deal-footer__avatars">◔◑◐◓ <span>+13</span></div>
            <div>18 residents interested</div>
            <button class="join-btn join-btn--solid" type="button">View Quotes</button>
          </div>
        </article>

        <article class="panel panel--right panel--invite">
          <div class="invite-card">
            <h2>Invite Your Neighbors</h2>
            <p>More members, more savings!</p>
            <button class="join-btn join-btn--solid" type="button">Invite Now</button>
          </div>
        </article>

        <article class="panel panel--main panel--vendors">
          <div class="panel__head"><h2>Popular Vendors in Avani Abode</h2><button class="link-btn" data-go="vendors">View all vendors</button></div>
          <div class="vendor-strip">
            ${data.vendors.map((vendor) => `
              <div class="vendor-mini">
                <div class="vendor-mini__icon">⌂</div>
                <strong>${vendor.name}</strong>
                <span>${vendor.category}</span>
                <small>${vendor.uses}</small>
              </div>
            `).join("")}
          </div>
        </article>
      </section>
    </section>
  `;
}

function communityAddressLine(address = {}) {
  return [
    address.address_line_1,
    address.address_line_2,
    address.locality,
    address.city,
    address.state,
    address.postal_code,
    address.country,
  ].filter(Boolean).join(", ");
}

function renderCommunityList(communities = []) {
  const list = document.getElementById("communityList");
  if (!list) return;
  if (!communities.length) {
    list.innerHTML = `
      <div class="community-empty">
        <strong>No communities found</strong>
        <span>Try another search or register your community.</span>
      </div>
    `;
    return;
  }
  list.innerHTML = communities.map((community) => {
    const created = community.created_at ? new Date(community.created_at).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }) : "Recently";
    return `
      <article class="community-card">
        <div class="community-card__mark">${escapeHtml(community.name?.charAt(0) || "C")}</div>
        <div>
          <div class="community-card__top">
            <h3>${escapeHtml(community.name || "Community")}</h3>
            <span>${escapeHtml(community.status || "ACTIVE")}</span>
          </div>
          <p>${escapeHtml(communityAddressLine(community.address))}</p>
          <small>Registered ${created}</small>
        </div>
      </article>
    `;
  }).join("");
}

function renderCommunityMatches(matches = []) {
  const box = document.getElementById("communityMatches");
  if (!box) return;
  if (!matches.length) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.classList.remove("hidden");
  box.innerHTML = `
    <strong>Possible existing communities found</strong>
    ${matches.map((match) => `
      <div class="community-match">
        <span>${escapeHtml(match.name)}</span>
        <small>${escapeHtml(communityAddressLine(match.address))}</small>
      </div>
    `).join("")}
  `;
}

async function loadCommunities(search = "") {
  const list = document.getElementById("communityList");
  if (list) list.innerHTML = `<div class="community-empty">Loading communities...</div>`;
  try {
    const response = await fetch(`/api/communities?q=${encodeURIComponent(search)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to load communities");
    renderCommunityList(result.communities || []);
  } catch (error) {
    if (list) list.innerHTML = `<div class="community-error">${escapeHtml(error.message)}</div>`;
  }
}

async function checkExistingCommunities(form) {
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  if (!payload.name && !payload.address_line_1 && !payload.city && !payload.postal_code) return;
  try {
    const { response, json } = await postJson("/api/communities/search-existing", payload);
    if (!response.ok) throw new Error(json.error || "Unable to search existing communities");
    renderCommunityMatches(json.matches || []);
  } catch (error) {
    renderCommunityMatches([]);
  }
}

function renderCommunity() {
  const registerAction = isAuthed()
    ? `<button class="dashboard-auth-btn" type="button" data-action="toggle-community-form">Register my community</button>`
    : "";
  screen.innerHTML = `
    <section class="community-page">
      <header class="community-hero">
        <div>
          <div class="kicker">Communities</div>
          <h1>Find your community</h1>
          <p>View registered communities by newest registration date and search by name, address, city, state, or postal code.</p>
        </div>
        ${registerAction}
      </header>

      <div class="community-search">
        <span>⌕</span>
        <input id="communitySearch" type="search" placeholder="Search community name, address, city, state, postal code..." />
      </div>

      <section class="community-register hidden" id="communityRegister">
        <div class="panel__head">
          <h2>Register my community</h2>
          <button class="link-btn" type="button" data-action="toggle-community-form">Close</button>
        </div>
        <form class="community-form" id="communityForm">
          <label><span>Community name</span><input name="name" required placeholder="Avani Abode" /></label>
          <label><span>Address line 1</span><input name="address_line_1" required placeholder="Street, block, society road" /></label>
          <label><span>Address line 2</span><input name="address_line_2" placeholder="Optional landmark or phase" /></label>
          <label><span>Locality</span><input name="locality" placeholder="Whitefield" /></label>
          <label><span>City</span><input name="city" required placeholder="Bengaluru" /></label>
          <label><span>State</span><input name="state" required placeholder="Karnataka" /></label>
          <label><span>Postal code</span><input name="postal_code" required placeholder="560066" /></label>
          <label><span>Country</span><input name="country" value="India" /></label>
          <div id="communityMatches" class="community-matches hidden"></div>
          <div class="community-form__actions">
            <button class="primary-big primary-big--compact" type="submit">Register community</button>
          </div>
          <div id="communityFormMessage" class="community-form-message"></div>
        </form>
      </section>

      <section class="community-results">
        <div class="panel__head">
          <h2>Registered communities</h2>
          <span>Newest first</span>
        </div>
        <div id="communityList" class="community-list"></div>
      </section>
    </section>
  `;
  loadCommunities();
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
  else if (view === "community") renderCommunity();
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
    setMobileMenu(false);
  });
});

screen.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "toggle-community-form") {
    document.getElementById("communityRegister")?.classList.toggle("hidden");
    return;
  }

  const go = event.target.closest("[data-go]")?.dataset.go;
  if (!go) return;
  setActive(go);
  routeTo(viewToPath(go));
  renderView(go);
});

screen.addEventListener("input", (event) => {
  if (event.target?.id === "communitySearch") {
    clearTimeout(communitySearchTimer);
    communitySearchTimer = window.setTimeout(() => loadCommunities(event.target.value.trim()), 250);
  }
});

screen.addEventListener("submit", async (event) => {
  const form = event.target.closest("#communityForm");
  if (!form) return;
  event.preventDefault();
  const message = document.getElementById("communityFormMessage");
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  if (message) {
    message.className = "community-form-message";
    message.textContent = "Checking and registering community...";
  }
  const { response, json } = await postJson("/api/communities", payload);
  if (!response.ok) {
    renderCommunityMatches(json.matches || []);
    if (message) {
      message.classList.add("is-error");
      message.textContent = json.error || "Unable to register community";
    }
    return;
  }
  if (message) {
    message.classList.add("is-success");
    message.textContent = "Community registered successfully.";
  }
  form.reset();
  form.querySelector('input[name="country"]').value = "India";
  renderCommunityMatches([]);
  loadCommunities(document.getElementById("communitySearch")?.value?.trim() || "");
});

function openLoginModal() {
  setAuthError("");
  loginModal?.removeAttribute("hidden");
}

function closeLoginModal() {
  loginModal?.setAttribute("hidden", "");
}

function setAuthPanel(panelName) {
  document.querySelectorAll("[data-auth-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.authPanel !== panelName);
  });
  document.querySelectorAll("[data-auth-tab]").forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.authTab === panelName);
  });
}

function showSignupOtpStep() {
  setAuthError("");
  document.querySelector('[data-signup-step="details"]')?.classList.add("hidden");
  document.querySelector('[data-signup-step="otp"]')?.classList.remove("hidden");
}

function showSignupDetailsStep() {
  setAuthError("");
  document.querySelector('[data-signup-step="otp"]')?.classList.add("hidden");
  document.querySelector('[data-signup-step="details"]')?.classList.remove("hidden");
}

function setOtpCountdown(seconds) {
  clearInterval(otpCountdownTimer);
  otpCountdownRemaining = seconds;
  const countdownEl = document.querySelector("[data-otp-countdown]");
  const resendBtn = document.querySelector("[data-action='resend-otp']");
  if (resendBtn) resendBtn.disabled = true;
  if (countdownEl) countdownEl.textContent = `${otpCountdownRemaining}s`;
  otpCountdownTimer = window.setInterval(() => {
    otpCountdownRemaining -= 1;
    if (countdownEl) countdownEl.textContent = `${Math.max(otpCountdownRemaining, 0)}s`;
    if (otpCountdownRemaining <= 0) {
      clearInterval(otpCountdownTimer);
      if (resendBtn) resendBtn.disabled = false;
      if (countdownEl) countdownEl.textContent = "";
    }
  }, 1000);
}

function notifyOpenerAndCloseSelf() {
  if (window.opener && !window.opener.closed) {
    window.opener.postMessage({ type: "oauth_success" }, window.location.origin);
    window.close();
    return true;
  }
  return false;
}

function handleAuthSuccess(user) {
  appState.authed = true;
  appState.currentUser = user;
  renderView("home");
  setActive("home");
  setAuthError("");
  closeLoginModal();
  if (notifyOpenerAndCloseSelf()) return;
  window.setTimeout(() => window.location.reload(), 120);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await response.json().catch(() => ({}));
  return { response, json };
}

document.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "toggle-nav") toggleMobileMenu();
  if (action === "open-login") {
    setMobileMenu(false);
    openLoginModal();
  }
  if (action === "close-login") closeLoginModal();
  if (action === "google-login") {
    const nextUrl = location.pathname || "/";
    const url = `/auth/google/login?popup=true&next=${encodeURIComponent(nextUrl)}`;
    const popup = window.open(url, "myhomecircle_google_login", "width=520,height=680");
    if (!popup) window.location.href = url.replace("popup=true&", "");
  }
  if (action === "verify-otp") {
    const form = document.querySelector(".auth-panel[data-auth-panel='signup']");
    const email = form?.querySelector("input[name='email']")?.value?.trim();
    const otp_code = form?.querySelector("input[name='otp_code']")?.value?.trim();
    if (!email || !otp_code) return;
    postJson("/api/auth/verify-email", { email, otp_code })
      .then(({ response, json }) => {
        if (!response.ok) throw new Error(json.error || "OTP verification failed");
        handleAuthSuccess(json.user);
      })
      .catch((error) => setAuthError(error.message));
  }
  if (action === "resend-otp") {
    const form = document.querySelector(".auth-panel[data-auth-panel='signup']");
    const email = form?.querySelector("input[name='email']")?.value?.trim();
    if (!email) return setAuthError("Please enter your email first.");
    postJson("/api/auth/resend-otp", { email })
      .then(({ response, json }) => {
        if (!response.ok) throw new Error(json.error || "Unable to resend OTP");
        showSignupOtpStep();
        setOtpCountdown(20);
      })
      .catch((error) => setAuthError(error.message));
  }
  if (action === "signup-back") {
    showSignupDetailsStep();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMobileMenu(false);
});

document.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-auth-tab]");
  if (!tab) return;
  setAuthPanel(tab.dataset.authTab);
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest(".auth-panel");
  if (!form) return;
  const action = event.submitter?.getAttribute("formaction");
  if (!action) return;
  event.preventDefault();
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  payload.accepted_terms = formData.get("accepted_terms") === "on";
  const response = await fetch(action, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    setAuthError(result.error || "Unable to complete auth step");
    return;
  }
  if (result.demo_otp) {
    showSignupOtpStep();
    setOtpCountdown(20);
    return;
  }
  if (result.user) {
    handleAuthSuccess(result.user);
  }
});

window.addEventListener("message", async (event) => {
  if (event.data?.type !== "oauth_success") return;
  const response = await fetch("/auth/me");
  const result = await response.json().catch(() => ({}));
  if (result.authenticated) {
    handleAuthSuccess(result.user);
  } else {
    window.location.reload();
  }
});

const initial = location.pathname.replace(/^\/+/, "") || "home";
renderView(initial);
setActive(initial === "" ? "home" : initial);
if (appState.authMode) setAuthPanel(appState.authMode);
