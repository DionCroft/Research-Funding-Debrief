const form = document.querySelector("#signup-form");
const statusMessage = document.querySelector("#form-status");
const liveUpdated = document.querySelector("#live-updated");
const liveList = document.querySelector("#live-list");
const liveActiveCount = document.querySelector("#live-active-count");
const liveClosingCount = document.querySelector("#live-closing-count");
const liveSourceCount = document.querySelector("#live-source-count");
const liveTopicCount = document.querySelector("#live-topic-count");
const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const configuredSignupApi = window.RESEARCH_FUNDING_SIGNUP_API || "";

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

function renderLiveItems(items) {
  if (!liveList || !items || items.length === 0) {
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

  try {
    const response = await fetch("data/live-updates.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Live updates unavailable");
    }
    const payload = await response.json();
    setText(liveUpdated, formatUpdatedAt(payload.generatedAt));
    updateLiveStats(payload.summary || {});
    renderLiveItems(payload.items || []);
  } catch (error) {
    setText(liveUpdated, "Live snapshot unavailable right now");
  }
}

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

loadLiveUpdates();
