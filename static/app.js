(function () {
  "use strict";

  const body = document.body;
  if (!body || body.dataset.loggedIn !== "1") {
    return;
  }

  const state = {
    activeSessionId: null,
    isBusy: false,
    bootstrapLoaded: false,
  };

  const widget = document.getElementById("wellness-widget");
  const widgetFab = document.getElementById("wellness-fab");
  const widgetClose = document.getElementById("wellness-close");
  const widgetPanel = document.getElementById("wellness-panel");
  const widgetSnapshot = document.getElementById("wellness-snapshot");
  const widgetMessages = document.getElementById("wellness-messages");
  const widgetForm = document.getElementById("wellness-form");
  const widgetInput = document.getElementById("wellness-input");
  const widgetSessionInput = document.getElementById("wellness-session-id");
  const widgetNewSession = document.getElementById("wellness-new-session");

  const coachPage = document.getElementById("coach-page");
  const coachForm = document.getElementById("coach-form");
  const coachInput = document.getElementById("coach-message-input");
  const coachSessionInput = document.getElementById("coach-session-id");
  const coachChatLog = document.getElementById("coach-chat-log");
  const coachSessionList = document.getElementById("coach-session-list");
  const coachThreadTitle = document.getElementById("coach-thread-title");
  const twinLab = document.getElementById("twin-lab");
  const twinRunButton = document.getElementById("twin-recompute");
  const twinStatus = document.getElementById("twin-status");
  const twinNarrative = document.getElementById("twin-narrative");
  const twinForecast = document.getElementById("twin-forecast");
  const twinInsightGrid = document.getElementById("twin-insight-grid");
  const twinConfidenceLabel = document.getElementById("twin-confidence-label");
  const twinScoreRing = twinLab ? twinLab.querySelector(".score-ring-progress") : null;
  const twinProjectScore = document.getElementById("twin-project-score");
  const twinBaselineScore = document.getElementById("twin-baseline-score");
  const twinScoreDelta = document.getElementById("twin-score-delta");
  const twinCurrentScore = document.getElementById("twin-current-score");
  const twinScoreTarget = document.getElementById("twin-score-target");
  const twinScoreChange = document.getElementById("twin-score-change");
  const twinBestLever = document.getElementById("twin-best-lever");
  const twinControlLabels = new Map();
  const twinValueLabels = new Map();
  const autopilotPage = document.getElementById("autopilot-page");
  const autoRefreshButton = document.getElementById("auto-refresh");
  const autoStatus = document.getElementById("auto-status");
  const autoConfidence = document.getElementById("auto-confidence");
  const autoTimeBudget = document.getElementById("auto-time-budget");
  const autoPriority = document.getElementById("auto-priority");
  const autoPriority2 = document.getElementById("auto-priority-2");
  const autoScore = document.getElementById("auto-score");
  const autoCurrentScore = document.getElementById("auto-current-score");
  const autoLift = document.getElementById("auto-lift");
  const autoExpectedLift = document.getElementById("auto-expected-lift");
  const autoTimeNeeded = document.getElementById("auto-time-needed");
  const autoAfterScore = document.getElementById("auto-after-score");
  const autoActionTitle = document.getElementById("auto-action-title");
  const autoDoNot = document.getElementById("auto-do-not");
  const autoPayoff = document.getElementById("auto-payoff");
  const autoContract = document.getElementById("auto-contract");
  const autoWhyNow = document.getElementById("auto-why-now");
  const autoWhyThis = document.getElementById("auto-why-this");
  const autoWhyNot = document.getElementById("auto-why-not");
  const autoNarrative = document.getElementById("auto-narrative");
  const autoInsightGrid = document.getElementById("auto-insights");
  const autoForecast = document.getElementById("auto-forecast");
  const autoScoreRing = autopilotPage ? autopilotPage.querySelector(".score-ring-progress") : null;

  const activeSearchParams = new URLSearchParams(window.location.search);
  const initialSessionFromUrl = activeSearchParams.get("session_id");
  if (initialSessionFromUrl) {
    state.activeSessionId = initialSessionFromUrl;
  }
  if (coachSessionInput && coachSessionInput.value) {
    state.activeSessionId = coachSessionInput.value;
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatMessageText(text) {
    return escapeHtml(text).replace(/\n/g, "<br>");
  }

  function formatMetaLabel(session, fallbackLabel) {
    if (!session) {
      return fallbackLabel;
    }
    return session.session_title || fallbackLabel;
  }

  function scrollToBottom(container) {
    if (!container) {
      return;
    }
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }

  function setWidgetOpen(open) {
    if (!widget) {
      return;
    }
    widget.classList.toggle("open", open);
    widget.setAttribute("aria-hidden", open ? "false" : "true");
    if (open && widgetInput) {
      widgetInput.focus({ preventScroll: true });
    }
  }

  function createBubble({ role, text, createdAt, label, pending = false }) {
    const article = document.createElement("article");
    article.className = `wellness-message ${role}${pending ? " typing" : ""}`;

    const meta = document.createElement("div");
    meta.className = "chat-meta";

    const strong = document.createElement("strong");
    strong.textContent = label || (role === "assistant" ? "Coach" : "You");

    const time = document.createElement("span");
    time.textContent = createdAt || "";

    meta.appendChild(strong);
    meta.appendChild(time);

    const paragraph = document.createElement("p");
    if (pending) {
      const dots = document.createElement("span");
      dots.className = "typing-dots";
      dots.innerHTML = "<span></span><span></span><span></span>";
      paragraph.appendChild(dots);
    } else {
      paragraph.innerHTML = formatMessageText(text);
    }

    article.appendChild(meta);
    article.appendChild(paragraph);
    return article;
  }

  function renderMessageStream(container, messages, userLabel) {
    if (!container) {
      return;
    }

    container.innerHTML = "";
    if (!messages || messages.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.innerHTML = "<h3>Start the conversation</h3><p>Tell the coach what you want help with, such as sleep, exercise, habits, or recovery planning.</p>";
      container.appendChild(empty);
      return;
    }

    messages.forEach((message) => {
      const isAssistant = message.sender_type === "assistant" || message.role === "assistant";
      container.appendChild(
        createBubble({
          role: isAssistant ? "assistant" : "user",
          text: message.message_text || message.text || "",
          createdAt: message.created_at || message.timestamp || "",
          label: isAssistant ? "Coach" : (userLabel || "You"),
        })
      );
    });

    scrollToBottom(container);
  }

  function renderSnapshot(snapshot) {
    if (!widgetSnapshot) {
      return;
    }

    if (!snapshot) {
      widgetSnapshot.innerHTML = '<span class="small-muted">No wellness context found yet.</span>';
      return;
    }

    const cards = [];
    const latestScore = snapshot.latest_score || null;
    const latestPlan = snapshot.latest_plan || null;
    const latestReport = snapshot.latest_report || null;

    if (latestScore) {
      cards.push(`
        <div class="wellness-snapshot-card">
          <span>Latest score</span>
          <strong>${latestScore.total_score ?? "--"}</strong>
        </div>
      `);
      if (latestScore.explanation_summary) {
        cards.push(`
          <div class="wellness-snapshot-card">
            <span>Signal</span>
            <strong style="font-size: 0.98rem; line-height: 1.45;">${escapeHtml(latestScore.explanation_summary)}</strong>
          </div>
        `);
      }
    }

    if (latestPlan) {
      const targetText = [
        latestPlan.sleep_target_hours ? `${latestPlan.sleep_target_hours}h sleep` : null,
        latestPlan.water_target_liters ? `${latestPlan.water_target_liters}L water` : null,
        latestPlan.exercise_target_minutes ? `${latestPlan.exercise_target_minutes}m activity` : null,
      ].filter(Boolean).join(" • ");
      cards.push(`
        <div class="wellness-snapshot-card">
          <span>Today's plan</span>
          <strong style="font-size: 0.98rem; line-height: 1.45;">${escapeHtml(targetText || latestPlan.motivational_note || "Plan ready")}</strong>
        </div>
      `);
    }

    if (latestReport) {
      cards.push(`
        <div class="wellness-snapshot-card">
          <span>Latest report</span>
          <strong>${escapeHtml(String(latestReport.metric_count ?? 0))} metric(s)</strong>
        </div>
      `);
    }

    if (snapshot.focus_habit) {
      cards.push(`
        <div class="wellness-snapshot-card">
          <span>Focus habit</span>
          <strong style="font-size: 0.98rem; line-height: 1.45;">${escapeHtml(snapshot.focus_habit)}</strong>
        </div>
      `);
    }

    widgetSnapshot.innerHTML = `
      <div class="wellness-snapshot-grid">
        ${cards.join("") || '<div class="wellness-snapshot-card"><span>Context</span><strong>No data yet</strong></div>'}
      </div>
    `;
  }

  function setSessionId(sessionId) {
    state.activeSessionId = sessionId ? String(sessionId) : null;
    if (widgetSessionInput) {
      widgetSessionInput.value = state.activeSessionId || "";
    }
    if (coachSessionInput) {
      coachSessionInput.value = state.activeSessionId || "";
    }
  }

  function updateSessionHighlight(sessionId) {
    if (!coachSessionList) {
      return;
    }
    const items = coachSessionList.querySelectorAll("[data-session-id]");
    items.forEach((item) => {
      item.classList.toggle("active", String(item.dataset.sessionId) === String(sessionId));
    });
  }

  function updateThreadTitle(session) {
    if (!coachThreadTitle || !session) {
      return;
    }
    coachThreadTitle.textContent = formatMetaLabel(session, "Wellness Coach");
  }

  function renderSessionList(sessions) {
    if (!coachSessionList || !Array.isArray(sessions)) {
      return;
    }

    coachSessionList.innerHTML = "";
    sessions.forEach((session) => {
      const anchor = document.createElement("a");
      anchor.className = "session-item";
      if (String(session.id) === String(state.activeSessionId)) {
        anchor.classList.add("active");
      }
      anchor.href = `/coach?session_id=${encodeURIComponent(session.id)}`;
      anchor.dataset.sessionId = session.id;

      const title = document.createElement("strong");
      title.textContent = session.session_title || "Wellness Coach";

      const count = document.createElement("span");
      count.textContent = `${session.message_count || 0} message(s)`;

      anchor.appendChild(title);
      anchor.appendChild(count);

      if (session.last_message_at) {
        const updated = document.createElement("small");
        updated.textContent = `Updated ${session.last_message_at}`;
        anchor.appendChild(updated);
      }

      coachSessionList.appendChild(anchor);
    });
  }

  function syncUrlSession(sessionId) {
    const url = new URL(window.location.href);
    if (sessionId) {
      url.searchParams.set("session_id", sessionId);
    } else {
      url.searchParams.delete("session_id");
    }
    window.history.replaceState({}, "", url);
  }

  function setFormBusy(form, busy) {
    if (!form) {
      return;
    }
    const button = form.querySelector('button[type="submit"]');
    const textarea = form.querySelector("textarea");
    form.classList.toggle("is-busy", busy);
    if (button) {
      button.disabled = busy;
      button.textContent = busy ? "Sending..." : "Send";
    }
    if (textarea) {
      textarea.disabled = busy;
    }
  }

  function appendTyping(container) {
    const bubble = createBubble({
      role: "assistant",
      text: "",
      label: "Coach",
      pending: true,
      createdAt: "",
    });
    container.appendChild(bubble);
    scrollToBottom(container);
    return bubble;
  }

  async function fetchBootstrap(sessionId) {
    const url = new URL("/api/coach/bootstrap", window.location.origin);
    if (sessionId) {
      url.searchParams.set("session_id", sessionId);
    }
    const response = await fetch(url.toString(), {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error("Unable to load coach context.");
    }
    return response.json();
  }

  async function loadSession(sessionId, options = {}) {
    const data = await fetchBootstrap(sessionId);
    setSessionId(data.active_session && data.active_session.id);
    updateSessionHighlight(state.activeSessionId);
    updateThreadTitle(data.active_session);
    renderSessionList(data.sessions);
    renderSnapshot(data.snapshot);
    renderMessageStream(widgetMessages, data.messages, "You");
    renderMessageStream(coachChatLog, data.messages, document.body.dataset.userName || "You");

    if (options.pushHistory !== false) {
      syncUrlSession(state.activeSessionId);
    }

    state.bootstrapLoaded = true;
    return data;
  }

  async function sendMessage({ form, input, container }) {
    const messageText = (input && input.value || "").trim();
    if (!messageText || state.isBusy) {
      return;
    }

    if (!state.activeSessionId && state.bootstrapLoaded === false) {
      try {
        await initialLoadPromise;
      } catch (error) {
        // handled below when the send request is attempted
      }
    }

    if (!state.activeSessionId) {
      return;
    }

    const userLabel = document.body.dataset.userName || "You";
    const normalizedForm = form || null;
    const targetContainer = container || widgetMessages || coachChatLog;
    const emptyState = targetContainer ? targetContainer.querySelector(".empty-state") : null;
    if (emptyState) {
      emptyState.remove();
    }
    const typingBubble = appendTyping(targetContainer);
    const timestamp = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

    targetContainer.insertBefore(
      createBubble({
        role: "user",
        text: messageText,
        label: userLabel,
        createdAt: timestamp,
      }),
      typingBubble
    );

    input.value = "";
    scrollToBottom(targetContainer);
    state.isBusy = true;
    setFormBusy(normalizedForm, true);

    try {
      const response = await fetch("/api/coach/message/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/plain",
        },
        credentials: "same-origin",
        body: JSON.stringify({
          session_id: state.activeSessionId,
          message_text: messageText,
        }),
      });

      if (!response.ok) {
        let errorMessage = "Failed to send message.";
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const errorData = await response.json();
          errorMessage = errorData.error || errorMessage;
        } else {
          errorMessage = (await response.text()) || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const assistantParagraph = typingBubble.querySelector("p");
      const reader = response.body && response.body.getReader ? response.body.getReader() : null;
      const decoder = new TextDecoder();
      let streamedText = "";
      let firstChunk = true;

      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            break;
          }
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) {
            continue;
          }
          streamedText += chunk;
          if (firstChunk) {
            typingBubble.classList.remove("typing");
            firstChunk = false;
          }
          if (assistantParagraph) {
            assistantParagraph.innerHTML = formatMessageText(streamedText);
            scrollToBottom(targetContainer);
          }
        }
      } else {
        streamedText = await response.text();
        if (assistantParagraph) {
          typingBubble.classList.remove("typing");
          assistantParagraph.innerHTML = formatMessageText(streamedText);
        }
      }

      if (!streamedText.trim()) {
        if (assistantParagraph) {
          assistantParagraph.innerHTML = formatMessageText("I couldn't generate a response just now.");
        }
      }

      try {
        await loadSession(state.activeSessionId, { pushHistory: false });
      } catch (refreshError) {
        // Keep the live stream visible even if the refresh snapshot fails.
      }
    } catch (error) {
      if (typingBubble && typingBubble.parentNode) {
        typingBubble.remove();
      }
      const errorBubble = document.createElement("div");
      errorBubble.className = "message error";
      errorBubble.textContent = error.message || "Something went wrong while sending the message.";
      targetContainer.prepend(errorBubble);
      scrollToBottom(targetContainer);
    } finally {
      state.isBusy = false;
      setFormBusy(normalizedForm, false);
      if (input) {
        input.focus();
      }
    }
  }

  async function createNewSession() {
    if (state.isBusy) {
      return;
    }

    state.isBusy = true;
    try {
      const response = await fetch("/api/coach/new-session", {
        method: "POST",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to start a new session.");
      }

      setSessionId(data.active_session && data.active_session.id);
      updateSessionHighlight(state.activeSessionId);
      updateThreadTitle(data.active_session);
      renderSessionList(data.sessions);
      renderSnapshot(data.snapshot);
      renderMessageStream(widgetMessages, data.messages, "You");
      renderMessageStream(coachChatLog, data.messages, document.body.dataset.userName || "You");
      syncUrlSession(state.activeSessionId);
      if (widgetInput) {
        widgetInput.value = "";
      }
      if (coachInput) {
        coachInput.value = "";
      }
    } catch (error) {
      const container = widgetMessages || coachChatLog;
      if (container) {
        const message = document.createElement("div");
        message.className = "message error";
        message.textContent = error.message || "Unable to start a new chat session.";
        container.prepend(message);
      }
    } finally {
      state.isBusy = false;
    }
  }

  function wireForm(form, input, container) {
    if (!form || !input) {
      return;
    }
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      sendMessage({ form, input, container });
    });
  }

  function setupComposer(input, form, container) {
    if (!input) {
      return;
    }

    const autoResize = () => {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
    };

    input.addEventListener("input", autoResize);
    input.addEventListener("focus", autoResize);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (form) {
          sendMessage({ form, input, container });
        }
      }
      if (event.key === "Escape") {
        input.blur();
      }
    });
    autoResize();
  }

  function getAutopilotControls() {
    const payload = window.__autopilotPayload || {};
    const controls = {
      time_budget_minutes: 15,
      energy_level: "medium",
      mode: "optimize",
    };
    document.querySelectorAll("[data-auto-control]").forEach((input) => {
      const key = input.dataset.autoControl;
      const numericValue = Number(input.value);
      controls[key] = Number.isNaN(numericValue) ? input.value : numericValue;
    });
    const activeMode = autopilotPage ? autopilotPage.querySelector(".autopilot-mode.active") : null;
    const activeEnergy = autopilotPage ? autopilotPage.querySelector(".autopilot-energy.active") : null;
    controls.mode = activeMode ? (activeMode.dataset.autoMode || controls.mode) : controls.mode;
    controls.energy_level = activeEnergy ? (activeEnergy.dataset.autoEnergy || controls.energy_level) : controls.energy_level;
    return controls;
  }

  function updateAutopilotValueLabels() {
    document.querySelectorAll("[data-auto-control]").forEach((input) => {
      const key = input.dataset.autoControl;
      const label = document.querySelector(`[data-auto-value="${key}"]`);
      if (!label) {
        return;
      }
      label.textContent = `${Math.round(Number(input.value) || 0)} min`;
    });
  }

  function renderAutopilotForecast(forecast) {
    if (!autoForecast || !Array.isArray(forecast)) {
      return;
    }
    autoForecast.innerHTML = forecast.map((point) => `
      <div class="autopilot-forecast-row">
        <span class="autopilot-forecast-label">${escapeHtml(point.label || "")}</span>
        <div class="autopilot-forecast-bars">
          <div class="autopilot-forecast-line baseline">
            <span>Baseline</span>
            <strong>${Math.round(Number(point.baseline) || 0)}</strong>
          </div>
          <div class="autopilot-forecast-line action">
            <span>Do it</span>
            <strong>${Math.round(Number(point.after_action) || 0)}</strong>
          </div>
          <div class="autopilot-forecast-line skip">
            <span>Skip it</span>
            <strong>${Math.round(Number(point.after_skip) || 0)}</strong>
          </div>
        </div>
      </div>
    `).join("");
  }

  function renderAutopilot(payload) {
    if (!payload) {
      return;
    }
    if (!payload.is_ready || !payload.plan) {
      if (autoStatus) {
        autoStatus.textContent = payload.lock_message || "Locked until 7 days of tracking";
      }
      if (autoConfidence) autoConfidence.textContent = "Locked";
      if (autoTimeBudget) autoTimeBudget.textContent = `${Math.round(Number(payload.controls?.time_budget_minutes) || 0)} min`;
      if (autoPriority) autoPriority.textContent = "Locked";
      if (autoPriority2) autoPriority2.textContent = "Locked";
      if (autoScore) autoScore.textContent = "--";
      if (autoCurrentScore) autoCurrentScore.textContent = Math.round(Number(payload.snapshot?.latest_score?.total_score) || 0).toString();
      if (autoLift) autoLift.textContent = "Locked";
      if (autoExpectedLift) autoExpectedLift.textContent = "Locked";
      if (autoTimeNeeded) autoTimeNeeded.textContent = "--";
      if (autoAfterScore) autoAfterScore.textContent = "--";
      if (autoActionTitle) autoActionTitle.textContent = "Locked until baseline is ready";
      if (autoDoNot) autoDoNot.textContent = "Locked";
      if (autoPayoff) autoPayoff.textContent = "Locked";
      if (autoContract) autoContract.textContent = "Locked";
      if (autoWhyNow) autoWhyNow.textContent = payload.reasoning?.why_now || "";
      if (autoWhyThis) autoWhyThis.textContent = payload.reasoning?.why_this || "";
      if (autoWhyNot) autoWhyNot.textContent = payload.reasoning?.why_not_other_things || "";
      if (autoNarrative) autoNarrative.textContent = payload.narrative || "Keep tracking to unlock Autopilot.";
      if (autoScoreRing) {
        autoScoreRing.setAttribute("stroke-dashoffset", "314.16");
      }
      if (autoInsightGrid) {
        autoInsightGrid.innerHTML = `
          <div class="autopilot-insight-card">
            <span>Locked</span>
            <strong>Complete 7 days of tracking to unlock Autopilot.</strong>
          </div>
        `;
      }
      if (autoForecast) {
        autoForecast.innerHTML = `<div class="autopilot-locked-curve"><p>The counterfactual forecast appears after the baseline is complete.</p></div>`;
      }
      return;
    }
    const plan = payload.plan;
    if (autoStatus) autoStatus.textContent = "Autopilot updated";
    if (autoConfidence) autoConfidence.textContent = `${Math.round(Number(payload.confidence) || 0)}%`;
    if (autoTimeBudget) autoTimeBudget.textContent = `${Math.round(Number(payload.controls?.time_budget_minutes) || 0)} min`;
    if (autoPriority) autoPriority.textContent = payload.priority?.label || "Unknown";
    if (autoPriority2) autoPriority2.textContent = payload.priority?.label || "Unknown";
    if (autoScore) autoScore.textContent = Math.round(Number(plan.projected_score) || 0).toString();
    if (autoCurrentScore) autoCurrentScore.textContent = Math.round(Number(payload.snapshot?.latest_score?.total_score) || 0).toString();
    if (autoLift) autoLift.textContent = `+${(Number(plan.expected_lift) || 0).toFixed(1)}`;
    if (autoExpectedLift) autoExpectedLift.textContent = `+${(Number(plan.expected_lift) || 0).toFixed(1)}`;
    if (autoTimeNeeded) autoTimeNeeded.textContent = `${Math.round(Number(plan.time_budget_minutes) || 0)} min`;
    if (autoAfterScore) autoAfterScore.textContent = Math.round(Number(plan.projected_score) || 0).toString();
    if (autoActionTitle) autoActionTitle.textContent = plan.action_title || "Autopilot";
    if (autoDoNot) autoDoNot.textContent = plan.do_not || "";
    if (autoPayoff) autoPayoff.textContent = plan.payoff || "";
    if (autoContract) autoContract.textContent = plan.micro_contract || "";
    if (autoWhyNow) autoWhyNow.textContent = payload.reasoning?.why_now || "";
    if (autoWhyThis) autoWhyThis.textContent = payload.reasoning?.why_this || "";
    if (autoWhyNot) autoWhyNot.textContent = payload.reasoning?.why_not_other_things || "";
    if (autoNarrative) autoNarrative.textContent = payload.narrative || "";
    if (autoScoreRing) {
      const projected = Number(plan.projected_score) || 0;
      const dashOffset = 314.16 * (1 - projected / 100);
      autoScoreRing.setAttribute("stroke-dashoffset", `${dashOffset}`);
    }
    const steps = Array.isArray(plan.action_steps) ? plan.action_steps : [];
    const stepsContainer = document.getElementById("auto-steps");
    if (stepsContainer) {
      stepsContainer.innerHTML = steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
    }
    renderAutopilotForecast(payload.forecast || []);
  }

  let autopilotDebounceTimer = null;
  async function refreshAutopilot() {
    if (!autopilotPage) {
      return;
    }
    if (!window.__autopilotPayload || !window.__autopilotPayload.is_ready) {
      return;
    }
    if (autoStatus) {
      autoStatus.textContent = "Recomputing...";
    }
    try {
      const response = await fetch("/api/wellness-autopilot/refresh", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        credentials: "same-origin",
        body: JSON.stringify(getAutopilotControls()),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to recompute autopilot.");
      }
      window.__autopilotPayload = data;
      renderAutopilot(data);
    } catch (error) {
      if (autoStatus) {
        autoStatus.textContent = error.message || "Autopilot failed";
      }
    }
  }

  function queueAutopilotRefresh() {
    if (!autopilotPage) {
      return;
    }
    if (autopilotDebounceTimer) {
      clearTimeout(autopilotDebounceTimer);
    }
    autopilotDebounceTimer = setTimeout(() => {
      refreshAutopilot();
    }, 220);
  }

  function applyAutopilotMode(mode) {
    if (!autopilotPage) {
      return;
    }
    autopilotPage.querySelectorAll(".autopilot-mode").forEach((button) => {
      button.classList.toggle("active", button.dataset.autoMode === mode);
    });
    queueAutopilotRefresh();
  }

  function applyAutopilotEnergy(energy) {
    if (!autopilotPage) {
      return;
    }
    autopilotPage.querySelectorAll(".autopilot-energy").forEach((button) => {
      button.classList.toggle("active", button.dataset.autoEnergy === energy);
    });
    queueAutopilotRefresh();
  }

  function getTwinControls() {
    const controls = {};
    document.querySelectorAll("[data-twin-control]").forEach((input) => {
      const key = input.dataset.twinControl;
      if (!key) {
        return;
      }
      const numericValue = Number(input.value);
      controls[key] = Number.isNaN(numericValue) ? input.value : numericValue;
    });
    const activePreset = twinLab ? twinLab.querySelector(".twin-preset.active") : null;
    controls.mode = activePreset ? (activePreset.dataset.twinPreset || "stability") : "stability";
    return controls;
  }

  function updateTwinValueLabels() {
    document.querySelectorAll("[data-twin-control]").forEach((input) => {
      const key = input.dataset.twinControl;
      const label = document.querySelector(`[data-twin-value="${key}"]`);
      if (!label) {
        return;
      }
      const value = input.value;
      label.textContent = key === "habit_completion_pct" ? `${Math.round(Number(value))}%` : value;
    });
  }

  function renderTwinInsights(simulation) {
    if (!twinInsightGrid || !simulation) {
      return;
    }
    const positiveCards = (simulation.opportunities || []).map((text) => `
      <div class="twin-insight-card positive">
        <span>Opportunity</span>
        <strong>${escapeHtml(text)}</strong>
      </div>
    `);
    const riskCards = (simulation.risk_notes || []).map((text) => `
      <div class="twin-insight-card warning">
        <span>Risk</span>
        <strong>${escapeHtml(text)}</strong>
      </div>
    `);
    twinInsightGrid.innerHTML = [...positiveCards, ...riskCards].join("")
      || '<div class="twin-insight-card"><span>Insight</span><strong>No insights available yet.</strong></div>';
  }

  function renderTwinForecast(forecast) {
    if (!twinForecast || !Array.isArray(forecast)) {
      return;
    }
    twinForecast.innerHTML = forecast.map((point) => `
      <div class="twin-forecast-row">
        <span class="twin-forecast-label">${escapeHtml(point.label || `Day ${point.day || ""}`)}</span>
        <div class="twin-forecast-bar">
          <div class="twin-forecast-fill" style="width:${Math.max(0, Math.min(100, Number(point.projected_score) || 0))}%;"></div>
        </div>
        <strong>${Math.round(Number(point.projected_score) || 0)}</strong>
      </div>
    `).join("");
  }

  function renderTwinSimulation(payload) {
    if (!payload) {
      return;
    }
    if (!payload.is_ready || !payload.simulation) {
      if (twinStatus) {
        twinStatus.textContent = payload.lock_message || "Locked until 7 days of tracking";
      }
      if (twinConfidenceLabel) {
        twinConfidenceLabel.textContent = "Locked";
      }
      if (twinProjectScore) {
        twinProjectScore.textContent = "--";
      }
      if (twinBaselineScore) {
        twinBaselineScore.textContent = "--";
      }
      if (twinScoreDelta) {
        twinScoreDelta.textContent = "Locked";
      }
      if (twinCurrentScore) {
        twinCurrentScore.textContent = "--";
      }
      if (twinScoreTarget) {
        twinScoreTarget.textContent = "--";
      }
      if (twinScoreChange) {
        twinScoreChange.textContent = "Locked";
      }
      if (twinBestLever) {
        twinBestLever.textContent = "Locked";
      }
      if (twinNarrative) {
        twinNarrative.textContent = payload.lock_message || "Keep tracking to unlock the twin.";
      }
      if (twinInsightGrid) {
        twinInsightGrid.innerHTML = `
          <div class="twin-insight-card warning">
            <span>Locked</span>
            <strong>Complete 7 days of tracking to unlock the twin.</strong>
          </div>
        `;
      }
      if (twinForecast) {
        twinForecast.innerHTML = `<div class="twin-locked-curve"><p>The forecast curve will appear after a full week of logs.</p></div>`;
      }
      return;
    }
    const simulation = payload.simulation;
    if (twinStatus) {
      twinStatus.textContent = "Twin updated";
    }
    if (twinConfidenceLabel) {
      twinConfidenceLabel.textContent = `${Math.round(Number(simulation.confidence) || 0)}%`;
    }
    if (twinProjectScore) {
      twinProjectScore.textContent = Math.round(Number(simulation.projected?.total_score) || 0).toString();
    }
    if (twinBaselineScore) {
      twinBaselineScore.textContent = Math.round(Number(simulation.baseline?.total_score) || 0).toString();
    }
    if (twinScoreDelta) {
      const delta = Number(simulation.delta?.total_score) || 0;
      twinScoreDelta.textContent = `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
    }
    if (twinCurrentScore) {
      twinCurrentScore.textContent = Math.round(Number(simulation.baseline?.total_score) || 0).toString();
    }
    if (twinScoreTarget) {
      twinScoreTarget.textContent = Math.round(Number(simulation.projected?.total_score) || 0).toString();
    }
    if (twinScoreChange) {
      const delta = Number(simulation.delta?.total_score) || 0;
      twinScoreChange.textContent = `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
    }
    if (twinBestLever) {
      twinBestLever.textContent = simulation.best_lever?.title || "Unknown";
    }
    if (twinNarrative) {
      twinNarrative.textContent = simulation.narrative || "The twin is thinking through your data.";
    }
    if (twinScoreRing) {
      const projected = Number(simulation.projected?.total_score) || 0;
      const dashOffset = 314.16 * (1 - projected / 100);
      twinScoreRing.setAttribute("stroke-dashoffset", `${dashOffset}`);
    }
    renderTwinInsights(simulation);
    renderTwinForecast(simulation.forecast || []);
  }

  let twinDebounceTimer = null;
  async function simulateTwinScenario() {
    if (!twinLab) {
      return;
    }
    if (!window.__twinPayload || !window.__twinPayload.is_ready) {
      return;
    }

    const status = twinStatus;
    const payload = getTwinControls();
    if (status) {
      status.textContent = "Simulating...";
    }

    try {
      const response = await fetch("/api/wellness-twin/simulate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to simulate your wellness twin.");
      }
      renderTwinSimulation(data);
    } catch (error) {
      if (status) {
        status.textContent = error.message || "Simulation failed";
      }
    }
  }

  function queueTwinSimulation() {
    if (!twinLab) {
      return;
    }
    if (twinDebounceTimer) {
      clearTimeout(twinDebounceTimer);
    }
    twinDebounceTimer = setTimeout(() => {
      simulateTwinScenario();
    }, 260);
  }

  function applyTwinPreset(presetName) {
    if (!twinLab) {
      return;
    }
    const payload = window.__twinPayload || {};
    const base = (payload.controls || {});
    const goals = ((payload.snapshot || {}).goals || {});
    const preset = (presetName || "stability").toLowerCase();

    const nextValues = {
      sleep_hours: base.sleep_hours,
      water_liters: base.water_liters,
      steps_count: base.steps_count,
      exercise_minutes: base.exercise_minutes,
      stress_minutes: base.stress_minutes,
      habit_completion_pct: base.habit_completion_pct,
    };

    if (preset === "recovery") {
      nextValues.sleep_hours = Math.min(10, (goals.sleep_goal_hours || nextValues.sleep_hours) + 0.5);
      nextValues.water_liters = Math.min(5, (goals.water_goal_liters || nextValues.water_liters) + 0.4);
      nextValues.steps_count = Math.max(2000, (goals.steps_goal || nextValues.steps_count) - 2000);
      nextValues.exercise_minutes = Math.max(0, (goals.exercise_goal_minutes || nextValues.exercise_minutes) - 10);
      nextValues.stress_minutes = 25;
      nextValues.habit_completion_pct = 80;
    } else if (preset === "momentum") {
      nextValues.sleep_hours = Math.min(10, (goals.sleep_goal_hours || nextValues.sleep_hours) + 0.25);
      nextValues.water_liters = Math.min(5, (goals.water_goal_liters || nextValues.water_liters) + 0.2);
      nextValues.steps_count = Math.min(15000, (goals.steps_goal || nextValues.steps_count) + 2000);
      nextValues.exercise_minutes = Math.min(90, (goals.exercise_goal_minutes || nextValues.exercise_minutes) + 10);
      nextValues.stress_minutes = 10;
      nextValues.habit_completion_pct = 90;
    } else if (preset === "performance") {
      nextValues.sleep_hours = Math.min(10, (goals.sleep_goal_hours || nextValues.sleep_hours) + 0.5);
      nextValues.water_liters = Math.min(5, (goals.water_goal_liters || nextValues.water_liters) + 0.2);
      nextValues.steps_count = Math.min(15000, (goals.steps_goal || nextValues.steps_count) + 3500);
      nextValues.exercise_minutes = Math.min(90, (goals.exercise_goal_minutes || nextValues.exercise_minutes) + 15);
      nextValues.stress_minutes = 5;
      nextValues.habit_completion_pct = 95;
    }

    document.querySelectorAll("[data-twin-control]").forEach((input) => {
      const key = input.dataset.twinControl;
      if (Object.prototype.hasOwnProperty.call(nextValues, key)) {
        input.value = nextValues[key];
      }
    });

    twinLab.querySelectorAll(".twin-preset").forEach((button) => {
      button.classList.toggle("active", button.dataset.twinPreset === preset);
    });

    updateTwinValueLabels();
    queueTwinSimulation();
  }

  function fillPrompt(prompt) {
    const target = coachInput || widgetInput;
    if (!target) {
      return;
    }
    target.value = prompt;
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.focus();
  }

  if (widgetFab) {
    widgetFab.addEventListener("click", () => setWidgetOpen(!widget || !widget.classList.contains("open")));
  }

  if (widgetClose) {
    widgetClose.addEventListener("click", () => setWidgetOpen(false));
  }

  if (widgetNewSession) {
    widgetNewSession.addEventListener("click", () => createNewSession());
  }

  if (coachSessionList) {
    coachSessionList.addEventListener("click", (event) => {
      const anchor = event.target.closest("[data-session-id]");
      if (!anchor) {
        return;
      }
      event.preventDefault();
      const sessionId = anchor.dataset.sessionId;
      if (sessionId) {
        loadSession(sessionId);
      }
    });
  }

  const coachNewSessionForm = document.querySelector(".coach-new-session-form");
  if (coachNewSessionForm) {
    coachNewSessionForm.addEventListener("submit", (event) => {
      event.preventDefault();
      createNewSession();
    });
  }

  document.querySelectorAll("[data-coach-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      fillPrompt(button.dataset.coachPrompt || "");
    });
  });

  if (twinLab) {
    updateTwinValueLabels();
    renderTwinSimulation(window.__twinPayload);

    twinLab.querySelectorAll("[data-twin-control]").forEach((input) => {
      input.addEventListener("input", () => {
        updateTwinValueLabels();
        queueTwinSimulation();
      });
      input.addEventListener("change", () => {
        updateTwinValueLabels();
        queueTwinSimulation();
      });
    });

    twinLab.querySelectorAll("[data-twin-preset]").forEach((button) => {
      button.addEventListener("click", () => {
        applyTwinPreset(button.dataset.twinPreset || "stability");
      });
    });

    if (twinRunButton) {
      twinRunButton.addEventListener("click", () => {
        updateTwinValueLabels();
        simulateTwinScenario();
      });
    }
  }

  if (autopilotPage) {
    updateAutopilotValueLabels();
    renderAutopilot(window.__autopilotPayload);

    autopilotPage.querySelectorAll("[data-auto-control]").forEach((input) => {
      input.addEventListener("input", () => {
        updateAutopilotValueLabels();
        queueAutopilotRefresh();
      });
      input.addEventListener("change", () => {
        updateAutopilotValueLabels();
        queueAutopilotRefresh();
      });
    });

    autopilotPage.querySelectorAll("[data-auto-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        applyAutopilotMode(button.dataset.autoMode || "optimize");
      });
    });

    autopilotPage.querySelectorAll("[data-auto-energy]").forEach((button) => {
      button.addEventListener("click", () => {
        applyAutopilotEnergy(button.dataset.autoEnergy || "medium");
      });
    });

    if (autoRefreshButton) {
      autoRefreshButton.addEventListener("click", () => {
        updateAutopilotValueLabels();
        refreshAutopilot();
      });
    }
  }

  wireForm(widgetForm, widgetInput, widgetMessages);
  wireForm(coachForm, coachInput, coachChatLog);
  setupComposer(widgetInput, widgetForm, widgetMessages);
  setupComposer(coachInput, coachForm, coachChatLog);

  const initialLoadPromise = loadSession(state.activeSessionId || initialSessionFromUrl || null, { pushHistory: false });

  initialLoadPromise.catch(() => {
    // Keep the app usable even if the snapshot API fails.
  });

  // Open the floating coach once the context is ready for fast first interaction.
  if (widget) {
    initialLoadPromise.finally(() => {
      if (window.innerWidth > 900 && state.activeSessionId) {
        setWidgetOpen(false);
      }
    });
  }

  // --- Hamburger menu ---
  const hamburger = document.getElementById('hamburger');
  const navLinks = document.getElementById('nav-links');
  const navOverlay = document.getElementById('nav-overlay');
  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      const open = navLinks.classList.toggle('open');
      hamburger.classList.toggle('open', open);
      if (navOverlay) navOverlay.classList.toggle('open', open);
    });
    if (navOverlay) {
      navOverlay.addEventListener('click', () => {
        navLinks.classList.remove('open');
        hamburger.classList.remove('open');
        navOverlay.classList.remove('open');
      });
    }
  }

  // --- Toast notification system ---
  window.showToast = function(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('out');
      toast.addEventListener('animationend', () => toast.remove());
    }, duration);
  };

  // --- Chart.js dashboard charts ---
  if (window.__scoreHistory && document.getElementById('scoreChart')) {
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
    script.onload = function() {
      const history = window.__scoreHistory.slice().reverse();
      const labels = history.map(h => h.log_date || '');
      const scores = history.map(h => Math.round(h.total_score || 0));
      const sleep = history.map(h => Math.round(h.sleep_score || 0));
      const hydration = history.map(h => Math.round(h.hydration_score || 0));
      const ctx = document.getElementById('scoreChart').getContext('2d');
      new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Total Score',
              data: scores,
              borderColor: '#7cdaff',
              backgroundColor: 'rgba(124,218,255,0.08)',
              fill: true,
              tension: 0.4,
              pointBackgroundColor: '#7cdaff',
              pointRadius: 4,
              borderWidth: 2.5,
            },
            {
              label: 'Sleep',
              data: sleep,
              borderColor: '#8b7dff',
              backgroundColor: 'transparent',
              fill: false,
              tension: 0.4,
              pointRadius: 3,
              borderWidth: 1.5,
              borderDash: [4, 3],
            },
            {
              label: 'Hydration',
              data: hydration,
              borderColor: '#59f0b6',
              backgroundColor: 'transparent',
              fill: false,
              tension: 0.4,
              pointRadius: 3,
              borderWidth: 1.5,
              borderDash: [4, 3],
            },
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: '#a8b4c7', font: { size: 12, weight: '600' }, boxWidth: 14, padding: 16 }
            },
            tooltip: {
              backgroundColor: 'rgba(8,15,27,0.95)',
              borderColor: 'rgba(124,218,255,0.2)',
              borderWidth: 1,
              titleColor: '#eef4ff',
              bodyColor: '#a8b4c7',
              padding: 12,
              cornerRadius: 10,
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#6f819f', font: { size: 11 } }
            },
            y: {
              min: 0, max: 100,
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#6f819f', font: { size: 11 }, stepSize: 20 }
            }
          }
        }
      });
    };
    document.head.appendChild(script);
  }

  // --- Animated number counters ---
  function animateCounters() {
    document.querySelectorAll('[data-count]').forEach(el => {
      const target = parseInt(el.dataset.count, 10);
      if (!target || target === 0) return;
      let current = 0;
      const step = Math.max(1, Math.ceil(target / 40));
      const timer = setInterval(() => {
        current = Math.min(current + step, target);
        el.textContent = current.toLocaleString();
        if (current >= target) clearInterval(timer);
      }, 30);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', animateCounters);
  } else {
    animateCounters();
  }
})();
