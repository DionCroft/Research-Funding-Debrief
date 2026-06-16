const form = document.querySelector("#signup-form");
const statusMessage = document.querySelector("#form-status");
const liveUpdated = document.querySelector("#live-updated");
const liveList = document.querySelector("#live-list");
const liveActiveCount = document.querySelector("#live-active-count");
const liveClosingCount = document.querySelector("#live-closing-count");
const liveSourceCount = document.querySelector("#live-source-count");
const liveTopicCount = document.querySelector("#live-topic-count");
const liveRefresh = document.querySelector("#live-refresh");
const personalRadarForm = document.querySelector("#personal-radar-form");
const personalRadarResults = document.querySelector("#personal-radar-results");
const personalRadarCount = document.querySelector("#personal-radar-count");
const personalRadarReset = document.querySelector("#personal-radar-reset");
const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const configuredSignupApi = window.RESEARCH_FUNDING_SIGNUP_API || "";
const personalRadarStorageKey = "researchFundingDebrief.personalRadar";
let liveFundingItems = [];

function selectedTopics(formData) {
  return formData.getAll("topics");
}

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.style.color = isError ? "#b3402f" : "#075f5b";
}

function signupApiUrl() {
  if (configuredSignupApi) {
    return configuredSignupApi;
  }

  if (localHosts.has(window.location.hostname)) {
    return "/api/signup";
  }

  return "";
}

function mailtoSignup(payload) {
  const subject = encodeURIComponent("Research Funding Debrief signup");
  const body = encodeURIComponent(
    [
      `Name: ${payload.firstName} ${payload.lastName}`,
      `Email: ${payload.email}`,
      `Frequency: ${payload.frequency}`,
      `Topics: ${payload.topics.join(", ")}`,
    ].join("\n")
  );
  window.location.href = `mailto:d.mariyanayagam@londonmet.ac.uk?subject=${subject}&body=${body}`;
}

function formatUpdatedAt(value) {
  if (!value) {
    return "Latest snapshot pending";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return `Last updated ${value}`;
  }

  return `Last updated ${parsed.toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  })}`;
}

function setText(element, value) {
  if (element) {
    element.textContent = value;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function updateLiveStats(summary) {
  setText(liveActiveCount, summary.trackedCalls ?? "--");
  setText(liveClosingCount, summary.closingSoon ?? "--");
  setText(liveSourceCount, summary.sourcesScanned ?? "--");
  setText(liveTopicCount, summary.topicCategories ?? "--");
}

function normaliseText(value) {
  return String(value || "").toLowerCase();
}

function selectedValues(name) {
  if (!personalRadarForm) {
    return [];
  }

  return Array.from(personalRadarForm.querySelectorAll(`input[name="${name}"]:checked`)).map(
    (input) => input.value
  );
}

function itemMatchesStatus(item, selectedStatuses) {
  if (selectedStatuses.length === 0) {
    return true;
  }

  const status = item.status || "Open";
  if (selectedStatuses.includes(status)) {
    return true;
  }

  return selectedStatuses.includes("Open") && !["New", "Closing soon"].includes(status);
}

function itemMatchesNeedle(item, selectedNeedles, fields) {
  if (selectedNeedles.length === 0) {
    return true;
  }

  const haystack = fields
    .flatMap((field) => {
      const value = item[field];
      return Array.isArray(value) ? value : [value];
    })
    .map(normaliseText)
    .join(" ");

  return selectedNeedles.some((needle) => haystack.includes(normaliseText(needle)));
}

function readPersonalRadarFilters() {
  return {
    status: selectedValues("status"),
    topics: selectedValues("topics"),
    sources: selectedValues("sources"),
  };
}

function savePersonalRadarFilters() {
  if (!personalRadarForm) {
    return;
  }

  window.localStorage.setItem(personalRadarStorageKey, JSON.stringify(readPersonalRadarFilters()));
}

function restorePersonalRadarFilters() {
  if (!personalRadarForm) {
    return;
  }

  try {
    const saved = JSON.parse(window.localStorage.getItem(personalRadarStorageKey) || "{}");
    ["status", "topics", "sources"].forEach((name) => {
      if (!Array.isArray(saved[name])) {
        return;
      }

      personalRadarForm.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
        input.checked = saved[name].includes(input.value);
      });
    });
  } catch (error) {
    window.localStorage.removeItem(personalRadarStorageKey);
  }
}

function filterPersonalRadarItems() {
  const filters = readPersonalRadarFilters();
  return liveFundingItems.filter((item) => {
    return (
      itemMatchesStatus(item, filters.status) &&
      itemMatchesNeedle(item, filters.topics, ["topics", "title"]) &&
      itemMatchesNeedle(item, filters.sources, ["source"])
    );
  });
}

function renderPersonalRadar() {
  if (!personalRadarResults) {
    return;
  }

  const matches = filterPersonalRadarItems();
  setText(
    personalRadarCount,
    `${matches.length} matching ${matches.length === 1 ? "call" : "calls"}`
  );

  if (matches.length === 0) {
    personalRadarResults.innerHTML = `
      <article>
        <p class="live-label">No matches</p>
        <h3>No calls match those filters yet.</h3>
        <p>Broaden the topics or funders to scan more of the current snapshot.</p>
      </article>
    `;
    return;
  }

  personalRadarResults.innerHTML = "";
  matches.slice(0, 12).forEach((item) => {
    const card = document.createElement("article");
    const link = item.url
      ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>`
      : escapeHtml(item.title);
    const topics = Array.isArray(item.topics) ? item.topics.slice(0, 4) : [];

    card.innerHTML = `
      <p class="live-label">${escapeHtml(item.status || "Open")} · ${escapeHtml(item.source || "Unknown source")}</p>
      <h3>${link}</h3>
      <p>${escapeHtml(item.deadline || "No deadline parsed")} <span>${escapeHtml(item.urgency || "")}</span></p>
      <div class="live-tags">${topics.map((topic) => `<span>${escapeHtml(topic)}</span>`).join("")}</div>
    `;
    personalRadarResults.append(card);
  });
}

function renderLiveItems(items) {
  if (!liveList || !items || items.length === 0) {
    if (liveList) {
      liveList.innerHTML = `
        <article>
          <p class="live-label">Snapshot empty</p>
          <h3>No funding calls are available yet.</h3>
          <p>Try refreshing the radar again shortly.</p>
        </article>
      `;
    }
    return;
  }

  liveList.innerHTML = "";
  items.slice(0, 8).forEach((item) => {
    const card = document.createElement("article");
    const link = item.url
      ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>`
      : escapeHtml(item.title);
    const topics = Array.isArray(item.topics) ? item.topics.slice(0, 3) : [];

    card.innerHTML = `
      <p class="live-label">${escapeHtml(item.status || "Tracked")} · ${escapeHtml(item.source || "Unknown source")}</p>
      <h3>${link}</h3>
      <p>${escapeHtml(item.deadline || "No deadline parsed")} <span>${escapeHtml(item.urgency || "")}</span></p>
      <div class="live-tags">${topics.map((topic) => `<span>${escapeHtml(topic)}</span>`).join("")}</div>
    `;
    liveList.append(card);
  });
}

async function loadLiveUpdates() {
  if (!liveList) {
    return;
  }

  if (liveRefresh) {
    liveRefresh.disabled = true;
    liveRefresh.classList.add("is-refreshing");
  }
  setText(liveUpdated, "Refreshing funding snapshot...");
  liveList.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(`data/live-updates.json?refresh=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Live updates unavailable");
    }
    const payload = await response.json();
    liveFundingItems = payload.items || [];
    setText(liveUpdated, formatUpdatedAt(payload.generatedAt));
    updateLiveStats(payload.summary || {});
    renderLiveItems(liveFundingItems);
    renderPersonalRadar();
  } catch (error) {
    liveFundingItems = [];
    setText(liveUpdated, "Live snapshot unavailable right now");
    liveList.innerHTML = `
      <article>
        <p class="live-label">Refresh failed</p>
        <h3>The radar could not load the latest snapshot.</h3>
        <p>Please use the refresh button again in a moment.</p>
      </article>
    `;
    renderPersonalRadar();
  } finally {
    liveList.setAttribute("aria-busy", "false");
    if (liveRefresh) {
      liveRefresh.disabled = false;
      liveRefresh.classList.remove("is-refreshing");
    }
  }
}

if (form) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(form);
    const payload = {
      firstName: String(formData.get("firstName") || "").trim(),
      lastName: String(formData.get("lastName") || "").trim(),
      email: String(formData.get("email") || "").trim(),
      frequency: String(formData.get("frequency") || "daily"),
      topics: selectedTopics(formData),
    };

    if (!payload.firstName || !payload.lastName || !payload.email) {
      setStatus("Please complete your name and email address.", true);
      return;
    }

    if (payload.topics.length === 0) {
      setStatus("Choose at least one topic of interest.", true);
      return;
    }

    const apiUrl = signupApiUrl();
    if (!apiUrl) {
      setStatus("Opening a prefilled email signup.", false);
      mailtoSignup(payload);
      return;
    }

    try {
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("Signup failed");
      }

      const result = await response.json();
      setStatus(result.message || "You're on the briefing list.");
      form.reset();
      form.elements.frequency.value = payload.frequency;
    } catch (error) {
      setStatus("Signup service is not running. Opening an email signup instead.", true);
      mailtoSignup(payload);
    }
  });
}

if (liveRefresh) {
  liveRefresh.addEventListener("click", () => {
    loadLiveUpdates();
  });
}

if (personalRadarForm) {
  restorePersonalRadarFilters();
  personalRadarForm.addEventListener("change", () => {
    savePersonalRadarFilters();
    renderPersonalRadar();
  });
}

if (personalRadarReset && personalRadarForm) {
  personalRadarReset.addEventListener("click", () => {
    window.localStorage.removeItem(personalRadarStorageKey);
    personalRadarForm.reset();
    renderPersonalRadar();
  });
}

loadLiveUpdates();
