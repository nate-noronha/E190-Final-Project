/**
 * MAKER. — FRONTEND SHELL CLIENT (WATTS + CHATGPT 3-COLUMN WORKSPACE)
 * HMC E190 Hardware & Machining Prototyping Assistant
 *
 * Strict Directives:
 * 1. Zero LLM calls on page load (DOMContentLoaded only queries GET /health).
 * 2. Mobile-first accessible interaction, native <dialog> showModal() / close().
 * 3. Zero generic container elements generated dynamically (strictly semantic tags).
 * 4. Explicit user actions ONLY trigger POST /api/projects, /generate-steps, and /chat.
 * 5. Honest failure UI with retry capability on simulated or real 502/503/504 errors.
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

  // 3-Column Layout & Drawer Controls
  const projectsSidebar = document.getElementById("projects-sidebar");
  const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
  const btnNewProject = document.getElementById("btn-new-project");
  const btnRefreshProjects = document.getElementById("btn-refresh-projects");
  const projectsHistoryList = document.getElementById("projects-history-list");
  const topbarProjectTitle = document.getElementById("topbar-project-title");

  const rightToolsDrawer = document.getElementById("right-tools-drawer");
  const btnToggleRightDrawer = document.getElementById("btn-toggle-right-drawer");
  const btnCloseRightDrawer = document.getElementById("btn-close-right-drawer");

  const btnViewStream = document.getElementById("btn-view-stream");
  const btnViewBrief = document.getElementById("btn-view-brief");
  const btnToggleBrief = document.getElementById("btn-toggle-brief");
  const btnQuickDecompose = document.getElementById("btn-quick-decompose");
  const welcomeHero = document.getElementById("welcome-hero");
  const starterChips = document.querySelectorAll(".starter-chip");

  // Subsystems & Copilot Form
  const subsystemBtns = document.querySelectorAll(".subsystem-btn");
  const activeSubsystemBadge = document.getElementById("active-subsystem-badge");
  const projectForm = document.getElementById("project-form");
  const projectTitleInput = document.getElementById("project-title-input");
  const projectDescInput = document.getElementById("project-desc-input");
  const btnGenerateSteps = document.getElementById("btn-generate-steps");
  const copilotActionStatus = document.getElementById("copilot-action-status");
  const generationProgress = document.getElementById("generation-progress");
  const generationAlert = document.getElementById("generation-alert");
  const generationAlertTitle = document.getElementById("generation-alert-title");
  const generationAlertMessage = document.getElementById("generation-alert-message");
  const btnRetryGenerate = document.getElementById("btn-retry-generate");

  // Manufacturing Steps & BOM
  const stepsList = document.getElementById("steps-ordered-list");
  const bomTableBody = document.getElementById("bom-table-body");
  const bomCountBadge = document.getElementById("bom-items-count-badge");

  // Chat Section
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const btnSendChat = document.getElementById("btn-send-chat");
  const chatThreadList = document.getElementById("chat-thread-list");
  const chatStatusBadge = document.getElementById("chat-status-badge");
  const chatActionStatus = document.getElementById("chat-action-status");
  const chatProgress = document.getElementById("chat-progress");
  const chatAlertBox = document.getElementById("chat-alert-box");
  const chatAlertTitle = document.getElementById("chat-alert-title");
  const chatAlertMessage = document.getElementById("chat-alert-message");
  const btnRetryChat = document.getElementById("btn-retry-chat");

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
  const inventorySearch = document.getElementById("inventory-search-input");
  const facilitySelect = document.getElementById("facility-select-dropdown");

  // State
  let currentActiveStudentId = null;
  let currentActiveStewardId = null;
  let currentProjectId = null;
  let currentPendingStepId = null;
  let currentSubsystemFilter = "all";
  let cachedSteps = [];
  let chatHistory = [];
  let lastFailedChatPayload = null;

  // Curated Preset Projects for Left Sidebar Switching (Zero LLM calls)
  const PRESET_PROJECTS = {
    "solar-tracker": {
      title: "Dual-Axis Solar Tracker Gimbal Assembly",
      description:
        "Machined 6061-T6 aluminum yoke with ±0.05 mm bearing bores, Bridgeport keyway slotting, 3D printed PETG optical sensor shroud, and dual NEMA 17 stepper drives with TMC2209 silent step sticks.",
      steps: [
        {
          id: "01",
          step_order: 1,
          subsystem: "mechanical",
          title: "Stock Preparation & Facing on Clausing Lathe",
          instructions:
            'Chuck 2.00" 6061-T6 round bar stock into 3-jaw chuck. Face both ends flat and turn outer diameter down to 48.00 mm ± 0.05 mm over 110 mm length. Apply cutting oil and calibrate dial calipers.',
          facility: "machine_shop",
          requires_steward_signoff: false,
          is_completed: false,
        },
        {
          id: "02",
          step_order: 2,
          subsystem: "mechanical",
          title: "Bridgeport Mill Precision Keyway Slotting",
          instructions:
            "Clamp prepared shaft in milling vise with parallels. End mill 6.00 mm keyway slot at 1200 RPM using 4-flute solid carbide center-cutting end mill. Depth of cut 3.50 mm.",
          facility: "machine_shop",
          requires_steward_signoff: true,
          safety_notes:
            "Risk Level: HIGH. High-speed spindle chips and workpiece deflection risk. A certified shop steward must inspect vise fixturing, parallel seating, and RPM configuration before spindle start.",
          is_completed: false,
        },
        {
          id: "03",
          step_order: 3,
          subsystem: "assembly",
          title: "Bearing Press-Fit with Dake Arbor Press",
          instructions:
            "Clean bearing journals with isopropanol. Apply thin film of Loctite 609 retaining compound. Press dual 608-2RS ball bearings into reamed bores using hand arbor press.",
          facility: "machine_shop",
          requires_steward_signoff: false,
          is_completed: false,
        },
      ],
      bom_items: [
        {
          part_name: '6061-T6 Round Bar 2.0" OD',
          subsystem: "mechanical",
          quantity_needed: 1,
          source_status: "in_stock_on_campus",
          facility: "machine_shop",
        },
        {
          part_name: "TMC2209 SilentStepStick Driver",
          subsystem: "electrical",
          quantity_needed: 2,
          source_status: "in_stock_on_campus",
          facility: "ee_stockroom",
        },
        {
          part_name: "AS5600 12-Bit Magnetic Rotary Encoder",
          subsystem: "electrical",
          quantity_needed: 1,
          source_status: "external_purchase_needed",
          external_purchase_note: "DigiKey #1568-1248-ND (Lead: 2 Days)",
        },
        {
          part_name: "NEMA 17 Stepper Motor 42x40mm",
          subsystem: "electrical",
          quantity_needed: 2,
          source_status: "in_stock_on_campus",
          facility: "ee_stockroom",
        },
      ],
      assistantWelcome:
        "Loaded Dual-Axis Solar Tracker Gimbal Assembly. OP 02 (Bridgeport Keyway Slotting) requires Steward Safety Sign-off before completion. Ask any question below or open Subsystems & Shop Tools in the top-right.",
    },
    "pendulum-cart": {
      title: "Inverted Pendulum Linear Cart",
      description:
        "Precision turned 303 stainless steel linear shaft, laser-cut Delrin carriage plate, AS5600 magnetic rotary encoder mount, and high-torque NEMA 17 belt drive.",
      steps: [
        {
          id: "101",
          step_order: 1,
          subsystem: "mechanical",
          title: "Turn 303 Stainless Linear Guide Journals on Lathe",
          instructions:
            "Mount 12.00 mm 303 stainless rod in collet chuck. Turn stepped shoulder to 10.00 mm ± 0.02 mm for linear ball bushing fit.",
          facility: "machine_shop",
          requires_steward_signoff: true,
          safety_notes:
            "Risk Level: HIGH. Stainless work-hardening hazard on lathe. Steward must verify collet projection length and spindle RPM <= 900.",
          is_completed: false,
        },
        {
          id: "102",
          step_order: 2,
          subsystem: "electrical",
          title: "Solder TMC2209 Carrier & Encoder Pull-up Bus",
          instructions:
            "Populate ESP32-S3 carrier protoboard at EE Stockroom rework station. Configure I2C 4.7k pull-ups for AS5600 pendulum angle sensor.",
          facility: "ee_stockroom",
          requires_steward_signoff: false,
          is_completed: false,
        },
        {
          id: "103",
          step_order: 3,
          subsystem: "firmware",
          title: "Calibrate 1 kHz State-Space LQR Control Loop",
          instructions:
            "Flash timers on ESP32-S3 for 1000 Hz encoder polling and verify emergency limit-switch cutoff.",
          facility: "ee_stockroom",
          requires_steward_signoff: false,
          is_completed: false,
        },
      ],
      bom_items: [
        {
          part_name: "ESP32-S3 Dual-Core Xtensa MCU Board",
          subsystem: "electrical",
          quantity_needed: 1,
          source_status: "in_stock_on_campus",
          facility: "ee_stockroom",
        },
        {
          part_name: "TMC2209 SilentStepStick Driver",
          subsystem: "electrical",
          quantity_needed: 1,
          source_status: "in_stock_on_campus",
          facility: "ee_stockroom",
        },
      ],
      assistantWelcome:
        "Loaded Inverted Pendulum Linear Cart. Review the 303 Stainless Lathe turning step or ask about LQR control loop timing and belt tensioning.",
    },
    "auv-hull": {
      title: "Autonomous AUV Pressure Hull",
      description:
        "Cast acrylic pressure cylinder with dual O-ring aluminum endcaps bored on Clausing lathe, Boss Laser acrylic internal electronics tray, and anodized bulkhead pass-throughs.",
      steps: [
        {
          id: "201",
          step_order: 1,
          subsystem: "mechanical",
          title: "Boss Laser 60W Internal Acrylic Electronics Tray Cut",
          instructions:
            'Place 1/4" cast acrylic sheet on Makerspace Boss Laser bed. Set air assist ON, exhaust blower HIGH, speed 18 mm/s at 75% power.',
          facility: "makerspace",
          requires_steward_signoff: true,
          safety_notes:
            "Risk Level: HIGH. Combustible acrylic vapor and laser flare-up risk. Steward must verify air assist pressure and optics cleanliness.",
          is_completed: false,
        },
        {
          id: "202",
          step_order: 2,
          subsystem: "mechanical",
          title: "Turn Radial O-Ring Grooves on Aluminum Endcaps",
          instructions:
            "Groove AS568-238 Buna-N O-ring gland to 3.55 mm width x 2.80 mm depth with surface finish Ra <= 0.8 um.",
          facility: "machine_shop",
          requires_steward_signoff: false,
          is_completed: false,
        },
        {
          id: "203",
          step_order: 3,
          subsystem: "assembly",
          title: "Vacuum Leak Test & Silicone Grease Assembly",
          instructions:
            "Apply Dow Corning 111 silicone lubricant to dual O-rings, seat acrylic hull tube, and pull -10 psi vacuum for 30 minutes.",
          facility: "makerspace",
          requires_steward_signoff: false,
          is_completed: false,
        },
      ],
      bom_items: [
        {
          part_name: '1/4" Cast Clear Acrylic Sheet 12"x24"',
          subsystem: "mechanical",
          quantity_needed: 2,
          source_status: "in_stock_on_campus",
          facility: "makerspace",
        },
        {
          part_name: "BlueRobotics WetLink Penetrator M10",
          subsystem: "assembly",
          quantity_needed: 4,
          source_status: "external_purchase_needed",
          external_purchase_note: "BlueRobotics #WLP-M10 (Lead: 3 Days)",
        },
      ],
      assistantWelcome:
        "Loaded Autonomous AUV Pressure Hull. Note that Boss Laser cutting of 1/4\" cast acrylic requires a Makerspace Steward Sign-off.",
    },
  };

  function escapeHtml(str) {
    if (typeof str !== "string") return str == null ? "" : String(str);
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatTime() {
    const d = new Date();
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

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
     2. 3-COLUMN SIDEBARS & RIGHT DRAWER TOGGLES
     ========================================================================== */
  function setRightDrawerOpen(isOpen) {
    if (!rightToolsDrawer) return;
    rightToolsDrawer.classList.toggle("is-collapsed", !isOpen);
    if (btnToggleRightDrawer) {
      btnToggleRightDrawer.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  }

  btnToggleRightDrawer?.addEventListener("click", () => {
    const isCurrentlyCollapsed = rightToolsDrawer?.classList.contains("is-collapsed");
    setRightDrawerOpen(Boolean(isCurrentlyCollapsed));
  });

  btnCloseRightDrawer?.addEventListener("click", () => {
    setRightDrawerOpen(false);
  });

  btnToggleSidebar?.addEventListener("click", () => {
    if (!projectsSidebar) return;
    const isCollapsed = projectsSidebar.classList.toggle("is-collapsed");
    btnToggleSidebar.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
  });

  function setBriefOpen(isOpen) {
    if (!projectForm) return;
    projectForm.classList.toggle("is-collapsed", !isOpen);
    btnToggleBrief?.setAttribute("aria-expanded", isOpen ? "true" : "false");
    btnViewBrief?.classList.toggle("active", isOpen);
    btnViewStream?.classList.toggle("active", !isOpen);
  }

  btnToggleBrief?.addEventListener("click", () => {
    const isCurrentlyCollapsed = projectForm?.classList.contains("is-collapsed");
    setBriefOpen(Boolean(isCurrentlyCollapsed));
  });

  btnViewBrief?.addEventListener("click", () => {
    setBriefOpen(true);
    projectForm?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  btnViewStream?.addEventListener("click", () => {
    setBriefOpen(false);
  });

  // Starter Chips in Watts Welcome Hero
  starterChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const title = chip.dataset.starterTitle || "";
      const desc = chip.dataset.starterDesc || "";
      if (projectTitleInput && title) projectTitleInput.value = title;
      if (projectDescInput && desc) projectDescInput.value = desc;
      if (topbarProjectTitle && title) topbarProjectTitle.textContent = title;
      if (chatInput) {
        chatInput.value = `${title}: ${desc}`;
        chatInput.focus();
      }
    });
  });

  /* ==========================================================================
     3. LEFT SIDEBAR PROJECTS LIST & SELECTION
     ========================================================================== */
  function markActiveProjectInSidebar(selectorAttr, selectorVal) {
    if (!projectsHistoryList) return;
    const items = projectsHistoryList.querySelectorAll(".project-nav-item");
    items.forEach((li) => {
      const matches = li.getAttribute(selectorAttr) === String(selectorVal);
      li.classList.toggle("active", matches);
    });
  }

  function loadPresetProject(presetKey) {
    const preset = PRESET_PROJECTS[presetKey];
    if (!preset) return;

    currentProjectId = null;
    markActiveProjectInSidebar("data-project-preset", presetKey);

    if (topbarProjectTitle) topbarProjectTitle.textContent = preset.title;
    if (projectTitleInput) projectTitleInput.value = preset.title;
    if (projectDescInput) projectDescInput.value = preset.description;

    renderGeneratedSteps(preset.steps);
    renderBOMTable(preset.bom_items);

    chatHistory = [];
    if (chatThreadList) {
      chatThreadList.innerHTML = "";
      appendChatMessage("model", preset.assistantWelcome);
    }
  }

  async function loadDatabaseProject(projectId) {
    try {
      const res = await fetch(`/api/projects/${projectId}`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return;
      const proj = await res.json();
      currentProjectId = proj.id;
      markActiveProjectInSidebar("data-project-id", String(proj.id));

      if (topbarProjectTitle) topbarProjectTitle.textContent = proj.title;
      if (projectTitleInput) projectTitleInput.value = proj.title;
      if (projectDescInput) projectDescInput.value = proj.description;

      renderGeneratedSteps(proj.steps || []);
      renderBOMTable(proj.bom_items || []);

      chatHistory = [];
      if (chatThreadList) {
        chatThreadList.innerHTML = "";
        appendChatMessage(
          "model",
          `Loaded project "${proj.title}" (#${proj.id}) with ${(proj.steps || []).length} manufacturing operations.`
        );
      }
    } catch (err) {
      console.warn("Could not load project:", err);
    }
  }

  function upsertProjectInSidebar(project) {
    if (!projectsHistoryList || !project || !project.id) return;
    let existing = projectsHistoryList.querySelector(
      `.project-nav-item[data-project-id="${project.id}"]`
    );
    const stepCount = Array.isArray(project.steps) ? project.steps.length : 0;

    if (!existing) {
      existing = document.createElement("li");
      existing.className = "project-nav-item";
      existing.setAttribute("data-project-id", String(project.id));
      projectsHistoryList.prepend(existing);
    }

    existing.innerHTML = `
      <button type="button" class="project-select-btn" data-db-project-id="${escapeHtml(String(project.id))}">
        <span class="project-item-title">${escapeHtml(project.title)}</span>
        <span class="project-item-meta"><kbd>${stepCount} OPS</kbd> &bull; SAVED BUILD</span>
      </button>
    `;

    markActiveProjectInSidebar("data-project-id", String(project.id));
  }

  projectsHistoryList?.addEventListener("click", (e) => {
    const btn = e.target.closest(".project-select-btn");
    if (!btn) return;

    const presetKey = btn.dataset.presetKey;
    const dbProjectId = btn.dataset.dbProjectId;
    if (presetKey) {
      loadPresetProject(presetKey);
    } else if (dbProjectId) {
      loadDatabaseProject(dbProjectId);
    }
  });

  btnNewProject?.addEventListener("click", () => {
    currentProjectId = null;
    markActiveProjectInSidebar("data-project-id", "__none__");
    if (topbarProjectTitle) topbarProjectTitle.textContent = "New Hardware Prototype";
    if (projectTitleInput) projectTitleInput.value = "";
    if (projectDescInput) projectDescInput.value = "";
    if (welcomeHero) welcomeHero.removeAttribute("hidden");
    setBriefOpen(true);
    if (chatInput) {
      chatInput.value = "";
      chatInput.focus();
    }
  });

  btnRefreshProjects?.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/projects", {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return;
      const list = await res.json();
      if (Array.isArray(list)) {
        list.forEach((p) => upsertProjectInSidebar(p));
      }
    } catch (err) {
      console.warn("Could not sync projects list:", err);
    }
  });

  /* ==========================================================================
     4. TAB NAVIGATION SYSTEM (INSIDE RIGHT DRAWER)
     ========================================================================== */
  function switchTab(targetTabId) {
    setRightDrawerOpen(true);

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

    if (targetTabId === "tab-steward") {
      loadStewardQueue();
    } else if (targetTabId === "tab-stockroom") {
      loadInventoryItems();
    }
  }

  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;
      switchTab(targetId);
    });
  });

  /* ==========================================================================
     5. ROLE SWITCHER (STUDENT <-> STEWARD)
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
     6. USER MANAGEMENT (STUDENT & STEWARD IDENTITY)
     ========================================================================== */
  async function ensureStudentUser() {
    if (currentActiveStudentId) return currentActiveStudentId;

    try {
      const res = await fetch("/api/users?role=student", {
        headers: { Accept: "application/json" },
      });
      if (res.ok) {
        const users = await res.json();
        if (Array.isArray(users) && users.length > 0) {
          currentActiveStudentId = users[0].id;
          return currentActiveStudentId;
        }
      }
    } catch (e) {
      // ignore and attempt POST
    }

    try {
      const createRes = await fetch("/api/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          name: "Nathan Noronha",
          email: "student@hmc.edu",
          role: "student",
        }),
      });

      if (createRes.ok) {
        const newUser = await createRes.json();
        currentActiveStudentId = newUser.id;
        return currentActiveStudentId;
      } else if (createRes.status === 409) {
        const retryRes = await fetch("/api/users?role=student", {
          headers: { Accept: "application/json" },
        });
        if (retryRes.ok) {
          const list = await retryRes.json();
          const match = list.find((u) => u.email === "student@hmc.edu") || list[0];
          if (match) {
            currentActiveStudentId = match.id;
            return currentActiveStudentId;
          }
        }
      }
    } catch (err) {
      console.warn("Could not create student user:", err);
    }

    return currentActiveStudentId;
  }

  async function ensureStewardUser() {
    if (currentActiveStewardId) return currentActiveStewardId;

    try {
      const res = await fetch("/api/users?role=steward", {
        headers: { Accept: "application/json" },
      });
      if (res.ok) {
        const users = await res.json();
        if (Array.isArray(users) && users.length > 0) {
          currentActiveStewardId = users[0].id;
          return currentActiveStewardId;
        }
      }
    } catch (e) {
      // ignore and attempt POST
    }

    try {
      const createRes = await fetch("/api/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          name: "Shop Steward Alex",
          email: "steward@hmc.edu",
          role: "steward",
        }),
      });

      if (createRes.ok) {
        const newUser = await createRes.json();
        currentActiveStewardId = newUser.id;
        return currentActiveStewardId;
      } else if (createRes.status === 409) {
        const retryRes = await fetch("/api/users?role=steward", {
          headers: { Accept: "application/json" },
        });
        if (retryRes.ok) {
          const list = await retryRes.json();
          const match = list.find((u) => u.email === "steward@hmc.edu") || list[0];
          if (match) {
            currentActiveStewardId = match.id;
            return currentActiveStewardId;
          }
        }
      }
    } catch (err) {
      console.warn("Could not create steward user:", err);
    }

    return currentActiveStewardId;
  }

  /* ==========================================================================
     7. SUBSYSTEM SWITCHING (FILTERS CENTER MANUFACTURING STEPS)
     ========================================================================== */
  function filterStepsBySubsystem(subsystemKey) {
    currentSubsystemFilter = (subsystemKey || "all").toLowerCase();

    subsystemBtns.forEach((btn) => {
      const match = (btn.dataset.subsystem || "").toLowerCase() === currentSubsystemFilter;
      btn.classList.toggle("active", match);
    });

    if (activeSubsystemBadge) {
      activeSubsystemBadge.textContent = `[ACTIVE SUBSYSTEM: ${currentSubsystemFilter.toUpperCase()}]`;
    }

    if (!stepsList) return;

    const cards = stepsList.querySelectorAll(".step-card:not(.step-empty-subsystem)");
    let visibleCount = 0;

    cards.forEach((card) => {
      const cardSub = (card.dataset.subsystem || "").toLowerCase();
      if (currentSubsystemFilter === "all" || cardSub === currentSubsystemFilter) {
        card.style.display = "";
        visibleCount++;
      } else {
        card.style.display = "none";
      }
    });

    const existingEmpty = stepsList.querySelector(".step-empty-subsystem");
    if (existingEmpty) {
      existingEmpty.remove();
    }

    if (visibleCount === 0 && cards.length > 0) {
      const emptyLi = document.createElement("li");
      emptyLi.className = "step-card step-empty-subsystem";
      emptyLi.innerHTML = `<article class="step-article"><p class="step-instruction">No manufacturing operations found for [${escapeHtml(currentSubsystemFilter.toUpperCase())}] subsystem.</p></article>`;
      stepsList.appendChild(emptyLi);
    }
  }

  subsystemBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterStepsBySubsystem(btn.dataset.subsystem);
    });
  });

  /* ==========================================================================
     8. STEP & BOM RENDERING (PURE SEMANTIC HTML)
     ========================================================================== */
  function renderGeneratedSteps(steps) {
    if (!stepsList) return;
    cachedSteps = steps || [];
    stepsList.innerHTML = "";

    cachedSteps.forEach((step, idx) => {
      const stepNumber = String(step.step_order || idx + 1).padStart(2, "0");
      const stepId = step.id || stepNumber;
      const requiresSignoff = Boolean(step.requires_steward_signoff);
      const isApproved = Boolean(step.safety_approved_at);
      const isLocked = requiresSignoff && !isApproved;
      const isCompleted = Boolean(step.is_completed);
      const subsystem = (step.subsystem || "mechanical").toLowerCase();
      const facility = (step.facility || "machine_shop").toLowerCase();

      const li = document.createElement("li");
      li.className = `step-card ${isLocked ? "step-locked" : "step-cleared"}`;
      li.id = `step-card-${stepId}`;
      li.dataset.subsystem = subsystem;

      let safetyBarrierHtml = "";
      let footerStatusHtml = "";

      if (isLocked) {
        safetyBarrierHtml = `
          <section class="safety-barrier" aria-label="Safety Sign-off Lock">
            <span class="barrier-warning-symbol" aria-hidden="true">&#9888;</span>
            <h5 class="barrier-title">STEWARD SAFETY SIGN-OFF REQUIRED BEFORE OPERATION</h5>
            <p class="barrier-text">
              ${escapeHtml(step.safety_notes || "Risk Level: CRITICAL. Certified shop steward physical inspection required prior to machine operation.")}
            </p>
            <button type="button" class="btn-request-signoff" data-step-id="${escapeHtml(String(stepId))}" data-step-title="${escapeHtml(step.title)}" data-facility="${escapeHtml(facility)}">
              REQUEST STEWARD SAFETY SIGN-OFF
            </button>
          </section>
        `;
        footerStatusHtml = `
          <footer class="step-status-footer">
            <span class="safety-tag safety-critical">&bull; Safety Gate Active &mdash; Machine Interlocked</span>
            <span class="gate-status-pill pill-locked" id="step-${escapeHtml(String(stepId))}-badge">[STATUS: PENDING STEWARD SIGN-OFF]</span>
            <button type="button" class="btn-toggle-step" data-step-id="${escapeHtml(String(stepId))}" data-completed="${isCompleted ? "true" : "false"}">
              ${isCompleted ? "[✓ COMPLETED]" : "[MARK OPERATION COMPLETE]"}
            </button>
          </footer>
        `;
      } else if (requiresSignoff && isApproved) {
        footerStatusHtml = `
          <footer class="step-status-footer">
            <span class="safety-tag safety-normal">&bull; Safety Barrier Unlocked &mdash; Steward Approved</span>
            <span class="gate-status-pill pill-cleared" id="step-${escapeHtml(String(stepId))}-badge">[STATUS: SAFETY APPROVED]</span>
            <button type="button" class="btn-toggle-step" data-step-id="${escapeHtml(String(stepId))}" data-completed="${isCompleted ? "true" : "false"}">
              ${isCompleted ? "[✓ COMPLETED]" : "[MARK OPERATION COMPLETE]"}
            </button>
          </footer>
        `;
      } else {
        footerStatusHtml = `
          <footer class="step-status-footer">
            <span class="safety-tag safety-normal">&bull; Standard Shop Floor Safety Protocol</span>
            <span class="gate-status-pill pill-cleared">[STATUS: CLEARED]</span>
            <button type="button" class="btn-toggle-step" data-step-id="${escapeHtml(String(stepId))}" data-completed="${isCompleted ? "true" : "false"}">
              ${isCompleted ? "[✓ COMPLETED]" : "[MARK OPERATION COMPLETE]"}
            </button>
          </footer>
        `;
      }

      li.innerHTML = `
        <article class="step-article">
          <header class="step-header">
            <span class="step-indicator"><kbd>OP ${escapeHtml(stepNumber)}</kbd></span>
            <h4 class="step-title">${escapeHtml(step.title)}</h4>
            <span class="facility-badge">[${escapeHtml(facility.toUpperCase())}]</span>
            <span class="subsystem-badge-pill"><kbd>[${escapeHtml(subsystem.toUpperCase())}]</kbd></span>
          </header>
          <p class="step-instruction">
            ${escapeHtml(step.instructions)}
          </p>
          ${safetyBarrierHtml}
          ${footerStatusHtml}
        </article>
      `;

      stepsList.appendChild(li);
    });

    filterStepsBySubsystem(currentSubsystemFilter);
  }

  function renderBOMTable(bomItems) {
    if (!bomTableBody) return;
    const items = bomItems || [];
    bomTableBody.innerHTML = "";

    items.forEach((item) => {
      const tr = document.createElement("tr");
      const isInStock = item.source_status === "in_stock_on_campus";
      const statusTag = isInStock
        ? `<span class="source-tag in-stock">[IN_STOCK_ON_CAMPUS]</span>`
        : `<span class="source-tag external">[EXTERNAL_PURCHASE_NEEDED]</span>`;

      const sourcingNote = item.external_purchase_note
        ? `<em>${escapeHtml(item.external_purchase_note)}</em>`
        : `<code>${escapeHtml(item.facility ? `Campus Stockroom (${item.facility.toUpperCase()})` : "HMC Inventory")}</code>`;

      tr.innerHTML = `
        <td><strong>${escapeHtml(item.part_name)}</strong></td>
        <td><kbd>[${escapeHtml((item.subsystem || item.facility || "MECHANICAL").toUpperCase())}]</kbd></td>
        <td><code>${escapeHtml(String(item.quantity_needed || 1))} pcs</code></td>
        <td>${statusTag}</td>
        <td>${sourcingNote}</td>
      `;

      bomTableBody.appendChild(tr);
    });

    if (bomCountBadge) {
      bomCountBadge.textContent = `TOTAL ITEMS: ${items.length}`;
    }
  }

  /* ==========================================================================
     9. HONEST FAILURE UI RENDERING (<aside class="stark-alert-box" role="alert">)
     ========================================================================== */
  function showGenerationError(errorCode, errorDetail) {
    if (!generationAlert || !generationAlertMessage) return;

    setBriefOpen(true);

    if (generationAlertTitle) {
      generationAlertTitle.textContent = `DECOMPOSITION FAILED • [${errorCode}]`;
    }
    generationAlertMessage.textContent = `${errorCode}: ${errorDetail}`;
    generationAlert.removeAttribute("hidden");

    if (copilotActionStatus) {
      copilotActionStatus.textContent = `Error: ${errorCode}. Review diagnostic banner above.`;
    }
  }

  function hideGenerationError() {
    if (generationAlert) {
      generationAlert.setAttribute("hidden", "until-found");
    }
  }

  /* ==========================================================================
     10. PROJECT DECOMPOSITION DISPATCH (EXPLICIT USER ACTION ONLY)
     ========================================================================== */
  async function triggerStepGeneration(projectId) {
    hideGenerationError();

    if (btnGenerateSteps) {
      btnGenerateSteps.disabled = true;
      btnGenerateSteps.textContent = "DECOMPOSING MANUFACTURING PLAN...";
    }
    if (btnQuickDecompose) {
      btnQuickDecompose.disabled = true;
      btnQuickDecompose.textContent = "Decomposing...";
    }
    if (generationProgress) {
      generationProgress.removeAttribute("hidden");
    }
    if (copilotActionStatus) {
      copilotActionStatus.textContent = "Dispatched decomposition to Gemini 2.0 API. Synthesizing fabrication plan...";
    }

    try {
      const response = await fetch(`/api/projects/${projectId}/generate-steps`, {
        method: "POST",
        headers: { Accept: "application/json" },
      });

      if (response.ok) {
        const projectData = await response.json();
        currentProjectId = projectData.id;
        hideGenerationError();

        if (topbarProjectTitle && projectData.title) {
          topbarProjectTitle.textContent = projectData.title;
        }
        upsertProjectInSidebar(projectData);
        renderGeneratedSteps(projectData.steps || []);
        renderBOMTable(projectData.bom_items || []);

        const lockCount = (projectData.steps || []).filter((s) => s.requires_steward_signoff).length;
        if (copilotActionStatus) {
          copilotActionStatus.textContent = `Plan decomposed into ${projectData.steps.length} sequential operations with ${lockCount} steward safety sign-off gates.`;
        }
      } else {
        const errPayload = await response.json().catch(() => ({}));
        const errCode = errPayload.error || `HTTP_${response.status}`;
        const errMsg = errPayload.message || response.statusText || "Decomposition service unavailable.";
        showGenerationError(errCode, errMsg);
      }
    } catch (networkErr) {
      showGenerationError("NETWORK_TIMEOUT", networkErr.message || "Please retry connecting to server.");
    } finally {
      if (btnGenerateSteps) {
        btnGenerateSteps.disabled = false;
        btnGenerateSteps.textContent = "DECOMPOSE INTO MANUFACTURING PLAN →";
      }
      if (btnQuickDecompose) {
        btnQuickDecompose.disabled = false;
        btnQuickDecompose.textContent = "Decompose Plan";
      }
      if (generationProgress) {
        generationProgress.setAttribute("hidden", "until-found");
      }
    }
  }

  async function handleProjectSubmit() {
    const title = (projectTitleInput?.value || "").trim() || "Hardware Prototype";
    const description = (projectDescInput?.value || "").trim() || "Machining specification brief";

    hideGenerationError();

    if (topbarProjectTitle) {
      topbarProjectTitle.textContent = title;
    }
    if (copilotActionStatus) {
      copilotActionStatus.textContent = "Initializing student context and project specification...";
    }

    try {
      const studentId = await ensureStudentUser();
      const createRes = await fetch("/api/projects", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          title: title,
          description: description,
          student_id: studentId || 1,
        }),
      });

      if (!createRes.ok) {
        const errJson = await createRes.json().catch(() => ({}));
        showGenerationError("PROJECT_CREATION_FAILED", errJson.detail || "Could not persist project record.");
        return;
      }

      const project = await createRes.json();
      currentProjectId = project.id;
      upsertProjectInSidebar(project);

      await triggerStepGeneration(currentProjectId);
    } catch (err) {
      showGenerationError("NETWORK_TIMEOUT", err.message || "Please check connection and retry.");
    }
  }

  btnGenerateSteps?.addEventListener("click", handleProjectSubmit);
  projectForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    handleProjectSubmit();
  });

  // Quick Decompose button inside the bottom ChatGPT prompt bar
  btnQuickDecompose?.addEventListener("click", () => {
    const promptVal = (chatInput?.value || "").trim();
    if (promptVal) {
      const firstSentence = promptVal.split(/[.:;\n]/)[0].trim();
      const derivedTitle = firstSentence.slice(0, 60) || "Custom Hardware Prototype";
      if (projectTitleInput) projectTitleInput.value = derivedTitle;
      if (projectDescInput) projectDescInput.value = promptVal;
      if (chatInput) chatInput.value = "";
    }
    handleProjectSubmit();
  });

  btnRetryGenerate?.addEventListener("click", () => {
    if (currentProjectId) {
      triggerStepGeneration(currentProjectId);
    } else {
      handleProjectSubmit();
    }
  });

  /* ==========================================================================
     11. CONVERSATIONAL REFINEMENT (CHAT)
     ========================================================================== */
  function showChatError(errorCode, errorDetail) {
    if (!chatAlertBox || !chatAlertMessage) return;

    if (chatAlertTitle) {
      chatAlertTitle.textContent = `QUERY FAILED • [${errorCode}]`;
    }
    chatAlertMessage.textContent = `${errorCode}: ${errorDetail}`;
    chatAlertBox.removeAttribute("hidden");

    if (chatStatusBadge) {
      chatStatusBadge.textContent = "[STATUS: ERROR]";
    }
    if (chatActionStatus) {
      chatActionStatus.textContent = `Query error: ${errorCode}. See diagnostic above.`;
    }
  }

  function hideChatError() {
    if (chatAlertBox) {
      chatAlertBox.setAttribute("hidden", "until-found");
    }
  }

  function appendChatMessage(role, text) {
    if (!chatThreadList) return;
    const isUser = role === "user";

    const li = document.createElement("li");
    li.className = `chat-message ${isUser ? "chat-user" : "chat-model"}`;

    const authorLabel = isUser ? "[STUDENT]" : "[ASSISTANT • GEMINI 2.0]";
    const timeLabel = formatTime();

    li.innerHTML = `
      <article class="chat-bubble">
        <header class="chat-meta">
          <strong class="chat-author">${escapeHtml(authorLabel)}</strong>
          <time class="chat-time">${escapeHtml(timeLabel)}</time>
        </header>
        <p class="chat-text">${escapeHtml(text)}</p>
      </article>
    `;

    chatThreadList.appendChild(li);
    li.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function handleChatSubmit() {
    const message = (chatInput?.value || "").trim();
    if (!message) return;

    hideChatError();
    lastFailedChatPayload = message;

    if (!currentProjectId) {
      try {
        const studentId = await ensureStudentUser();
        const createRes = await fetch("/api/projects", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            title: projectTitleInput?.value?.trim() || "Hardware Project",
            description: projectDescInput?.value?.trim() || "Specification brief",
            student_id: studentId || 1,
          }),
        });
        if (createRes.ok) {
          const newProj = await createRes.json();
          currentProjectId = newProj.id;
          upsertProjectInSidebar(newProj);
        } else {
          showChatError("PROJECT_INIT_FAILED", "Please formulate project brief above first.");
          return;
        }
      } catch (e) {
        showChatError("NETWORK_TIMEOUT", "Could not connect to project server.");
        return;
      }
    }

    appendChatMessage("user", message);
    if (chatInput) chatInput.value = "";

    if (btnSendChat) btnSendChat.disabled = true;
    if (chatProgress) chatProgress.removeAttribute("hidden");
    if (chatStatusBadge) chatStatusBadge.textContent = "[STATUS: CONSULTING GEMINI...]";
    if (chatActionStatus) chatActionStatus.textContent = "Gemini analyzing tooling parameters and physical constraints...";

    try {
      const response = await fetch(`/api/projects/${currentProjectId}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          message: message,
          history: chatHistory,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const reply = data.reply || "";
        chatHistory.push({ role: "user", content: message });
        chatHistory.push({ role: "model", content: reply });

        appendChatMessage("model", reply);
        if (chatStatusBadge) chatStatusBadge.textContent = "[STATUS: READY]";
        if (chatActionStatus) chatActionStatus.textContent = "Query answered. Ready for follow-up.";
        hideChatError();
      } else {
        const errPayload = await response.json().catch(() => ({}));
        const errCode = errPayload.error || `HTTP_${response.status}`;
        const errMsg = errPayload.message || response.statusText || "Gemini chat query failed.";
        showChatError(errCode, errMsg);
      }
    } catch (networkErr) {
      showChatError("NETWORK_TIMEOUT", networkErr.message || "Please retry sending message.");
    } finally {
      if (btnSendChat) btnSendChat.disabled = false;
      if (chatProgress) chatProgress.setAttribute("hidden", "until-found");
    }
  }

  btnSendChat?.addEventListener("click", handleChatSubmit);
  chatForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    handleChatSubmit();
  });

  // Support Enter-to-send (Shift+Enter for newline) in ChatGPT prompt bar
  chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit();
    }
  });

  btnRetryChat?.addEventListener("click", () => {
    if (lastFailedChatPayload && chatInput) {
      chatInput.value = lastFailedChatPayload;
      handleChatSubmit();
    }
  });

  /* ==========================================================================
     12. SAFETY SIGN-OFF MODAL DIALOG (<dialog id="safety-modal">)
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

  safetyModal?.addEventListener("click", (event) => {
    if (event.target === safetyModal) {
      closeSafetyModal();
    }
  });

  stepsList?.addEventListener("click", async (e) => {
    const toggleBtn = e.target.closest(".btn-toggle-step");
    if (toggleBtn) {
      const stepId = toggleBtn.dataset.stepId;
      const isCurrentlyCompleted = toggleBtn.dataset.completed === "true";
      const studentId = await ensureStudentUser();

      try {
        const response = await fetch(`/api/steps/${stepId}/toggle-complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            student_id: studentId || 1,
            is_completed: !isCurrentlyCompleted,
          }),
        });

        if (response.ok) {
          const updated = await response.json();
          toggleBtn.dataset.completed = updated.is_completed ? "true" : "false";
          toggleBtn.textContent = updated.is_completed ? "[✓ COMPLETED]" : "[MARK OPERATION COMPLETE]";
        } else {
          const errPayload = await response.json().catch(() => ({}));
          alert(errPayload.detail || "Cannot complete step before shop steward safety sign-off.");
        }
      } catch (err) {
        alert("Could not update step completion: " + err.message);
      }
      return;
    }

    const reqBtn = e.target.closest(".btn-request-signoff");
    if (reqBtn) {
      const stepId = reqBtn.dataset.stepId;
      const stepTitle = reqBtn.dataset.stepTitle;
      const facility = reqBtn.dataset.facility;
      openSafetyModal(stepId, stepTitle, facility);
    }
  });

  dialogSignoffForm?.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!currentPendingStepId) {
      closeSafetyModal();
      return;
    }

    const stewardId = await ensureStewardUser();
    const notesInput = document.getElementById("dialog-steward-notes");
    const notes = (notesInput?.value || "").trim() || "Physical safety check-off completed.";

    try {
      const response = await fetch(`/api/steps/${currentPendingStepId}/approve-safety`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          steward_id: stewardId || 2,
          notes: notes,
        }),
      });

      if (response.ok) {
        const stepBadge = document.getElementById(`step-${currentPendingStepId}-badge`);
        const stepCard = document.getElementById(`step-card-${currentPendingStepId}`);
        if (stepBadge) {
          stepBadge.textContent = "[STATUS: SAFETY APPROVED]";
          stepBadge.className = "gate-status-pill pill-cleared";
        }
        if (stepCard) {
          stepCard.classList.remove("step-locked");
          stepCard.classList.add("step-cleared");
          const barrier = stepCard.querySelector(".safety-barrier");
          if (barrier) barrier.remove();
        }

        loadStewardQueue();
      } else {
        const errPayload = await response.json().catch(() => ({}));
        alert(errPayload.detail || "Steward sign-off could not be registered.");
      }
    } catch (err) {
      alert("Network error submitting safety sign-off: " + err.message);
    } finally {
      closeSafetyModal();
    }
  });

  /* ==========================================================================
     13. STEWARD QUEUE API & ACTIONS
     ========================================================================== */
  async function loadStewardQueue(facilityFilter = "all") {
    const stewardContainer = document.getElementById("steward-queue-container");
    if (!stewardContainer) return;

    try {
      let url = "/api/steward/pending-signoffs";
      if (facilityFilter && facilityFilter !== "all") {
        url += `?facility=${encodeURIComponent(facilityFilter)}`;
      }

      const res = await fetch(url);
      if (!res.ok) return;

      const items = await res.json();
      if (safetyQueueCount) {
        safetyQueueCount.textContent = items.length;
      }

      stewardContainer.innerHTML = "";
      if (items.length === 0) {
        const emptyLi = document.createElement("li");
        emptyLi.className = "queue-item queue-empty";
        emptyLi.innerHTML = `
          <article class="steward-card">
            <p class="queue-risk-brief">Zero pending safety sign-offs in queue for the selected facility. Shop floor is clear.</p>
          </article>
        `;
        stewardContainer.appendChild(emptyLi);
        return;
      }

      items.forEach((item) => {
        const li = document.createElement("li");
        const facilityKey = (item.facility || "machine_shop").toLowerCase();
        li.className = "queue-item";
        li.dataset.facility = facilityKey;

        li.innerHTML = `
          <article class="steward-card">
            <header class="card-header-bar">
              <span class="facility-badge">[${escapeHtml(facilityKey.toUpperCase())}]</span>
              <time class="card-timestamp">REQUIRES ATTENTION</time>
            </header>
            <h3 class="queue-operation-title">${escapeHtml(item.title)}</h3>
            <p class="queue-student-meta">
              Student: <strong>${escapeHtml(item.student_name)}</strong> &bull; Project: <em>${escapeHtml(item.project_title)}</em> &bull; Step: <kbd>OP ${escapeHtml(String(item.step_order).padStart(2, "0"))}</kbd>
            </p>
            <p class="queue-risk-brief">
              <strong>Instructions:</strong> ${escapeHtml(item.instructions)}
              ${item.safety_notes ? `<br><strong>Safety Notes:</strong> ${escapeHtml(item.safety_notes)}` : ""}
            </p>
            <footer class="queue-card-actions">
              <button type="button" class="btn-steward-approve" data-step-id="${escapeHtml(String(item.step_id))}" data-step-title="${escapeHtml(item.title)}" data-facility="${escapeHtml(facilityKey)}">
                APPROVE SIGN-OFF
              </button>
              <button type="button" class="btn-steward-flag" data-step-id="${escapeHtml(String(item.step_id))}" data-step-title="${escapeHtml(item.title)}" data-facility="${escapeHtml(facilityKey)}">
                FLAG SAFETY CONCERN
              </button>
            </footer>
          </article>
        `;
        stewardContainer.appendChild(li);
      });
    } catch (err) {
      console.warn("Could not load steward queue:", err);
    }
  }

  const stewardQueueContainer = document.getElementById("steward-queue-container");
  stewardQueueContainer?.addEventListener("click", async (e) => {
    const approveBtn = e.target.closest(".btn-steward-approve");
    if (approveBtn) {
      const stepId = approveBtn.dataset.stepId;
      const stepTitle = approveBtn.dataset.stepTitle;
      const facility = approveBtn.dataset.facility;
      openSafetyModal(stepId, stepTitle, facility);
      return;
    }

    const flagBtn = e.target.closest(".btn-steward-flag");
    if (flagBtn) {
      const stepId = flagBtn.dataset.stepId;
      const stepTitle = flagBtn.dataset.stepTitle || "Operation";
      const reason = prompt(
        `Enter safety hazard or reason for flagging "${stepTitle}":`,
        "Fixture rigidity insufficient / missing eye protection"
      );
      if (!reason || !reason.trim()) return;

      const stewardId = await ensureStewardUser();
      try {
        const response = await fetch(`/api/steps/${stepId}/flag-safety`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            steward_id: stewardId || 2,
            reason: reason.trim(),
          }),
        });
        if (response.ok) {
          alert(`Flagged step: "${stepTitle}". Notification recorded.`);
          loadStewardQueue();
        } else {
          const errPayload = await response.json().catch(() => ({}));
          alert(errPayload.detail || "Could not record safety flag.");
        }
      } catch (err) {
        alert("Failed to flag safety concern: " + err.message);
      }
    }
  });

  queueFilterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      queueFilterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const filter = btn.dataset.queueFilter || "all";
      loadStewardQueue(filter);
    });
  });

  /* ==========================================================================
     14. CAMPUS STOCKROOM INVENTORY & BATCH CSV
     ========================================================================== */
  async function loadInventoryItems() {
    const gridList = document.getElementById("inventory-grid-list");
    if (!gridList) return;

    const query = (inventorySearch?.value || "").trim();
    const facility = facilitySelect?.value || "all";

    let url = "/api/inventory?";
    if (facility && facility !== "all") {
      url += `facility=${encodeURIComponent(facility)}&`;
    }
    if (query) {
      url += `search=${encodeURIComponent(query)}&`;
    }

    try {
      const res = await fetch(url);
      if (!res.ok) return;

      const items = await res.json();
      if (!Array.isArray(items) || items.length === 0) {
        gridList.innerHTML = `
          <li class="inventory-item-card">
            <article class="stock-card">
              <h3 class="stock-title">No Matching Inventory Items Found</h3>
              <p class="stock-location">Adjust search terms or facility filter above, or import via CSV below.</p>
            </article>
          </li>
        `;
        return;
      }

      gridList.innerHTML = "";
      items.forEach((item) => {
        const facilityKey = (item.facility || "machine_shop").toLowerCase();
        const li = document.createElement("li");
        li.className = "inventory-item-card";
        li.dataset.facility = facilityKey;

        li.innerHTML = `
          <article class="stock-card">
            <header class="stock-header">
              <span class="facility-badge">[${escapeHtml(facilityKey.toUpperCase())}]</span>
              <code class="stock-sku">SKU: ${escapeHtml(item.sku)}</code>
            </header>
            <h3 class="stock-title">${escapeHtml(item.name)}</h3>
            <p class="stock-location">
              LOCATION: <kbd>${escapeHtml(item.location || "UNASSIGNED")}</kbd> &bull; CATEGORY: <strong>${escapeHtml(item.category || "General")}</strong>
            </p>
            <footer class="stock-footer">
              <span class="stock-count">AVAILABLE: <strong>${item.quantity}</strong> ${escapeHtml(item.unit || "pcs")}</span>
              <span class="source-tag ${item.quantity > 0 ? "in-stock" : "out-of-stock"}">[${item.quantity > 0 ? "ON_HAND" : "DEPLETED"}]</span>
              <button type="button" class="btn-adjust-qty" data-item-id="${item.id}" data-current-qty="${item.quantity}" data-delta="1">+1</button>
              <button type="button" class="btn-adjust-qty" data-item-id="${item.id}" data-current-qty="${item.quantity}" data-delta="-1">-1</button>
            </footer>
          </article>
        `;
        gridList.appendChild(li);
      });
    } catch (err) {
      console.warn("Could not load inventory:", err);
    }
  }

  inventorySearch?.addEventListener("input", () => {
    loadInventoryItems();
  });
  facilitySelect?.addEventListener("change", () => {
    loadInventoryItems();
  });

  const inventoryGridList = document.getElementById("inventory-grid-list");
  inventoryGridList?.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-adjust-qty");
    if (!btn) return;
    const itemId = btn.dataset.itemId;
    const currentQty = parseInt(btn.dataset.currentQty, 10) || 0;
    const delta = parseInt(btn.dataset.delta, 10) || 0;
    const newQty = Math.max(0, currentQty + delta);

    try {
      const res = await fetch(`/api/inventory/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantity: newQty }),
      });
      if (res.ok) {
        loadInventoryItems();
      }
    } catch (err) {
      console.warn("Could not adjust inventory quantity:", err);
    }
  });

  const btnUploadCsv = document.getElementById("btn-upload-csv");
  const csvTextInput = document.getElementById("csv-text-input");
  const csvUploadStatus = document.getElementById("csv-upload-status");

  btnUploadCsv?.addEventListener("click", async () => {
    const csvContent = (csvTextInput?.value || "").trim();
    if (!csvContent) {
      alert("Please paste CSV records into the textarea first.");
      return;
    }

    if (csvUploadStatus) {
      csvUploadStatus.textContent = "Parsing and syncing CSV records into PostgreSQL...";
    }

    try {
      const stewardId = await ensureStewardUser();
      const res = await fetch(`/api/inventory/upload-csv?steward_id=${stewardId || 2}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(csvContent),
      });

      if (res.ok) {
        const summary = await res.json();
        const msg = `Synced ${summary.imported_count} inventory records. (Errors: ${summary.errors.length})`;
        if (csvUploadStatus) csvUploadStatus.textContent = msg;
        if (summary.errors && summary.errors.length > 0) {
          alert(`CSV imported with notices:\n${summary.errors.join("\n")}`);
        } else {
          alert(msg);
        }
        loadInventoryItems();
      } else {
        const err = await res.json().catch(() => ({}));
        if (csvUploadStatus) csvUploadStatus.textContent = "CSV upload failed.";
        alert(err.detail || "CSV upload failed.");
      }
    } catch (err) {
      if (csvUploadStatus) csvUploadStatus.textContent = "Network error during CSV upload.";
      alert("Error uploading CSV: " + err.message);
    }
  });

  /* ==========================================================================
     15. CLASSMATE CAD 3D TOOL INTEGRATION HARNESS
     ========================================================================== */
  const btnCheckCadStatus = document.getElementById("btn-check-cad-status");
  const btnExportCadStub = document.getElementById("btn-export-cad-stub");
  const cadTelemetryStatus = document.getElementById("cad-telemetry-status");
  const cadPromptText = document.getElementById("cad-prompt-text");
  const cadActionStatus = document.getElementById("cad-action-status");

  btnCheckCadStatus?.addEventListener("click", async () => {
    if (cadActionStatus) cadActionStatus.textContent = "Checking CAD bridge status...";
    try {
      const res = await fetch("/api/integrations/cad/status");
      if (res.ok) {
        const status = await res.json();
        if (cadTelemetryStatus) {
          cadTelemetryStatus.textContent = `[BRIDGE_STATUS: ${status.status.toUpperCase()} • VERSION: ${status.bridge_version.toUpperCase()} • FORMATS: ${status.supported_formats.join(",").toUpperCase()}]`;
        }
        if (cadPromptText) {
          cadPromptText.textContent = `Connected to CAD Webhook: ${status.webhook_url}. Standby for model stream.`;
        }
        if (cadActionStatus) {
          cadActionStatus.textContent = "CAD tool bridge active and connected.";
        }
      }
    } catch (err) {
      if (cadActionStatus) cadActionStatus.textContent = "CAD bridge query failed: " + err.message;
    }
  });

  btnExportCadStub?.addEventListener("click", async () => {
    if (cadActionStatus) cadActionStatus.textContent = "Dispatching export job to CAD bridge...";
    try {
      const res = await fetch("/api/integrations/cad/export-stl-stub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: currentProjectId || 1,
          part_name: projectTitleInput?.value?.trim() || "Chassis Blank",
          format: "stl",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (cadPromptText) {
          cadPromptText.textContent = `${data.note} (Mock download ready: ${data.download_stub_url})`;
        }
        if (cadActionStatus) {
          cadActionStatus.textContent = `CAD export job ${data.job_id} scheduled.`;
        }
      }
    } catch (err) {
      if (cadActionStatus) cadActionStatus.textContent = "CAD export failed: " + err.message;
    }
  });

  /* ==========================================================================
     16. DOMContentLoaded INITIALIZATION (ZERO LLM CALLS)
     ========================================================================== */
  document.addEventListener("DOMContentLoaded", () => {
    // STRICT DIRECTIVE: Only invoke static relational / health endpoint
    checkBackendHealth();
  });
})();
