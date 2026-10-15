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
        updateFilterPlacesOptions();
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

// Filtri Avanzati di Tabella
let filterPurchasedPlace = "";
let filterSellingPlace = "";
let filterMinPrice = null;
let filterMaxPrice = null;

// Modalità Selezione Multipla & Operazioni Massive
let isSelectionModeActive = false;
let selectedProductIds = new Set();
let expandedBundles = new Set();

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
// FILTRI AVANZATI DI TABELLA (Luogo Acquisto, Luogo Vendita, Prezzo Min/Max)
// ==========================================================================
function updateFilterPlacesOptions() {
  const pSelect = document.getElementById("filter-purchased-place");
  const sSelect = document.getElementById("filter-selling-place");
  if (!pSelect || !sSelect) return;

  const currentP = pSelect.value;
  const currentS = sSelect.value;

  const purchasedSet = new Set();
  const sellingSet = new Set();

  inventoryData.forEach((item) => {
    if (item.purchasedPlace && item.purchasedPlace.trim()) {
      purchasedSet.add(item.purchasedPlace.trim());
    }
    if (item.sellingPlace && item.sellingPlace.trim()) {
      sellingSet.add(item.sellingPlace.trim());
    }
  });

  const pList = Array.from(purchasedSet).sort((a, b) => a.localeCompare(b));
  const sList = Array.from(sellingSet).sort((a, b) => a.localeCompare(b));

  pSelect.innerHTML = '<option value="">Tutti i luoghi</option>';
  pList.forEach((place) => {
    const opt = document.createElement("option");
    opt.value = place;
    opt.textContent = place;
    if (place === currentP) opt.selected = true;
    pSelect.appendChild(opt);
  });

  sSelect.innerHTML = '<option value="">Tutti i marketplace</option>';
  sList.forEach((place) => {
    const opt = document.createElement("option");
    opt.value = place;
    opt.textContent = place;
    if (place === currentS) opt.selected = true;
    sSelect.appendChild(opt);
  });
}

function toggleAdvancedFilters() {
  const panel = document.getElementById("advancedFiltersPanel");
  const btn = document.getElementById("btnToggleFilters");
  const arrow = document.getElementById("toggleFilterArrow");
  if (!panel) return;

  const isHidden = panel.style.display === "none";
  panel.style.display = isHidden ? "block" : "none";
  if (btn) btn.classList.toggle("active", isHidden);
  if (arrow) {
    arrow.style.transform = isHidden ? "rotate(180deg)" : "rotate(0deg)";
  }
}

function onFilterChanged() {
  const pSelect = document.getElementById("filter-purchased-place");
  const sSelect = document.getElementById("filter-selling-place");
  const minInput = document.getElementById("filter-min-price");
  const maxInput = document.getElementById("filter-max-price");

  filterPurchasedPlace = pSelect ? pSelect.value.trim() : "";
  filterSellingPlace = sSelect ? sSelect.value.trim() : "";

  const minVal = minInput && minInput.value !== "" ? parseFloat(minInput.value) : NaN;
  filterMinPrice = !isNaN(minVal) ? minVal : null;

  const maxVal = maxInput && maxInput.value !== "" ? parseFloat(maxInput.value) : NaN;
  filterMaxPrice = !isNaN(maxVal) ? maxVal : null;

  updateFilterIndicators();
  renderTable();
}

function updateFilterIndicators() {
  const hasActiveAdvanced = Boolean(
    filterPurchasedPlace ||
    filterSellingPlace ||
    (filterMinPrice !== null && filterMinPrice !== undefined) ||
    (filterMaxPrice !== null && filterMaxPrice !== undefined)
  );

  const hasAnyFilter = Boolean(hasActiveAdvanced || searchTerm);

  const btnToggle = document.getElementById("btnToggleFilters");
  if (btnToggle) {
    btnToggle.classList.toggle("has-active-filters", hasActiveAdvanced);
  }

  const btnReset = document.getElementById("btnResetFilters");
  if (btnReset) {
    btnReset.style.display = hasAnyFilter ? "inline-flex" : "none";
  }
}

function resetAllFilters() {
  searchTerm = "";
  const searchInput = document.getElementById("global-search-input");
  if (searchInput) searchInput.value = "";

  filterPurchasedPlace = "";
  const pSelect = document.getElementById("filter-purchased-place");
  if (pSelect) pSelect.value = "";

  filterSellingPlace = "";
  const sSelect = document.getElementById("filter-selling-place");
  if (sSelect) sSelect.value = "";

  filterMinPrice = null;
  const minInput = document.getElementById("filter-min-price");
  if (minInput) minInput.value = "";

  filterMaxPrice = null;
  const maxInput = document.getElementById("filter-max-price");
  if (maxInput) maxInput.value = "";

  sortField = "date";
  sortOrder = "desc";

  document.querySelectorAll(".sort-menu-item").forEach((item) => {
    item.classList.toggle("active", item.getAttribute("data-sort-key") === "date-desc");
  });

  updateFilterIndicators();
  renderTable();
}

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
  let stockCount = 0;
  let preorderCount = 0;
  let activeCount = 0;

  if (metricsData && metricsData.kpi) {
    const kpi = metricsData.kpi;
    totalInvested = kpi.totalInvested || 0;
    totalStockValue = kpi.totalStockValue || 0;
    totalProfit = kpi.totalProfit || 0;
    const avgRoi = kpi.avgRoi || 0;
    stockCount = kpi.stockCount || 0;
    preorderCount = kpi.preorderCount || 0;
    activeCount = kpi.activeSalesCount || 0;
    completedCount = kpi.completedSalesCount || 0;

    const kpiInvested = document.getElementById("kpi-invested");
    const kpiStock = document.getElementById("kpi-stock");
    const kpiProfit = document.getElementById("kpi-profit");
    const kpiRoi = document.getElementById("kpi-roi");
    const kpiInvestedSub = document.getElementById("kpi-invested-sub");
    const kpiStockSub = document.getElementById("kpi-stock-sub");
    const kpiProfitSub = document.getElementById("kpi-profit-sub");

    if (kpiInvested) setMetricValue(kpiInvested, totalInvested, true);
    if (kpiStock) setMetricValue(kpiStock, totalStockValue, true);
    if (kpiProfit) setMetricValue(kpiProfit, totalProfit, true);
    if (kpiRoi) {
      kpiRoi.textContent = `${avgRoi >= 0 ? "+" : ""}${avgRoi.toFixed(1)}% ROI`;
      kpiRoi.className = `kpi-trend ${avgRoi >= 0 ? "positive" : "negative"}`;
    }
    if (kpiInvestedSub) kpiInvestedSub.textContent = `${stockCount} in stock • ${preorderCount} pre-ordini`;
    if (kpiStockSub) kpiStockSub.textContent = `${stockCount} articoli a costo di carico`;
    if (kpiProfitSub) kpiProfitSub.textContent = `${completedCount} completate • ${activeCount} attive`;
  } else {
    // Calcolo fedele basato sullo stato reale dei prodotti SQLite
    inventoryData.forEach((item) => {
      const qty = item.quantity || 1;
      const cost = (item.purchasedPrice || 0) * qty;

      if (item.status === "stock") {
        totalInvested += cost;
        totalStockValue += cost;
        stockCount += qty;
      } else if (item.status === "preorder") {
        totalInvested += cost;
        preorderCount += qty;
      } else if (item.status === "completed" || item.status === "active-sale") {
        if (item.status === "active-sale") activeCount += qty;
        if (item.status === "completed") completedCount += qty;
        const sale = (item.salePrice || 0) * qty;
        const fees = (item.fees || 0) * qty;
        const profit = sale - cost - fees;
        totalProfit += profit;
        if (cost > 0) totalRoiSum += (profit / cost) * 100;
      }
    });

    const totalSold = completedCount + activeCount;
    const avgRoi = totalSold > 0 ? (totalRoiSum / totalSold) : 0;

    const kpiInvested = document.getElementById("kpi-invested");
    const kpiStock = document.getElementById("kpi-stock");
    const kpiProfit = document.getElementById("kpi-profit");
    const kpiRoi = document.getElementById("kpi-roi");
    const kpiInvestedSub = document.getElementById("kpi-invested-sub");
    const kpiStockSub = document.getElementById("kpi-stock-sub");
    const kpiProfitSub = document.getElementById("kpi-profit-sub");

    if (kpiInvested) setMetricValue(kpiInvested, totalInvested, true);
    if (kpiStock) setMetricValue(kpiStock, totalStockValue, true);
    if (kpiProfit) setMetricValue(kpiProfit, totalProfit, true);
    if (kpiRoi) {
      kpiRoi.textContent = `${avgRoi >= 0 ? "+" : ""}${avgRoi.toFixed(1)}% ROI`;
      kpiRoi.className = `kpi-trend ${avgRoi >= 0 ? "positive" : "negative"}`;
    }
    if (kpiInvestedSub) kpiInvestedSub.textContent = `${stockCount} in stock • ${preorderCount} pre-ordini`;
    if (kpiStockSub) kpiStockSub.textContent = `${stockCount} articoli a costo di carico`;
    if (kpiProfitSub) kpiProfitSub.textContent = `${completedCount} completate • ${activeCount} attive`;
  }

  // Aggiorna badge laterali
  const badgeStock = document.getElementById("badge-stock");
  const badgePreorder = document.getElementById("badge-preorder");
  const badgeActive = document.getElementById("badge-active");
  const badgeCompleted = document.getElementById("badge-completed");

  if (badgeStock) badgeStock.textContent = stockCount;
  if (badgePreorder) badgePreorder.textContent = preorderCount;
  if (badgeActive) badgeActive.textContent = activeCount;
  if (badgeCompleted) badgeCompleted.textContent = completedCount;
}

// ==========================================================================
// RENDER TABLE & FILTRAGGIO
// ==========================================================================
function getFilteredAndSortedProducts() {
  let filtered = inventoryData.filter((item) => {
    // 1. Filtro per stato tab
    if (activeFilter !== "all" && item.status !== activeFilter) return false;

    // 2. Filtro di ricerca testuale
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const match =
        item.name.toLowerCase().includes(term) ||
        item.size.toLowerCase().includes(term) ||
        (item.sellingPlace && item.sellingPlace.toLowerCase().includes(term)) ||
        (item.purchasedPlace && item.purchasedPlace.toLowerCase().includes(term));
      if (!match) return false;
    }

    // 3. Filtro Luogo di Acquisto
    if (filterPurchasedPlace) {
      if ((item.purchasedPlace || "").trim() !== filterPurchasedPlace) return false;
    }

    // 4. Filtro Luogo di Vendita
    if (filterSellingPlace) {
      if ((item.sellingPlace || "").trim() !== filterSellingPlace) return false;
    }

    // 5. Filtro Prezzo Minimo
    if (filterMinPrice !== null && filterMinPrice !== undefined && !isNaN(filterMinPrice)) {
      if ((item.purchasedPrice || 0) < filterMinPrice) return false;
    }

    // 6. Filtro Prezzo Massimo
    if (filterMaxPrice !== null && filterMaxPrice !== undefined && !isNaN(filterMaxPrice)) {
      if ((item.purchasedPrice || 0) > filterMaxPrice) return false;
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
    } else if (sortField === "date") {
      valA = a.date || "";
      valB = b.date || "";
      return sortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }

    if (typeof valA === "string") {
      return sortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortOrder === "asc" ? (valA || 0) - (valB || 0) : (valB || 0) - (valA || 0);
  });

  return filtered;
}

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

  const checkboxTh = isSelectionModeActive
    ? '<th class="col-checkbox col-center"><input type="checkbox" id="selectAllCheckbox" onchange="toggleSelectAll(this.checked)" /></th>'
    : '';

  // Render dell'Header in base alla visualizzazione attiva (misure ottimizzate "Zero-Lag")
  if (thead) {
    if (isStockView) {
      thead.innerHTML = `
        <tr>
          ${checkboxTh}
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
          ${checkboxTh}
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

  const filtered = getFilteredAndSortedProducts();
  tbody.innerHTML = "";

  const totalCols = (isStockView ? 7 : 10) + (isSelectionModeActive ? 1 : 0);
  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="${totalCols}" style="text-align: center; padding: 40px; color: var(--text-dim);">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 8px; opacity: 0.5;"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <div style="font-size: 12px; font-weight: 500;">Nessun prodotto trovato per i criteri selezionati.</div>
        </td>
      </tr>
    `;
    return;
  }

  // Raggruppamento Bundle / Vendita Multipla (identico all'approccio di main_window.py)
  const bundleGroups = new Map();
  filtered.forEach((item) => {
    const bId = item.bundle_id || item.bundleId;
    if (bId && (item.status === "active-sale" || item.status === "completed")) {
      if (!bundleGroups.has(bId)) {
        bundleGroups.set(bId, []);
      }
      bundleGroups.get(bId).push(item);
    }
  });

  const displayList = [];
  const processedBundleIds = new Set();
  filtered.forEach((item) => {
    const bId = item.bundle_id || item.bundleId;
    if (bId && bundleGroups.has(bId) && bundleGroups.get(bId).length > 1) {
      if (!processedBundleIds.has(bId)) {
        processedBundleIds.add(bId);
        displayList.push({
          isBundle: true,
          bundleId: bId,
          items: bundleGroups.get(bId),
        });
      }
    } else {
      displayList.push({
        isBundle: false,
        item: item,
      });
    }
  });

  displayList.forEach((entry) => {
    if (entry.isBundle) {
      const bItems = entry.items;
      const bId = entry.bundleId;
      const isExpanded = expandedBundles.has(bId);

      const distinctNames = Array.from(new Set(bItems.map((r) => r.name))).sort();
      let bundleTitle = `Vendita Multipla (${distinctNames.join(", ")})`;
      if (bundleTitle.length > 55) {
        bundleTitle = bundleTitle.substring(0, 52) + "...)";
      }

      const totalQty = bItems.reduce((acc, r) => acc + (r.quantity || 1), 0);
      const totalPurchased = bItems.reduce((acc, r) => acc + ((r.purchasedPrice || 0) * (r.quantity || 1)), 0);
      const totalSold = bItems.reduce((acc, r) => acc + (r.salePrice || 0), 0);
      const totalFees = bItems.reduce((acc, r) => acc + (r.fees || 0), 0);
      const totalProfit = totalSold - totalPurchased - totalFees;
      const totalRoi = totalPurchased > 0 ? (totalProfit / totalPurchased) * 100 : 0;
      const sellingPlace = bItems[0].sellingPlace || "-";
      const bundleStatus = bItems[0].status || "active-sale";
      const bundleStatusLabel = bundleStatus === "completed" ? "Venduto" : "In Vendita";
      const bundleStatusClass = bundleStatus === "completed" ? "completed" : "active-sale";

      const isAllChecked = bItems.every((r) => selectedProductIds.has(r.id));
      const isSomeChecked = bItems.some((r) => selectedProductIds.has(r.id));

      const bundleTr = document.createElement("tr");
      bundleTr.className = `bundle-row ${isAllChecked ? "row-selected" : ""}`;

      const checkboxTd = isSelectionModeActive
        ? `<td class="col-checkbox col-center" onclick="event.stopPropagation()">
             <input type="checkbox" class="row-checkbox bundle-chk" ${isAllChecked ? "checked" : ""} onchange="toggleBundleSelection('${bId}', this.checked)" />
           </td>`
        : "";

      const actionBtnsHtml = `
        <div class="action-btns">
          <button class="btn-action-icon delete" title="Elimina Vendita Multipla" onclick="event.stopPropagation(); deleteBundle('${bId}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          </button>
        </div>
      `;

      if (isStockView) {
        bundleTr.innerHTML = `
          ${checkboxTd}
          <td class="col-prod" title="${distinctNames.join(", ")}">
            <div class="product-cell" style="flex-direction: row; align-items: center; gap: 8px;">
              <span class="bundle-chevron" onclick="event.stopPropagation(); toggleBundleExpand('${bId}')" title="${isExpanded ? 'Comprimi' : 'Espandi'}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="transform: ${isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'}; transition: transform 0.15s ease;"><path d="m9 18 6-6-6-6"/></svg>
              </span>
              <span class="bundle-tag">Bundle</span>
              <span class="product-name" style="font-weight: 700;">${bundleTitle}</span>
            </div>
          </td>
          <td class="col-size col-center" style="color: var(--text-dim);">-</td>
          <td class="col-qty col-center"><strong>${totalQty} pz</strong></td>
          <td class="col-buy">${formatMoney(totalPurchased)}</td>
          <td class="col-place" style="color: var(--text-muted);">${sellingPlace}</td>
          <td class="col-status col-center">
            <span class="status-badge ${bundleStatusClass}">
              <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
              ${bundleStatusLabel}
            </span>
          </td>
          <td class="col-actions col-center">${actionBtnsHtml}</td>
        `;
      } else {
        bundleTr.innerHTML = `
          ${checkboxTd}
          <td class="col-prod" title="${distinctNames.join(", ")}">
            <div class="product-cell" style="flex-direction: row; align-items: center; gap: 8px;">
              <span class="bundle-chevron" onclick="event.stopPropagation(); toggleBundleExpand('${bId}')" title="${isExpanded ? 'Comprimi' : 'Espandi'}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="transform: ${isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'}; transition: transform 0.15s ease;"><path d="m9 18 6-6-6-6"/></svg>
              </span>
              <span class="bundle-tag">Bundle</span>
              <span class="product-name" style="font-weight: 700;">${bundleTitle}</span>
            </div>
          </td>
          <td class="col-size col-center" style="color: var(--text-dim);">-</td>
          <td class="col-qty col-center"><strong>${totalQty} pz</strong></td>
          <td class="col-buy">${formatMoney(totalPurchased)}</td>
          <td class="col-sell"><strong>${formatMoney(totalSold)}</strong></td>
          <td class="col-channel"><span style="font-size: 11.5px; color: var(--text-muted);">${sellingPlace}</span></td>
          <td class="col-profit"><span class="profit-pos">+${formatMoney(totalProfit)}</span></td>
          <td class="col-roi col-center"><span class="roi-badge">+${totalRoi.toFixed(1)}%</span></td>
          <td class="col-status col-center">
            <span class="status-badge ${bundleStatusClass}">
              <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
              ${bundleStatusLabel}
            </span>
          </td>
          <td class="col-actions col-center">${actionBtnsHtml}</td>
        `;
      }

      if (isSelectionModeActive) {
        const chkBox = bundleTr.querySelector(".bundle-chk");
        if (chkBox) chkBox.indeterminate = !isAllChecked && isSomeChecked;
        bundleTr.addEventListener("click", () => toggleBundleSelection(bId, !isAllChecked));
      } else {
        bundleTr.addEventListener("click", () => toggleBundleExpand(bId));
      }

      bundleTr.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isSelectionModeActive) {
          selectedProductIds.clear();
        }
        bItems.forEach((r) => selectedProductIds.add(r.id));
        updateSelectionBadge();
        renderTable();
        showContextMenu(e.clientX, e.clientY);
      });

      tbody.appendChild(bundleTr);

      // Se espanso, disegna le sotto-righe dei singoli prodotti del bundle
      if (isExpanded) {
        bItems.forEach((child) => {
          const childTr = document.createElement("tr");
          childTr.className = `bundle-child-row ${selectedProductIds.has(child.id) ? "row-selected" : ""}`;

          const childCheckboxTd = isSelectionModeActive
            ? `<td class="col-checkbox col-center" onclick="event.stopPropagation()">
                 <input type="checkbox" class="row-checkbox" ${selectedProductIds.has(child.id) ? "checked" : ""} onchange="toggleItemSelection(${child.id}, this.checked)" />
               </td>`
            : "";

          const childEditBtnHtml = (child.status === "completed") ? "" : `
            <button class="btn-action-icon" title="Modifica Prodotto" onclick="event.stopPropagation(); editProduct(${child.id})">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
            </button>
          `;

          const childActionsHtml = `
            <div class="action-btns">
              <button class="btn-action-icon" title="Stima Prezzi eBay" onclick="event.stopPropagation(); openEbayPriceLookup('${child.name.replace(/'/g, "\\'")}')">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              </button>
              ${childEditBtnHtml}
              <button class="btn-action-icon delete" title="Elimina" onclick="event.stopPropagation(); deleteProduct(${child.id})">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
              </button>
            </div>
          `;

          if (isStockView) {
            childTr.innerHTML = `
              ${childCheckboxTd}
              <td class="col-prod" title="${child.name}">
                <div class="product-cell" style="padding-left: 28px;">
                  <div class="product-name" style="color: var(--text-secondary); font-size: 12px;">↳ ${child.name}</div>
                  <div class="product-brand" style="font-size: 11px;">${child.purchasedPlace || "In Magazzino"}</div>
                </div>
              </td>
              <td class="col-size col-center"><strong>${child.size}</strong></td>
              <td class="col-qty col-center">${child.quantity} pz</td>
              <td class="col-buy">${formatMoney(child.purchasedPrice)}</td>
              <td class="col-place" style="color: var(--text-dim);">${child.purchasedPlace || "-"}</td>
              <td class="col-status col-center"><span style="color: var(--text-dim); font-size: 11px;">(incluso)</span></td>
              <td class="col-actions col-center">${childActionsHtml}</td>
            `;
          } else {
            childTr.innerHTML = `
              ${childCheckboxTd}
              <td class="col-prod" title="${child.name}">
                <div class="product-cell" style="padding-left: 28px;">
                  <div class="product-name" style="color: var(--text-secondary); font-size: 12px;">↳ ${child.name}</div>
                  <div class="product-brand" style="font-size: 11px;">${child.purchasedPlace || "In Magazzino"}</div>
                </div>
              </td>
              <td class="col-size col-center"><strong>${child.size}</strong></td>
              <td class="col-qty col-center">${child.quantity} pz</td>
              <td class="col-buy">${formatMoney(child.purchasedPrice)}</td>
              <td class="col-sell" style="color: var(--text-dim); font-size: 11.5px;">(in bundle)</td>
              <td class="col-channel"><span style="font-size: 11.5px; color: var(--text-dim);">${child.sellingPlace || "-"}</span></td>
              <td class="col-profit" style="color: var(--text-dim);">-</td>
              <td class="col-roi col-center" style="color: var(--text-dim);">-</td>
              <td class="col-status col-center"><span style="color: var(--text-dim); font-size: 11px;">(incluso)</span></td>
              <td class="col-actions col-center">${childActionsHtml}</td>
            `;
          }

          if (isSelectionModeActive) {
            childTr.addEventListener("click", () => toggleItemSelection(child.id));
          } else {
            childTr.addEventListener("click", () => openDrawer(child.id));
            childTr.addEventListener("dblclick", () => openDrawer(child.id));
          }

          childTr.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!selectedProductIds.has(child.id)) {
              if (!isSelectionModeActive) {
                selectedProductIds.clear();
              }
              selectedProductIds.add(child.id);
              updateSelectionBadge();
              renderTable();
            }
            showContextMenu(e.clientX, e.clientY);
          });

          tbody.appendChild(childTr);
        });
      }
    } else {
      // Prodotto Standard
      const item = entry.item;
      const tr = document.createElement("tr");
      const isChecked = selectedProductIds.has(item.id);
      if (isChecked) {
        tr.classList.add("row-selected");
      }

      const checkboxTd = isSelectionModeActive
        ? `<td class="col-checkbox col-center" onclick="event.stopPropagation()"><input type="checkbox" class="row-checkbox" ${isChecked ? "checked" : ""} onchange="toggleItemSelection(${item.id}, this.checked)" /></td>`
        : "";

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
          ${checkboxTd}
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
          ${checkboxTd}
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

      // Gestione click riga: se selezione attiva fa toggle checkbox; altrimenti apre il drawer
      if (isSelectionModeActive) {
        tr.addEventListener("click", () => toggleItemSelection(item.id));
      } else {
        tr.addEventListener("click", () => openDrawer(item.id));
        tr.addEventListener("dblclick", () => openDrawer(item.id));
      }

      // Menu contestuale personalizzato col tasto destro del mouse
      tr.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!selectedProductIds.has(item.id)) {
          if (!isSelectionModeActive) {
            selectedProductIds.clear();
          }
          selectedProductIds.add(item.id);
          updateSelectionBadge();
          renderTable();
        }
        showContextMenu(e.clientX, e.clientY);
      });

      tbody.appendChild(tr);
    }
  });

  // Aggiorna checkbox master nell'intestazione
  if (isSelectionModeActive) {
    const selectAllBox = document.getElementById("selectAllCheckbox");
    if (selectAllBox && filtered.length > 0) {
      const allSelected = filtered.every((p) => selectedProductIds.has(p.id));
      const someSelected = filtered.some((p) => selectedProductIds.has(p.id));
      selectAllBox.checked = allSelected;
      selectAllBox.indeterminate = !allSelected && someSelected;
    }
  }
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
  document.getElementById("prod-sold-price").value = "";
  document.getElementById("prod-status").value = "stock";
  const notesEl = document.getElementById("prod-notes");
  if (notesEl) notesEl.value = "";
}

function onModalStatusChange(_val) {
  // Prezzo di Vendita è ora un campo permanente del layout
}

function closeModal() {
  document.querySelectorAll(".modal-backdrop").forEach((el) => {
    el.classList.remove("open");
  });
  const excelStatus = document.getElementById("excel-parse-status");
  if (excelStatus) excelStatus.textContent = "";
  const excelInput = document.getElementById("excelFileInput");
  if (excelInput) excelInput.value = "";
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
      openEbayPriceLookup(item.name, item.size);
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

  const soldPriceEl = document.getElementById("prod-sold-price");
  const salePrice = soldPriceEl && soldPriceEl.value !== "" ? (parseFloat(soldPriceEl.value) || null) : null;
  const notesEl = document.getElementById("prod-notes");
  const notes = notesEl ? notesEl.value.trim() : "";

  if (!name) {
    showToast("Inserisci un nome per il prodotto!");
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
    notes,
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
      showToast(isEdit ? `"${name}" aggiornato nel database!` : `"${name}" salvato nel database!`);
    } else {
      showToast(`Errore: ${result.error || "Salvataggio non riuscito"}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
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
        showToast(`"${item.name}" rimosso dal database.`);
      } else {
        showToast(`Errore eliminazione: ${result.error}`);
      }
    } catch (err) {
      showToast(`Errore di rete: ${err.message}`);
    }
  }
}

function editProduct(id) {
  const item = inventoryData.find((i) => i.id === id);
  if (!item) return;
  if (item.status === "completed") {
    showToast("Le vendite completate non possono essere modificate.");
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
  document.getElementById("prod-sold-price").value = (item.salePrice !== null && item.salePrice !== undefined) ? item.salePrice : "";
  document.getElementById("prod-status").value = item.status || "stock";
  const notesEl = document.getElementById("prod-notes");
  if (notesEl) notesEl.value = item.notes || "";
}

// ==========================================================================
// FUNZIONALITÀ REALI RSM (eBay, AI, Sync Email)
// ==========================================================================
let currentEbayQuery = { name: "", size: "" };

async function openEbayPriceLookup(productName, size = "") {
  closeDrawer();
  closeModal();
  const modal = document.getElementById("ebayModal");
  if (!modal) return;
  modal.classList.add("open");

  currentEbayQuery = { name: productName, size: size || "" };

  const effectiveSize = (size || "").trim();
  const subtitle = (effectiveSize && effectiveSize.toUpperCase() !== "UNI")
    ? `${productName}  ·  taglia ${effectiveSize}`
    : productName;

  const subEl = document.getElementById("ebay-subtitle");
  if (subEl) subEl.textContent = subtitle;

  const loadingEl = document.getElementById("ebay-loading");
  const resultsEl = document.getElementById("ebay-results");
  if (loadingEl) loadingEl.style.display = "block";
  if (resultsEl) resultsEl.style.display = "none";

  try {
    const url = `${API_BASE}/ebay-prices?name=${encodeURIComponent(productName)}&size=${encodeURIComponent(size || "")}`;
    const res = await fetch(url);
    const json = await res.json();
    if (loadingEl) loadingEl.style.display = "none";

    if (json.success && json.data) {
      if (resultsEl) resultsEl.style.display = "block";
      const { avg, min, max, count } = json.data;
      const minEl = document.getElementById("ebay-min-val");
      const avgEl = document.getElementById("ebay-avg-val");
      const maxEl = document.getElementById("ebay-max-val");
      const countEl = document.getElementById("ebay-count-text");

      if (minEl) minEl.textContent = `€ ${min.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      if (avgEl) avgEl.textContent = `€ ${avg.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      if (maxEl) maxEl.textContent = `€ ${max.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      if (countEl) countEl.textContent = `Analizzate ${count} inserzioni controllate su eBay.it`;
    } else {
      showToast(`eBay: ${json.error || "Nessun risultato trovato"}`);
      closeModal();
    }
  } catch (err) {
    if (loadingEl) loadingEl.style.display = "none";
    showToast(`Errore ricerca eBay: ${err.message}`);
    closeModal();
  }
}

async function openEbayInBrowser() {
  if (!currentEbayQuery.name) return;
  try {
    await fetch(`${API_BASE}/ebay-open-browser`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: currentEbayQuery.name,
        size: currentEbayQuery.size
      })
    });
  } catch (err) {
    showToast(`Errore apertura browser: ${err.message}`);
  }
}

// ==========================================================================
// SELEZIONE MULTIPLA & OPERAZIONI MASSIVE (BULK ACTIONS & CONTEXT MENU)
// ==========================================================================

function toggleSelectionMode() {
  isSelectionModeActive = !isSelectionModeActive;
  const btn = document.getElementById("btnToggleSelect");
  if (btn) btn.classList.toggle("active", isSelectionModeActive);
  if (!isSelectionModeActive) {
    selectedProductIds.clear();
  }
  updateSelectionBadge();
  renderTable();
}

function updateSelectionBadge() {
  const badge = document.getElementById("selectedCountBadge");
  if (!badge) return;
  const count = selectedProductIds.size;
  if (isSelectionModeActive && count > 0) {
    badge.textContent = count;
    badge.style.display = "inline-block";
  } else {
    badge.style.display = "none";
  }
}

function toggleItemSelection(id, explicitState = null) {
  if (explicitState !== null) {
    if (explicitState) {
      selectedProductIds.add(id);
    } else {
      selectedProductIds.delete(id);
    }
  } else {
    if (selectedProductIds.has(id)) {
      selectedProductIds.delete(id);
    } else {
      selectedProductIds.add(id);
    }
  }
  updateSelectionBadge();
  renderTable();
}

function toggleSelectAll(checked) {
  const visible = getFilteredAndSortedProducts();
  if (checked) {
    visible.forEach((p) => selectedProductIds.add(p.id));
  } else {
    visible.forEach((p) => selectedProductIds.delete(p.id));
  }
  updateSelectionBadge();
  renderTable();
}

function toggleBundleExpand(bundleId) {
  if (expandedBundles.has(bundleId)) {
    expandedBundles.delete(bundleId);
  } else {
    expandedBundles.add(bundleId);
  }
  renderTable();
}

function toggleBundleSelection(bundleId, forceChecked = null) {
  const items = inventoryData.filter((p) => (p.bundle_id || p.bundleId) === bundleId);
  if (!items.length) return;
  const isAllChecked = items.every((r) => selectedProductIds.has(r.id));
  const shouldCheck = (forceChecked !== null) ? forceChecked : !isAllChecked;

  items.forEach((r) => {
    if (shouldCheck) {
      selectedProductIds.add(r.id);
    } else {
      selectedProductIds.delete(r.id);
    }
  });

  updateSelectionBadge();
  renderTable();
}

async function deleteBundle(bundleId) {
  const items = inventoryData.filter((p) => (p.bundle_id || p.bundleId) === bundleId);
  if (!items.length) return;
  if (!confirm(`Sei sicuro di voler eliminare tutti i ${items.length} prodotti di questa vendita multipla dal database?`)) {
    return;
  }
  const ids = items.map((p) => p.id);
  try {
    const res = await callApi("/products/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    const json = await res.json();
    if (json.success) {
      ids.forEach((id) => selectedProductIds.delete(id));
      updateSelectionBadge();
      await loadProductsFromBackend();
      showToast(`Vendita multipla eliminata con successo (${items.length} prodotti).`);
    } else {
      showToast(`Errore eliminazione bundle: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  }
}

// Visualizzazione menu contestuale
function showContextMenu(x, y) {
  const menu = document.getElementById("tableContextMenu");
  if (!menu) return;

  const count = selectedProductIds.size;
  if (count === 0) return;

  const header = document.getElementById("ctxMenuHeader");
  if (header) {
    header.textContent = `${count} Prodott${count === 1 ? "o Selezionato" : "i Selezionati"}`;
  }

  const selectedRecords = inventoryData.filter((i) => selectedProductIds.has(i.id));

  // Regole visibilità voci di menu fedeli al progetto originale
  const canEdit = count === 1 && selectedRecords[0] && selectedRecords[0].status !== "completed";
  const canDuplicate = true;
  const canSell = selectedRecords.some((i) => i.status === "stock" || i.status === "preorder");
  const canStock = selectedRecords.some((i) => i.status === "preorder" || i.status === "active-sale");
  const canComplete = selectedRecords.some((i) => i.status === "active-sale");
  const canSearchEbay = true;
  const canEbayPrices = count === 1;
  const canDelete = true;

  const elEdit = document.getElementById("ctxItemEdit");
  const elDup = document.getElementById("ctxItemDuplicate");
  const elSell = document.getElementById("ctxItemSell");
  const elStock = document.getElementById("ctxItemStock");
  const elComplete = document.getElementById("ctxItemComplete");
  const elSearchEbay = document.getElementById("ctxItemSearchEbay");
  const elEbayPrices = document.getElementById("ctxItemEbayPrices");
  const elDelete = document.getElementById("ctxItemDelete");

  if (elEdit) elEdit.style.display = canEdit ? "flex" : "none";
  if (elDup) elDup.style.display = canDuplicate ? "flex" : "none";
  if (elSell) elSell.style.display = canSell ? "flex" : "none";
  if (elStock) elStock.style.display = canStock ? "flex" : "none";
  if (elComplete) elComplete.style.display = canComplete ? "flex" : "none";
  if (elSearchEbay) elSearchEbay.style.display = canSearchEbay ? "flex" : "none";
  if (elEbayPrices) elEbayPrices.style.display = canEbayPrices ? "flex" : "none";
  if (elDelete) elDelete.style.display = canDelete ? "flex" : "none";

  // Posizionamento nel viewport
  menu.style.display = "block";
  const rect = menu.getBoundingClientRect();
  const winW = window.innerWidth;
  const winH = window.innerHeight;

  let left = x;
  let top = y;
  if (left + rect.width > winW - 10) left = winW - rect.width - 10;
  if (top + rect.height > winH - 10) top = winH - rect.height - 10;

  menu.style.left = `${Math.max(8, left)}px`;
  menu.style.top = `${Math.max(8, top)}px`;
}

function hideContextMenu() {
  const menu = document.getElementById("tableContextMenu");
  if (menu) menu.style.display = "none";
}

// Azioni del menu contestuale
function ctxActionEdit() {
  hideContextMenu();
  const ids = Array.from(selectedProductIds);
  if (ids.length === 1) {
    editProduct(ids[0]);
  }
}

async function ctxActionDuplicate() {
  hideContextMenu();
  const ids = Array.from(selectedProductIds);
  if (ids.length === 0) return;
  try {
    const res = await callApi("/products/duplicate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    const json = await res.json();
    if (json.success) {
      selectedProductIds.clear();
      updateSelectionBadge();
      await loadProductsFromBackend();
      showToast(`Duplicati ${ids.length} prodotti con successo!`);
    } else {
      showToast(`Errore duplicazione: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  }
}

function ctxActionSell() {
  hideContextMenu();
  openBulkSaleModal();
}

async function ctxActionStock() {
  hideContextMenu();
  const ids = Array.from(selectedProductIds);
  if (ids.length === 0) return;
  if (!confirm(`Spostare ${ids.length} prodotti in Magazzino?`)) return;

  try {
    const res = await callApi("/products/bulk-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, status: "stock" }),
    });
    const json = await res.json();
    if (json.success) {
      selectedProductIds.clear();
      updateSelectionBadge();
      activeFilter = "stock";
      document.querySelectorAll(".table-tab-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.getAttribute("data-filter") === "stock");
      });
      await loadProductsFromBackend();
      showToast(`${ids.length} prodotti spostati in Magazzino!`);
    } else {
      showToast(`Errore spostamento: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  }
}

async function ctxActionComplete() {
  hideContextMenu();
  const ids = Array.from(selectedProductIds);
  if (ids.length === 0) return;
  if (!confirm(`Contrassegnare ${ids.length} vendite come completate?`)) return;

  try {
    const res = await callApi("/products/bulk-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, status: "completed" }),
    });
    const json = await res.json();
    if (json.success) {
      selectedProductIds.clear();
      updateSelectionBadge();
      activeFilter = "completed";
      document.querySelectorAll(".table-tab-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.getAttribute("data-filter") === "completed");
      });
      await loadProductsFromBackend();
      showToast(`${ids.length} vendite contrassegnate come completate!`);
    } else {
      showToast(`Errore completamento: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  }
}

async function ctxActionSearchEbay() {
  hideContextMenu();
  const selectedRecords = inventoryData.filter((i) => selectedProductIds.has(i.id));
  if (selectedRecords.length === 0) return;

  let opened = 0;
  for (const item of selectedRecords) {
    if (!item.name) continue;
    try {
      await callApi("/ebay-open-browser", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: item.name,
          size: item.size || "",
        }),
      });
      opened++;
    } catch (_) {}
  }
  showToast(`Aperte ${opened} schede di ricerca eBay nel browser.`);
}

function ctxActionEbayPrices() {
  hideContextMenu();
  const ids = Array.from(selectedProductIds);
  if (ids.length !== 1) return;
  const item = inventoryData.find((i) => i.id === ids[0]);
  if (item) {
    openEbayPriceLookup(item.name, item.size || "");
  }
}

async function ctxActionDelete() {
  hideContextMenu();
  const ids = Array.from(selectedProductIds);
  if (ids.length === 0) return;
  const msg = ids.length === 1
    ? "Eliminare definitivamente il prodotto selezionato?"
    : `Eliminare definitivamente ${ids.length} prodotti selezionati dal database SQLite?`;
  if (!confirm(msg)) return;

  try {
    const res = await callApi("/products/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    const json = await res.json();
    if (json.success) {
      selectedProductIds.clear();
      updateSelectionBadge();
      await loadProductsFromBackend();
      showToast(`Eliminati ${json.deleted_count} prodotti dal database.`);
    } else {
      showToast(`Errore eliminazione: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  }
}

// Modale Vendita Multipla / Metti in Vendita (Bulk Status & Partial Move)
function openBulkSaleModal() {
  const modal = document.getElementById("bulkSaleModal");
  if (!modal) return;
  const count = selectedProductIds.size;
  if (count === 0) return;

  const titleEl = document.getElementById("bulkSaleModalTitle");
  const subtitleEl = document.getElementById("bulkSaleModalSubtitle");
  const qtyGroup = document.getElementById("bulk-sale-qty-group");
  const qtySelect = document.getElementById("bulk-sale-qty-select");
  const qtyHint = document.getElementById("bulk-sale-qty-hint");
  const priceLabel = document.getElementById("bulk-sale-price-label");

  if (count === 1) {
    const singleId = Array.from(selectedProductIds)[0];
    const item = inventoryData.find((p) => p.id === singleId);
    if (titleEl) titleEl.textContent = "Metti in Vendita";
    if (subtitleEl) subtitleEl.textContent = `Configura la vendita per "${item ? item.name : "il prodotto selezionato"}".`;
    if (priceLabel) priceLabel.textContent = "Prezzo di Vendita (€) *";

    if (item && item.quantity > 1) {
      if (qtyGroup) qtyGroup.style.display = "block";
      if (qtySelect) {
        qtySelect.innerHTML = "";
        for (let q = 1; q <= item.quantity; q++) {
          const opt = document.createElement("option");
          opt.value = q;
          opt.textContent = `${q} di ${item.quantity} pz`;
          if (q === item.quantity) opt.selected = true;
          qtySelect.appendChild(opt);
        }
        qtySelect.onchange = () => {
          const chosen = parseInt(qtySelect.value, 10);
          if (qtyHint) {
            const remaining = item.quantity - chosen;
            if (remaining > 0) {
              const placeText = item.status === "preorder" ? "pre-ordine" : "magazzino";
              qtyHint.textContent = `${chosen} pz andranno in Vendita Attiva, ${remaining} pz rimarranno in ${placeText}.`;
            } else {
              qtyHint.textContent = `Tutti i ${chosen} pz verranno messi in vendita.`;
            }
          }
        };
        qtySelect.dispatchEvent(new Event("change"));
      }
    } else {
      if (qtyGroup) qtyGroup.style.display = "none";
    }
  } else {
    if (titleEl) titleEl.textContent = `Metti in Vendita (${count} Prodotti)`;
    if (subtitleEl) subtitleEl.textContent = "Stai per mettere in vendita i prodotti selezionati insieme come bundle. Il prezzo totale e le commissioni verranno ripartiti equamente e verrà visualizzato un unico gruppo di vendita.";
    if (priceLabel) priceLabel.textContent = "Prezzo di Vendita TOTALE (€) *";
    if (qtyGroup) qtyGroup.style.display = "none";
  }

  const datalist = document.getElementById("bulk-selling-places-list");
  if (datalist) {
    const placesSet = new Set();
    inventoryData.forEach((i) => {
      if (i.sellingPlace && i.sellingPlace.trim()) placesSet.add(i.sellingPlace.trim());
    });
    datalist.innerHTML = "";
    Array.from(placesSet).sort().forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      datalist.appendChild(opt);
    });
  }

  document.getElementById("bulk-sale-total-price").value = "";
  document.getElementById("bulk-sale-total-fees").value = "0.00";
  document.getElementById("bulk-sale-place").value = "";

  modal.classList.add("open");
  const priceInput = document.getElementById("bulk-sale-total-price");
  if (priceInput) setTimeout(() => priceInput.focus(), 60);
}

function closeBulkSaleModal() {
  const modal = document.getElementById("bulkSaleModal");
  if (modal) modal.classList.remove("open");
}

async function handleBulkSaleSubmit(e) {
  e.preventDefault();
  const ids = Array.from(selectedProductIds);
  if (ids.length === 0) return;

  const priceVal = parseFloat(document.getElementById("bulk-sale-total-price").value) || 0;
  const feesVal = parseFloat(document.getElementById("bulk-sale-total-fees").value) || 0;
  const placeVal = document.getElementById("bulk-sale-place").value.trim();

  if (priceVal <= 0) {
    showToast("Inserisci un prezzo di vendita valido!");
    return;
  }

  const payload = {
    ids,
    status: "active-sale",
    sold_price_total: priceVal,
    fees_total: feesVal,
    selling_place: placeVal,
  };

  const qtyGroup = document.getElementById("bulk-sale-qty-group");
  const qtySelect = document.getElementById("bulk-sale-qty-select");
  if (ids.length === 1 && qtyGroup && qtyGroup.style.display !== "none" && qtySelect) {
    payload.quantity_to_sell = parseInt(qtySelect.value, 10);
  }

  try {
    const res = await callApi("/products/bulk-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (json.success) {
      closeBulkSaleModal();
      selectedProductIds.clear();
      updateSelectionBadge();
      activeFilter = "active-sale";
      document.querySelectorAll(".table-tab-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.getAttribute("data-filter") === "active-sale");
      });
      await loadProductsFromBackend();
      showToast(`${ids.length === 1 ? "Prodotto messo" : ids.length + " prodotti messi"} in vendita con successo!`);
    } else {
      showToast(`Errore vendita: ${json.error}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
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

// ==========================================================================
// IMPORTAZIONE EXCEL / SPREADSHEET CON AI & MAPPER (IDENTICO AD EXCELIMPORTDIALOG)
// ==========================================================================
let pendingExcelFile = null;
let excelExtractedProducts = [];

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function triggerExcelFileInput() {
  const input = document.getElementById("excelFileInput");
  if (input) {
    input.value = "";
    input.click();
  }
}

function handleExcelFileSelected(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  pendingExcelFile = file;

  closeDrawer();
  closeModal();

  const hintModal = document.getElementById("excelHintModal");
  if (hintModal) {
    document.getElementById("excel-hint-filename").textContent = `File selezionato: ${file.name}`;
    document.getElementById("excel-hint-text").value = "";
    document.getElementById("excel-parse-status").textContent = "";
    const btnNoHint = document.getElementById("btn-excel-no-hint");
    const btnWithHint = document.getElementById("btn-excel-with-hint");
    if (btnNoHint) btnNoHint.disabled = false;
    if (btnWithHint) btnWithHint.disabled = false;
    hintModal.classList.add("open");
  }
}

async function executeExcelAnalysis(useHint) {
  if (!pendingExcelFile) return;

  const hintText = useHint ? document.getElementById("excel-hint-text").value.trim() : "";
  const statusEl = document.getElementById("excel-parse-status");
  const btnNoHint = document.getElementById("btn-excel-no-hint");
  const btnWithHint = document.getElementById("btn-excel-with-hint");

  if (btnNoHint) btnNoHint.disabled = true;
  if (btnWithHint) btnWithHint.disabled = true;
  if (statusEl) statusEl.textContent = "Lettura del foglio di calcolo e analisi AI con Gemini in corso...";

  try {
    const reader = new FileReader();
    const base64Data = await new Promise((resolve, reject) => {
      reader.onload = () => {
        const result = reader.result;
        const b64 = typeof result === "string" ? result.split(",")[1] : "";
        resolve(b64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(pendingExcelFile);
    });

    const res = await callApi("/parse-excel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: pendingExcelFile.name,
        file_base64: base64Data,
        user_hint: hintText
      })
    });
    const json = await res.json();

    if (!json.success || !json.products || json.products.length === 0) {
      const errMsg = json.error || "Nessun prodotto valido rilevato nel file.";
      if (statusEl) statusEl.textContent = `Errore: ${errMsg}`;
      showToast(`Excel: ${errMsg}`);
      if (btnNoHint) btnNoHint.disabled = false;
      if (btnWithHint) btnWithHint.disabled = false;
      return;
    }

    excelExtractedProducts = json.products;
    closeModal();
    openExcelPreviewModal();
  } catch (err) {
    if (statusEl) statusEl.textContent = `Errore: ${err.message}`;
    showToast(`Errore analisi Excel: ${err.message}`);
    if (btnNoHint) btnNoHint.disabled = false;
    if (btnWithHint) btnWithHint.disabled = false;
  }
}

function openExcelPreviewModal() {
  const modal = document.getElementById("excelPreviewModal");
  if (!modal) return;
  modal.classList.add("open");

  const count = excelExtractedProducts.length;
  const subtitleEl = document.getElementById("excel-preview-subtitle");
  if (subtitleEl) {
    subtitleEl.textContent = `L'AI ha analizzato il file e trovato ${count} prodott${count === 1 ? 'o' : 'i'} pronti per l'importazione. Controlla l'anteprima e conferma.`;
  }

  const summaryCountEl = document.getElementById("excel-summary-count");
  if (summaryCountEl) {
    summaryCountEl.textContent = `${count} prodott${count === 1 ? 'o' : 'i'} pronti per l'importazione.`;
  }

  const tbody = document.getElementById("excel-preview-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  excelExtractedProducts.forEach((p) => {
    const rawStatus = (p.status || "").trim();
    let labelStatus = "In Magazzino";
    let statusClass = "stock";
    if (rawStatus === "Venduto" || rawStatus === "Vendite Attive" || rawStatus === "completed" || rawStatus === "active-sale") {
      labelStatus = "Vendite Attive";
      statusClass = "active-sale";
    } else if (rawStatus === "Pre-ordine" || rawStatus === "Preordine" || rawStatus === "preorder") {
      labelStatus = "Pre-ordine";
      statusClass = "preorder";
    }

    const buyPrice = parseFloat(p.purchased_price) || 0;
    const formattedPrice = `€ ${buyPrice.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 600; color: #fff;">${escapeHtml(p.name || "-")}</td>
      <td class="col-center"><span class="table-size-pill">${escapeHtml(p.size || "UNI")}</span></td>
      <td class="col-center">${parseInt(p.quantity, 10) || 1}</td>
      <td class="col-center" style="font-weight: 700; color: #34d399;">${formattedPrice}</td>
      <td>${escapeHtml(p.purchased_place || "-")}</td>
      <td>${escapeHtml(p.selling_place || "-")}</td>
      <td class="col-center"><span class="status-badge ${statusClass}">${labelStatus}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

async function saveExcelExtractedProducts() {
  if (!excelExtractedProducts || excelExtractedProducts.length === 0) return;

  const btnSave = document.getElementById("btn-excel-confirm-save");
  if (btnSave) btnSave.disabled = true;

  try {
    const res = await callApi("/save-excel-products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ products: excelExtractedProducts })
    });
    const json = await res.json();
    if (json.success) {
      showToast(`${json.saved_count || excelExtractedProducts.length} prodotti importati con successo nel database!`);
      closeModal();
      excelExtractedProducts = [];
      pendingExcelFile = null;
      await loadProductsFromBackend();
    } else {
      showToast(`Errore salvataggio: ${json.error || "Operazione non riuscita"}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  } finally {
    if (btnSave) btnSave.disabled = false;
  }
}

// Toast Helper (Zero-Emoji Guaranteed)
function showToast(message) {
  const toast = document.getElementById("toastNotification");
  if (!toast) return;
  // Rimozione totale di emoji grafiche e simboli non testuali per standard aziendale pulito
  const cleanMessage = String(message || "")
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F02F}\u{1F0A0}-\u{1F0FF}]/gu, "")
    .trim();
  toast.innerHTML = `<span>${cleanMessage}</span>`;
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
      updateFilterIndicators();
      renderTable();
    });
  }

  // Filter Pills (Tutti, Magazzino, Pre-ordini, ecc.)
  document.querySelectorAll(".table-tab-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".table-tab-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeFilter = pill.getAttribute("data-filter");

      // Reset completo della modalità selezione passando da una tabella all'altra
      isSelectionModeActive = false;
      const btnToggle = document.getElementById("btnToggleSelect");
      if (btnToggle) btnToggle.classList.remove("active");
      selectedProductIds.clear();
      updateSelectionBadge();

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

      // Reset completo della modalità selezione passando da una tabella all'altra
      isSelectionModeActive = false;
      const btnToggle = document.getElementById("btnToggleSelect");
      if (btnToggle) btnToggle.classList.remove("active");
      selectedProductIds.clear();
      updateSelectionBadge();

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

  // Chiusura al clic sullo sfondo scuro dei modali
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) {
        closeModal();
        closeBulkSaleModal();
      }
    });
  });

  // Chiusura al click fuori dal menu contestuale
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#tableContextMenu")) {
      hideContextMenu();
    }
  });

  // Chiusura rapida con tasto ESC
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
      closeModal();
      closeBulkSaleModal();
      hideContextMenu();
    }
  });
});
