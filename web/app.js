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
        loadPlacesFromBackend();
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
let bulkSaleTargetIds = [];

// Storico Annulla (Undo Stack - Punto 6)
let undoStack = []; // Max 20 azioni
let clipboardProductIds = []; // Per scorciatoie Ctrl+C e Ctrl+V

function pushUndo(action) {
  undoStack.push(action);
  if (undoStack.length > 20) {
    undoStack.shift();
  }
}

async function performUndo() {
  if (undoStack.length === 0) {
    showToast("Nessuna azione da annullare.");
    return;
  }
  const action = undoStack.pop();
  try {
    if (action.type === "restore_records" && action.records && action.records.length > 0) {
      const res = await callApi("/undo/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ records: action.records }),
      });
      const json = await res.json();
      if (json.success) {
        await loadProductsFromBackend();
        showToast(`Annullato: ${action.desc}`);
      } else {
        showToast(`Errore durante l'annullamento: ${json.error}`);
      }
    } else if (action.type === "delete_ids" && action.ids && action.ids.length > 0) {
      const res = await callApi("/products/bulk-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: action.ids }),
      });
      const json = await res.json();
      if (json.success) {
        await loadProductsFromBackend();
        showToast(`Annullato: ${action.desc}`);
      } else {
        showToast(`Errore durante l'annullamento: ${json.error}`);
      }
    }
  } catch (err) {
    showToast(`Errore durante l'annullamento: ${err.message}`);
  }
}

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
    const stockPct = totalInvested > 0 ? Math.round((totalStockValue / totalInvested) * 100) : 0;
    if (kpiInvestedSub) kpiInvestedSub.textContent = `${stockCount} in stock • ${preorderCount} pre-ordini`;
    if (kpiStockSub) kpiStockSub.textContent = `${stockPct}% del capitale investito`;
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
        const sale = item.salePrice || 0;
        const fees = item.fees || 0;
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

    const stockPct = totalInvested > 0 ? Math.round((totalStockValue / totalInvested) * 100) : 0;

    if (kpiInvested) setMetricValue(kpiInvested, totalInvested, true);
    if (kpiStock) setMetricValue(kpiStock, totalStockValue, true);
    if (kpiProfit) setMetricValue(kpiProfit, totalProfit, true);
    if (kpiRoi) {
      kpiRoi.textContent = `${avgRoi >= 0 ? "+" : ""}${avgRoi.toFixed(1)}% ROI`;
      kpiRoi.className = `kpi-trend ${avgRoi >= 0 ? "positive" : "negative"}`;
    }
    if (kpiInvestedSub) kpiInvestedSub.textContent = `${stockCount} in stock • ${preorderCount} pre-ordini`;
    if (kpiStockSub) kpiStockSub.textContent = `${stockPct}% del capitale investito`;
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
  // Pre-calcolo aggregato dei bundle per consentire la ricerca sia sui singoli capi sia sui totali del bundle (es. prezzo acquisto totale bundle)
  const bundleTotalsMap = new Map();
  inventoryData.forEach((p) => {
    const bId = p.bundle_id || p.bundleId;
    if (bId) {
      if (!bundleTotalsMap.has(bId)) {
        bundleTotalsMap.set(bId, { totalPurchased: 0, totalSold: 0, totalFees: 0, allItems: [] });
      }
      const bInfo = bundleTotalsMap.get(bId);
      bInfo.allItems.push(p);
      const qty = p.quantity || 1;
      bInfo.totalPurchased += (p.purchasedPrice || 0) * qty;
      bInfo.totalSold += (p.salePrice || 0);
      bInfo.totalFees += (p.fees || 0);
    }
  });

  let filtered = inventoryData.filter((item) => {
    // 1. Filtro per stato tab
    if (activeFilter !== "all" && item.status !== activeFilter) return false;

    // 2. Filtro di ricerca testuale esteso (tutte le colonne tranne quantità, utile netto, roi, stato)
    if (searchTerm) {
      const terms = searchTerm.toLowerCase().trim().split(/\s+/).filter(Boolean);
      if (terms.length > 0) {
        const buyRaw = item.purchasedPrice !== undefined && item.purchasedPrice !== null ? String(item.purchasedPrice) : "";
        const buyFormatted = item.purchasedPrice ? formatMoney(item.purchasedPrice).toLowerCase() : "";
        const sellRaw = item.salePrice !== undefined && item.salePrice !== null ? String(item.salePrice) : "";
        const sellFormatted = item.salePrice ? formatMoney(item.salePrice).toLowerCase() : "";
        const feesRaw = item.fees !== undefined && item.fees !== null ? String(item.fees) : "";
        const feesFormatted = item.fees ? formatMoney(item.fees).toLowerCase() : "";

        // Se l'elemento fa parte di una vendita multipla (bundle), includiamo anche il totale di acquisto e vendita aggregato
        const bId = item.bundle_id || item.bundleId;
        const bInfo = bId ? bundleTotalsMap.get(bId) : null;
        let bBuyRaw = "";
        let bBuyFormatted = "";
        let bBuyComma = "";
        let bBuyDec = "";
        let bBuyDecComma = "";
        let bSellRaw = "";
        let bSellFormatted = "";
        let bSellComma = "";

        if (bInfo) {
          bBuyRaw = String(bInfo.totalPurchased);
          bBuyFormatted = formatMoney(bInfo.totalPurchased).toLowerCase();
          bBuyComma = String(bInfo.totalPurchased).replace(".", ",");
          bBuyDec = bInfo.totalPurchased.toFixed(2);
          bBuyDecComma = bInfo.totalPurchased.toFixed(2).replace(".", ",");

          bSellRaw = String(bInfo.totalSold);
          bSellFormatted = formatMoney(bInfo.totalSold).toLowerCase();
          bSellComma = String(bInfo.totalSold).replace(".", ",");
        }

        const searchBlob = [
          item.id !== undefined && item.id !== null ? String(item.id) : "",
          item.name || "",
          item.size || "",
          item.purchasedPlace || "",
          item.sellingPlace || "",
          item.notes || "",
          item.date || "",
          buyRaw,
          buyRaw.replace(".", ","),
          buyFormatted,
          sellRaw,
          sellRaw.replace(".", ","),
          sellFormatted,
          feesRaw,
          feesRaw.replace(".", ","),
          feesFormatted,
          bBuyRaw,
          bBuyComma,
          bBuyFormatted,
          bBuyDec,
          bBuyDecComma,
          bSellRaw,
          bSellComma,
          bSellFormatted
        ].join(" ").toLowerCase();

        const match = terms.every((t) => searchBlob.includes(t));
        if (!match) return false;
      }
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

  // Se la ricerca o i filtri matchano elementi di una vendita multipla, assicuriamo che tutti i prodotti
  // di quel bundle vengano mantenuti insieme per consentire alla riga bundle di mostrare il totale corretto
  const matchedBundleIds = new Set();
  filtered.forEach((item) => {
    const bId = item.bundle_id || item.bundleId;
    if (bId) matchedBundleIds.add(bId);
  });

  if (matchedBundleIds.size > 0) {
    const existingIds = new Set(filtered.map((i) => i.id));
    matchedBundleIds.forEach((bId) => {
      const bInfo = bundleTotalsMap.get(bId);
      if (bInfo && bInfo.allItems) {
        bInfo.allItems.forEach((p) => {
          if (!existingIds.has(p.id)) {
            if (activeFilter === "all" || p.status === activeFilter) {
              existingIds.add(p.id);
              filtered.push(p);
            }
          }
        });
      }
    });
  }

  // Ordinamento
  filtered.sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];

    if (sortField === "profit") {
      const qtyA = a.quantity || 1;
      const qtyB = b.quantity || 1;
      valA = (a.salePrice || 0) - ((a.purchasedPrice || 0) * qtyA) - (a.fees || 0);
      valB = (b.salePrice || 0) - ((b.purchasedPrice || 0) * qtyB) - (b.fees || 0);
    } else if (sortField === "roi") {
      const qtyA = a.quantity || 1;
      const qtyB = b.quantity || 1;
      const costA = (a.purchasedPrice || 0) * qtyA;
      const costB = (b.purchasedPrice || 0) * qtyB;
      const pA = (a.salePrice || 0) - costA - (a.fees || 0);
      const pB = (b.salePrice || 0) - costB - (b.fees || 0);
      valA = costA > 0 ? (pA / costA) * 100 : 0;
      valB = costB > 0 ? (pB / costB) * 100 : 0;
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
          <th class="col-qty col-center">Q.tà</th>
          <th class="col-buy ${getSortClass('purchasedPrice')}" data-sort="purchasedPrice">P. Acquisto</th>
          <th class="col-sell ${getSortClass('salePrice')}" data-sort="salePrice">P. Vendita</th>
          <th class="col-channel">Canale</th>
          <th class="col-fees ${getSortClass('fees')}" data-sort="fees">Spese / Comm.</th>
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
          <td class="col-qty col-center"><strong>${totalQty} pz</strong></td>
          <td class="col-buy">${formatMoney(totalPurchased)}</td>
          <td class="col-sell"><strong>${formatMoney(totalSold)}</strong></td>
          <td class="col-channel"><span style="font-size: 11.5px; color: var(--text-muted);">${sellingPlace}</span></td>
          <td class="col-fees">${totalFees > 0 ? formatMoney(totalFees) : '<span style="color:var(--text-dim)">-</span>'}</td>
          <td class="col-profit">${totalProfit > 0 ? `<span style="color: #34d399; font-weight: 700;">€ ${totalProfit.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>` : totalProfit < 0 ? `<span style="color: #ef4444; font-weight: 700;">-€ ${Math.abs(totalProfit).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>` : `<span style="color: var(--text-dim); font-weight: 600;">€ 0,00</span>`}</td>
          <td class="col-roi col-center">${totalRoi > 0 ? `<span style="color: #34d399; font-weight: 700;">${totalRoi.toFixed(1)}%</span>` : totalRoi < 0 ? `<span style="color: #ef4444; font-weight: 700;">${totalRoi.toFixed(1)}%</span>` : `<span style="color: var(--text-dim); font-weight: 600;">0.0%</span>`}</td>
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
                  <div class="product-name" style="color: var(--text-secondary); font-size: 12px;">${child.name}</div>
                  <div class="product-brand" style="font-size: 11px;">${child.purchasedPlace || "Magazzino"}</div>
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
                  <div class="product-name" style="color: var(--text-secondary); font-size: 12px;">${child.name}</div>
                  <div class="product-brand" style="font-size: 11px;">${child.purchasedPlace || "Magazzino"}</div>
                </div>
              </td>
              <td class="col-qty col-center">${child.quantity} pz</td>
              <td class="col-buy">${formatMoney(child.purchasedPrice)}</td>
              <td class="col-sell" style="color: var(--text-dim); font-size: 11.5px;">(in bundle)</td>
              <td class="col-channel"><span style="font-size: 11.5px; color: var(--text-dim);">${child.sellingPlace || "-"}</span></td>
              <td class="col-fees" style="color: var(--text-dim); font-size: 11.5px;">${child.fees ? formatMoney(child.fees) : "-"}</td>
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
      let statusLabel = "Magazzino";
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
              <div class="product-brand">${item.purchasedPlace || "Magazzino"}</div>
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
        const qty = item.quantity || 1;
        const totalCost = (item.purchasedPrice || 0) * qty;
        const netProfit = (item.salePrice || 0) - totalCost - (item.fees || 0);
        const roi = totalCost > 0 ? (netProfit / totalCost) * 100 : 0;
        const hasSaleData = item.status === "completed" || item.status === "active-sale";
        const salePriceHtml = hasSaleData && item.salePrice ? formatMoney(item.salePrice) : `<span style="color:var(--text-dim)">-</span>`;
        const sellingPlaceHtml = hasSaleData && item.sellingPlace ? `<span style="font-size: 11.5px; color: var(--text-muted);">${item.sellingPlace}</span>` : `<span style="color:var(--text-dim)">-</span>`;

        let profitHtml = `<span style="color:var(--text-dim)">-</span>`;
        if (hasSaleData) {
          if (netProfit > 0) {
            profitHtml = `<span style="color: #34d399; font-weight: 700;">€ ${netProfit.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>`;
          } else if (netProfit < 0) {
            profitHtml = `<span style="color: #ef4444; font-weight: 700;">-€ ${Math.abs(netProfit).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>`;
          } else {
            profitHtml = `<span style="color: var(--text-dim); font-weight: 600;">€ 0,00</span>`;
          }
        }

        let roiHtml = `<span style="color:var(--text-dim)">-</span>`;
        if (hasSaleData) {
          if (roi > 0) {
            roiHtml = `<span style="color: #34d399; font-weight: 700;">${roi.toFixed(1)}%</span>`;
          } else if (roi < 0) {
            roiHtml = `<span style="color: #ef4444; font-weight: 700;">${roi.toFixed(1)}%</span>`;
          } else {
            roiHtml = `<span style="color: var(--text-dim); font-weight: 600;">0.0%</span>`;
          }
        }

        const feesHtml = hasSaleData && item.fees ? formatMoney(item.fees) : `<span style="color:var(--text-dim)">-</span>`;

        tr.innerHTML = `
          ${checkboxTd}
          <td class="col-prod" title="${item.name}">
            <div class="product-cell">
              <div class="product-name">${item.name}</div>
              <div class="product-brand">${item.purchasedPlace || "Canale Diretto"}</div>
            </div>
          </td>
          <td class="col-qty col-center">${item.quantity} pz</td>
          <td class="col-buy">${formatMoney(item.purchasedPrice)}</td>
          <td class="col-sell">${salePriceHtml}</td>
          <td class="col-channel">${sellingPlaceHtml}</td>
          <td class="col-fees">${feesHtml}</td>
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
        devicePixelRatio: Math.max(window.devicePixelRatio || 1, 2),
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0f172a",
            titleColor: "#ffffff",
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

  // Chart 2: Piattaforme Reale (ripartizione per numero di vendite, base 100%)
  const ctxPlatform = document.getElementById("platformPieChart");
  if (ctxPlatform) {
    let platLabels = [];
    let platData = [];
    let platCounts = [];
    const platColors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#06b6d4", "#ec4899", "#6366f1", "#14b8a6"];

    // Raggruppamento per NUMERO DI VENDITE con normalizzazione case-insensitive
    const channelMap = new Map();

    inventoryData.forEach((item) => {
      const isSold = item.status === "completed" || item.status === "active-sale";
      if (!isSold) return;

      const rawPlace = (item.sellingPlace || "").trim();
      const lower = rawPlace.toLowerCase();
      const qty = parseInt(item.quantity, 10) || 1;

      let cleanLabel = rawPlace || "N.S.";
      if (lower === "ebay") cleanLabel = "eBay";
      else if (lower === "stockx") cleanLabel = "StockX";
      else if (lower === "vinted") cleanLabel = "Vinted";
      else if (lower === "restocks") cleanLabel = "Restocks";
      else if (lower === "wallapop") cleanLabel = "Wallapop";
      else if (!rawPlace || lower === "n.s." || lower === "n.s" || lower === "ns") cleanLabel = "N.S.";
      else cleanLabel = rawPlace.charAt(0).toUpperCase() + rawPlace.slice(1);

      const groupKey = cleanLabel.toLowerCase();
      if (channelMap.has(groupKey)) {
        channelMap.get(groupKey).count += qty;
      } else {
        channelMap.set(groupKey, { label: cleanLabel, count: qty });
      }
    });

    // Se inventoryData non ha ancora vendite attive o completate caricate, fallback su metricsData.platforms
    if (channelMap.size === 0 && metricsData && metricsData.platforms && Object.keys(metricsData.platforms).length > 0) {
      Object.entries(metricsData.platforms).forEach(([k, v]) => {
        const rawPlace = (k || "").trim();
        const lower = rawPlace.toLowerCase();
        let cleanLabel = rawPlace || "N.S.";
        if (lower === "ebay") cleanLabel = "eBay";
        else if (lower === "stockx") cleanLabel = "StockX";
        else if (lower === "vinted") cleanLabel = "Vinted";
        else if (lower === "restocks") cleanLabel = "Restocks";
        else if (!rawPlace || lower === "n.s.") cleanLabel = "N.S.";
        else cleanLabel = rawPlace.charAt(0).toUpperCase() + rawPlace.slice(1);

        const groupKey = cleanLabel.toLowerCase();
        const cnt = Number(v || 0);
        if (cnt > 0) {
          if (channelMap.has(groupKey)) {
            channelMap.get(groupKey).count += cnt;
          } else {
            channelMap.set(groupKey, { label: cleanLabel, count: cnt });
          }
        }
      });
    }

    const sortedChannels = Array.from(channelMap.values()).sort((a, b) => b.count - a.count);
    const totalSalesUnits = sortedChannels.reduce((sum, ch) => sum + ch.count, 0);

    if (sortedChannels.length > 0 && totalSalesUnits > 0) {
      platLabels = sortedChannels.map((item) => item.label);
      // Calibrazione rigorosa su base 100%
      platData = sortedChannels.map((item) => Number(((item.count / totalSalesUnits) * 100).toFixed(1)));
      platCounts = sortedChannels.map((item) => item.count);
    } else {
      platLabels = ["Nessuna vendita"];
      platData = [100];
      platCounts = [0];
    }

    const isNoSales = platLabels[0] === "Nessuna vendita";

    platformPieChart = new Chart(ctxPlatform, {
      type: "doughnut",
      data: {
        labels: platLabels,
        datasets: [
          {
            data: platData,
            backgroundColor: isNoSales ? ["#1e293b"] : platColors.slice(0, platLabels.length),
            borderWidth: 2,
            borderColor: "#0b0f19",
            hoverOffset: isNoSales ? 0 : 5
          }
        ]
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        devicePixelRatio: Math.max(window.devicePixelRatio || 1, 2),
        cutout: "68%",
        layout: {
          padding: {
            top: 4,
            bottom: 4,
            left: 6,
            right: 6
          }
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#ffffff",
              boxWidth: 9,
              boxHeight: 9,
              padding: 9,
              font: { size: 11, weight: "600", family: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" },
              generateLabels: (chart) => {
                const data = chart.data;
                if (data.labels.length && data.datasets.length) {
                  const dataset = data.datasets[0];
                  return data.labels.map((label, i) => {
                    const pct = dataset.data[i] || 0;
                    return {
                      text: `${label} (${pct}%)`,
                      fillStyle: dataset.backgroundColor[i],
                      strokeStyle: dataset.borderColor || "#0b0f19",
                      lineWidth: dataset.borderWidth || 1,
                      fontColor: "#ffffff",
                      hidden: false,
                      index: i
                    };
                  });
                }
                return [];
              }
            }
          },
          tooltip: {
            backgroundColor: "#0f172a",
            borderColor: "rgba(255, 255, 255, 0.15)",
            borderWidth: 1,
            titleColor: "#ffffff",
            bodyColor: "#f8fafc",
            titleFont: { size: 12, weight: "700" },
            bodyFont: { size: 11.5, weight: "500" },
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              label: (context) => {
                if (platLabels[0] === "Nessuna vendita") {
                  return " Nessuna vendita registrata";
                }
                const idx = context.dataIndex;
                const pct = context.parsed;
                const count = platCounts[idx] || 0;
                const plural = count === 1 ? "pezzo venduto" : "pezzi venduti";
                return ` ${context.label}: ${count} ${plural} (${pct}% del totale)`;
              }
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
function applyActiveSaleFieldLocks(isActiveSale) {
  const lockedInputIds = [
    "prod-name",
    "prod-size",
    "prod-qty",
    "prod-buy-place",
    "prod-sell-place",
    "prod-notes"
  ];
  const lockedLabelIds = [
    "lbl-prod-name",
    "lbl-prod-size",
    "lbl-prod-qty",
    "lbl-prod-buy-place",
    "lbl-prod-sell-place",
    "lbl-prod-notes"
  ];

  lockedInputIds.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.disabled = isActiveSale;
    el.classList.toggle("input-locked", isActiveSale);
  });

  lockedLabelIds.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("label-locked", isActiveSale);
  });

  const manageBtn = document.getElementById("btn-manage-places");
  if (manageBtn) {
    manageBtn.disabled = isActiveSale;
    manageBtn.classList.toggle("btn-locked", isActiveSale);
  }

  const noticeEl = document.getElementById("active-sale-lock-notice");
  if (noticeEl) {
    noticeEl.style.display = isActiveSale ? "flex" : "none";
  }
}

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

  applyActiveSaleFieldLocks(false);

  // Reset form pulito al 100% (senza dati fittizi)
  document.getElementById("prod-name").value = "";
  document.getElementById("prod-size").value = "";
  document.getElementById("prod-qty").value = "1";
  document.getElementById("prod-buy-price").value = "";
  document.getElementById("prod-buy-place").value = "";
  document.getElementById("prod-sell-place").value = "";
  document.getElementById("prod-sold-price").value = "";
  const feesEl = document.getElementById("prod-fees");
  if (feesEl) feesEl.value = "";
  document.getElementById("prod-status").value = "stock";
  const notesEl = document.getElementById("prod-notes");
  if (notesEl) notesEl.value = "";
  updateModalProfitPreview();
}

function onModalStatusChange(val) {
  if (currentEditingId !== null) {
    applyActiveSaleFieldLocks(val === "active-sale");
  }
  updateModalProfitPreview();
}

function closeModal() {
  document.querySelectorAll(".modal-backdrop").forEach((el) => {
    if (el.id === "updateModal" && isApplyingUpdate) return;
    el.classList.remove("open");
  });
  document.querySelectorAll(".autocomplete-dropdown.open").forEach((dd) => {
    dd.classList.remove("open");
  });
  const excelStatus = document.getElementById("excel-parse-status");
  if (excelStatus) excelStatus.textContent = "";
  const excelInput = document.getElementById("excelFileInput");
  if (excelInput) excelInput.value = "";
  if (typeof resetVoiceRecordingState === "function") {
    resetVoiceRecordingState();
  }
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

  const qty = item.quantity || 1;
  const totalCost = (item.purchasedPrice || 0) * qty;
  const netProfit = (item.salePrice || 0) - totalCost - (item.fees || 0);
  const roi = totalCost > 0 ? (netProfit / totalCost) * 100 : 0;
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
      if (netProfit > 0) {
        drawerProfit.textContent = `€ ${netProfit.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        drawerProfit.style.color = "#34d399";
      } else if (netProfit < 0) {
        drawerProfit.textContent = `-€ ${Math.abs(netProfit).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        drawerProfit.style.color = "#ef4444";
      } else {
        drawerProfit.textContent = "€ 0,00";
        drawerProfit.style.color = "var(--text-dim)";
      }
      drawerProfit.className = "drawer-metric-val";
    } else {
      drawerProfit.textContent = "-";
      drawerProfit.style.color = "";
      drawerProfit.className = "drawer-metric-val";
    }
  }

  if (drawerSize) drawerSize.textContent = item.size;
  if (drawerQty) drawerQty.textContent = `${item.quantity} pz`;
  if (drawerStore) drawerStore.textContent = item.purchasedPlace || "Store Ufficiale";
  if (drawerDate) drawerDate.textContent = item.date || "Recente";
  if (drawerChannel) drawerChannel.textContent = item.sellingPlace || "-";
  if (drawerRoi) {
    if (hasSaleData) {
      drawerRoi.textContent = `${roi.toFixed(1)}%`;
      drawerRoi.style.color = roi > 0 ? "#34d399" : roi < 0 ? "#ef4444" : "var(--text-dim)";
    } else {
      drawerRoi.textContent = "-";
      drawerRoi.style.color = "";
    }
  }
  if (drawerFees) drawerFees.textContent = item.fees ? formatMoney(item.fees) : "€ 0,00";

  if (drawerNotes) {
    drawerNotes.textContent = item.notes || `Prodotto autentico verificato (${item.name}). Condizioni perfette DSWT, scatola integra e accessori originali inclusi.`;
  }

  // Badge di stato
  const badgeEl = document.getElementById("drawerStatusBadge");
  const textEl = document.getElementById("drawerStatusText");
  let statusClass = "stock";
  let statusLabel = "Magazzino";
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
          <div class="drawer-timeline-title">Vendita Attiva</div>
          <div class="drawer-timeline-date">Piattaforma: ${item.sellingPlace || "Marketplace"}</div>
        </div>
      `;
    }

    if (item.status === "completed") {
      timelineHtml += `
        <div class="drawer-timeline-step completed">
          <div class="drawer-timeline-title">Vendita Conclusa & Accreditata</div>
          <div class="drawer-timeline-date">Utile netto incassato: ${netProfit >= 0 ? `€ ${netProfit.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : `-€ ${Math.abs(netProfit).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}</div>
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

function updateModalProfitPreview() {
  const buyEl = document.getElementById("prod-buy-price");
  const sellEl = document.getElementById("prod-sold-price");
  const feesEl = document.getElementById("prod-fees");
  const qtyEl = document.getElementById("prod-qty");
  const badge = document.getElementById("prod-modal-profit-badge");
  if (!badge) return;

  const buy = parseFloat((buyEl && buyEl.value) ? buyEl.value.replace(",", ".") : 0) || 0;
  const sell = parseFloat((sellEl && sellEl.value) ? sellEl.value.replace(",", ".") : 0) || 0;
  const fees = parseFloat((feesEl && feesEl.value) ? feesEl.value.replace(",", ".") : 0) || 0;
  const qty = parseInt(qtyEl && qtyEl.value ? qtyEl.value : 1, 10) || 1;

  if (sell > 0) {
    const totalCost = buy * qty;
    const netProfit = sell - totalCost - fees;
    const roi = totalCost > 0 ? (netProfit / totalCost) * 100 : 0;
    const sign = netProfit >= 0 ? "+" : "";
    badge.textContent = `Utile Netto: ${sign}${formatMoney(netProfit)} (${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% ROI)`;
    if (netProfit >= 0) {
      badge.style.color = "#10b981";
      badge.style.background = "rgba(16, 185, 129, 0.12)";
      badge.style.borderColor = "rgba(16, 185, 129, 0.25)";
    } else {
      badge.style.color = "#f43f5e";
      badge.style.background = "rgba(244, 63, 94, 0.12)";
      badge.style.borderColor = "rgba(244, 63, 94, 0.25)";
    }
  } else {
    badge.textContent = "In Stock (Nessuna vendita)";
    badge.style.color = "#8b9bb4";
    badge.style.background = "rgba(139, 155, 180, 0.1)";
    badge.style.borderColor = "rgba(139, 155, 180, 0.2)";
  }
}

async function handleSaveProduct(e) {
  e.preventDefault();
  const status = document.getElementById("prod-status").value;
  const existingItem = currentEditingId ? inventoryData.find((i) => i.id === currentEditingId) : null;
  const isLocked = existingItem && existingItem.status === "active-sale" && status === "active-sale";

  const rawName = document.getElementById("prod-name").value;
  const name = ((isLocked && existingItem.name) ? existingItem.name : rawName).trim();

  const rawSize = document.getElementById("prod-size").value;
  const size = ((isLocked && existingItem.size) ? existingItem.size : rawSize).trim();

  const rawQty = parseInt(document.getElementById("prod-qty").value, 10);
  const quantity = (isLocked && existingItem.quantity) ? existingItem.quantity : (rawQty || 1);

  const purchasedPrice = parseFloat(String(document.getElementById("prod-buy-price").value || "").replace(",", ".")) || 0;

  const rawBuyPlace = document.getElementById("prod-buy-place").value;
  const purchasedPlace = ((isLocked && existingItem.purchasedPlace !== undefined) ? existingItem.purchasedPlace : rawBuyPlace).trim();

  const rawSellPlace = document.getElementById("prod-sell-place").value;
  const sellingPlace = ((isLocked && existingItem.sellingPlace !== undefined) ? existingItem.sellingPlace : rawSellPlace).trim();

  const soldPriceEl = document.getElementById("prod-sold-price");
  const salePrice = soldPriceEl && soldPriceEl.value !== "" ? (parseFloat(String(soldPriceEl.value).replace(",", ".")) || null) : null;
  const feesEl = document.getElementById("prod-fees");
  const fees = feesEl && feesEl.value !== "" ? (parseFloat(String(feesEl.value).replace(",", ".")) || 0) : 0;
  const notesEl = document.getElementById("prod-notes");
  const rawNotes = notesEl ? notesEl.value : "";
  const notes = ((isLocked && existingItem.notes !== undefined) ? existingItem.notes : rawNotes).trim();

  if (!name) {
    showToast("Inserisci un nome per il prodotto!");
    return;
  }

  const prevSnapshot = existingItem ? JSON.parse(JSON.stringify(existingItem)) : null;
  const payload = {
    name,
    size,
    quantity,
    purchasedPrice,
    purchasedPlace,
    sellingPlace,
    salePrice,
    fees,
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
      if (isEdit && prevSnapshot) {
        pushUndo({
          type: "restore_records",
          desc: `Modifica "${prevSnapshot.name}"`,
          records: [prevSnapshot],
        });
      } else if (!isEdit && result.id) {
        pushUndo({
          type: "delete_ids",
          desc: `Creazione "${payload.name}"`,
          ids: [result.id],
        });
      }
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
    const snapshot = JSON.parse(JSON.stringify(item));
    try {
      const res = await callApi(`/products/${id}`, { method: "DELETE" });
      const result = await res.json();
      if (result.success) {
        pushUndo({
          type: "restore_records",
          desc: `Eliminazione "${snapshot.name}"`,
          records: [snapshot],
        });
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
  const feesEl = document.getElementById("prod-fees");
  if (feesEl) {
    feesEl.value = (item.fees !== null && item.fees !== undefined && item.fees > 0) ? item.fees : "";
  }
  document.getElementById("prod-status").value = item.status || "stock";
  const notesEl = document.getElementById("prod-notes");
  if (notesEl) notesEl.value = item.notes || "";
  applyActiveSaleFieldLocks(item.status === "active-sale");
  updateModalProfitPreview();
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

  // Parte sempre da zero elementi selezionati all'attivazione o disattivazione
  selectedProductIds.clear();
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
  const snapshots = JSON.parse(JSON.stringify(items));
  const ids = items.map((p) => p.id);
  try {
    const res = await callApi("/products/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    const json = await res.json();
    if (json.success) {
      pushUndo({
        type: "restore_records",
        desc: `Eliminazione vendita multipla (${snapshots.length} prodotti)`,
        records: snapshots,
      });
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
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  if (!isSelectionModeActive) {
    selectedProductIds.clear();
    updateSelectionBadge();
    renderTable();
  }
  if (ids.length === 1) {
    editProduct(ids[0]);
  }
}

async function ctxActionDuplicate() {
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  if (!isSelectionModeActive) {
    selectedProductIds.clear();
    updateSelectionBadge();
    renderTable();
  }
  if (ids.length === 0) return;
  try {
    const res = await callApi("/products/duplicate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    const json = await res.json();
    if (json.success && json.ids) {
      pushUndo({
        type: "delete_ids",
        desc: `Duplicazione di ${json.ids.length} prodotti`,
        ids: json.ids,
      });
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
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  openBulkSaleModal(ids);
}

async function ctxActionStock() {
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  if (ids.length === 0) return;
  if (!confirm(`Spostare ${ids.length} prodotti in Magazzino?`)) {
    if (!isSelectionModeActive) {
      selectedProductIds.clear();
      updateSelectionBadge();
      renderTable();
    }
    return;
  }

  const snapshots = inventoryData
    .filter((i) => ids.includes(i.id))
    .map((i) => JSON.parse(JSON.stringify(i)));

  try {
    const res = await callApi("/products/bulk-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, status: "stock" }),
    });
    const json = await res.json();
    if (json.success) {
      pushUndo({
        type: "restore_records",
        desc: `Spostamento in Magazzino (${snapshots.length} prodotti)`,
        records: snapshots,
      });
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
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  if (ids.length === 0) return;
  if (!confirm(`Contrassegnare ${ids.length} vendite come completate?`)) {
    if (!isSelectionModeActive) {
      selectedProductIds.clear();
      updateSelectionBadge();
      renderTable();
    }
    return;
  }

  const snapshots = inventoryData
    .filter((i) => ids.includes(i.id))
    .map((i) => JSON.parse(JSON.stringify(i)));

  try {
    const res = await callApi("/products/bulk-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, status: "completed" }),
    });
    const json = await res.json();
    if (json.success) {
      pushUndo({
        type: "restore_records",
        desc: `Completamento vendite (${snapshots.length} prodotti)`,
        records: snapshots,
      });
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
  const selectedRecords = inventoryData.filter((i) => selectedProductIds.has(i.id));
  hideContextMenu();
  if (!isSelectionModeActive) {
    selectedProductIds.clear();
    updateSelectionBadge();
    renderTable();
  }
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
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  if (!isSelectionModeActive) {
    selectedProductIds.clear();
    updateSelectionBadge();
    renderTable();
  }
  if (ids.length !== 1) return;
  const item = inventoryData.find((i) => i.id === ids[0]);
  if (item) {
    openEbayPriceLookup(item.name, item.size || "");
  }
}

async function ctxActionDelete() {
  const ids = Array.from(selectedProductIds);
  hideContextMenu();
  if (ids.length === 0) return;
  const msg = ids.length === 1
    ? "Eliminare definitivamente il prodotto selezionato?"
    : `Eliminare definitivamente ${ids.length} prodotti selezionati dal database SQLite?`;
  if (!confirm(msg)) {
    if (!isSelectionModeActive) {
      selectedProductIds.clear();
      updateSelectionBadge();
      renderTable();
    }
    return;
  }

  const snapshots = inventoryData
    .filter((i) => ids.includes(i.id))
    .map((i) => JSON.parse(JSON.stringify(i)));

  try {
    const res = await callApi("/products/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    const json = await res.json();
    if (json.success) {
      pushUndo({
        type: "restore_records",
        desc: `Eliminazione (${snapshots.length} prodotti)`,
        records: snapshots,
      });
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
function openBulkSaleModal(targetIds = null) {
  const modal = document.getElementById("bulkSaleModal");
  if (!modal) return;

  if (Array.isArray(targetIds) && targetIds.length > 0) {
    bulkSaleTargetIds = Array.from(targetIds);
  } else if (selectedProductIds.size > 0) {
    bulkSaleTargetIds = Array.from(selectedProductIds);
  } else {
    bulkSaleTargetIds = [];
  }

  const count = bulkSaleTargetIds.length;
  if (count === 0) return;

  const titleEl = document.getElementById("bulkSaleModalTitle");
  const subtitleEl = document.getElementById("bulkSaleModalSubtitle");
  const qtyGroup = document.getElementById("bulk-sale-qty-group");
  const qtySelect = document.getElementById("bulk-sale-qty-select");
  const qtyHint = document.getElementById("bulk-sale-qty-hint");
  const priceLabel = document.getElementById("bulk-sale-price-label");

  if (bulkSaleTargetIds.length === 1) {
    const singleId = bulkSaleTargetIds[0];
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
    if (titleEl) titleEl.textContent = `Metti in Vendita (${bulkSaleTargetIds.length} Prodotti)`;
    if (subtitleEl) subtitleEl.textContent = "Stai per mettere in vendita i prodotti selezionati insieme come bundle. Il prezzo totale e le commissioni verranno ripartiti equamente e verrà visualizzato un unico gruppo di vendita.";
    if (priceLabel) priceLabel.textContent = "Prezzo di Vendita TOTALE (€) *";
    if (qtyGroup) qtyGroup.style.display = "none";
  }

  updateDatalistsPlaces();

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
  document.querySelectorAll(".autocomplete-dropdown.open").forEach((dd) => {
    dd.classList.remove("open");
  });
  if (!isSelectionModeActive && selectedProductIds.size > 0) {
    selectedProductIds.clear();
    updateSelectionBadge();
    renderTable();
  }
  bulkSaleTargetIds = [];
}

async function handleBulkSaleSubmit(e) {
  if (e && typeof e.preventDefault === "function") {
    e.preventDefault();
  }
  const ids = bulkSaleTargetIds.length > 0 ? Array.from(bulkSaleTargetIds) : Array.from(selectedProductIds);
  if (ids.length === 0) {
    showToast("Nessun prodotto selezionato per la vendita.");
    return;
  }

  const priceVal = parseFloat(String(document.getElementById("bulk-sale-total-price").value || "").replace(",", ".")) || 0;
  const feesVal = parseFloat(String(document.getElementById("bulk-sale-total-fees").value || "").replace(",", ".")) || 0;
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

  const snapshots = inventoryData
    .filter((i) => ids.includes(i.id))
    .map((i) => JSON.parse(JSON.stringify(i)));

  try {
    const res = await callApi("/products/bulk-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (json.success) {
      pushUndo({
        type: "restore_records",
        desc: `Messa in vendita (${snapshots.length} prodotti)`,
        records: snapshots,
      });
      bulkSaleTargetIds = [];
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
// GESTIONE CANALI E LUOGHI DINAMICI (PUNTO 7)
// ==========================================================================
let availableSellingPlaces = [];
let availablePurchasedPlaces = [];

async function loadPlacesFromBackend() {
  try {
    const res = await fetch(`${API_BASE}/places`);
    if (res.ok) {
      const json = await res.json();
      if (json.success) {
        availablePurchasedPlaces = Array.isArray(json.purchased) ? json.purchased : [];
        availableSellingPlaces = Array.isArray(json.selling) ? json.selling : [];
        updateDatalistsPlaces();
        renderManagePlacesModal();
      }
    }
  } catch (err) {
    console.warn("Impossibile caricare canali/luoghi dal bridge:", err);
  }
}

function updateDatalistsPlaces() {
  const pListEl = document.getElementById("purchased-places-list");
  const sListEl = document.getElementById("selling-places-list");

  if (pListEl) {
    pListEl.innerHTML = availablePurchasedPlaces
      .map((p) => `<option value="${escapeHtml(p)}"></option>`)
      .join("");
  }

  if (sListEl) {
    sListEl.innerHTML = availableSellingPlaces
      .map((s) => `<option value="${escapeHtml(s)}"></option>`)
      .join("");
  }
}

// ==========================================================================
// AUTOCOMPLETE FLOATING PILL DROPDOWN (OPZIONE 1: BADGE & PILL)
// ==========================================================================
function highlightMatch(text, query) {
  if (!query) return escapeHtml(text);
  const index = text.toLowerCase().indexOf(query.toLowerCase());
  if (index === -1) return escapeHtml(text);
  const before = text.slice(0, index);
  const match = text.slice(index, index + query.length);
  const after = text.slice(index + query.length);
  return `${escapeHtml(before)}<span class="autocomplete-highlight">${escapeHtml(match)}</span>${escapeHtml(after)}`;
}

function setupFloatingPillAutocomplete(inputId, dropdownId, getItemsFn, typeBadge = "Marketplace") {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;

  let activeIndex = -1;

  function renderDropdown(filterText = "") {
    const items = getItemsFn() || [];
    const q = filterText.trim().toLowerCase();
    const filtered = q
      ? items.filter((item) => item.toLowerCase().includes(q))
      : items;

    activeIndex = -1;

    if (filtered.length === 0) {
      dropdown.innerHTML = `<div class="autocomplete-empty">Nessun suggerimento corrispondente</div>`;
      dropdown.classList.add("open");
      return;
    }

    const isPurchased = typeBadge.toLowerCase().includes("acquisto") || typeBadge.toLowerCase().includes("store");
    const iconSvg = isPurchased
      ? `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/></svg>`
      : `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z"/><circle cx="7" cy="7" r="1.5"/></svg>`;

    dropdown.innerHTML = filtered
      .map((item, idx) => {
        return `
          <div class="autocomplete-item" data-index="${idx}" data-val="${escapeHtml(item)}">
            <div class="autocomplete-item-left">
              <span class="autocomplete-item-icon ${isPurchased ? "purchased" : ""}">${iconSvg}</span>
              <span>${highlightMatch(item, q)}</span>
            </div>
            <span class="autocomplete-badge ${isPurchased ? "purchased" : ""}">${escapeHtml(typeBadge)}</span>
          </div>
        `;
      })
      .join("");

    dropdown.querySelectorAll(".autocomplete-item").forEach((el) => {
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        const val = el.getAttribute("data-val");
        if (val) {
          input.value = val;
          dropdown.classList.remove("open");
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });
    });

    // Calcolo dinamico dello spazio verticale per allungare la tendina senza tagliarla
    const rect = input.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom - 20;
    if (spaceBelow < 220 && rect.top > 250) {
      dropdown.style.top = "auto";
      dropdown.style.bottom = "calc(100% + 4px)";
      dropdown.style.maxHeight = `${Math.min(320, Math.floor(rect.top - 20))}px`;
    } else {
      dropdown.style.top = "calc(100% + 4px)";
      dropdown.style.bottom = "auto";
      dropdown.style.maxHeight = `${Math.min(320, Math.max(220, Math.floor(spaceBelow)))}px`;
    }

    dropdown.classList.add("open");
  }

  input.addEventListener("input", () => {
    renderDropdown(input.value);
  });

  input.addEventListener("focus", () => {
    renderDropdown(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (!dropdown.classList.contains("open")) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        renderDropdown(input.value);
        return;
      }
    }

    const items = dropdown.querySelectorAll(".autocomplete-item");
    if (items.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateActiveItem(items);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateActiveItem(items);
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && activeIndex < items.length) {
        e.preventDefault();
        const val = items[activeIndex].getAttribute("data-val");
        if (val) {
          input.value = val;
          dropdown.classList.remove("open");
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
      } else {
        dropdown.classList.remove("open");
      }
    } else if (e.key === "Escape") {
      dropdown.classList.remove("open");
    }
  });

  function updateActiveItem(items) {
    items.forEach((item, idx) => {
      item.classList.toggle("active", idx === activeIndex);
      if (idx === activeIndex) {
        item.scrollIntoView({ block: "nearest" });
      }
    });
  }
}

function initAllAutocompletes() {
  setupFloatingPillAutocomplete(
    "prod-buy-place",
    "dropdown-prod-buy-place",
    () => availablePurchasedPlaces,
    "Store"
  );
  setupFloatingPillAutocomplete(
    "prod-sell-place",
    "dropdown-prod-sell-place",
    () => availableSellingPlaces,
    "Marketplace"
  );
  setupFloatingPillAutocomplete(
    "bulk-sale-place",
    "dropdown-bulk-sale-place",
    () => availableSellingPlaces,
    "Marketplace"
  );
}

// Chiusura automatica al click fuori
document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete-wrap")) {
    document.querySelectorAll(".autocomplete-dropdown.open").forEach((dd) => {
      dd.classList.remove("open");
    });
  }
});

function openManagePlacesModal() {
  closeDrawer();
  const modal = document.getElementById("managePlacesModal");
  if (!modal) return;
  modal.classList.add("open");

  const input = document.getElementById("new-place-input");
  if (input) {
    input.value = "";
    setTimeout(() => input.focus(), 80);
  }

  renderManagePlacesModal();
  loadPlacesFromBackend();
}

function closeManagePlacesModal() {
  const modal = document.getElementById("managePlacesModal");
  if (modal) modal.classList.remove("open");
}

function renderManagePlacesModal() {
  const sellingContainer = document.getElementById("selling-places-chips");
  const purchasedContainer = document.getElementById("purchased-places-chips");
  const sellingCount = document.getElementById("selling-places-count");
  const purchasedCount = document.getElementById("purchased-places-count");

  if (sellingCount) {
    sellingCount.textContent = `${availableSellingPlaces.length} canal${availableSellingPlaces.length === 1 ? "e" : "i"}`;
  }
  if (purchasedCount) {
    purchasedCount.textContent = `${availablePurchasedPlaces.length} luog${availablePurchasedPlaces.length === 1 ? "o" : "hi"}`;
  }

  if (sellingContainer) {
    if (availableSellingPlaces.length === 0) {
      sellingContainer.innerHTML = '<span style="font-size:11px; color:var(--text-dim); padding:6px;">Nessun canale di vendita configurato.</span>';
    } else {
      sellingContainer.innerHTML = availableSellingPlaces
        .map((place) => {
          const safePlace = escapeHtml(place);
          return `<div class="place-chip">
            <span>${safePlace}</span>
            <button type="button" class="place-chip-del" title="Elimina canale" data-place="${safePlace}">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </button>
          </div>`;
        })
        .join("");

      sellingContainer.querySelectorAll(".place-chip-del").forEach((btn) => {
        btn.addEventListener("click", () => {
          const p = btn.getAttribute("data-place");
          if (p) deleteCustomPlace(p);
        });
      });
    }
  }

  if (purchasedContainer) {
    if (availablePurchasedPlaces.length === 0) {
      purchasedContainer.innerHTML = '<span style="font-size:11px; color:var(--text-dim); padding:6px;">Nessun luogo di acquisto registrato.</span>';
    } else {
      purchasedContainer.innerHTML = availablePurchasedPlaces
        .map((place) => {
          return `<div class="place-chip" style="background: rgba(99, 102, 241, 0.08); border-color: rgba(99, 102, 241, 0.2);">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" style="margin-right: 2px;"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/></svg>
            <span>${escapeHtml(place)}</span>
          </div>`;
        })
        .join("");
    }
  }
}

async function submitAddCustomPlace() {
  const input = document.getElementById("new-place-input");
  if (!input) return;
  const name = input.value.trim();
  if (!name) {
    showToast("Inserisci il nome del canale da aggiungere.");
    input.focus();
    return;
  }

  try {
    const res = await callApi("/places", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const json = await res.json();
    if (json.success) {
      input.value = "";
      showToast(`Canale "${name}" aggiunto con successo!`);
      await loadPlacesFromBackend();
    } else {
      showToast(`Errore: ${json.error || "Operazione non riuscita"}`);
    }
  } catch (err) {
    showToast(`Errore di rete: ${err.message}`);
  }
}

async function deleteCustomPlace(name) {
  if (!confirm(`Vuoi rimuovere il canale "${name}" dai suggerimenti?`)) return;

  try {
    const res = await callApi("/places/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const json = await res.json();
    if (json.success) {
      showToast(`Canale "${name}" rimosso!`);
      await loadPlacesFromBackend();
    } else {
      showToast(`Errore: ${json.error || "Operazione non riuscita"}`);
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
let isVoiceCountdown = false;
let voiceCountdownTimer = null;

function resetVoiceRecordingState() {
  if (voiceCountdownTimer) {
    clearInterval(voiceCountdownTimer);
    voiceCountdownTimer = null;
  }
  isVoiceCountdown = false;
  isVoiceRecording = false;
  const btn = document.getElementById("btn-mic");
  if (btn) {
    btn.classList.remove("recording");
    btn.classList.remove("countdown");
  }
}

function openAIModal() {
  closeDrawer();
  closeModal();
  resetVoiceRecordingState();
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

  // Se l'utente clicca mentre c'è il countdown attivo, annulla il conto alla rovescia
  if (isVoiceCountdown) {
    resetVoiceRecordingState();
    if (statusEl) statusEl.textContent = "Registrazione annullata.";
    try {
      await fetch(`${API_BASE}/speech/stop`, { method: "POST" });
    } catch (_) {}
    return;
  }

  // Se la registrazione è già attiva, il secondo clic la arresta e avvia la trascrizione con Gemini
  if (isVoiceRecording) {
    resetVoiceRecordingState();
    if (statusEl) statusEl.textContent = "Elaborazione audio e trascrizione con Gemini in corso...";

    try {
      const res = await fetch(`${API_BASE}/speech/stop`, { method: "POST" });
      const json = await res.json();
      if (json.success && json.text) {
        if (statusEl) statusEl.textContent = "Trascrizione vocale completata.";
        const current = promptEl.value.trim();
        promptEl.value = current ? `${current} ${json.text}` : json.text;
      } else {
        const errMsg = json.error || "Nessun parlato rilevato";
        if (statusEl) statusEl.textContent = errMsg;
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = `Errore trascrizione: ${err.message}`;
    }
    return;
  }

  // 1° Clic: Avvia countdown di 3 secondi per riscaldare buffer e microfono prima di parlare
  isVoiceCountdown = true;
  if (btn) {
    btn.classList.remove("recording");
    btn.classList.add("countdown");
  }

  // Avviamo già l'acquisizione nel thread Python così i driver audio e lo stream si stabilizzano
  try {
    const res = await fetch(`${API_BASE}/speech/start`, { method: "POST" });
    const json = await res.json();
    if (!json.success) {
      throw new Error(json.error || "Impossibile attivare il microfono");
    }
  } catch (err) {
    resetVoiceRecordingState();
    if (statusEl) statusEl.textContent = `Errore microfono: ${err.message}`;
    return;
  }

  // Countdown visivo 3... 2... 1... calmo e pulito
  let secondsLeft = 3;
  if (statusEl) {
    statusEl.innerHTML = `<span style="color: var(--text-muted); font-size: 11.5px;">In ascolto tra ${secondsLeft}s...</span>`;
  }

  voiceCountdownTimer = setInterval(() => {
    secondsLeft--;
    if (secondsLeft > 0) {
      if (statusEl) {
        statusEl.innerHTML = `<span style="color: var(--text-muted); font-size: 11.5px;">In ascolto tra ${secondsLeft}s...</span>`;
      }
    } else {
      clearInterval(voiceCountdownTimer);
      voiceCountdownTimer = null;
      isVoiceCountdown = false;
      isVoiceRecording = true;
      if (btn) {
        btn.classList.remove("countdown");
        btn.classList.add("recording");
      }
      if (statusEl) {
        statusEl.innerHTML = `<span style="color: #34d399; font-size: 11.5px;">In ascolto, puoi parlare. Clicca di nuovo sul microfono per elaborare.</span>`;
      }
    }
  }, 1000);
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
        <td style="font-weight: 600; color: #fff;">${escapeHtml(p.name || "Sconosciuto")}</td>
        <td class="col-center"><span class="table-size-pill">${escapeHtml(p.size || "UNI")}</span></td>
        <td class="col-center" style="color: var(--text-muted);">${p.quantity || 1} pz</td>
        <td class="col-center" style="font-weight: 700; color: #34d399;">${formatMoney(p.purchased_price || 0)}</td>
        <td style="color: var(--text-muted); font-size: 11px;">${escapeHtml(p.purchased_place || "-")}</td>
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
        <td style="font-weight: 600; color: #fff;">${escapeHtml(item.name || "Sconosciuto")}</td>
        <td class="col-center"><span class="table-size-pill">${escapeHtml(item.size || "UNI")}</span></td>
        <td class="col-center" style="color: var(--text-muted);">${item.quantity || 1} pz</td>
        <td class="col-center" style="font-weight: 700; color: #34d399;">${formatMoney(item.price || 0)}</td>
        <td style="color: var(--text-main); font-size: 11px;">${escapeHtml(item.store || "Email")}</td>
        <td class="col-center" style="color: var(--text-muted); font-size: 11px;">${escapeHtml(item.date || "-")}</td>
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
// AUTO-UPDATER & VERIFICA AGGIORNAMENTI (PUNTO 8)
// ==========================================================================
let currentAppVersion = "1.6.1";
let pendingUpdateInfo = null;
let updatePollingTimer = null;
let isApplyingUpdate = false;

async function checkForUpdates(isUserInitiated = false) {
  try {
    if (isUserInitiated) {
      showToast("Verifica aggiornamenti in corso...");
    }
    const res = await callApi("/updates/check");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (json.success) {
      if (json.current_version) {
        currentAppVersion = json.current_version;
        const verEl = document.getElementById("app-version-label");
        if (verEl) verEl.textContent = currentAppVersion;
      }

      if (json.has_update && json.update) {
        pendingUpdateInfo = json.update;
        const badge = document.getElementById("update-badge");
        if (badge) {
          badge.textContent = json.update.version || "NEW";
          badge.style.display = "inline-flex";
        }
        openUpdateModal(json.update);
      } else {
        pendingUpdateInfo = null;
        const badge = document.getElementById("update-badge");
        if (badge) badge.style.display = "none";
        if (isUserInitiated) {
          showToast(`RSM è già aggiornato all'ultima versione (v${currentAppVersion})!`);
        }
      }
    } else if (isUserInitiated) {
      showToast(`Errore verifica: ${json.error || "Impossibile verificare"}`);
    }
  } catch (err) {
    if (isUserInitiated) {
      showToast(`Errore verifica aggiornamenti: ${err.message}`);
    }
  }
}

function openUpdateModal(updateInfo) {
  if (!updateInfo) return;
  closeDrawer();
  closeModal();

  const modal = document.getElementById("updateModal");
  if (!modal) return;

  const targetVerEl = document.getElementById("update-target-version");
  const currVerEl = document.getElementById("update-current-version");
  const changelogEl = document.getElementById("update-changelog-box");
  const progressWrap = document.getElementById("update-progress-wrap");
  const progressBar = document.getElementById("update-progress-bar");
  const statusLabel = document.getElementById("update-status-label");
  const btnStart = document.getElementById("btn-update-start");
  const btnCancel = document.getElementById("btn-update-cancel");
  const closeX = document.getElementById("update-close-x");

  if (targetVerEl) targetVerEl.textContent = updateInfo.version || "Nuova";
  if (currVerEl) currVerEl.textContent = `v${currentAppVersion}`;
  if (changelogEl) changelogEl.textContent = updateInfo.changelog || "Nessuna nota di rilascio specificata.";

  if (progressWrap) progressWrap.style.display = "none";
  if (progressBar) progressBar.style.width = "0%";
  if (statusLabel) statusLabel.textContent = "Download dell'aggiornamento in corso...";
  if (btnStart) {
    btnStart.disabled = false;
    btnStart.style.display = "inline-flex";
    btnStart.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg><span>Aggiorna Ora</span>`;
  }
  if (btnCancel) {
    btnCancel.disabled = false;
    btnCancel.textContent = "Più Tardi";
  }
  if (closeX) closeX.style.display = "block";

  isApplyingUpdate = false;
  modal.classList.add("open");
}

function closeUpdateModal() {
  if (isApplyingUpdate) {
    showToast("Aggiornamento in corso, attendere il completamento...");
    return;
  }
  const modal = document.getElementById("updateModal");
  if (modal) modal.classList.remove("open");
  if (updatePollingTimer) {
    clearInterval(updatePollingTimer);
    updatePollingTimer = null;
  }
}

async function startAppUpdate() {
  if (isApplyingUpdate || !pendingUpdateInfo) return;
  isApplyingUpdate = true;

  const btnStart = document.getElementById("btn-update-start");
  const btnCancel = document.getElementById("btn-update-cancel");
  const closeX = document.getElementById("update-close-x");
  const progressWrap = document.getElementById("update-progress-wrap");
  const progressBar = document.getElementById("update-progress-bar");
  const statusLabel = document.getElementById("update-status-label");

  if (btnStart) btnStart.disabled = true;
  if (btnCancel) btnCancel.disabled = true;
  if (closeX) closeX.style.display = "none";
  if (progressWrap) progressWrap.style.display = "block";

  try {
    const res = await callApi("/updates/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ download_url: pendingUpdateInfo.download_url }),
    });
    const json = await res.json();
    if (!json.success) {
      throw new Error(json.error || "Impossibile avviare il download");
    }

    // Polling stato avanzamento
    updatePollingTimer = setInterval(async () => {
      try {
        const progRes = await fetch(`${API_BASE}/updates/progress`);
        if (!progRes.ok) return;
        const progJson = await progRes.json();
        if (progJson.success) {
          const pct = Math.round((progJson.progress || 0) * 100);
          if (progressBar) progressBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;

          if (progJson.message && statusLabel) {
            statusLabel.textContent = progJson.message;
          }

          if (progJson.status === "applying") {
            if (statusLabel) {
              statusLabel.innerHTML = '<span style="color:#10b981; font-weight:700;">Estrazione completata! Applicazione aggiornamento e riavvio di RSM in corso...</span>';
            }
            if (progressBar) progressBar.style.width = "100%";
            clearInterval(updatePollingTimer);
            updatePollingTimer = null;
          } else if (progJson.status === "error") {
            clearInterval(updatePollingTimer);
            updatePollingTimer = null;
            isApplyingUpdate = false;
            if (statusLabel) {
              statusLabel.innerHTML = `<span style="color:#ef4444;">Errore: ${escapeHtml(progJson.error || "Operazione non riuscita")}</span>`;
            }
            if (btnCancel) {
              btnCancel.disabled = false;
              btnCancel.textContent = "Chiudi";
            }
          }
        }
      } catch (_) {
        if (statusLabel) {
          statusLabel.innerHTML = '<span style="color:#10b981; font-weight:700;">Riavvio di RSM in corso...</span>';
        }
        clearInterval(updatePollingTimer);
        updatePollingTimer = null;
      }
    }, 250);
  } catch (err) {
    isApplyingUpdate = false;
    if (statusLabel) {
      statusLabel.innerHTML = `<span style="color:#ef4444;">Errore: ${escapeHtml(err.message)}</span>`;
    }
    if (btnCancel) {
      btnCancel.disabled = false;
      btnCancel.textContent = "Chiudi";
    }
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
    let labelStatus = "Magazzino";
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
      <td class="col-center" style="color: var(--text-muted);">${parseInt(p.quantity, 10) || 1} pz</td>
      <td class="col-center" style="font-weight: 700; color: #34d399;">${formattedPrice}</td>
      <td style="color: var(--text-muted); font-size: 11px;">${escapeHtml(p.purchased_place || "-")}</td>
      <td style="color: var(--text-muted); font-size: 11px;">${escapeHtml(p.selling_place || "-")}</td>
      <td class="col-center">
        <span class="status-badge ${statusClass}">
          <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
          ${labelStatus}
        </span>
      </td>
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
// MONITORAGGIO DINAMICO LATENZA BRIDGE SQLITE LOCALE
// ==========================================================================
async function pingBridgeLatency() {
  const latencyEl = document.getElementById("bridge-latency-val");
  const indicatorEl = document.getElementById("bridge-status-indicator");
  if (!latencyEl) return;
  try {
    const t0 = performance.now();
    const res = await fetch(`${API_BASE}/version`, { cache: "no-store" });
    const ms = Math.max(1, Math.round(performance.now() - t0));
    if (res.ok) {
      latencyEl.textContent = `${ms}ms`;
      if (indicatorEl) {
        indicatorEl.style.background = "#10b981";
        indicatorEl.style.boxShadow = "0 0 6px rgba(16, 185, 129, 0.6)";
      }
    } else {
      latencyEl.textContent = "Offline";
      if (indicatorEl) {
        indicatorEl.style.background = "#ef4444";
        indicatorEl.style.boxShadow = "0 0 6px rgba(239, 68, 68, 0.6)";
      }
    }
  } catch (_) {
    latencyEl.textContent = "Offline";
    if (indicatorEl) {
      indicatorEl.style.background = "#ef4444";
      indicatorEl.style.boxShadow = "0 0 6px rgba(239, 68, 68, 0.6)";
    }
  }
}

// ==========================================================================
// EVENT LISTENERS & INIZIALIZZAZIONE
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
  // Disabilita il menu contestuale predefinito del browser (Microsoft Edge / WebView2)
  window.addEventListener("contextmenu", (e) => {
    const tag = e.target.tagName ? e.target.tagName.toLowerCase() : "";
    const isTextInput = tag === "input" || tag === "textarea" || e.target.isContentEditable;
    if (!isTextInput) {
      e.preventDefault();
    }
  });

  pingBridgeLatency();
  setInterval(pingBridgeLatency, 10000);
  loadProductsFromBackend();
  loadPlacesFromBackend();
  initAllAutocompletes();
  initCharts();
  updateDashboardMetrics();
  renderTable();

  // Controllo automatico aggiornamenti in background (Punto 8)
  setTimeout(() => {
    checkForUpdates(false);
  }, 1000);

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
        if (backdrop.id === "updateModal" && isApplyingUpdate) return;
        closeModal();
        closeBulkSaleModal();
        closeUpdateModal();
      }
    });
  });

  // Chiusura al click fuori dal menu contestuale (solo se il menu è effettivamente aperto)
  document.addEventListener("click", (e) => {
    const menu = document.getElementById("tableContextMenu");
    const isMenuOpen = menu && menu.style.display !== "none" && menu.style.display !== "";
    if (isMenuOpen && !e.target.closest("#tableContextMenu")) {
      hideContextMenu();
      if (!isSelectionModeActive && selectedProductIds.size > 0) {
        selectedProductIds.clear();
        updateSelectionBadge();
        renderTable();
      }
    }
  });

  // Scorciatoie Avanzate Tastiera (Punto 6)
  let lastCtrlPressTime = 0;

  window.addEventListener("keyup", (e) => {
    if (e.key === "Control") {
      const now = Date.now();
      if (now - lastCtrlPressTime < 320 && now - lastCtrlPressTime > 40) {
        lastCtrlPressTime = 0;
        toggleSelectionMode();
        showToast(isSelectionModeActive ? "Modalità Selezione: Attivata" : "Modalità Selezione: Disattivata");
      } else {
        lastCtrlPressTime = now;
      }
    } else {
      lastCtrlPressTime = 0;
    }
  });

  window.addEventListener("keydown", async (e) => {
    // Chiusura rapida con tasto ESC
    if (e.key === "Escape") {
      if (isApplyingUpdate) return;
      closeDrawer();
      closeModal();
      closeBulkSaleModal();
      closeUpdateModal();
      hideContextMenu();
      if (!isSelectionModeActive && selectedProductIds.size > 0) {
        selectedProductIds.clear();
        updateSelectionBadge();
        renderTable();
      }
      return;
    }

    const isInputActive = e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT";
    const isCtrl = e.ctrlKey || e.metaKey;

    // 1. Ctrl + F: Ricerca rapida immediata
    if (isCtrl && (e.key === "f" || e.key === "F")) {
      e.preventDefault();
      const searchInput = document.getElementById("global-search-input");
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // 2. Ctrl + Z: Storico Annulla (Undo Stack)
    if (isCtrl && (e.key === "z" || e.key === "Z") && !e.shiftKey) {
      if (!isInputActive) {
        e.preventDefault();
        await performUndo();
        return;
      }
    }

    // 3. Ctrl + Tab / Ctrl + Shift + Tab: Spostamento ciclico tra tabelle
    if (isCtrl && e.key === "Tab") {
      e.preventDefault();
      const tabKeys = ["all", "stock", "preorder", "active-sale", "completed"];
      const currentIdx = tabKeys.indexOf(activeFilter);
      const step = e.shiftKey ? -1 : 1;
      const nextIdx = (currentIdx + step + tabKeys.length) % tabKeys.length;
      activeFilter = tabKeys[nextIdx];

      isSelectionModeActive = false;
      const btnToggle = document.getElementById("btnToggleSelect");
      if (btnToggle) btnToggle.classList.remove("active");
      selectedProductIds.clear();
      updateSelectionBadge();

      document.querySelectorAll(".table-tab-pill").forEach((pill) => {
        pill.classList.toggle("active", pill.getAttribute("data-filter") === activeFilter);
      });
      document.querySelectorAll(".nav-item").forEach((item) => {
        const sec = item.getAttribute("data-section");
        let matches = false;
        if (activeFilter === "stock" && sec === "magazzino") matches = true;
        else if (activeFilter === "preorder" && sec === "preordini") matches = true;
        else if (activeFilter === "active-sale" && sec === "vendite") matches = true;
        else if (activeFilter === "completed" && sec === "storico") matches = true;
        else if (activeFilter === "all" && !["magazzino", "preordini", "vendite", "storico"].includes(sec)) matches = true;
        item.classList.toggle("active", matches);
      });

      renderTable();
      const pillActive = document.querySelector(".table-tab-pill.active");
      if (pillActive) {
        showToast(`Tabella: ${pillActive.textContent.trim()}`);
      }
      return;
    }

    // 4. Ctrl + C: Copia prodotti selezionati
    if (isCtrl && (e.key === "c" || e.key === "C") && !isInputActive) {
      if (selectedProductIds.size > 0) {
        e.preventDefault();
        clipboardProductIds = Array.from(selectedProductIds);
        const selItems = inventoryData.filter((p) => selectedProductIds.has(p.id));
        const tsv = selItems.map((p) => `${p.name}\t${p.size}\t${p.quantity}\t${p.purchasedPrice}\t${p.purchasedPlace}\t${p.sellingPlace || ""}\t${p.salePrice || ""}\t${p.fees || ""}`).join("\n");
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(tsv).catch(() => {});
        }
        showToast(`Copiati ${clipboardProductIds.length} prodott${clipboardProductIds.length === 1 ? "o" : "i"} negli appunti.`);
        return;
      }
    }

    // 5. Ctrl + V: Incolla prodotti duplicandoli
    if (isCtrl && (e.key === "v" || e.key === "V") && !isInputActive) {
      if (clipboardProductIds.length > 0) {
        e.preventDefault();
        try {
          const res = await callApi("/products/duplicate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: clipboardProductIds }),
          });
          const json = await res.json();
          if (json.success && json.ids) {
            pushUndo({
              type: "delete_ids",
              desc: `Incollati ${json.ids.length} prodotti`,
              ids: json.ids,
            });
            await loadProductsFromBackend();
            showToast(`Incollati ${json.ids.length} prodott${json.ids.length === 1 ? "o" : "i"} con successo.`);
          } else {
            showToast(`Errore durante l'incolla: ${json.error || "Operazione non riuscita"}`);
          }
        } catch (err) {
          showToast(`Errore di rete: ${err.message}`);
        }
        return;
      }
    }

    // 6. Ctrl + Shift + Freccia Su / Giù (o Shift + Freccia Su / Giù): Selezione a intervallo da tastiera
    if (e.shiftKey && (e.key === "ArrowUp" || e.key === "ArrowDown") && !isInputActive) {
      e.preventDefault();
      const visible = getFilteredAndSortedProducts();
      if (visible.length === 0) return;

      if (!isSelectionModeActive) {
        isSelectionModeActive = true;
        const btn = document.getElementById("btnToggleSelect");
        if (btn) btn.classList.add("active");
        selectedProductIds.clear();
      }

      const visibleIds = visible.map((p) => p.id);
      if (selectedProductIds.size === 0) {
        selectedProductIds.add(visibleIds[0]);
      } else {
        let lastIdx = -1;
        visibleIds.forEach((id, idx) => {
          if (selectedProductIds.has(id)) lastIdx = idx;
        });

        if (e.key === "ArrowDown") {
          const nextIdx = Math.min(visibleIds.length - 1, lastIdx + 1);
          selectedProductIds.add(visibleIds[nextIdx]);
        } else if (e.key === "ArrowUp") {
          let firstIdx = visibleIds.findIndex((id) => selectedProductIds.has(id));
          const prevIdx = Math.max(0, firstIdx - 1);
          selectedProductIds.add(visibleIds[prevIdx]);
        }
      }

      updateSelectionBadge();
      renderTable();
      return;
    }
  });
});
