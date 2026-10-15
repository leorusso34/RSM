// ==========================================================================
// RSM NEXT-GEN - INTERACTIVE APPLICATION CONTROLLER
// Spotlight Glow, Animated KPI Counters, Reactive Table, Live Charts & Modals
// ==========================================================================

// ==========================================================================
// RSM NEXT-GEN - LIVE BRIDGE CONTROLLER
// Collegamento API in tempo reale al database SQLite locale (127.0.0.1:28472)
// ==========================================================================

const API_BASE = "http://127.0.0.1:28472/api";
let inventoryData = [];
let currentEditingId = null;
let metricsData = null;
let realMonthlySales = [];
let realPlatformProfits = [];

async function callApi(endpoint, options = {}, retries = 2) {
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, options);
      return res;
    } catch (err) {
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 300));
      } else {
        throw err;
      }
    }
  }
}

function formatMoney(val) {
  if (val === null || val === undefined || isNaN(val)) return "-";
  return `€ ${Number(val).toLocaleString("it-IT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}

async function loadProductsFromBackend(retries = 6, delay = 500) {
  for (let i = 0; i < retries; i++) {
    try {
      const [resProd, resMetrics] = await Promise.all([
        fetch(`${API_BASE}/products`),
        fetch(`${API_BASE}/metrics`).catch(() => null)
      ]);
      if (!resProd.ok) throw new Error(`HTTP error ${resProd.status}`);
      const json = await resProd.json();
      if (json.success && Array.isArray(json.data)) {
        inventoryData = json.data;
        if (resMetrics && resMetrics.ok) {
          try {
            const mJson = await resMetrics.json();
            if (mJson.success) {
              metricsData = mJson;
              realMonthlySales = mJson.monthlySales || [];
              realPlatformProfits = mJson.platformProfits || [];
            }
          } catch (_) {}
        }
        renderTable();
        updateDashboardMetrics();
        initCharts();
        return true;
      }
    } catch (err) {
      if (i < retries - 1) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      } else {
        console.warn("Bridge locale in attesa di avvio o non raggiungibile:", err);
      }
    }
  }
  return false;
}

let activeFilter = "all";
let searchTerm = "";
let sortField = "date";
let sortOrder = "desc";

let monthlyProfitChart = null;
let platformPieChart = null;

// ==========================================================================
// SIDEBAR COLLAPSE TOGGLE (WITH AUTOMATIC CHART RESIZE)
// ==========================================================================
function toggleSidebar(expand) {
  const sidebar = document.getElementById("appSidebar");
  const openBtn = document.getElementById("openSidebarBtn");
  if (!sidebar || !openBtn) return;
  if (expand) {
    sidebar.classList.remove("collapsed");
    openBtn.classList.remove("visible");
  } else {
    sidebar.classList.add("collapsed");
    openBtn.classList.add("visible");
  }

  // Risolve il problema del grafico: resize immediato e dopo la transizione CSS
  if (monthlyProfitChart) monthlyProfitChart.resize();
  if (platformPieChart) platformPieChart.resize();

  setTimeout(() => {
    if (monthlyProfitChart) monthlyProfitChart.resize();
    if (platformPieChart) platformPieChart.resize();
  }, 240);
}

window.addEventListener("resize", () => {
  if (monthlyProfitChart) monthlyProfitChart.resize();
  if (platformPieChart) platformPieChart.resize();
});

// ==========================================================================
// SORTING MENU CONTROLLER
// ==========================================================================
function toggleSortMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById("sortMenu");
  const btn = document.getElementById("sortDropdownBtn");
  if (!menu) return;
  const isOpen = menu.classList.contains("open");
  if (isOpen) {
    menu.classList.remove("open");
    if (btn) btn.classList.remove("active");
  } else {
    menu.classList.add("open");
    if (btn) btn.classList.add("active");
  }
}

function applySort(field, order) {
  sortField = field;
  sortOrder = order;

  // Aggiorna stato attivo nella tendina
  const sortKey = `${field}-${order}`;
  document.querySelectorAll(".sort-menu-item").forEach((item) => {
    if (item.getAttribute("data-sort-key") === sortKey) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  // Chiudi menu
  const menu = document.getElementById("sortMenu");
  const btn = document.getElementById("sortDropdownBtn");
  if (menu) menu.classList.remove("open");
  if (btn) btn.classList.remove("active");

  renderTable();
}

// Chiudi la tendina di ordinamento se si clicca all'esterno
document.addEventListener("click", (e) => {
  const wrap = document.querySelector(".sort-dropdown-wrap");
  if (wrap && !wrap.contains(e.target)) {
    const menu = document.getElementById("sortMenu");
    const btn = document.getElementById("sortDropdownBtn");
    if (menu) menu.classList.remove("open");
    if (btn) btn.classList.remove("active");
  }
});

// ==========================================================================
// METRIC COUNTERS (Instant render, 0 CPU delay)
// ==========================================================================
function setMetricValue(elem, value, isCurrency = true, isPercent = false) {
  if (!elem) return;
  if (isCurrency) {
    elem.textContent = `€ ${value.toLocaleString("it-IT", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  } else if (isPercent) {
    elem.textContent = `${value.toFixed(1)}%`;
  } else {
    elem.textContent = Math.round(value).toString();
  }
}

// ==========================================================================
// CALCULATE & UPDATE METRICS
// ==========================================================================
function updateDashboardMetrics() {
  let totalInvested = 0;
  let totalStockValue = 0;
  let totalProfit = 0;
  let totalRoiSum = 0;
  let completedCount = 0;

  inventoryData.forEach((item) => {
    const cost = item.purchasedPrice * item.quantity;
    totalInvested += cost;

    const estSale = (item.salePrice || item.purchasedPrice * 1.5) * item.quantity;
    totalStockValue += estSale;

    if (item.status === "completed" || item.salePrice) {
      const sale = item.salePrice * item.quantity;
      const fees = (item.fees || 0) * item.quantity;
      const profit = sale - cost - fees;
      totalProfit += profit;
      const roi = cost > 0 ? (profit / cost) * 100 : 0;
      totalRoiSum += roi;
      completedCount++;
    }
  });

  const avgRoi = completedCount > 0 ? totalRoiSum / completedCount : 48.2;

  const kpiInvested = document.getElementById("kpi-invested");
  const kpiStock = document.getElementById("kpi-stock");
  const kpiProfit = document.getElementById("kpi-profit");
  const kpiRoi = document.getElementById("kpi-roi");

  if (kpiInvested) setMetricValue(kpiInvested, totalInvested, true);
  if (kpiStock) setMetricValue(kpiStock, totalStockValue, true);
  if (kpiProfit) setMetricValue(kpiProfit, totalProfit, true);
  if (kpiRoi) kpiRoi.textContent = `+${avgRoi.toFixed(1)}% ROI`;

  // Aggiorna badge laterali
  const badgeStock = document.getElementById("badge-stock");
  const badgePreorder = document.getElementById("badge-preorder");
  const badgeActive = document.getElementById("badge-active");
  const badgeCompleted = document.getElementById("badge-completed");

  if (badgeStock) badgeStock.textContent = inventoryData.filter(i => i.status === "stock").length;
  if (badgePreorder) badgePreorder.textContent = inventoryData.filter(i => i.status === "preorder").length;
  if (badgeActive) badgeActive.textContent = inventoryData.filter(i => i.status === "active-sale").length;
  if (badgeCompleted) badgeCompleted.textContent = inventoryData.filter(i => i.status === "completed").length;
}

// ==========================================================================
// RENDER TABLE
// ==========================================================================
function renderTable() {
  const thead = document.getElementById("inventory-table-head");
  const tbody = document.getElementById("inventory-table-body");
  if (!tbody) return;

  const isStockView = (activeFilter === "stock" || activeFilter === "preorder");

  // Helper per classi di ordinamento
  const getSortClass = (field) => {
    if (sortField !== field) return "sortable";
    return `sortable ${sortOrder === "asc" ? "sorted-asc" : "sorted-desc"}`;
  };

  // Render dell'Header in base alla visualizzazione attiva (misure ottimizzate "Zero-Lag")
  if (thead) {
    if (isStockView) {
      thead.innerHTML = `
        <tr>
          <th class="col-prod ${getSortClass('name')}" data-sort="name">Prodotto</th>
          <th class="col-size col-center">Taglia</th>
          <th class="col-qty col-center">Q.tà</th>
          <th class="col-buy ${getSortClass('purchasedPrice')}" data-sort="purchasedPrice">P. Acquisto</th>
          <th class="col-place">L. Acquisto</th>
          <th class="col-status col-center">Stato</th>
          <th class="col-actions col-center">Azioni</th>
        </tr>
      `;
    } else {
      thead.innerHTML = `
        <tr>
          <th class="col-prod ${getSortClass('name')}" data-sort="name">Prodotto</th>
          <th class="col-size col-center">Taglia</th>
          <th class="col-qty col-center">Q.tà</th>
          <th class="col-buy ${getSortClass('purchasedPrice')}" data-sort="purchasedPrice">P. Acquisto</th>
          <th class="col-sell ${getSortClass('salePrice')}" data-sort="salePrice">P. Vendita</th>
          <th class="col-channel">Canale</th>
          <th class="col-profit ${getSortClass('profit')}" data-sort="profit">Utile Netto</th>
          <th class="col-roi col-center ${getSortClass('roi')}" data-sort="roi">ROI</th>
          <th class="col-status col-center">Stato</th>
          <th class="col-actions col-center">Azioni</th>
        </tr>
      `;
    }
  }

  let filtered = inventoryData.filter((item) => {
    // Filtro per stato
    if (activeFilter !== "all" && item.status !== activeFilter) return false;
    // Filtro di ricerca
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const match =
        item.name.toLowerCase().includes(term) ||
        item.size.toLowerCase().includes(term) ||
        (item.sellingPlace && item.sellingPlace.toLowerCase().includes(term)) ||
        item.purchasedPlace.toLowerCase().includes(term);
      if (!match) return false;
    }
    return true;
  });

  // Ordinamento
  filtered.sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];

    if (sortField === "profit") {
      valA = (a.salePrice || 0) - a.purchasedPrice - (a.fees || 0);
      valB = (b.salePrice || 0) - b.purchasedPrice - (b.fees || 0);
    } else if (sortField === "roi") {
      const pA = (a.salePrice || 0) - a.purchasedPrice - (a.fees || 0);
      const pB = (b.salePrice || 0) - b.purchasedPrice - (b.fees || 0);
      valA = a.purchasedPrice > 0 ? (pA / a.purchasedPrice) * 100 : 0;
      valB = b.purchasedPrice > 0 ? (pB / b.purchasedPrice) * 100 : 0;
    }

    if (typeof valA === "string") {
      return sortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortOrder === "asc" ? valA - valB : valB - valA;
  });

  tbody.innerHTML = "";

  const totalCols = isStockView ? 7 : 10;
  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="${totalCols}" style="text-align: center; padding: 40px; color: var(--text-dim);">
          <div style="font-size: 28px; margin-bottom: 8px;">🔍</div>
          Nessun prodotto trovato per i criteri selezionati.
        </td>
      </tr>
    `;
    return;
  }

  filtered.forEach((item) => {
    const tr = document.createElement("tr");

    // Status Badge Info
    let statusClass = "stock";
    let statusLabel = "In Magazzino";
    if (item.status === "preorder") {
      statusClass = "preorder";
      statusLabel = "Pre-ordine";
    } else if (item.status === "active-sale") {
      statusClass = "active-sale";
      statusLabel = "In Vendita";
    } else if (item.status === "completed") {
      statusClass = "completed";
      statusLabel = "Venduto";
    }

    // Le vendite completate non possono essere modificate (solo visualizzazione/storico)
    const editBtnHtml = (item.status === "completed") ? "" : `
      <button class="btn-action-icon" title="Modifica Prodotto" onclick="event.stopPropagation(); editProduct(${item.id})">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
      </button>
    `;

    // Action buttons html
    const actionBtnsHtml = `
      <div class="action-btns">
        <button class="btn-action-icon" title="Stima Prezzi eBay" onclick="event.stopPropagation(); openEbayPriceLookup('${item.name.replace(/'/g, "\\'")}')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </button>
        ${editBtnHtml}
        <button class="btn-action-icon delete" title="Elimina" onclick="event.stopPropagation(); deleteProduct(${item.id})">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
        </button>
      </div>
    `;

    if (isStockView) {
      tr.innerHTML = `
        <td class="col-prod" title="${item.name}">
          <div class="product-cell">
            <div class="product-name">${item.name}</div>
            <div class="product-brand">${item.purchasedPlace || "In Magazzino"}</div>
          </div>
        </td>
        <td class="col-size col-center"><strong>${item.size}</strong></td>
        <td class="col-qty col-center">${item.quantity} pz</td>
        <td class="col-buy">${formatMoney(item.purchasedPrice)}</td>
        <td class="col-place" style="color: var(--text-muted);">${item.purchasedPlace}</td>
        <td class="col-status col-center">
          <span class="status-badge ${statusClass}">
            <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
            ${statusLabel}
          </span>
        </td>
        <td class="col-actions col-center">
          ${actionBtnsHtml}
        </td>
      `;
    } else {
      // Calcolo Utile & ROI
      const netProfit = (item.salePrice || 0) - item.purchasedPrice - (item.fees || 0);
      const roi = item.purchasedPrice > 0 ? (netProfit / item.purchasedPrice) * 100 : 0;
      const hasSaleData = item.status === "completed" || item.status === "active-sale";
      const salePriceHtml = hasSaleData && item.salePrice ? formatMoney(item.salePrice) : `<span style="color:var(--text-dim)">-</span>`;
      const sellingPlaceHtml = hasSaleData && item.sellingPlace ? `<span style="font-size: 11.5px; color: var(--text-muted);">${item.sellingPlace}</span>` : `<span style="color:var(--text-dim)">-</span>`;
      const profitHtml = hasSaleData ? `<span class="profit-pos">+${formatMoney(netProfit)}</span>` : `<span style="color:var(--text-dim)">-</span>`;
      const roiHtml = hasSaleData ? `<span class="roi-badge">+${roi.toFixed(1)}%</span>` : `<span style="color:var(--text-dim)">-</span>`;

      tr.innerHTML = `
        <td class="col-prod" title="${item.name}">
          <div class="product-cell">
            <div class="product-name">${item.name}</div>
            <div class="product-brand">${item.purchasedPlace || "Canale Diretto"}</div>
          </div>
        </td>
        <td class="col-size col-center"><strong>${item.size}</strong></td>
        <td class="col-qty col-center">${item.quantity} pz</td>
        <td class="col-buy">${formatMoney(item.purchasedPrice)}</td>
        <td class="col-sell">${salePriceHtml}</td>
        <td class="col-channel">${sellingPlaceHtml}</td>
        <td class="col-profit">${profitHtml}</td>
        <td class="col-roi col-center">${roiHtml}</td>
        <td class="col-status col-center">
          <span class="status-badge ${statusClass}">
            <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
            ${statusLabel}
          </span>
        </td>
        <td class="col-actions col-center">
          ${actionBtnsHtml}
        </td>
      `;
    }

    // Apertura Side-Drawer con click singolo o doppio tap sulla riga
    tr.addEventListener("click", () => openDrawer(item.id));
    tr.addEventListener("dblclick", () => openDrawer(item.id));

    tbody.appendChild(tr);
  });
}

// ==========================================================================
// CHARTS INITIALIZATION (CHART.JS) & TIMEFRAME FILTERS
// ==========================================================================
let currentProfitTimeframe = "year"; // 'all', 'year', '6m'

function setProfitTimeframe(range) {
  currentProfitTimeframe = range;
  document.querySelectorAll(".timeframe-pill").forEach((pill) => {
    pill.classList.toggle("active", pill.getAttribute("data-range") === range);
  });
  updateMonthlyChart();
}

function updateMonthlyChart() {
  if (!monthlyProfitChart) return;
  let dataset = (realMonthlySales && realMonthlySales.length > 0) ? [...realMonthlySales] : [];

  if (currentProfitTimeframe === "6m") {
    dataset = dataset.slice(-6);
  } else if (currentProfitTimeframe === "year") {
    dataset = dataset.slice(-12);
  }

  const itMonths = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"];
  let labels = [];
  let data = [];

  if (dataset.length > 0) {
    labels = dataset.map((m) => {
      const parts = String(m.month || "").split("-");
      if (parts.length === 2) {
        const mIdx = parseInt(parts[1], 10) - 1;
        const yr = parts[0].slice(2);
        return `${itMonths[mIdx] || parts[1]} '${yr}`;
      }
      return m.month || "Mese";
    });
    data = dataset.map((m) => Number(m.profit || 0));
  } else {
    labels = ["Nessun dato vendite"];
    data = [0];
  }

  monthlyProfitChart.data.labels = labels;
  monthlyProfitChart.data.datasets[0].data = data;
  monthlyProfitChart.update();
}

function initCharts() {
  if (typeof Chart === "undefined") {
    console.warn("Chart.js non ancora caricato.");
    return;
  }

  if (monthlyProfitChart) {
    try { monthlyProfitChart.destroy(); } catch (_) {}
    monthlyProfitChart = null;
  }
  if (platformPieChart) {
    try { platformPieChart.destroy(); } catch (_) {}
    platformPieChart = null;
  }

  // Chart 1: Andamento Profitto Mensile Reale (dal database SQLite)
  const ctxMonthly = document.getElementById("monthlyProfitChart");
  if (ctxMonthly) {
    const gradient = ctxMonthly.getContext("2d").createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, "rgba(99, 102, 241, 0.45)");
    gradient.addColorStop(1, "rgba(99, 102, 241, 0.0)");

    monthlyProfitChart = new Chart(ctxMonthly, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Utile Netto (€)",
            data: [],
            borderColor: "#6366f1",
            borderWidth: 3,
            fill: true,
            backgroundColor: gradient,
            tension: 0.38,
            pointBackgroundColor: "#818cf8",
            pointBorderColor: "#111827",
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 8
          }
        ]
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#111827",
            titleColor: "#f8fafc",
            bodyColor: "#a5b4fc",
            borderColor: "rgba(99, 102, 241, 0.4)",
            borderWidth: 1,
            padding: 12,
            displayColors: false,
            callbacks: {
              label: (context) => ` Utile: € ${Number(context.parsed.y).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            }
          }
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#94a3b8", font: { size: 11 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: {
              color: "#94a3b8",
              font: { size: 11 },
              callback: (value) => `€ ${Number(value).toLocaleString("it-IT")}`
            }
          }
        }
      }
    });

    updateMonthlyChart();
  }

  // Chart 2: Piattaforme Reale (dal database SQLite)
  const ctxPlatform = document.getElementById("platformPieChart");
  if (ctxPlatform) {
    let platLabels = [];
    let platData = [];
    const platColors = ["#6366f1", "#10b981", "#8b5cf6", "#f59e0b", "#3b82f6", "#ec4899", "#14b8a6"];

    if (realPlatformProfits && realPlatformProfits.length > 0) {
      platLabels = realPlatformProfits.map((p) => p.platform || "Altro");
      platData = realPlatformProfits.map((p) => Math.max(0, Number(p.profit || 0)));
    } else if (metricsData && metricsData.platforms && Object.keys(metricsData.platforms).length > 0) {
      platLabels = Object.keys(metricsData.platforms);
      platData = Object.values(metricsData.platforms);
    } else {
      platLabels = ["Nessuna vendita"];
      platData = [1];
    }

    platformPieChart = new Chart(ctxPlatform, {
      type: "doughnut",
      data: {
        labels: platLabels,
        datasets: [
          {
            data: platData,
            backgroundColor: platColors.slice(0, platLabels.length),
            borderWidth: 2,
            borderColor: "#101726",
            hoverOffset: 4
          }
        ]
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        layout: {
          padding: {
            top: 2,
            bottom: 4,
            left: 6,
            right: 6
          }
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#94a3b8",
              boxWidth: 8,
              boxHeight: 8,
              padding: 8,
              font: { size: 10.5 }
            }
          },
          tooltip: {
            backgroundColor: "#111827",
            borderColor: "rgba(255, 255, 255, 0.1)",
            borderWidth: 1,
            callbacks: {
              label: (context) => ` ${context.label}: ${context.parsed}% delle vendite`
            }
          }
        }
      }
    });
  }
}

// ==========================================================================
// MODAL CONTROLLERS & ACTIONS
// ==========================================================================
function openAddProductModal() {
  currentEditingId = null;
  closeDrawer();
  closeModal();
  const modal = document.getElementById("productModal");
  if (!modal) return;
  modal.classList.add("open");

  const modalTitle = document.querySelector("#productModal .modal-header h3");
  if (modalTitle) modalTitle.textContent = "Aggiungi Nuovo Prodotto";
  const submitBtn = document.querySelector("#productModal .modal-footer button[type='submit']");
  if (submitBtn) submitBtn.textContent = "Salva nel Database";

  // Reset form pulito al 100% (senza dati fittizi)
  document.getElementById("prod-name").value = "";
  document.getElementById("prod-size").value = "";
  document.getElementById("prod-qty").value = "1";
  document.getElementById("prod-buy-price").value = "";
  document.getElementById("prod-buy-place").value = "";
  document.getElementById("prod-sell-place").value = "";
  document.getElementById("prod-status").value = "stock";

  const soldGroup = document.getElementById("prod-sold-price-group");
  if (soldGroup) soldGroup.style.display = "none";
  const soldPriceInput = document.getElementById("prod-sold-price");
  if (soldPriceInput) soldPriceInput.value = "";
}

function onModalStatusChange(val) {
  const soldGroup = document.getElementById("prod-sold-price-group");
  if (soldGroup) {
    soldGroup.style.display = (val === "completed") ? "block" : "none";
  }
}

function closeModal() {
  ["productModal", "ebayModal", "aiModal", "emailSyncModal"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.remove("open");
  });
}

// ==========================================================================
// SIDE-DRAWER OVERLAY CONTROLLERS (DETTAGLIO A COMPARSA DA DESTRA)
// ==========================================================================
let currentDrawerItem = null;

function openDrawer(id) {
  closeModal();
  const item = inventoryData.find((i) => i.id === id);
  if (!item) return;
  currentDrawerItem = item;

  const netProfit = (item.salePrice || 0) - item.purchasedPrice - (item.fees || 0);
  const roi = item.purchasedPrice > 0 ? (netProfit / item.purchasedPrice) * 100 : 0;
  const hasSaleData = item.status === "completed" || item.status === "active-sale";

  const drawerId = document.getElementById("drawerId");
  const drawerTitle = document.getElementById("drawerTitle");
  const drawerPlace = document.getElementById("drawerPlace") || document.getElementById("drawerBrand");
  const drawerBuyPrice = document.getElementById("drawerBuyPrice");
  const drawerSellPrice = document.getElementById("drawerSellPrice");
  const drawerProfit = document.getElementById("drawerProfit");
  const drawerSize = document.getElementById("drawerSize");
  const drawerQty = document.getElementById("drawerQty");
  const drawerStore = document.getElementById("drawerStore");
  const drawerDate = document.getElementById("drawerDate");
  const drawerChannel = document.getElementById("drawerChannel");
  const drawerRoi = document.getElementById("drawerRoi");
  const drawerFees = document.getElementById("drawerFees");
  const drawerNotes = document.getElementById("drawerNotes");

  if (drawerId) drawerId.textContent = item.id;
  if (drawerTitle) drawerTitle.textContent = item.name;
  if (drawerPlace) drawerPlace.textContent = item.purchasedPlace ? `Luogo Acquisto: ${item.purchasedPlace}` : "Acquisto Diretto";
  if (drawerBuyPrice) drawerBuyPrice.textContent = formatMoney(item.purchasedPrice);
  if (drawerSellPrice) drawerSellPrice.textContent = item.salePrice ? formatMoney(item.salePrice) : "-";

  if (drawerProfit) {
    if (hasSaleData) {
      drawerProfit.textContent = `+${formatMoney(netProfit)}`;
      drawerProfit.className = "drawer-metric-val profit";
    } else {
      drawerProfit.textContent = "-";
      drawerProfit.className = "drawer-metric-val";
    }
  }

  if (drawerSize) drawerSize.textContent = item.size;
  if (drawerQty) drawerQty.textContent = `${item.quantity} pz`;
  if (drawerStore) drawerStore.textContent = item.purchasedPlace || "Store Ufficiale";
  if (drawerDate) drawerDate.textContent = item.date || "Recente";
  if (drawerChannel) drawerChannel.textContent = item.sellingPlace || "-";
  if (drawerRoi) drawerRoi.textContent = hasSaleData ? `+${roi.toFixed(1)}%` : "-";
  if (drawerFees) drawerFees.textContent = item.fees ? formatMoney(item.fees) : "€ 0,00";

  if (drawerNotes) {
    drawerNotes.textContent = item.notes || `Prodotto autentico verificato (${item.name}). Condizioni perfette DSWT, scatola integra e accessori originali inclusi.`;
  }

  // Badge di stato
  const badgeEl = document.getElementById("drawerStatusBadge");
  const textEl = document.getElementById("drawerStatusText");
  let statusClass = "stock";
  let statusLabel = "In Magazzino";
  if (item.status === "preorder") {
    statusClass = "preorder";
    statusLabel = "Pre-ordine";
  } else if (item.status === "active-sale") {
    statusClass = "active-sale";
    statusLabel = "In Vendita";
  } else if (item.status === "completed") {
    statusClass = "completed";
    statusLabel = "Venduto";
  }

  if (badgeEl) badgeEl.className = `status-badge ${statusClass}`;
  if (textEl) textEl.textContent = statusLabel;

  // Timeline Eventi
  const timelineEl = document.getElementById("drawerTimeline");
  if (timelineEl) {
    let timelineHtml = `
      <div class="drawer-timeline-step completed">
        <div class="drawer-timeline-title">Acquisto Confermato</div>
        <div class="drawer-timeline-date">${item.date || "Ricevuto"} • Store: ${item.purchasedPlace || "Ufficiale"}</div>
      </div>
    `;

    if (item.status === "stock" || item.status === "active-sale" || item.status === "completed") {
      timelineHtml += `
        <div class="drawer-timeline-step completed">
          <div class="drawer-timeline-title">Arrivato in Magazzino</div>
          <div class="drawer-timeline-date">Controllo integrità e taglia completato</div>
        </div>
      `;
    }

    if (item.status === "active-sale" || item.status === "completed") {
      timelineHtml += `
        <div class="drawer-timeline-step completed">
          <div class="drawer-timeline-title">Inserzione Attiva</div>
          <div class="drawer-timeline-date">Piattaforma: ${item.sellingPlace || "Marketplace"}</div>
        </div>
      `;
    }

    if (item.status === "completed") {
      timelineHtml += `
        <div class="drawer-timeline-step completed">
          <div class="drawer-timeline-title">Vendita Conclusa & Accreditata</div>
          <div class="drawer-timeline-date">Utile netto incassato: +€ ${netProfit.toFixed(2)}</div>
        </div>
      `;
    } else if (item.status === "preorder") {
      timelineHtml += `
        <div class="drawer-timeline-step">
          <div class="drawer-timeline-title">In Transito verso Magazzino</div>
          <div class="drawer-timeline-date">In attesa di consegna corriere</div>
        </div>
      `;
    }

    timelineEl.innerHTML = timelineHtml;
  }

  // Pulsanti del Footer Drawer
  const ebayBtn = document.getElementById("drawerEbayBtn");
  const editBtn = document.getElementById("drawerEditBtn");
  const statusBtn = document.getElementById("drawerStatusActionBtn");

  if (ebayBtn) {
    ebayBtn.onclick = () => {
      closeDrawer();
      openEbayPriceLookup(item.name);
    };
  }

  // Le vendite completate non consentono modifiche né ripristino in stock
  if (item.status === "completed") {
    if (editBtn) editBtn.style.display = "none";
    if (statusBtn) statusBtn.style.display = "none";
  } else {
    if (editBtn) {
      editBtn.style.display = "inline-flex";
      editBtn.onclick = () => {
        closeDrawer();
        editProduct(item.id);
      };
    }
    if (statusBtn) {
      statusBtn.style.display = "inline-flex";
      statusBtn.textContent = "Segna Venduto";
      statusBtn.className = "btn btn-primary";
      statusBtn.onclick = () => {
        closeDrawer();
        editProduct(item.id);
      };
    }
  }

  const backdrop = document.getElementById("drawerBackdrop");
  const drawer = document.getElementById("sideDrawer");
  if (backdrop) backdrop.classList.add("open");
  if (drawer) drawer.classList.add("open");
}

function closeDrawer() {
  const backdrop = document.getElementById("drawerBackdrop");
  const drawer = document.getElementById("sideDrawer");
  if (backdrop) backdrop.classList.remove("open");
  if (drawer) drawer.classList.remove("open");
  currentDrawerItem = null;
}

function updateModalProfitPreview() {}

async function handleSaveProduct(e) {
  e.preventDefault();
  const name = document.getElementById("prod-name").value.trim();
  const size = document.getElementById("prod-size").value.trim();
  const quantity = parseInt(document.getElementById("prod-qty").value, 10) || 1;
  const purchasedPrice = parseFloat(document.getElementById("prod-buy-price").value) || 0;
  const purchasedPlace = document.getElementById("prod-buy-place").value.trim();
  const sellingPlace = document.getElementById("prod-sell-place").value.trim();
  const status = document.getElementById("prod-status").value;

  const isSold = (status === "completed");
  const soldPriceEl = document.getElementById("prod-sold-price");
  const salePrice = isSold && soldPriceEl ? (parseFloat(soldPriceEl.value) || null) : null;

  if (!name) {
    showToast("⚠️ Inserisci un nome per il prodotto!");
    return;
  }

  const existingItem = currentEditingId ? inventoryData.find((i) => i.id === currentEditingId) : null;
  const payload = {
    name,
    size,
    quantity,
    purchasedPrice,
    purchasedPlace,
    sellingPlace,
    salePrice,
    fees: salePrice ? salePrice * 0.08 : 0,
    status,
    date: (existingItem && existingItem.date) ? existingItem.date : new Date().toISOString().split("T")[0]
  };

  try {
    let res;
    const isEdit = Boolean(currentEditingId);
    if (isEdit) {
      res = await callApi(`/products/${currentEditingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } else {
      res = await callApi("/products", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }

    const result = await res.json();
    if (result.success) {
      closeModal();
      currentEditingId = null;
      await loadProductsFromBackend();
      showToast(isEdit ? `✅ "${name}" aggiornato nel database!` : `✅ "${name}" salvato nel database!`);
    } else {
      showToast(`❌ Errore: ${result.error || "Salvataggio non riuscito"}`);
    }
  } catch (err) {
    showToast(`❌ Errore di rete: ${err.message}`);
  }
}

async function deleteProduct(id) {
  const item = inventoryData.find((i) => i.id === id);
  if (!item) return;

  if (confirm(`Confermi l'eliminazione di "${item.name}" dal database SQLite?`)) {
    try {
      const res = await callApi(`/products/${id}`, { method: "DELETE" });
      const result = await res.json();
      if (result.success) {
        closeDrawer();
        await loadProductsFromBackend();
        showToast(`🗑️ "${item.name}" rimosso dal database.`);
      } else {
        showToast(`❌ Errore eliminazione: ${result.error}`);
      }
    } catch (err) {
      showToast(`❌ Errore di rete: ${err.message}`);
    }
  }
}

function editProduct(id) {
  const item = inventoryData.find((i) => i.id === id);
  if (!item) return;
  if (item.status === "completed") {
    showToast("⚠️ Le vendite completate non possono essere modificate.");
    return;
  }
  closeDrawer();
  closeModal();
  openAddProductModal();
  // Assegna l'ID DOPO openAddProductModal (per non essere azzerato a null)
  currentEditingId = id;

  const modalTitle = document.querySelector("#productModal .modal-header h3");
  if (modalTitle) modalTitle.textContent = `Modifica Prodotto #${id}`;
  const submitBtn = document.querySelector("#productModal .modal-footer button[type='submit']");
  if (submitBtn) submitBtn.textContent = "Aggiorna Prodotto";

  document.getElementById("prod-name").value = item.name || "";
  document.getElementById("prod-size").value = item.size || "";
  document.getElementById("prod-qty").value = item.quantity || 1;
  document.getElementById("prod-buy-price").value = item.purchasedPrice || 0;
  document.getElementById("prod-buy-place").value = item.purchasedPlace || "";
  document.getElementById("prod-sell-place").value = item.sellingPlace || "";
  document.getElementById("prod-status").value = item.status || "stock";

  const isSold = (item.status === "completed" || item.status === "active-sale");
  const soldGroup = document.getElementById("prod-sold-price-group");
  const soldPriceInput = document.getElementById("prod-sold-price");
  if (soldGroup) soldGroup.style.display = isSold ? "block" : "none";
  if (soldPriceInput) soldPriceInput.value = item.salePrice || "";
}

// ==========================================================================
// FUNZIONALITÀ REALI RSM (eBay, AI, Sync Email)
// ==========================================================================
async function openEbayPriceLookup(productName, size = "") {
  closeDrawer();
  closeModal();
  const modal = document.getElementById("ebayModal");
  if (!modal) return;
  modal.classList.add("open");

  document.getElementById("ebay-query-title").textContent = productName;
  document.getElementById("ebay-loading").style.display = "block";
  document.getElementById("ebay-results").style.display = "none";

  try {
    const url = `${API_BASE}/ebay-prices?name=${encodeURIComponent(productName)}&size=${encodeURIComponent(size || "")}`;
    const res = await fetch(url);
    const json = await res.json();
    document.getElementById("ebay-loading").style.display = "none";

    if (json.success && json.data) {
      document.getElementById("ebay-results").style.display = "block";
      const { avg, min, max, count } = json.data;
      document.getElementById("ebay-avg-val").textContent = `€ ${avg.toLocaleString("it-IT", { minimumFractionDigits: 2 })}`;
      document.getElementById("ebay-rec-val").textContent = `€ ${min.toLocaleString("it-IT", { minimumFractionDigits: 2 })} - € ${max.toLocaleString("it-IT", { minimumFractionDigits: 2 })}`;
      document.getElementById("ebay-vol-val").textContent = `${count} inserzioni attive`;
    } else {
      showToast(`⚠️ eBay: ${json.error || "Nessun risultato trovato"}`);
      closeModal();
    }
  } catch (err) {
    document.getElementById("ebay-loading").style.display = "none";
    showToast(`❌ Errore ricerca eBay: ${err.message}`);
    closeModal();
  }
}

// ==========================================================================
// ASSISTENTE AI GEMINI (INSERIMENTO RAPIDO - IDENTICO AD AIDIALOG)
// ==========================================================================
let aiExtractedProducts = [];
let speechRecognitionInstance = null;
let isVoiceRecording = false;

function openAIModal() {
  closeDrawer();
  closeModal();
  const modal = document.getElementById("aiModal");
  if (!modal) return;
  modal.classList.add("open");

  document.getElementById("ai-prompt-text").value = "";
  document.getElementById("ai-status-msg").textContent = "Scrivi o detta i prodotti da inserire.";
  document.getElementById("ai-results-wrap").style.display = "none";
  document.getElementById("btn-ai-save-all").style.display = "none";
  document.getElementById("btn-ai-analyze").disabled = false;
  aiExtractedProducts = [];
}

async function toggleVoiceRecording() {
  const btn = document.getElementById("btn-mic");
  const statusEl = document.getElementById("ai-status-msg");
  const promptEl = document.getElementById("ai-prompt-text");

  if (!isVoiceRecording) {
    // 1° Clic: Avvia registrazione con microfono di sistema
    isVoiceRecording = true;
    if (btn) btn.classList.add("recording");
    if (statusEl) statusEl.textContent = "Microfono attivo: parla ora... (clicca di nuovo sul microfono per terminare e trascrivere)";

    try {
      const res = await fetch(`${API_BASE}/speech/start`, { method: "POST" });
      const json = await res.json();
      if (!json.success) {
        throw new Error(json.error || "Impossibile attivare il microfono");
      }
    } catch (err) {
      isVoiceRecording = false;
      if (btn) btn.classList.remove("recording");
      if (statusEl) statusEl.textContent = `⚠️ Errore microfono: ${err.message}`;
      showToast(`Errore microfono: ${err.message}`);
    }
  } else {
    // 2° Clic: Arresta registrazione e trascrivi con Gemini
    isVoiceRecording = false;
    if (btn) btn.classList.remove("recording");
    if (statusEl) statusEl.textContent = "Elaborazione audio e trascrizione con Gemini in corso...";

    try {
      const res = await fetch(`${API_BASE}/speech/stop`, { method: "POST" });
      const json = await res.json();
      if (json.success && json.text) {
        if (statusEl) statusEl.textContent = "Trascrizione vocale completata con successo!";
        const current = promptEl.value.trim();
        promptEl.value = current ? `${current} ${json.text}` : json.text;
        showToast("Audio trascritto con successo!");
      } else {
        const errMsg = json.error || "Nessun parlato rilevato";
        if (statusEl) statusEl.textContent = `⚠️ ${errMsg}`;
        showToast(`Trascrizione: ${errMsg}`);
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = `⚠️ Errore trascrizione: ${err.message}`;
      showToast(`Errore: ${err.message}`);
    }
  }
}

async function handleAIAnalyze() {
  const prompt = document.getElementById("ai-prompt-text").value.trim();
  const statusEl = document.getElementById("ai-status-msg");
  const btnAnalyze = document.getElementById("btn-ai-analyze");

  if (!prompt) {
    showToast("Scrivi o detta i prodotti prima di analizzare.");
    return;
  }

  btnAnalyze.disabled = true;
  statusEl.textContent = "Analisi del testo con Gemini in corso...";

  try {
    const res = await fetch(`${API_BASE}/ai-parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt })
    });
    const json = await res.json();
    btnAnalyze.disabled = false;

    if (!res.ok || !json.success) {
      const errMsg = json.error || `Errore server (${res.status})`;
      statusEl.textContent = `⚠️ ${errMsg}`;
      showToast(`Errore AI: ${errMsg}`);
      return;
    }

    if (!Array.isArray(json.data) || json.data.length === 0) {
      statusEl.textContent = "Nessun prodotto valido rilevato nel testo. Prova a specificare nome o dettagli del prodotto.";
      showToast("Nessun prodotto valido rilevato dall'AI.");
      return;
    }

    aiExtractedProducts = json.data;
    statusEl.textContent = `Rilevati ${aiExtractedProducts.length} prodotti con successo!`;

    const tbody = document.getElementById("ai-results-body");
    tbody.innerHTML = "";
    aiExtractedProducts.forEach((p) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${p.name || "Sconosciuto"}</strong></td>
        <td>${p.size || "UNI"}</td>
        <td>${p.quantity || 1} pz</td>
        <td>${formatMoney(p.purchased_price || 0)}</td>
        <td style="color:var(--text-muted);">${p.purchased_place || "-"}</td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("ai-results-wrap").style.display = "block";
    document.getElementById("btn-ai-save-all").style.display = "inline-flex";
  } catch (err) {
    btnAnalyze.disabled = false;
    statusEl.textContent = "Errore durante l'analisi AI.";
    showToast(`Errore AI: ${err.message}`);
  }
}

async function handleAISaveAll() {
  if (!aiExtractedProducts || aiExtractedProducts.length === 0) return;
  const btnSave = document.getElementById("btn-ai-save-all");
  btnSave.disabled = true;

  try {
    let res = await fetch(`${API_BASE}/products-batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ products: aiExtractedProducts })
    });
    // Fallback sicuro se un bridge precedente non ha la route separata
    if (res.status === 404) {
      res = await fetch(`${API_BASE}/products`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ products: aiExtractedProducts })
      });
    }
    const json = await res.json();
    if (json.success) {
      showToast(`${json.inserted_count || aiExtractedProducts.length} prodotti salvati con successo in SQLite!`);
      closeModal();
      await loadProductsFromBackend();
    } else {
      showToast(`Errore salvataggio: ${json.error || "Operazione non riuscita"}`);
    }
  } catch (err) {
    showToast(`Errore: ${err.message}`);
  } finally {
    btnSave.disabled = false;
  }
}

// ==========================================================================
// SINCRONIZZAZIONE EMAIL GMAIL (IDENTICO AD EMAILSYNCDIALOG)
// ==========================================================================
let emailScannedItems = [];

async function openEmailSyncModal() {
  closeDrawer();
  closeModal();
  const modal = document.getElementById("emailSyncModal");
  if (!modal) return;
  modal.classList.add("open");

  document.getElementById("email-scan-status").textContent = "Pronto per la scansione delle email.";
  document.getElementById("email-sync-count-info").textContent = "Nessun prodotto in attesa di importazione.";
  document.getElementById("btn-save-email-preorders").style.display = "none";
  emailScannedItems = [];

  // Carica credenziali correnti dal database
  try {
    const res = await fetch(`${API_BASE}/settings`);
    if (res.ok) {
      const data = await res.json();
      if (data.email_sync_address) {
        document.getElementById("email-sync-address").value = data.email_sync_address;
      }
    }
  } catch (_) {}
}

function toggleEmailPwdVisibility(show) {
  const pwdInput = document.getElementById("email-sync-pwd");
  if (pwdInput) {
    pwdInput.type = show ? "text" : "password";
  }
}

async function saveEmailCredentials() {
  const email = document.getElementById("email-sync-address").value.trim();
  const pwd = document.getElementById("email-sync-pwd").value.replace(/\s+/g, "").trim();

  if (!email || !pwd) {
    showToast("Inserisci l'indirizzo Gmail e la Password per le App a 16 caratteri.");
    return;
  }

  try {
    const res = await callApi("/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_sync_address: email, email_sync_app_password: pwd })
    });
    const json = await res.json();
    if (json.success) {
      showToast("Credenziali email salvate con successo nel database!");
    } else {
      showToast(`Errore salvataggio: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore: ${err.message}`);
  }
}

async function testEmailConnection() {
  const email = document.getElementById("email-sync-address").value.trim();
  const pwd = document.getElementById("email-sync-pwd").value.replace(/\s+/g, "").trim();
  const statusEl = document.getElementById("email-scan-status");

  if (!email || !pwd) {
    showToast("Compila prima Email e Password per le App.");
    return;
  }

  statusEl.textContent = "Verifica connessione a Gmail in corso...";
  try {
    const res = await callApi("/test-email-connection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_sync_address: email, email_sync_app_password: pwd })
    });
    const json = await res.json();
    if (json.success) {
      statusEl.textContent = "Connessione a Gmail stabilita con successo!";
      showToast("Connessione a Gmail riuscita!");
    } else {
      statusEl.textContent = "Errore di connessione a Gmail.";
      showToast(`Connessione fallita: ${json.error || json.message}`);
    }
  } catch (err) {
    statusEl.textContent = "Errore durante il test di connessione.";
    showToast(`Errore: ${err.message}`);
  }
}

async function startEmailScan() {
  const email = document.getElementById("email-sync-address").value.trim();
  const pwd = document.getElementById("email-sync-pwd").value.replace(/\s+/g, "").trim();
  const statusEl = document.getElementById("email-scan-status");
  const btnScan = document.getElementById("btn-start-email-scan");
  const tbody = document.getElementById("email-sync-table-body");
  const countInfo = document.getElementById("email-sync-count-info");
  const btnSave = document.getElementById("btn-save-email-preorders");

  if (!email || !pwd) {
    showToast("Inserisci Email e Password per le App prima di avviare la scansione.");
    return;
  }

  btnScan.disabled = true;
  statusEl.textContent = "Connessione a Gmail e ricerca nuove email non lette...";

  try {
    const res = await callApi("/scan-emails", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_sync_address: email, email_sync_app_password: pwd })
    });
    const json = await res.json();
    btnScan.disabled = false;

    if (!res.ok || !json.success) {
      statusEl.textContent = "Errore durante la scansione.";
      showToast(`Scansione fallita: ${json.error || "Impossibile leggere la casella Gmail."}`);
      return;
    }

    emailScannedItems = json.items || [];
    const scannedCount = json.emails_scanned || 0;

    if (emailScannedItems.length === 0) {
      statusEl.textContent = `Scansione completata: ${scannedCount} email analizzate, nessun prodotto nuovo rilevato.`;
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-dim); padding:20px;">Nessuna nuova email d'ordine rilevata nella casella INBOX.</td></tr>`;
      countInfo.textContent = "Nessun prodotto da importare.";
      btnSave.style.display = "none";
      return;
    }

    statusEl.textContent = `Scansione completata: ${emailScannedItems.length} prodotti trovati in ${scannedCount} email.`;
    countInfo.textContent = `${emailScannedItems.length} prodotti pronti per l'importazione nei Pre-ordini.`;
    btnSave.style.display = "inline-flex";

    tbody.innerHTML = "";
    emailScannedItems.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${item.name}</strong></td>
        <td class="col-center"><strong>${item.size || "UNI"}</strong></td>
        <td class="col-center">${item.quantity || 1} pz</td>
        <td class="col-center">${formatMoney(item.price || 0)}</td>
        <td>${item.store || "Email"}</td>
        <td class="col-center" style="color:var(--text-muted);">${item.date || "-"}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    btnScan.disabled = false;
    statusEl.textContent = "Errore durante la scansione.";
    showToast(`Errore: ${err.message}`);
  }
}

async function saveEmailPreorders() {
  if (!emailScannedItems || emailScannedItems.length === 0) return;
  const btnSave = document.getElementById("btn-save-email-preorders");
  btnSave.disabled = true;

  const uids = emailScannedItems.map((i) => i.uid).filter(Boolean);

  try {
    const res = await callApi("/save-scanned-emails", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: emailScannedItems, uids })
    });
    const json = await res.json();
    if (json.success) {
      showToast(`${json.saved_count} pre-ordini importati con successo dalle email!`);
      closeModal();
      await loadProductsFromBackend();
    } else {
      showToast(`Errore salvataggio: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore: ${err.message}`);
  } finally {
    btnSave.disabled = false;
  }
}

// Toast Helper
function showToast(message) {
  const toast = document.getElementById("toastNotification");
  if (!toast) return;
  toast.innerHTML = `<span>${message}</span>`;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 3200);
}

// ==========================================================================
// EVENT LISTENERS & INIZIALIZZAZIONE
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
  loadProductsFromBackend();
  initCharts();
  updateDashboardMetrics();
  renderTable();

  // Resize automatico al termine animazione apertura/chiusura sidebar
  const sidebar = document.getElementById("appSidebar");
  if (sidebar) {
    sidebar.addEventListener("transitionend", () => {
      if (monthlyProfitChart) monthlyProfitChart.resize();
      if (platformPieChart) platformPieChart.resize();
    });
  }

  // Observer per mantenere sempre proporzionati e precisi i grafici
  const chartsGrid = document.querySelector(".charts-grid");
  if (chartsGrid && window.ResizeObserver) {
    let resizeTimer = null;
    const ro = new ResizeObserver(() => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (monthlyProfitChart) monthlyProfitChart.resize();
        if (platformPieChart) platformPieChart.resize();
      }, 40);
    });
    ro.observe(chartsGrid);
  }

  // Search input live filtering
  const searchInput = document.getElementById("global-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      searchTerm = e.target.value;
      renderTable();
    });
  }

  // Filter Pills (Tutti, Magazzino, Pre-ordini, ecc.)
  document.querySelectorAll(".table-tab-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".table-tab-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeFilter = pill.getAttribute("data-filter");
      renderTable();
    });
  });

  // Sidebar navigation switching
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((i) => i.classList.remove("active"));
      item.classList.add("active");

      const section = item.getAttribute("data-section");
      if (section === "magazzino") {
        activeFilter = "stock";
      } else if (section === "preordini") {
        activeFilter = "preorder";
      } else if (section === "vendite") {
        activeFilter = "active-sale";
      } else if (section === "storico") {
        activeFilter = "completed";
      } else {
        activeFilter = "all";
      }

      // Sincronizza anche la pill attiva
      document.querySelectorAll(".table-tab-pill").forEach((pill) => {
        if (pill.getAttribute("data-filter") === activeFilter) {
          pill.classList.add("active");
        } else {
          pill.classList.remove("active");
        }
      });

      renderTable();
      showToast(`Visualizzazione: ${item.querySelector("span").textContent}`);
    });
  });



  // Delegazione click per ordinamento colonne tabella
  const tableHead = document.getElementById("inventory-table-head");
  if (tableHead) {
    tableHead.addEventListener("click", (e) => {
      const th = e.target.closest("th.sortable");
      if (!th) return;
      const field = th.getAttribute("data-sort");
      if (!field) return;

      if (sortField === field) {
        sortOrder = sortOrder === "asc" ? "desc" : "asc";
      } else {
        sortField = field;
        sortOrder = "asc";
      }

      renderTable();
    });
  }

  // Form submit
  const form = document.getElementById("productForm");
  if (form) {
    form.addEventListener("submit", handleSaveProduct);
  }

  // Massimizza la finestra all'avvio per visualizzazione zoomed a schermo intero
  if (window.__TAURI__ && window.__TAURI__.window) {
    try {
      window.__TAURI__.window.appWindow.maximize();
    } catch (_) {}
  }

  // Chiusura rapida con tasto ESC
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
      closeModal();
    }
  });
});
