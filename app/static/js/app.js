/**
 * ARCHITECT & MAKER — FRONTEND SHELL CLIENT
 * HMC E190 Hardware & Machining Prototyping Assistant
 *
 * Strict Directives:
 * 1. Zero LLM calls on page load (DOMContentLoaded only queries GET /health).
 * 2. Mobile-first accessible interaction, native <dialog> showModal() / close().
 * 3. Zero <div> elements generated dynamically.
 */

(function () {
  "use strict";

  // Cache core DOM elements
  const connectionPill = document.getElementById("connection-pill");
  const connectionText = document.getElementById("connection-status-text");
  const navTabs = document.querySelectorAll(".nav-tab");
  const viewPanels = document.querySelectorAll(".view-panel");
  const roleRadios = document.querySelectorAll('input[name="user-role"]');
  const roleStudentLabel = document.getElementById("label-role-student");
  const roleStewardLabel = document.getElementById("label-role-steward");

  // Subsystems & Copilot Form
  const subsystemBtns = document.querySelectorAll(".subsystem-btn");
  const activeSubsystemBadge = document.getElementById("active-subsystem-badge");
  const btnGenerateSteps = document.getElementById("btn-generate-steps");
  const copilotActionStatus = document.getElementById("copilot-action-status");

  // Safety Modal & Actions
  const safetyModal = document.getElementById("safety-modal");
  const dialogSignoffForm = document.getElementById("dialog-signoff-form");
  const btnDialogClose = document.getElementById("btn-dialog-close");
  const btnDialogCancel = document.getElementById("btn-dialog-cancel");
  const dialogStepTitle = document.getElementById("dialog-step-title");
  const dialogFacilityBadge = document.getElementById("dialog-facility-badge");
  const safetyQueueCount = document.getElementById("safety-queue-count");

  // Steward Queue & Stockroom Filters
  const queueFilterBtns = document.querySelectorAll(".facility-pill");
  const queueItems = document.querySelectorAll(".queue-item");
  const inventorySearch = document.getElementById("inventory-search-input");
  const facilitySelect = document.getElementById("facility-select-dropdown");
  const inventoryItems = document.querySelectorAll(".inventory-item-card");

  let currentPendingStepId = null;

  /* ==========================================================================
     1. ZERO-LLM HEALTH CHECK ON PAGE LOAD
     ========================================================================== */
  async function checkBackendHealth() {
    if (!connectionPill || !connectionText) return;

    try {
      const response = await fetch("/health", {
        method: "GET",
        headers: { Accept: "application/json" },
      });

      if (response.ok) {
        const data = await response.json();
        connectionPill.classList.remove("status-standby", "status-offline");
        connectionPill.classList.add("status-online");
        connectionText.textContent = "ONLINE • POSTGRES OK";
      } else {
        connectionPill.classList.remove("status-standby", "status-online");
        connectionPill.classList.add("status-offline");
        connectionText.textContent = "OFFLINE • STANDALONE";
      }
    } catch (err) {
      connectionPill.classList.remove("status-standby", "status-online");
      connectionPill.classList.add("status-offline");
      connectionText.textContent = "OFFLINE • STANDALONE";
    }
  }

  /* ==========================================================================
     2. TAB NAVIGATION SYSTEM
     ========================================================================== */
  function switchTab(targetTabId) {
    navTabs.forEach((tab) => {
      const isTarget = tab.dataset.tab === targetTabId;
      tab.classList.toggle("active", isTarget);
      tab.setAttribute("aria-selected", isTarget ? "true" : "false");
    });

    viewPanels.forEach((panel) => {
      if (panel.id === targetTabId) {
        panel.removeAttribute("hidden");
        panel.classList.add("active");
      } else {
        panel.setAttribute("hidden", "until-found");
        panel.classList.remove("active");
      }
    });
  }

  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;
      switchTab(targetId);
    });
  });

  /* ==========================================================================
     3. ROLE SWITCHER (STUDENT <-> STEWARD)
     ========================================================================== */
  function handleRoleChange(selectedRole) {
    if (selectedRole === "steward") {
      roleStewardLabel?.classList.add("active");
      roleStudentLabel?.classList.remove("active");
      switchTab("tab-steward");
    } else {
      roleStudentLabel?.classList.add("active");
      roleStewardLabel?.classList.remove("active");
      switchTab("tab-copilot");
    }
  }

  roleRadios.forEach((radio) => {
    radio.addEventListener("change", (e) => {
      handleRoleChange(e.target.value);
    });
  });

  /* ==========================================================================
     4. SUBSYSTEM SWITCHING (TAB 1)
     ========================================================================== */
  subsystemBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      subsystemBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const subsystem = btn.dataset.subsystem.toUpperCase();
      if (activeSubsystemBadge) {
        activeSubsystemBadge.textContent = `[ACTIVE SUBSYSTEM: ${subsystem}]`;
      }
    });
  });

  /* ==========================================================================
     5. PROJECT DECOMPOSITION DISPATCH (EXPLICIT USER ACTION ONLY)
     ========================================================================== */
  if (btnGenerateSteps && copilotActionStatus) {
    btnGenerateSteps.addEventListener("click", () => {
      copilotActionStatus.textContent =
        "Plan decomposed into 3 sequential operations with 1 safety interlock gate.";
      copilotActionStatus.style.borderLeftColor = "#000000";
    });
  }

  /* ==========================================================================
     6. SAFETY SIGN-OFF MODAL DIALOG (<dialog id="safety-modal">)
     ========================================================================== */
  function openSafetyModal(stepId, stepTitle, facility) {
    if (!safetyModal) return;
    currentPendingStepId = stepId;

    if (dialogStepTitle) {
      dialogStepTitle.textContent = stepTitle || "Precision Machining Operation";
    }
    if (dialogFacilityBadge) {
      dialogFacilityBadge.textContent = `[${(facility || "MACHINE_SHOP").toUpperCase()}]`;
    }

    if (typeof safetyModal.showModal === "function") {
      safetyModal.showModal();
    } else {
      safetyModal.setAttribute("open", "true");
    }
  }

  function closeSafetyModal() {
    if (!safetyModal) return;
    if (typeof safetyModal.close === "function") {
      safetyModal.close();
    } else {
      safetyModal.removeAttribute("open");
    }
  }

  btnDialogClose?.addEventListener("click", closeSafetyModal);
  btnDialogCancel?.addEventListener("click", closeSafetyModal);

  // Close dialog on backdrop click
  safetyModal?.addEventListener("click", (event) => {
    if (event.target === safetyModal) {
      closeSafetyModal();
    }
  });

  // Attach modal trigger to student sign-off requests
  document.querySelectorAll(".btn-request-signoff").forEach((btn) => {
    btn.addEventListener("click", () => {
      const stepId = btn.dataset.stepId;
      const stepTitle = btn.dataset.stepTitle;
      const facility = btn.dataset.facility;
      openSafetyModal(stepId, stepTitle, facility);
    });
  });

  // Attach modal trigger to steward approve buttons
  document.querySelectorAll(".btn-steward-approve").forEach((btn) => {
    btn.addEventListener("click", () => {
      const stepId = btn.dataset.stepId;
      const stepTitle = btn.dataset.stepTitle;
      const facility = btn.dataset.facility;
      openSafetyModal(stepId, stepTitle, facility);
    });
  });

  // Steward flag action
  document.querySelectorAll(".btn-steward-flag").forEach((btn) => {
    btn.addEventListener("click", () => {
      const title = btn.dataset.stepTitle || "Operation";
      alert(`Flagged "${title}" for student revision. Inspection notes recorded.`);
    });
  });

  // Confirm sign-off form submission
  dialogSignoffForm?.addEventListener("submit", (e) => {
    e.preventDefault();

    // Mark step 2 cleared in UI
    const step02Badge = document.getElementById("step-02-badge");
    const stepCard02 = document.getElementById("step-card-02");
    if (step02Badge) {
      step02Badge.textContent = "[STATUS: CLEARED BY STEWARD]";
      step02Badge.className = "gate-status-pill pill-cleared";
    }
    if (stepCard02) {
      stepCard02.classList.remove("step-locked");
      stepCard02.classList.add("step-cleared");
    }

    // Unlock downstream step 3
    const step03Badge = document.getElementById("step-03-badge");
    if (step03Badge) {
      step03Badge.textContent = "[STATUS: UNLOCKED & READY FOR PRESS-FIT]";
      step03Badge.className = "gate-status-pill pill-cleared";
    }

    // Decrement queue count
    if (safetyQueueCount) {
      const current = parseInt(safetyQueueCount.textContent, 10) || 1;
      safetyQueueCount.textContent = Math.max(0, current - 1);
    }

    closeSafetyModal();
  });

  /* ==========================================================================
     7. STEWARD QUEUE FACILITY FILTER
     ========================================================================== */
  queueFilterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      queueFilterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const filter = btn.dataset.queueFilter;

      queueItems.forEach((item) => {
        if (filter === "all" || item.dataset.facility === filter) {
          item.style.display = "";
        } else {
          item.style.display = "none";
        }
      });
    });
  });

  /* ==========================================================================
     8. CAMPUS STOCKROOM SEARCH & FACILITY FILTER
     ========================================================================== */
  function filterInventory() {
    const query = (inventorySearch?.value || "").toLowerCase().trim();
    const facility = facilitySelect?.value || "all";

    inventoryItems.forEach((card) => {
      const cardFacility = card.dataset.facility;
      const text = card.textContent.toLowerCase();

      const matchesFacility = facility === "all" || cardFacility === facility;
      const matchesQuery = query === "" || text.includes(query);

      if (matchesFacility && matchesQuery) {
        card.style.display = "";
      } else {
        card.style.display = "none";
      }
    });
  }

  inventorySearch?.addEventListener("input", filterInventory);
  facilitySelect?.addEventListener("change", filterInventory);

  /* ==========================================================================
     9. DOMContentLoaded INITIALIZATION (ZERO LLM CALLS)
     ========================================================================== */
  document.addEventListener("DOMContentLoaded", () => {
    // Only invoke static relational / health endpoint
    checkBackendHealth();
  });
})();
