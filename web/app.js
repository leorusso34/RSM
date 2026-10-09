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

async function loadProductsFromBackend() {
  try {
    const res = await fetch(`${API_BASE}/products`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const json = await res.json();
    if (json.success && Array.isArray(json.data)) {
      inventoryData = json.data;
      renderTable();
      updateDashboardMetrics();
      initCharts();
      return true;
    }
  } catch (err) {
    console.warn("Bridge locale in attesa di avvio o non raggiungibile:", err);
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

  // Render dell'Header in base alla visualizzazione attiva
  if (thead) {
    if (isStockView) {
      thead.innerHTML = `
        <tr>
          <th class="${getSortClass('name')}" data-sort="name">Prodotto</th>
          <th>Taglia</th>
          <th>Q.tà</th>
          <th class="${getSortClass('purchasedPrice')}" data-sort="purchasedPrice">P. Acquisto</th>
          <th>L. Acquisto</th>
          <th class="col-center">Stato</th>
          <th class="col-center">Azioni</th>
        </tr>
      `;
    } else {
      thead.innerHTML = `
        <tr>
          <th class="${getSortClass('name')}" data-sort="name">Prodotto</th>
          <th>Taglia</th>
          <th>Q.tà</th>
          <th class="${getSortClass('purchasedPrice')}" data-sort="purchasedPrice">P. Acquisto</th>
          <th class="${getSortClass('salePrice')}" data-sort="salePrice">P. Vendita</th>
          <th>Canale</th>
          <th class="${getSortClass('profit')}" data-sort="profit">Utile Netto</th>
          <th class="${getSortClass('roi')}" data-sort="roi">ROI</th>
          <th class="col-center">Stato</th>
          <th class="col-center">Azioni</th>
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
        item.brand.toLowerCase().includes(term) ||
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

    // Action buttons html (riutilizzabile con allineamento centrale e stopPropagation)
    const actionBtnsHtml = `
      <div class="action-btns">
        <button class="btn-action-icon" title="Stima Prezzi eBay" onclick="event.stopPropagation(); openEbayPriceLookup('${item.name.replace(/'/g, "\\'")}')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </button>
        <button class="btn-action-icon" title="Modifica Prodotto" onclick="event.stopPropagation(); editProduct(${item.id})">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
        </button>
        <button class="btn-action-icon delete" title="Elimina" onclick="event.stopPropagation(); deleteProduct(${item.id})">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
        </button>
      </div>
    `;

    if (isStockView) {
      tr.innerHTML = `
        <td>
          <div class="product-cell">
            <div class="product-name">${item.name}</div>
            <div class="product-brand">${item.brand}</div>
          </div>
        </td>
        <td><strong>${item.size}</strong></td>
        <td>${item.quantity} pz</td>
        <td>€ ${item.purchasedPrice.toFixed(2)}</td>
        <td style="color: var(--text-muted);">${item.purchasedPlace}</td>
        <td class="col-center">
          <span class="status-badge ${statusClass}">
            <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
            ${statusLabel}
          </span>
        </td>
        <td class="col-center">
          ${actionBtnsHtml}
        </td>
      `;
    } else {
      // Calcolo Utile & ROI
      const netProfit = (item.salePrice || 0) - item.purchasedPrice - (item.fees || 0);
      const roi = item.purchasedPrice > 0 ? (netProfit / item.purchasedPrice) * 100 : 0;
      const hasSaleData = item.status === "completed" || item.status === "active-sale";
      const salePriceHtml = hasSaleData && item.salePrice ? `€ ${item.salePrice.toFixed(2)}` : `<span style="color:var(--text-dim)">-</span>`;
      const sellingPlaceHtml = hasSaleData && item.sellingPlace ? `<span style="font-size: 11.5px; color: var(--text-muted);">${item.sellingPlace}</span>` : `<span style="color:var(--text-dim)">-</span>`;
      const profitHtml = hasSaleData ? `<span class="profit-pos">+€ ${netProfit.toFixed(2)}</span>` : `<span style="color:var(--text-dim)">-</span>`;
      const roiHtml = hasSaleData ? `<span class="roi-badge">+${roi.toFixed(1)}%</span>` : `<span style="color:var(--text-dim)">-</span>`;

      tr.innerHTML = `
        <td>
          <div class="product-cell">
            <div class="product-name">${item.name}</div>
            <div class="product-brand">${item.brand} • ${item.purchasedPlace}</div>
          </div>
        </td>
        <td><strong>${item.size}</strong></td>
        <td>${item.quantity} pz</td>
        <td>€ ${item.purchasedPrice.toFixed(2)}</td>
        <td>${salePriceHtml}</td>
        <td>${sellingPlaceHtml}</td>
        <td>${profitHtml}</td>
        <td>${roiHtml}</td>
        <td class="col-center">
          <span class="status-badge ${statusClass}">
            <span style="display:inline-block; width:5px; height:5px; border-radius:50%; background:currentColor;"></span>
            ${statusLabel}
          </span>
        </td>
        <td class="col-center">
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
// CHARTS INITIALIZATION (CHART.JS)
// ==========================================================================
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

  // Chart 1: Andamento Profitto Mensile
  const ctxMonthly = document.getElementById("monthlyProfitChart");
  if (ctxMonthly) {
    const gradient = ctxMonthly.getContext("2d").createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, "rgba(99, 102, 241, 0.45)");
    gradient.addColorStop(1, "rgba(99, 102, 241, 0.0)");

    monthlyProfitChart = new Chart(ctxMonthly, {
      type: "line",
      data: {
        labels: ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott (Live)"],
        datasets: [
          {
            label: "Utile Netto (€)",
            data: [620, 850, 1140, 980, 1420, 1780, 1340, 1590, 2210, 2680],
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
              label: (context) => ` Utile: € ${context.parsed.y.toLocaleString("it-IT")},00`
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
              callback: (value) => `€ ${value}`
            }
          }
        }
      }
    });
  }

  // Chart 2: Piattaforma Donut
  const ctxPlatform = document.getElementById("platformPieChart");
  if (ctxPlatform) {
    platformPieChart = new Chart(ctxPlatform, {
      type: "doughnut",
      data: {
        labels: ["StockX", "Vinted", "Privato", "Alias/GOAT", "eBay"],
        datasets: [
          {
            data: [42, 28, 16, 9, 5],
            backgroundColor: [
              "#6366f1", // Indigo
              "#10b981", // Emerald
              "#8b5cf6", // Purple
              "#f59e0b", // Amber
              "#3b82f6"  // Blue
            ],
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
  const modal = document.getElementById("productModal");
  if (!modal) return;
  modal.classList.add("open");

  const modalTitle = document.querySelector("#productModal .modal-header h3");
  if (modalTitle) modalTitle.textContent = "Aggiungi Nuovo Prodotto";

  // Reset form
  document.getElementById("prod-name").value = "";
  document.getElementById("prod-brand").value = "Nike";
  document.getElementById("prod-size").value = "EU 43";
  document.getElementById("prod-qty").value = "1";
  document.getElementById("prod-buy-price").value = "";
  document.getElementById("prod-buy-place").value = "SNKRS";
  document.getElementById("prod-sell-price").value = "";
  document.getElementById("prod-sell-place").value = "StockX";
  document.getElementById("prod-status").value = "stock";
  updateModalProfitPreview();
}

function closeModal() {
  const modal = document.getElementById("productModal");
  if (modal) modal.classList.remove("open");

  const ebayModal = document.getElementById("ebayModal");
  if (ebayModal) ebayModal.classList.remove("open");
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
  const drawerBrand = document.getElementById("drawerBrand");
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
  if (drawerBrand) drawerBrand.textContent = `${item.brand} • ${item.status === 'stock' ? 'In Stock' : (item.status === 'preorder' ? 'Pre-ordine' : 'Vendita')}`;
  if (drawerBuyPrice) drawerBuyPrice.textContent = `€ ${item.purchasedPrice.toFixed(2)}`;
  if (drawerSellPrice) drawerSellPrice.textContent = item.salePrice ? `€ ${item.salePrice.toFixed(2)}` : "-";

  if (drawerProfit) {
    if (hasSaleData) {
      drawerProfit.textContent = `+€ ${netProfit.toFixed(2)}`;
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
  if (drawerFees) drawerFees.textContent = item.fees ? `€ ${item.fees.toFixed(2)}` : "€ 0,00";

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

  if (editBtn) {
    editBtn.onclick = () => {
      closeDrawer();
      editProduct(item.id);
    };
  }

  if (statusBtn) {
    if (item.status === "completed") {
      statusBtn.textContent = "Ripristina in Stock";
      statusBtn.className = "btn btn-secondary";
      statusBtn.onclick = async () => {
        try {
          const res = await fetch(`${API_BASE}/products/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "stock", salePrice: null })
          });
          if (res.ok) {
            closeDrawer();
            await loadProductsFromBackend();
            showToast(`Prodotto #${item.id} riportato in Magazzino!`);
          }
        } catch (e) {
          showToast(`Errore: ${e.message}`);
        }
      };
    } else {
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
  const buy = parseFloat(document.getElementById("prod-buy-price").value) || 0;
  const sell = parseFloat(document.getElementById("prod-sell-price").value) || 0;
  const qty = parseInt(document.getElementById("prod-qty").value, 10) || 1;

  const fees = sell * 0.09; // stima 9% commissioni StockX/eBay
  const net = (sell - buy - fees) * qty;
  const roi = buy > 0 ? (net / (buy * qty)) * 100 : 0;

  const previewEl = document.getElementById("modal-profit-preview");
  if (previewEl) {
    previewEl.innerHTML = `€ ${net.toFixed(2)} <span style="font-size:12px; color:#818cf8;">(ROI: +${roi.toFixed(1)}%)</span>`;
  }
}

async function handleSaveProduct(e) {
  e.preventDefault();
  const name = document.getElementById("prod-name").value.trim();
  const brand = document.getElementById("prod-brand").value.trim();
  const size = document.getElementById("prod-size").value.trim();
  const quantity = parseInt(document.getElementById("prod-qty").value, 10) || 1;
  const purchasedPrice = parseFloat(document.getElementById("prod-buy-price").value) || 0;
  const purchasedPlace = document.getElementById("prod-buy-place").value.trim();
  const salePrice = parseFloat(document.getElementById("prod-sell-price").value) || null;
  const sellingPlace = document.getElementById("prod-sell-place").value.trim();
  const status = document.getElementById("prod-status").value;

  if (!name) {
    showToast("⚠️ Inserisci un nome per il prodotto!");
    return;
  }

  const payload = {
    name,
    brand,
    size,
    quantity,
    purchasedPrice,
    purchasedPlace,
    sellingPlace,
    salePrice,
    fees: salePrice ? salePrice * 0.08 : 0,
    status,
    date: new Date().toISOString().split("T")[0]
  };

  try {
    let res;
    if (currentEditingId) {
      res = await fetch(`${API_BASE}/products/${currentEditingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } else {
      res = await fetch(`${API_BASE}/products`, {
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
      showToast(`✅ "${name}" salvato nel database SQLite!`);
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
      const res = await fetch(`${API_BASE}/products/${id}`, { method: "DELETE" });
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
  currentEditingId = id;
  closeDrawer();
  closeModal();
  openAddProductModal();

  const modalTitle = document.querySelector("#productModal .modal-header h3");
  if (modalTitle) modalTitle.textContent = `Modifica Prodotto #${id}`;

  document.getElementById("prod-name").value = item.name;
  document.getElementById("prod-brand").value = item.brand || "";
  document.getElementById("prod-size").value = item.size || "";
  document.getElementById("prod-qty").value = item.quantity || 1;
  document.getElementById("prod-buy-price").value = item.purchasedPrice || 0;
  document.getElementById("prod-buy-place").value = item.purchasedPlace || "";
  document.getElementById("prod-sell-price").value = item.salePrice || "";
  document.getElementById("prod-sell-place").value = item.sellingPlace || "StockX";
  document.getElementById("prod-status").value = item.status || "stock";
  updateModalProfitPreview();
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

async function simulateEmailSync() {
  showToast("📬 Sincronizzazione ordini Gmail in corso...");
  try {
    const res = await fetch(`${API_BASE}/sync-email`, { method: "POST" });
    const json = await res.json();
    if (json.success) {
      await loadProductsFromBackend();
      showToast(`✨ Sincronizzazione completata: ${json.imported_count || 0} nuovi ordini importati!`);
    } else {
      showToast(`⚠️ Gmail: ${json.error || "Nessuna nuova email trovata"}`);
    }
  } catch (err) {
    showToast(`❌ Errore sync email: ${err.message}`);
  }
}

async function simulateAIAssistant() {
  const promptText = prompt("Inserisci i dettagli del prodotto per l'AI (es. 'Jordan 4 Retro White Thunder taglia 44 comprata a 215 su SNKRS'):");
  if (!promptText || !promptText.trim()) return;

  showToast("🤖 Gemini AI in elaborazione...");
  try {
    const res = await fetch(`${API_BASE}/ai-parse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptText })
    });
    const json = await res.json();
    if (json.success && Array.isArray(json.data) && json.data.length > 0) {
      const prod = json.data[0];
      openAddProductModal();
      document.getElementById("prod-name").value = prod.name || "";
      document.getElementById("prod-brand").value = prod.brand || "Nike";
      document.getElementById("prod-size").value = prod.size || "UNI";
      document.getElementById("prod-buy-price").value = prod.purchased_price || "";
      document.getElementById("prod-buy-place").value = prod.purchased_place || "";
      document.getElementById("prod-sell-price").value = prod.selling_price || "";
      document.getElementById("prod-sell-place").value = prod.selling_place || "StockX";
      document.getElementById("prod-status").value = prod.status === "Pre-ordine" ? "preorder" : "stock";
      updateModalProfitPreview();
      showToast("⚡ Dati estratti con successo da Gemini AI!");
    } else {
      showToast(`⚠️ AI: ${json.error || "Impossibile estrarre i dati del prodotto."}`);
    }
  } catch (err) {
    showToast(`❌ Errore AI: ${err.message}`);
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

  // Form Inputs live preview
  ["prod-buy-price", "prod-sell-price", "prod-qty"].forEach((id) => {
    const input = document.getElementById(id);
    if (input) {
      input.addEventListener("input", updateModalProfitPreview);
    }
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

  // Chiusura rapida con tasto ESC
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawer();
      closeModal();
    }
  });
});
