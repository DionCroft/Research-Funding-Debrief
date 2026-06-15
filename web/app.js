const form = document.querySelector("#signup-form");
const statusMessage = document.querySelector("#form-status");
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
