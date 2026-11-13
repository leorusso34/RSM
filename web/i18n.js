/**
 * ============================================================================
 * RUSSO STOCK MANAGER (RSM) - MODULO INTERNAZIONALIZZAZIONE (i18n)
 * ============================================================================
 * Gestione centralizzata bilingue Italiano (it) e Inglese (en).
 * Rilevamento automatico della lingua, persistenza sicura in localStorage,
 * helper di traduzione t(key, params) e applicazione reattiva al DOM.
 */

// Dizionari completi per Italiano ed Inglese
window.RSM_I18N = {
  it: {
    common: {
      pcs: "pz",
      daysShort: "gg",
      cancel: "Annulla",
      close: "Chiudi",
      edit: "Modifica",
      delete: "Elimina",
      show: "Mostra",
      unknown: "Sconosciuto",
      closeEsc: "Chiudi (ESC)"
    },
    titlebar: {
      deliveryNotifications: "Notifiche Consegne",
      clearAll: "Pulisci tutto",
      noNotifications: "Nessuna notifica presente",
      minimize: "Riduci a icona",
      maximize: "Ingrandisci o Ripristina",
      close: "Chiudi finestra"
    },
    sidebar: {
      openSidebar: "Apri barra laterale",
      addProductTooltip: "Aggiungi prodotto all'inventario",
      newProduct: "Nuovo Prodotto",
      closeSidebar: "Nascondi barra laterale",
      sqliteDb: "Database Locale SQLite",
      syncedLatency: "Sincronizzato • Latenza",
      langSelector: "Selettore lingua"
    },
    nav: {
      overview: "PANORAMICA",
      dashboard: "Dashboard & Grafici",
      stock: "Magazzino",
      preorders: "Pre-ordini",
      activeSales: "Vendite Attive",
      salesHistory: "Storico Vendite",
      integrations: "INTEGRAZIONI",
      aiAssistant: "Assistente AI Gemini",
      emailSync: "Sincronizzazione Email",
      importExcel: "Importa Excel / CSV",
      channelsPlaces: "Canali & Luoghi",
      packlinkShipments: "Spedizioni Packlink",
      updates: "Aggiornamenti"
    },
    kpi: {
      investedCapital: "Capitale Investito",
      investedSub: "{stockCount} in stock • {preorderCount} pre-ordini",
      stockValue: "Valore Magazzino",
      stockSub: "{pct}% del capitale investito",
      profitRoi: "Profitto Netto & ROI",
      profitSub: "{completedCount} completate • {activeCount} attive"
    },
    stockHealth: {
      toggleTooltip: "Clicca per espandere/comprimere il dettaglio macro-blocchi",
      normalTooltip: "Regolare (<60gg)",
      warningTooltip: "Attenzione (60-90gg)",
      criticalTooltip: "Dead Stock (>90gg)",
      detailsTooltip: "Espandi / Comprimi dettagli",
      details: "Dettagli",
      filterNormalTooltip: "Clicca per filtrare prodotti regolari (<60gg)",
      normalBadge: "< 60 giorni",
      normalLabel: "Regolare",
      filterWarningTooltip: "Clicca per filtrare prodotti in attenzione (60-90gg)",
      warningBadge: "60 - 90 giorni",
      warningLabel: "Attenzione",
      filterCriticalTooltip: "Clicca per filtrare prodotti dead stock (>90gg)",
      criticalBadge: "> 90 giorni",
      criticalLabel: "Dead Stock"
    },
    charts: {
      monthlyProfitTitle: "Andamento Profitto Mensile (€)",
      monthlyProfitSub: "Guadagno netto mese per mese",
      timeframe1Year: "1 Anno",
      timeframe6Months: "6 Mesi",
      timeframeAll: "Tutto",
      salesChannelsTitle: "Canali di Vendita",
      salesChannelsSub: "Ripartizione numero vendite",
      months: ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"],
      noSalesData: "Nessun dato vendite",
      netProfitLabel: "Utile Netto (€)",
      profitTooltip: "Utile",
      noSales: "Nessuna vendita",
      noSalesRecorded: "Nessuna vendita registrata",
      soldItemSingle: "pezzo venduto",
      soldItemPlural: "pezzi venduti",
      pctOfTotal: "({pct}% del totale)"
    },
    table: {
      tabAll: "Tutti i Prodotti",
      tabStock: "Magazzino",
      tabPreorder: "Pre-ordini",
      tabActive: "Vendite Attive",
      tabCompleted: "Vendite Completate",
      searchPlaceholder: "Cerca prodotto o luogo...",
      toggleSelectTooltip: "Attiva/Disattiva modalità selezione",
      select: "Seleziona",
      toggleFiltersTooltip: "Mostra/Nascondi filtri avanzati",
      filters: "Filtri",
      resetFilters: "Azzera",
      sortTooltip: "Ordina tabella",
      colProduct: "Prodotto",
      colSize: "Taglia",
      colQty: "Q.tà",
      colBuyPrice: "P. Acquisto",
      colBuyPlace: "L. Acquisto",
      colStatus: "Stato",
      colActions: "Azioni",
      colSellPrice: "P. Vendita",
      colChannel: "Canale",
      colFees: "Spese / Comm.",
      colProfit: "Utile Netto",
      colRoi: "ROI",
      emptyState: "Nessun prodotto trovato per i criteri selezionati.",
      bundleTitle: "Vendita Multipla ({names})",
      bundleTag: "Bundle",
      included: "(incluso)",
      collapse: "Comprimi",
      expand: "Espandi",
      deleteBundle: "Elimina Vendita Multipla",
      agingCriticalTooltip: "In giacenza da {days} giorni (> 90 gg - Dead Stock)",
      agingWarningTooltip: "In giacenza da {days} giorni (60-90 gg)",
      agingNormalTooltip: "In giacenza da {days} giorni",
      directChannel: "Canale Diretto",
      estimateEbayPrices: "Stima Prezzi eBay",
      editProduct: "Modifica Prodotto",
      delete: "Elimina"
    },
    sort: {
      header: "CRITERIO DI ORDINAMENTO",
      dateDesc: "Ultima aggiunta (Recenti)",
      dateAsc: "Prima aggiunta (Vecchi)",
      buyPriceDesc: "Prezzo acquisto (Più alto)",
      buyPriceAsc: "Prezzo acquisto (Più basso)",
      sellPriceDesc: "Prezzo vendita (Più alto)",
      profitDesc: "Utile netto (Maggiore)",
      roiDesc: "ROI (%) (Maggiore)",
      nameAsc: "Nome prodotto (A → Z)"
    },
    filters: {
      buyPlace: "Luogo Acquisto",
      allPlaces: "Tutti i luoghi",
      sellPlace: "Luogo Vendita",
      allMarketplaces: "Tutti i marketplace",
      minPrice: "Prezzo Min (€)",
      maxPrice: "Prezzo Max (€)",
      reset: "Azzera",
      deadStockFilter: "Filtra Fermi (>60gg)",
      showAll: "Mostra Tutti"
    },
    selection: {
      capsuleRegion: "Riepilogo prodotti selezionati",
      costLabel: "Spesa:",
      avgLabel: "Media:",
      saleLabel: "Vendita:",
      profitLabel: "Utile:",
      clearTooltip: "Deseleziona tutti i prodotti (Esc)",
      countOnly: "{count} sel.",
      countWithQty: "{count} sel. ({qty} pz)",
      selectedShort: "sel."
    },
    capsule: {
      countOnly: "{count} sel.",
      countWithQty: "{count} sel. ({qty} pz)",
      selectedShort: "sel."
    },
    modal: {
      addProductTitle: "Aggiungi Prodotto all'Inventario",
      editProductTitle: "Modifica Prodotto",
      activeSaleNotice: "Vendita attiva: anagrafica prodotto bloccata. Puoi aggiornare prezzo vendita, canale, commissioni e note.",
      productName: "Nome Prodotto / Modello",
      size: "Taglia",
      quantity: "Quantità",
      purchasePlace: "Luogo di Acquisto",
      purchasePlacePlaceholder: "es. Nike, SNKRS, Foot Locker...",
      sellingChannel: "Canale di Vendita",
      manage: "Gestisci",
      sellingChannelPlaceholder: "es. StockX, Vinted, eBay, Privato...",
      economicData: "Dati Economici",
      profitStockNoSale: "In Stock (Nessuna vendita)",
      inStockNoSale: "In Stock (Nessuna vendita)",
      netProfitPrefix: "Utile Netto:",
      buyPrice: "Prezzo Acquisto (€) *",
      salePrice: "Prezzo Vendita (€)",
      fees: "Commissioni / Spese (€)",
      status: "Stato",
      statusStock: "Magazzino",
      statusPreorder: "Pre-ordine",
      statusActive: "Vendita attiva",
      statusCompleted: "Venduto",
      notes: "Note",
      saveToDb: "Salva nel Database",
      saveProduct: "Salva nel Database",
      updateProduct: "Aggiorna Prodotto"
    },
    status: {
      stock: "Magazzino",
      preorder: "Pre-ordine",
      activeSale: "In Vendita",
      completed: "Venduto"
    },
    ebay: {
      marketPrices: "Prezzi di Mercato eBay",
      loading: "Caricamento...",
      fetching: "Recupero prezzi in corso...",
      minimum: "MINIMO",
      average: "MEDIO",
      maximum: "MASSIMO",
      viewOnEbay: "Vedi su eBay",
      sizePrefix: "taglia",
      analyzedCount: "Analizzate {count} inserzioni controllate su eBay.it",
      noResults: "Nessun risultato trovato"
    },
    ai: {
      quickEntry: "Inserimento Rapido con AI",
      description: "Descrivi i prodotti a voce o per testo, Gemini li estrarrà automaticamente.",
      promptLabel: "COSA VUOI AGGIUNGERE?",
      voiceDictationTooltip: "Dettatura vocale con microfono",
      extractedProducts: "Prodotti Estratti:",
      colProduct: "Prodotto",
      colSize: "Taglia",
      colQty: "Q.tà",
      colBuyPrice: "P. Acquisto",
      colPlace: "Luogo",
      analyzeAndCreate: "Analizza e Crea",
      saveToInventory: "Salva nell'Inventario",
      recordingCancelled: "Registrazione annullata.",
      transcribingAudio: "Elaborazione audio e trascrizione con Gemini in corso...",
      transcriptionCompleted: "Trascrizione vocale completata.",
      noSpeechDetected: "Nessun parlato rilevato",
      transcriptionError: "Errore trascrizione: {error}",
      micError: "Errore microfono: {error}",
      listeningIn: "In ascolto tra {seconds}s...",
      listeningPrompt: "In ascolto, puoi parlare. Clicca di nuovo sul microfono per elaborare.",
      toastEnterText: "Scrivi o detta i prodotti prima di analizzare.",
      analyzingText: "Analisi del testo con Gemini in corso...",
      noValidProducts: "Nessun prodotto valido rilevato dall'AI."
    },
    email: {
      syncOrders: "Sincronizzazione Ordini via Email",
      description: "Scarica le conferme d'ordine non lette da Gmail ed estrai automaticamente i dettagli dei prodotti tramite intelligenza artificiale.",
      addressLabel: "Email Gmail:",
      pwdLabel: "Password App (16 car.):",
      pwdPlaceholder: "Inserisci password a 16 caratteri",
      testConnection: "Test Connessione",
      saveCredentials: "Salva Dati",
      helpText: "Inserisci una password per le app di Google generata dal tuo account di sicurezza. È richiesta l'autenticazione a due fattori (2FA) sul tuo account Google.",
      startScan: "Avvia Scansione Email Non Lette",
      readyStatus: "Pronto per la scansione delle email.",
      colDetectedProduct: "PRODOTTO RILEVATO",
      colSize: "TAGLIA",
      colQty: "Q.TÀ",
      colPrice: "PREZZO",
      colStore: "NEGOZIO",
      colOrderDate: "DATA ORDINE",
      emptyList: "Nessun prodotto in attesa di importazione. Avvia una scansione per trovare ordini recenti.",
      syncCountEmpty: "Nessun prodotto in attesa di importazione.",
      saveAllPreorders: "Salva Tutti nei Pre-ordini",
      testingConnection: "Verifica connessione a Gmail in corso...",
      connectionEstablished: "Connessione a Gmail stabilita con successo!",
      connectionError: "Errore di connessione a Gmail.",
      scanningUnread: "Connessione a Gmail e ricerca nuove email non lette...",
      scanError: "Errore durante la scansione.",
      scanEmptyResult: "Scansione completata: {scanned} email analizzate, nessun prodotto nuovo rilevato.",
      inboxEmptyRow: "Nessuna nuova email d'ordine rilevata nella casella INBOX.",
      nothingToImport: "Nessun prodotto da importare.",
      scanFoundResult: "Scansione completata: {found} prodotti trovati in {scanned} email.",
      readyForPreorders: "{count} prodotti pronti per l'importazione nei Pre-ordini."
    },
    excel: {
      hintTitle: "Suggerimento per l'AI (opzionale)",
      hintDesc: "Puoi fornire indicazioni contestuali per aiutare Gemini ad interpretare al meglio il foglio di calcolo.",
      hintPlaceholder: "Es: Dalla riga 15 in poi sono pre-ordini, la colonna C indica il prezzo in euro...",
      proceedWithoutHint: "Procedi senza note",
      proceedWithHint: "Procedi con nota",
      previewTitle: "Importazione Excel con AI",
      previewSubtitle: "L'AI ha analizzato il file e identificato i prodotti. Controlla e correggi se necessario.",
      colProduct: "PRODOTTO",
      colSize: "TAGLIA",
      colQty: "Q.TÀ",
      colBuyPrice: "P. ACQUISTO",
      colBuyPlace: "L. ACQUISTO",
      colSellPlace: "L. VENDITA",
      colStatus: "STATO",
      confirmAndSave: "Conferma e Salva",
      selectedFile: "File selezionato: {name}",
      readingAndAnalyzing: "Lettura del foglio di calcolo e analisi AI con Gemini in corso...",
      previewFoundSubtitle: "L'AI ha analizzato il file e trovato {count} prodotti pronti per l'importazione. Controlla l'anteprima e conferma.",
      summaryReadyCount: "{count} prodotti pronti per l'importazione."
    },
    drawer: {
      metricBuy: "Acquisto",
      metricSell: "Vendita / Stima",
      metricProfit: "Utile Netto",
      secPurchaseLogistics: "Dati Acquisto & Logistica",
      fieldSize: "Taglia / Misura:",
      fieldQty: "Quantità:",
      fieldStore: "Store / Fornitore:",
      fieldDate: "Data Inserimento:",
      secChannelSale: "Canale & Vendita",
      fieldPlatform: "Piattaforma:",
      fieldRoi: "ROI Calcolato:",
      fieldFees: "Commissioni Piattaforma:",
      secNotes: "Note e Condizioni",
      secTracking: "Spedizione & Tracking (17TRACK)",
      btnEbayLookup: "Lookup eBay",
      purchasePlacePrefix: "Luogo Acquisto",
      directPurchase: "Acquisto Diretto",
      officialStore: "Store Ufficiale",
      recent: "Recente",
      markAsSold: "Segna Venduto",
      defaultNotes: "Prodotto autentico verificato ({name}). Condizioni perfette DSWT, scatola integra e accessori originali inclusi."
    },
    contextMenu: {
      edit: "Modifica",
      duplicate: "Duplica",
      putOnSale: "Metti in vendita",
      confirmStock: "Conferma in magazzino",
      completeSale: "Completa Vendita",
      searchEbay: "Cerca su eBay",
      ebayPrices: "Stima Prezzi eBay",
      delete: "Elimina",
      selectedSingle: "{count} Prodotto Selezionato",
      selectedMultiple: "{count} Prodotti Selezionati"
    },
    bulkSale: {
      title: "Metti in Vendita",
      subtitle: "Stai per mettere in vendita i prodotti selezionati...",
      qtyLabel: "Quantità da mettere in vendita",
      totalPriceLabel: "Prezzo di Vendita TOTALE (€) *",
      totalFeesLabel: "Commissioni / Spese TOTALI (€)",
      placePlaceholder: "es. Vinted, StockX, Wallapop...",
      confirm: "Conferma Vendita",
      titleSingle: "Metti in Vendita",
      subtitleSingle: "Configura la vendita per \"{name}\".",
      defaultItem: "il prodotto selezionato",
      priceLabelSingle: "Prezzo di Vendita (€) *",
      qtyOption: "{current} di {total} pz",
      qtySplitHint: "{chosen} pz andranno in Vendita Attiva, {remaining} pz rimarranno in {place}.",
      qtyAllHint: "Tutti i {count} pz verranno messi in vendita.",
      titleMultiple: "Metti in Vendita ({count} Prodotti)",
      subtitleMultiple: "Stai per mettere in vendita i prodotti selezionati insieme come bundle. Il prezzo totale e le spese restano unici e vengono mostrati una sola volta sulla riga del bundle.",
      priceLabelMultiple: "Prezzo di Vendita TOTALE (€) *"
    },
    confirmStock: {
      title: "Conferma in Magazzino",
      subtitle: "Conferma l'arrivo dei prodotti in magazzino...",
      qtyLabel: "Quantità arrivata in Magazzino",
      singleHint: "Il prodotto selezionato passerà dallo stato di Pre-ordine a Disponibile in Magazzino.",
      confirm: "Conferma Spostamento",
      titleSingle: "Conferma in Magazzino",
      subtitleSingle: "Conferma l'arrivo dei pezzi per \"{name}\" in magazzino.",
      defaultItem: "il prodotto selezionato",
      qtySplitHint: "{chosen} pz andranno in Magazzino, {remaining} pz rimarranno in pre-ordine.",
      qtyAllHint: "Tutti i {count} pz verranno spostati in magazzino.",
      singleDesc: "Il prodotto selezionato passerà dallo stato di Pre-ordine a Disponibile in Magazzino.",
      titleMultiple: "Conferma in Magazzino ({count} Prodotti)",
      subtitleMultiple: "Stai per confermare l'arrivo in magazzino di tutti i prodotti in pre-ordine selezionati.",
      multipleDesc: "Tutti i {count} pre-ordini selezionati verranno spostati contemporaneamente in Magazzino."
    },
    managePlaces: {
      title: "Gestione Canali e Luoghi",
      subtitle: "Personalizza i marketplace e visualizza i canali di acquisto registrati.",
      addNewLabel: "AGGIUNGI NUOVO CANALE DI VENDITA",
      inputPlaceholder: "es. Vestiaire Collective, Subito...",
      salesChannelsTitle: "Canali di Vendita & Marketplace",
      purchasePlacesTitle: "Luoghi di Acquisto Registrati",
      noSuggestions: "Nessun suggerimento corrispondente",
      channelsCountSingle: "{count} canale",
      channelsCountPlural: "{count} canali",
      placesCountSingle: "{count} luogo",
      placesCountPlural: "{count} luoghi",
      noSellingChannels: "Nessun canale di vendita configurato.",
      noPurchasePlaces: "Nessun luogo di acquisto registrato.",
      deleteChannelTooltip: "Elimina canale"
    },
    packlink: {
      modalTitle: "Nuova Spedizione Packlink PRO",
      configApiKey: "Configura Chiave API Packlink PRO",
      savedLocally: "Salvata localmente nel tuo config.json personale",
      apiKeyPlaceholder: "Incolla qui la tua API Key di Packlink PRO...",
      saveKey: "Salva Chiave",
      quickPasteAi: "Incolla Rapido con AI",
      aiHint: "Incolla il testo grezzo dell'ordine e clicca il pulsante per compilare i campi del destinatario tramite intelligenza artificiale.",
      smartPastePlaceholder: "Incolla qui l'intero testo dell'ordine (email di conferma, riepilogo acquirente Vinted/eBay, ecc.)...",
      sendToGemini: "Invia a Gemini & Compila Campi",
      recipientData: "Dati Destinatario",
      senderFromAccount: "Mittente da account",
      fullName: "Nome e Cognome / Ragione Sociale *",
      address: "Indirizzo (Via/Piazza e Civico) *",
      address2: "Interno / Scala / Citofono (Opzionale)",
      zip: "CAP *",
      city: "Città *",
      province: "Provincia",
      country: "Nazione",
      phone: "Telefono *",
      email: "Email (Opzionale)",
      parcelDataPreset: "Dati Pacco & Preset",
      oneParcel: "1 collo",
      formatPresets: "Preset Rapidi Formato",
      presetShoes: "Scarpe",
      presetEnvelope: "Busta",
      presetCustom: "Custom",
      actualWeight: "Peso Effettivo (kg) *",
      dimensions: "Dimensioni Pacco (L × W × H cm) *",
      contentDesc: "Descrizione Contenuto per Corriere",
      contentPlaceholder: "Es. Abbigliamento, Sneakers...",
      draftTariffsHint: "Genera la bozza con calcolo automatico tariffe corrieri.",
      footerHint: "Genera bozza su Packlink PRO per pagamento ed etichetta",
      apiKeyBtn: "Chiave API",
      createDraft: "Crea Bozza Packlink",
      keyMissing: "Chiave Assente",
      proActive: "PRO Attivo ({key})",
      keyConfigured: "Chiave API configurata: {key}",
      sendingToGemini: "Invio a Gemini in corso...",
      analyzingAddresses: "Analisi e normalizzazione recapiti con Google Gemini in corso...",
      addressesVerified: "Dati estratti e verificati con successo. Controlla e conferma.",
      extractFailedHint: "Non è stato possibile estrarre i dati. Compila i campi manualmente.",
      connectionErrorHint: "Errore di connessione. Inserisci i campi manualmente.",
      creatingDraft: "Creazione bozza in corso...",
      defaultShoesContent: "Scarpe / Sneakers",
      defaultClothingContent: "Abbigliamento"
    },
    update: {
      modalTitle: "Nuova Versione Disponibile",
      changelogTitle: "NOVITÀ DELL'AGGIORNAMENTO:",
      dataSafetyGuarantee: "I tuoi dati locali (database SQLite e configurazioni) sono protetti e non verranno sovrascritti.",
      downloadInProgress: "Download dell'aggiornamento in corso...",
      later: "Più Tardi",
      updateNow: "Aggiorna Ora"
    },
    bridgeOffline: {
      modalTitle: "Motore Locale non Raggiungibile",
      modalSubtitle: "Il server bridge Python locale (porta 28472) non risponde o si è interrotto.",
      description: "L'applicazione non riesce a comunicare con il backend locale. I dati rimangono comunque salvi sul tuo disco in SQLite.",
      possibleCauses: "Possibili cause: permessi di esecuzione, librerie mancanti o antivirus che ha bloccato il processo bridge.exe.",
      continueAnyway: "Continua Comunque",
      retryConnection: "Riprova Connessione",
      connecting: "Connessione in corso..."
    },
    dialogs: {
      confirmDeleteProduct: "Confermi l'eliminazione di \"{name}\" dal database SQLite?",
      confirmDeleteBundle: "Sei sicuro di voler eliminare tutti i {count} prodotti di questa vendita multipla dal database?",
      confirmCompleteSales: "Contrassegnare {count} vendite come completate?",
      confirmDeleteSingle: "Eliminare definitivamente il prodotto selezionato?",
      confirmDeleteMultiple: "Eliminare definitivamente {count} prodotti selezionati dal database SQLite?",
      confirmRemoveChannel: "Vuoi rimuovere il canale \"{name}\" dai suggerimenti?"
    },
    tracking: {
      productTimeline: "Cronologia Prodotto",
      purchaseConfirmed: "Acquisto Confermato",
      received: "Ricevuto",
      store: "Store:",
      officialStore: "Ufficiale",
      arrivedStock: "Arrivato in Magazzino",
      checkCompleted: "Controllo integrità e taglia completato",
      inTransitToStock: "In Transito verso Magazzino",
      waitingDelivery: "In attesa di consegna corriere",
      addTrackingBtn: "Aggiungi Tracciamento 17TRACK",
      shippingTitle: "Spedizione & Tracking (17TRACK)",
      editTracking: "Modifica Codice di Spedizione",
      noTrackingAssociated: "Nessun tracciamento associato",
      inputHint: "Inserisci la lettera di vettura per monitorare le tappe del corriere in tempo reale con 17TRACK.",
      codeLabel: "Codice Spedizione *",
      carrierLabel: "Corriere",
      carrierAuto: "Auto (17TRACK)",
      saveAndMonitor: "Salva e Monitora",
      inProgress: "In Lavorazione",
      carrierDefault: "Corriere",
      registeredWaiting: "Spedizione registrata su 17TRACK. In attesa del primo aggiornamento dal corriere.",
      connecting: "Connessione a 17TRACK in corso...",
      eventDefault: "Evento",
      stepDefault: "Tappa",
      expandHistory: "Espandi cronologia completa (altre {count} tappe)",
      collapseHistory: "Comprimi cronologia (mostra solo ultime)",
      clickToCopy: "Clicca per copiare il codice",
      refreshTooltip: "Aggiorna tracking da 17TRACK",
      editTooltip: "Modifica codice / corriere",
      removeTooltip: "Rimuovi tracciamento",
      confirmRemove: "Sei sicuro di voler rimuovere il tracciamento da questo prodotto?"
    },
    notifications: {
      emptyState: "Nessuna notifica presente",
      deliveredDefault: "Il pacco risulta Consegnato",
      dismissTooltip: "Rimuovi notifica"
    },
    toasts: {
      bridgeConnected: "Connessione al motore locale stabilita con successo!",
      bridgeNoResponse: "Il motore locale non risponde ancora. Controlla data/bridge.log.",
      noActionToUndo: "Nessuna azione da annullare.",
      actionUndone: "Annullato: {desc}",
      undoError: "Errore durante l'annullamento: {error}",
      agingFilterRemoved: "Filtro giacenza rimosso",
      deadStockFilterActive: "Filtro Dead Stock: mostrati capi con oltre 60 giorni di giacenza",
      deadStockFilterRemoved: "Filtro Dead Stock rimosso",
      codeCopied: "Codice copiato: {code}",
      validTrackingCodeRequired: "Inserisci un codice di spedizione valido.",
      trackingSaved: "Tracciamento salvato ed aggiornato con successo!",
      trackingUpdated: "Stato spedizione aggiornato!",
      trackingUpdateFailed: "Aggiornamento non riuscito: {error}",
      trackingRemoved: "Tracciamento rimosso con successo.",
      productNameRequired: "Inserisci un nome per il prodotto!",
      productSaved: "\"{name}\" salvato nel database!",
      productUpdated: "\"{name}\" aggiornato nel database!",
      productRemoved: "\"{name}\" rimosso dal database.",
      completedSalesLocked: "Le vendite completate non possono essere modificate.",
      bundleDeleted: "Vendita multipla eliminata con successo ({count} prodotti).",
      productsDuplicated: "Duplicati {count} prodotti con successo!",
      salesCompleted: "{count} vendite contrassegnate come completate!",
      ebayTabsOpened: "Aperte {count} schede di ricerca eBay nel browser.",
      productsDeleted: "Eliminati {count} prodotti dal database.",
      noProductSelectedSale: "Nessun prodotto selezionato per la vendita.",
      validSalePriceRequired: "Inserisci un prezzo di vendita valido!",
      productPutOnSaleSingle: "Prodotto messo in vendita con successo!",
      productPutOnSaleMultiple: "{count} prodotti messi in vendita con successo!",
      noProductSelectedStock: "Nessun prodotto selezionato per lo spostamento.",
      productMovedStockSingle: "Prodotto spostato in Magazzino con successo!",
      productMovedStockMultiple: "{count} prodotti spostati in Magazzino con successo!",
      qtyMovedStock: "{count} pz spostati in Magazzino con successo!",
      channelNameRequired: "Inserisci il nome del canale da aggiungere.",
      channelAdded: "Canale \"{name}\" aggiunto con successo!",
      channelRemoved: "Canale \"{name}\" rimosso!",
      aiEnterText: "Scrivi o detta i prodotti prima di analizzare.",
      aiNoValidProducts: "Nessun prodotto valido rilevato dall'AI.",
      aiProductsSaved: "{count} prodotti salvati con successo in SQLite!",
      emailCredsSaved: "Credenziali email salvate con successo nel database!",
      gmailConnected: "Connessione a Gmail riuscita!",
      emailPreordersSaved: "{count} pre-ordini importati con successo dalle email!",
      checkingUpdates: "Verifica aggiornamenti in corso...",
      appUpToDate: "RSM è già aggiornato all'ultima versione (v{version})!",
      updateInProgress: "Aggiornamento in corso, attendere il completamento...",
      excelProductsImported: "{count} prodotti importati con successo nel database!",
      packlinkKeySaved: "Chiave API Packlink PRO salvata con successo!",
      packlinkAddressExtracted: "Recapiti estratti e compilati con successo dall'AI!",
      fillRequiredFields: "Compila tutti i campi obbligatori contrassegnati da *!",
      packlinkDraftCreated: "Bozza Packlink creata con successo! Rif: {ref}",
      selectionModeEnabled: "Modalità Selezione: Attivata",
      selectionModeDisabled: "Modalità Selezione: Disattivata",
      copiedToClipboard: "Copiati {count} prodotti negli appunti.",
      pastedFromClipboard: "Incollati {count} prodotti con successo.",
      viewSwitched: "Visualizzazione: {name}",
      tableSwitched: "Tabella: {name}",
      agingFilterActive: "Filtro giacenza attivo: mostrati prodotti {label}",
      agingLabelNormal: "regolari (<60gg)",
      agingLabelWarning: "in attenzione (60-90gg)",
      agingLabelCritical: "dead stock (>90gg)",
      networkError: "Errore di rete: {error}",
      genericError: "Errore: {error}",
      operationFailed: "Operazione non riuscita",
      emailRequiredFields: "Inserisci l'indirizzo Gmail e la Password per le App a 16 caratteri.",
      emailFillFirst: "Compila prima Email e Password per le App.",
      emailFillBeforeScan: "Inserisci Email e Password per le App prima di avviare la scansione.",
      packlinkInvalidKey: "Inserisci una chiave API valida generata su Packlink PRO.",
      packlinkPasteFirst: "Incolla prima il messaggio dell'acquirente nella casella!"
    },
    undo: {
      editProduct: "Modifica \"{name}\"",
      createProduct: "Creazione \"{name}\"",
      deleteProduct: "Eliminazione \"{name}\"",
      deleteBundle: "Eliminazione vendita multipla ({count} prodotti)",
      duplicateProducts: "Duplicazione di {count} prodotti",
      completeSales: "Completamento vendite ({count} prodotti)",
      deleteMultiple: "Eliminazione ({count} prodotti)",
      putOnSale: "Messa in vendita ({count} prodotti)",
      moveToStock: "Spostamento in Magazzino ({count} prodotti)",
      pasteProducts: "Incollati {count} prodotti"
    }
  },
  en: {
    common: {
      pcs: "pcs",
      daysShort: "d",
      cancel: "Cancel",
      close: "Close",
      edit: "Edit",
      delete: "Delete",
      show: "Show",
      unknown: "Unknown",
      closeEsc: "Close (ESC)"
    },
    titlebar: {
      deliveryNotifications: "Delivery Notifications",
      clearAll: "Clear all",
      noNotifications: "No notifications",
      minimize: "Minimize",
      maximize: "Maximize or Restore",
      close: "Close window"
    },
    sidebar: {
      openSidebar: "Open sidebar",
      addProductTooltip: "Add product to inventory",
      newProduct: "New Product",
      closeSidebar: "Hide sidebar",
      sqliteDb: "Local SQLite Database",
      syncedLatency: "Synced • Latency",
      langSelector: "Language selector"
    },
    nav: {
      overview: "OVERVIEW",
      dashboard: "Dashboard & Charts",
      stock: "Stock",
      preorders: "Pre-orders",
      activeSales: "Active Sales",
      salesHistory: "Sales History",
      integrations: "INTEGRATIONS",
      aiAssistant: "Gemini AI Assistant",
      emailSync: "Email Synchronization",
      importExcel: "Import Excel / CSV",
      channelsPlaces: "Channels & Places",
      packlinkShipments: "Packlink Shipments",
      updates: "Updates"
    },
    kpi: {
      investedCapital: "Invested Capital",
      investedSub: "{stockCount} in stock • {preorderCount} pre-orders",
      stockValue: "Stock Value",
      stockSub: "{pct}% of invested capital",
      profitRoi: "Net Profit & ROI",
      profitSub: "{completedCount} completed • {activeCount} active"
    },
    stockHealth: {
      toggleTooltip: "Click to expand/collapse macro-blocks breakdown",
      normalTooltip: "Regular (<60d)",
      warningTooltip: "Warning (60-90d)",
      criticalTooltip: "Dead Stock (>90d)",
      detailsTooltip: "Expand / Collapse details",
      details: "Details",
      filterNormalTooltip: "Click to filter regular products (<60d)",
      normalBadge: "< 60 days",
      normalLabel: "Regular",
      filterWarningTooltip: "Click to filter warning products (60-90d)",
      warningBadge: "60 - 90 days",
      warningLabel: "Warning",
      filterCriticalTooltip: "Click to filter dead stock products (>90d)",
      criticalBadge: "> 90 days",
      criticalLabel: "Dead Stock"
    },
    charts: {
      monthlyProfitTitle: "Monthly Profit Trend (€)",
      monthlyProfitSub: "Net profit month by month",
      timeframe1Year: "1 Year",
      timeframe6Months: "6 Months",
      timeframeAll: "All",
      salesChannelsTitle: "Sales Channels",
      salesChannelsSub: "Sales volume breakdown",
      months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
      noSalesData: "No sales data",
      netProfitLabel: "Net Profit (€)",
      profitTooltip: "Profit",
      noSales: "No sales",
      noSalesRecorded: "No sales recorded",
      soldItemSingle: "sold item",
      soldItemPlural: "sold items",
      pctOfTotal: "({pct}% of total)"
    },
    table: {
      tabAll: "All Products",
      tabStock: "Stock",
      tabPreorder: "Pre-orders",
      tabActive: "Active Sales",
      tabCompleted: "Completed Sales",
      searchPlaceholder: "Search product or place...",
      toggleSelectTooltip: "Toggle selection mode",
      select: "Select",
      toggleFiltersTooltip: "Show/Hide advanced filters",
      filters: "Filters",
      resetFilters: "Reset",
      sortTooltip: "Sort table",
      colProduct: "Product",
      colSize: "Size",
      colQty: "Qty",
      colBuyPrice: "Buy Price",
      colBuyPlace: "Buy Place",
      colStatus: "Status",
      colActions: "Actions",
      colSellPrice: "Sell Price",
      colChannel: "Channel",
      colFees: "Fees / Comm.",
      colProfit: "Net Profit",
      colRoi: "ROI",
      emptyState: "No products found for the selected criteria.",
      bundleTitle: "Multi Sale ({names})",
      bundleTag: "Bundle",
      included: "(included)",
      collapse: "Collapse",
      expand: "Expand",
      deleteBundle: "Delete Multi Sale",
      agingCriticalTooltip: "In storage for {days} days (> 90 d - Dead Stock)",
      agingWarningTooltip: "In storage for {days} days (60-90 d)",
      agingNormalTooltip: "In storage for {days} days",
      directChannel: "Direct Channel",
      estimateEbayPrices: "Estimate eBay Prices",
      editProduct: "Edit Product",
      delete: "Delete"
    },
    sort: {
      header: "SORTING CRITERIA",
      dateDesc: "Recently Added (Newest)",
      dateAsc: "First Added (Oldest)",
      buyPriceDesc: "Buy Price (Highest)",
      buyPriceAsc: "Buy Price (Lowest)",
      sellPriceDesc: "Sell Price (Highest)",
      profitDesc: "Net Profit (Highest)",
      roiDesc: "ROI (%) (Highest)",
      nameAsc: "Product Name (A → Z)"
    },
    filters: {
      buyPlace: "Purchase Place",
      allPlaces: "All places",
      sellPlace: "Selling Channel",
      allMarketplaces: "All marketplaces",
      minPrice: "Min Price (€)",
      maxPrice: "Max Price (€)",
      reset: "Reset",
      deadStockFilter: "Filter Stagnant (>60d)",
      showAll: "Show All"
    },
    selection: {
      capsuleRegion: "Selected products summary",
      costLabel: "Cost:",
      avgLabel: "Avg:",
      saleLabel: "Sale:",
      profitLabel: "Profit:",
      clearTooltip: "Deselect all products (Esc)",
      countOnly: "{count} sel.",
      countWithQty: "{count} sel. ({qty} pcs)",
      selectedShort: "sel."
    },
    capsule: {
      countOnly: "{count} sel.",
      countWithQty: "{count} sel. ({qty} pcs)",
      selectedShort: "sel."
    },
    modal: {
      addProductTitle: "Add Product to Inventory",
      editProductTitle: "Edit Product",
      activeSaleNotice: "Active sale: product master data locked. You can update sale price, channel, fees, and notes.",
      productName: "Product Name / Model",
      size: "Size",
      quantity: "Quantity",
      purchasePlace: "Purchase Place",
      purchasePlacePlaceholder: "e.g. Nike, SNKRS, Foot Locker...",
      sellingChannel: "Selling Channel",
      manage: "Manage",
      sellingChannelPlaceholder: "e.g. StockX, Vinted, eBay, Private...",
      economicData: "Financial Details",
      profitStockNoSale: "In Stock (No sale)",
      inStockNoSale: "In Stock (No sale)",
      netProfitPrefix: "Net Profit:",
      buyPrice: "Purchase Price (€) *",
      salePrice: "Selling Price (€)",
      fees: "Fees / Expenses (€)",
      status: "Status",
      statusStock: "Stock",
      statusPreorder: "Pre-order",
      statusActive: "Active Sale",
      statusCompleted: "Sold",
      notes: "Notes",
      saveToDb: "Save to Database",
      saveProduct: "Save to Database",
      updateProduct: "Update Product"
    },
    status: {
      stock: "In Stock",
      preorder: "Pre-order",
      activeSale: "On Sale",
      completed: "Sold"
    },
    ebay: {
      marketPrices: "eBay Market Prices",
      loading: "Loading...",
      fetching: "Fetching prices...",
      minimum: "MINIMUM",
      average: "AVERAGE",
      maximum: "MAXIMUM",
      viewOnEbay: "View on eBay",
      sizePrefix: "size",
      analyzedCount: "Analyzed {count} verified listings on eBay",
      noResults: "No results found"
    },
    ai: {
      quickEntry: "Quick Entry with AI",
      description: "Describe products by voice or text, Gemini will extract them automatically.",
      promptLabel: "WHAT DO YOU WANT TO ADD?",
      voiceDictationTooltip: "Voice dictation with microphone",
      extractedProducts: "Extracted Products:",
      colProduct: "Product",
      colSize: "Size",
      colQty: "Qty",
      colBuyPrice: "Buy Price",
      colPlace: "Place",
      analyzeAndCreate: "Analyze & Create",
      saveToInventory: "Save to Inventory",
      recordingCancelled: "Recording cancelled.",
      transcribingAudio: "Processing audio and transcribing with Gemini...",
      transcriptionCompleted: "Voice transcription completed.",
      noSpeechDetected: "No speech detected",
      transcriptionError: "Transcription error: {error}",
      micError: "Microphone error: {error}",
      listeningIn: "Listening in {seconds}s...",
      listeningPrompt: "Listening, you can speak. Click the microphone again to process.",
      toastEnterText: "Type or dictate products before analyzing.",
      analyzingText: "Analyzing text with Gemini...",
      noValidProducts: "No valid products detected by AI."
    },
    email: {
      syncOrders: "Email Order Synchronization",
      description: "Download unread order confirmations from Gmail and automatically extract product details via artificial intelligence.",
      addressLabel: "Gmail Address:",
      pwdLabel: "App Password (16 chars):",
      pwdPlaceholder: "Enter 16-character password",
      testConnection: "Test Connection",
      saveCredentials: "Save Credentials",
      helpText: "Enter a Google app password generated from your Google security account. Two-factor authentication (2FA) is required.",
      startScan: "Start Scanning Unread Emails",
      readyStatus: "Ready to scan emails.",
      colDetectedProduct: "DETECTED PRODUCT",
      colSize: "SIZE",
      colQty: "QTY",
      colPrice: "PRICE",
      colStore: "STORE",
      colOrderDate: "ORDER DATE",
      emptyList: "No products waiting to import. Start a scan to find recent orders.",
      syncCountEmpty: "No products waiting to import.",
      saveAllPreorders: "Save All to Pre-orders",
      testingConnection: "Testing Gmail connection...",
      connectionEstablished: "Gmail connection established successfully!",
      connectionError: "Gmail connection error.",
      scanningUnread: "Connecting to Gmail and searching for unread emails...",
      scanError: "Error during scan.",
      scanEmptyResult: "Scan complete: {scanned} emails analyzed, no new products detected.",
      inboxEmptyRow: "No new order emails detected in INBOX.",
      nothingToImport: "No products to import.",
      scanFoundResult: "Scan complete: {found} products found in {scanned} emails.",
      readyForPreorders: "{count} products ready for import into Pre-orders."
    },
    excel: {
      hintTitle: "AI Hint (Optional)",
      hintDesc: "You can provide contextual guidance to help Gemini best interpret the spreadsheet.",
      hintPlaceholder: "e.g. From row 15 onwards they are pre-orders, column C is price in euros...",
      proceedWithoutHint: "Proceed without notes",
      proceedWithHint: "Proceed with note",
      previewTitle: "Excel Import with AI",
      previewSubtitle: "AI analyzed the file and identified products. Check and adjust if needed.",
      colProduct: "PRODUCT",
      colSize: "SIZE",
      colQty: "QTY",
      colBuyPrice: "BUY PRICE",
      colBuyPlace: "BUY PLACE",
      colSellPlace: "SELL PLACE",
      colStatus: "STATUS",
      confirmAndSave: "Confirm and Save",
      selectedFile: "Selected file: {name}",
      readingAndAnalyzing: "Reading spreadsheet and analyzing with Gemini AI...",
      previewFoundSubtitle: "AI analyzed the file and found {count} products ready for import. Check the preview and confirm.",
      summaryReadyCount: "{count} products ready for import."
    },
    drawer: {
      metricBuy: "Purchase",
      metricSell: "Sale / Estimate",
      metricProfit: "Net Profit",
      secPurchaseLogistics: "Purchase & Logistics Data",
      fieldSize: "Size / Measurement:",
      fieldQty: "Quantity:",
      fieldStore: "Store / Supplier:",
      fieldDate: "Date Added:",
      secChannelSale: "Channel & Sale",
      fieldPlatform: "Platform:",
      fieldRoi: "Calculated ROI:",
      fieldFees: "Platform Fees:",
      secNotes: "Notes & Conditions",
      secTracking: "Shipping & Tracking (17TRACK)",
      btnEbayLookup: "Lookup eBay",
      purchasePlacePrefix: "Purchase Place",
      directPurchase: "Direct Purchase",
      officialStore: "Official Store",
      recent: "Recent",
      markAsSold: "Mark as Sold",
      defaultNotes: "Verified authentic product ({name}). Perfect DSWT condition, intact box and original accessories included."
    },
    contextMenu: {
      edit: "Edit",
      duplicate: "Duplicate",
      putOnSale: "Put on sale",
      confirmStock: "Confirm in stock",
      completeSale: "Complete Sale",
      searchEbay: "Search on eBay",
      ebayPrices: "Estimate eBay Prices",
      delete: "Delete",
      selectedSingle: "{count} Product Selected",
      selectedMultiple: "{count} Products Selected"
    },
    bulkSale: {
      title: "Put on Sale",
      subtitle: "You are about to put the selected products on sale...",
      qtyLabel: "Quantity to put on sale",
      totalPriceLabel: "TOTAL Sale Price (€) *",
      totalFeesLabel: "TOTAL Fees / Expenses (€)",
      placePlaceholder: "e.g. Vinted, StockX, Wallapop...",
      confirm: "Confirm Sale",
      titleSingle: "Put on Sale",
      subtitleSingle: "Configure sale for \"{name}\".",
      defaultItem: "the selected product",
      priceLabelSingle: "Sale Price (€) *",
      qtyOption: "{current} of {total} pcs",
      qtySplitHint: "{chosen} pcs will go to Active Sale, {remaining} pcs will remain in {place}.",
      qtyAllHint: "All {count} pcs will be put on sale.",
      titleMultiple: "Put on Sale ({count} Products)",
      subtitleMultiple: "You are about to put the selected products on sale together as a bundle. Total price and fees remain unified and are shown once on the bundle row.",
      priceLabelMultiple: "TOTAL Sale Price (€) *"
    },
    confirmStock: {
      title: "Confirm in Stock",
      subtitle: "Confirm arrival of products into stock...",
      qtyLabel: "Quantity arrived in Stock",
      singleHint: "The selected product will transition from Pre-order to Available in Stock.",
      confirm: "Confirm Move",
      titleSingle: "Confirm in Stock",
      subtitleSingle: "Confirm arrival of items for \"{name}\" into stock.",
      defaultItem: "the selected product",
      qtySplitHint: "{chosen} pcs will go to Stock, {remaining} pcs will remain in pre-order.",
      qtyAllHint: "All {count} pcs will be moved to stock.",
      singleDesc: "The selected product will transition from Pre-order to Available in Stock.",
      titleMultiple: "Confirm in Stock ({count} Products)",
      subtitleMultiple: "You are about to confirm stock arrival for all selected pre-orders.",
      multipleDesc: "All {count} selected pre-orders will be moved to Stock at the same time."
    },
    managePlaces: {
      title: "Channels & Places Management",
      subtitle: "Customize marketplaces and view registered purchase channels.",
      addNewLabel: "ADD NEW SALES CHANNEL",
      inputPlaceholder: "e.g. Vestiaire Collective, Subito...",
      salesChannelsTitle: "Sales Channels & Marketplaces",
      purchasePlacesTitle: "Registered Purchase Places",
      noSuggestions: "No matching suggestions",
      channelsCountSingle: "{count} channel",
      channelsCountPlural: "{count} channels",
      placesCountSingle: "{count} place",
      placesCountPlural: "{count} places",
      noSellingChannels: "No sales channels configured.",
      noPurchasePlaces: "No purchase places recorded.",
      deleteChannelTooltip: "Delete channel"
    },
    packlink: {
      modalTitle: "New Packlink PRO Shipment",
      configApiKey: "Configure Packlink PRO API Key",
      savedLocally: "Saved locally in your personal config.json",
      apiKeyPlaceholder: "Paste your Packlink PRO API Key here...",
      saveKey: "Save Key",
      quickPasteAi: "Quick Paste with AI",
      aiHint: "Paste raw order text and click the button to populate recipient fields via AI.",
      smartPastePlaceholder: "Paste the entire order text here (order confirmation, Vinted/eBay buyer summary, etc.)...",
      sendToGemini: "Send to Gemini & Fill Fields",
      recipientData: "Recipient Details",
      senderFromAccount: "Sender from account",
      fullName: "Full Name / Company Name *",
      address: "Address (Street & Number) *",
      address2: "Apt / Suite / Intercom (Optional)",
      zip: "ZIP / Postal Code *",
      city: "City *",
      province: "Province / State",
      country: "Country",
      phone: "Phone *",
      email: "Email (Optional)",
      parcelDataPreset: "Parcel Data & Presets",
      oneParcel: "1 parcel",
      formatPresets: "Quick Format Presets",
      presetShoes: "Shoes",
      presetEnvelope: "Envelope",
      presetCustom: "Custom",
      actualWeight: "Actual Weight (kg) *",
      dimensions: "Parcel Dimensions (L × W × H cm) *",
      contentDesc: "Content Description for Carrier",
      contentPlaceholder: "e.g. Clothing, Sneakers...",
      draftTariffsHint: "Generate draft with automatic carrier rate calculation.",
      footerHint: "Generate draft on Packlink PRO for payment and shipping label",
      apiKeyBtn: "API Key",
      createDraft: "Create Packlink Draft",
      keyMissing: "Key Missing",
      proActive: "PRO Active ({key})",
      keyConfigured: "API Key configured: {key}",
      sendingToGemini: "Sending to Gemini...",
      analyzingAddresses: "Analyzing and normalizing addresses with Google Gemini...",
      addressesVerified: "Data extracted and verified successfully. Check and confirm.",
      extractFailedHint: "Could not extract data. Please fill in the fields manually.",
      connectionErrorHint: "Connection error. Please fill in the fields manually.",
      creatingDraft: "Creating draft...",
      defaultShoesContent: "Shoes / Sneakers",
      defaultClothingContent: "Clothing"
    },
    update: {
      modalTitle: "New Version Available",
      changelogTitle: "WHAT'S NEW IN THIS UPDATE:",
      dataSafetyGuarantee: "Your local data (SQLite database and configurations) is safe and will not be overwritten.",
      downloadInProgress: "Downloading update...",
      later: "Later",
      updateNow: "Update Now"
    },
    bridgeOffline: {
      modalTitle: "Local Engine Unreachable",
      modalSubtitle: "The local Python bridge server (port 28472) is not responding or stopped.",
      description: "The application cannot communicate with the local backend. Your data remains safe on disk in SQLite.",
      possibleCauses: "Possible causes: execution permissions, missing libraries, or antivirus blocking bridge.exe.",
      continueAnyway: "Continue Anyway",
      retryConnection: "Retry Connection",
      connecting: "Connecting..."
    },
    dialogs: {
      confirmDeleteProduct: "Confirm deletion of \"{name}\" from the SQLite database?",
      confirmDeleteBundle: "Are you sure you want to delete all {count} products of this multi sale from the database?",
      confirmCompleteSales: "Mark {count} sales as completed?",
      confirmDeleteSingle: "Permanently delete the selected product?",
      confirmDeleteMultiple: "Permanently delete {count} selected products from the SQLite database?",
      confirmRemoveChannel: "Do you want to remove channel \"{name}\" from suggestions?"
    },
    tracking: {
      productTimeline: "Product Timeline",
      purchaseConfirmed: "Purchase Confirmed",
      received: "Received",
      store: "Store:",
      officialStore: "Official",
      arrivedStock: "Arrived in Stock",
      checkCompleted: "Condition and size check completed",
      inTransitToStock: "In Transit to Stock",
      waitingDelivery: "Waiting for carrier delivery",
      addTrackingBtn: "Add 17TRACK Tracking",
      shippingTitle: "Shipping & Tracking (17TRACK)",
      editTracking: "Edit Tracking Code",
      noTrackingAssociated: "No tracking associated",
      inputHint: "Enter the waybill number to monitor carrier milestones in real time with 17TRACK.",
      codeLabel: "Tracking Code *",
      carrierLabel: "Carrier",
      carrierAuto: "Auto (17TRACK)",
      saveAndMonitor: "Save & Track",
      inProgress: "In Progress",
      carrierDefault: "Carrier",
      registeredWaiting: "Shipment registered on 17TRACK. Awaiting first carrier update.",
      connecting: "Connecting to 17TRACK...",
      eventDefault: "Event",
      stepDefault: "Checkpoint",
      expandHistory: "Expand full timeline ({count} more milestones)",
      collapseHistory: "Collapse timeline (show latest only)",
      clickToCopy: "Click to copy code",
      refreshTooltip: "Refresh tracking from 17TRACK",
      editTooltip: "Edit code / carrier",
      removeTooltip: "Remove tracking",
      confirmRemove: "Are you sure you want to remove tracking from this product?"
    },
    notifications: {
      emptyState: "No notifications",
      deliveredDefault: "Package is marked as Delivered",
      dismissTooltip: "Dismiss notification"
    },
    toasts: {
      bridgeConnected: "Successfully connected to local engine!",
      bridgeNoResponse: "Local engine not responding yet. Check data/bridge.log.",
      noActionToUndo: "No action to undo.",
      actionUndone: "Undone: {desc}",
      undoError: "Error during undo: {error}",
      agingFilterRemoved: "Aging filter removed",
      deadStockFilterActive: "Dead Stock filter: showing items over 60 days of storage",
      deadStockFilterRemoved: "Dead Stock filter removed",
      codeCopied: "Code copied: {code}",
      validTrackingCodeRequired: "Please enter a valid tracking code.",
      trackingSaved: "Tracking successfully saved and updated!",
      trackingUpdated: "Shipment status updated!",
      trackingUpdateFailed: "Update failed: {error}",
      trackingRemoved: "Tracking successfully removed.",
      productNameRequired: "Please enter a product name!",
      productSaved: "\"{name}\" saved to database!",
      productUpdated: "\"{name}\" updated in database!",
      productRemoved: "\"{name}\" removed from database.",
      completedSalesLocked: "Completed sales cannot be modified.",
      bundleDeleted: "Multi sale successfully deleted ({count} products).",
      productsDuplicated: "Successfully duplicated {count} products!",
      salesCompleted: "{count} sales marked as completed!",
      ebayTabsOpened: "Opened {count} eBay search tabs in browser.",
      productsDeleted: "Deleted {count} products from database.",
      noProductSelectedSale: "No product selected for sale.",
      validSalePriceRequired: "Please enter a valid sale price!",
      productPutOnSaleSingle: "Product put on sale successfully!",
      productPutOnSaleMultiple: "{count} products put on sale successfully!",
      noProductSelectedStock: "No product selected to move.",
      productMovedStockSingle: "Product moved to Stock successfully!",
      productMovedStockMultiple: "{count} products moved to Stock successfully!",
      qtyMovedStock: "{count} pcs moved to Stock successfully!",
      channelNameRequired: "Please enter the channel name to add.",
      channelAdded: "Channel \"{name}\" added successfully!",
      channelRemoved: "Channel \"{name}\" removed!",
      aiEnterText: "Type or dictate products before analyzing.",
      aiNoValidProducts: "No valid products detected by AI.",
      aiProductsSaved: "{count} products successfully saved to SQLite!",
      emailCredsSaved: "Email credentials saved to database successfully!",
      gmailConnected: "Connected to Gmail successfully!",
      emailPreordersSaved: "{count} pre-orders imported successfully from emails!",
      checkingUpdates: "Checking for updates...",
      appUpToDate: "RSM is already up to date (v{version})!",
      updateInProgress: "Update in progress, please wait for completion...",
      excelProductsImported: "{count} products imported successfully into database!",
      packlinkKeySaved: "Packlink PRO API Key saved successfully!",
      packlinkAddressExtracted: "Addresses extracted and filled successfully by AI!",
      fillRequiredFields: "Please fill all mandatory fields marked with *!",
      packlinkDraftCreated: "Packlink draft created successfully! Ref: {ref}",
      selectionModeEnabled: "Selection Mode: Enabled",
      selectionModeDisabled: "Selection Mode: Disabled",
      copiedToClipboard: "Copied {count} products to clipboard.",
      pastedFromClipboard: "Pasted {count} products successfully.",
      viewSwitched: "View: {name}",
      tableSwitched: "Table: {name}",
      agingFilterActive: "Aging filter active: showing {label} products",
      agingLabelNormal: "regular (<60d)",
      agingLabelWarning: "warning (60-90d)",
      agingLabelCritical: "dead stock (>90d)",
      networkError: "Network error: {error}",
      genericError: "Error: {error}",
      operationFailed: "Operation failed",
      emailRequiredFields: "Please enter your Gmail address and 16-character App Password.",
      emailFillFirst: "Please fill in Email and App Password first.",
      emailFillBeforeScan: "Please enter Email and App Password before starting the scan.",
      packlinkInvalidKey: "Please enter a valid API key generated on Packlink PRO.",
      packlinkPasteFirst: "Please paste the buyer's message in the box first!"
    },
    undo: {
      editProduct: "Edit \"{name}\"",
      createProduct: "Create \"{name}\"",
      deleteProduct: "Delete \"{name}\"",
      deleteBundle: "Delete multi sale ({count} products)",
      duplicateProducts: "Duplicate {count} products",
      completeSales: "Complete sales ({count} products)",
      deleteMultiple: "Delete ({count} products)",
      putOnSale: "Put on sale ({count} products)",
      moveToStock: "Move to Stock ({count} products)",
      pasteProducts: "Paste {count} products"
    }
  }
};

/**
 * Accesso sicuro a localStorage con gestione errori (sandbox/private browsing).
 */
function getStoredLanguage() {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      const saved = window.localStorage.getItem("rsm_app_lang");
      if (saved === "it" || saved === "en") return saved;
    }
  } catch (_) {
    // Gestione silenziosa errori di accesso allo storage
  }
  return null;
}

function storeLanguage(lang) {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem("rsm_app_lang", lang);
    }
  } catch (_) {
    // Gestione silenziosa errori di scrittura nello storage
  }
}

/**
 * Rilevamento iniziale della lingua dell'applicazione.
 * Priorità: 1. Preferenza salvata in localStorage, 2. navigator.language (it* -> it, altrimenti en).
 */
function detectInitialLanguage() {
  const saved = getStoredLanguage();
  if (saved) return saved;

  if (typeof navigator !== "undefined") {
    const nav = (navigator.language || navigator.userLanguage || "").toLowerCase();
    if (nav.startsWith("it")) return "it";
  }
  return "en";
}

/**
 * Risoluzione di valori annidati tramite notazione a punti (es. "nav.stock").
 */
function getNestedValue(obj, keyPath) {
  if (!obj || !keyPath) return undefined;
  const parts = keyPath.split(".");
  let curr = obj;
  for (let i = 0; i < parts.length; i++) {
    if (curr === null || curr === undefined) return undefined;
    curr = curr[parts[i]];
  }
  return curr;
}

/**
 * Funzione di traduzione principale t(key, params).
 * - Ricerca prima nella lingua attiva (currentAppLanguage).
 * - Fallback in italiano ("it") se non trovato.
 * - Fallback al nome stesso della chiave se non trovato in alcun dizionario.
 * - Sostituzione dei token {paramName}.
 */
function t(key, params) {
  if (!key) return "";
  const lang = window.currentAppLanguage || "it";
  let val = getNestedValue(window.RSM_I18N?.[lang], key);

  if (val === undefined && lang !== "it") {
    val = getNestedValue(window.RSM_I18N?.["it"], key);
  }

  if (val === undefined) {
    return key;
  }

  // Se il valore è un array o un oggetto (es. lista mesi charts.months), restituiscilo direttamente
  if (typeof val !== "string") {
    return val;
  }

  // Interpolazione dei parametri {key}
  if (params && typeof params === "object") {
    return val.replace(/\{(\w+)\}/g, (match, paramName) => {
      return Object.prototype.hasOwnProperty.call(params, paramName) && params[paramName] !== undefined
        ? params[paramName]
        : match;
    });
  }

  return val;
}

/**
 * Applica le traduzioni a tutti gli elementi marcati con attributi data-i18n* nel sotto-albero DOM fornito.
 */
function applyTranslations(root) {
  const container = root || document;
  if (!container || !container.querySelectorAll) return;

  // 1. data-i18n -> textContent
  const textEls = container.querySelectorAll("[data-i18n]");
  for (let i = 0; i < textEls.length; i++) {
    const el = textEls[i];
    const key = el.getAttribute("data-i18n");
    if (key) {
      el.textContent = t(key);
    }
  }

  // 2. data-i18n-placeholder -> placeholder
  const phEls = container.querySelectorAll("[data-i18n-placeholder]");
  for (let i = 0; i < phEls.length; i++) {
    const el = phEls[i];
    const key = el.getAttribute("data-i18n-placeholder");
    if (key) {
      el.placeholder = t(key);
    }
  }

  // 3. data-i18n-title -> title
  const titleEls = container.querySelectorAll("[data-i18n-title]");
  for (let i = 0; i < titleEls.length; i++) {
    const el = titleEls[i];
    const key = el.getAttribute("data-i18n-title");
    if (key) {
      el.title = t(key);
    }
  }

  // 4. data-i18n-aria-label -> aria-label
  const ariaEls = container.querySelectorAll("[data-i18n-aria-label]");
  for (let i = 0; i < ariaEls.length; i++) {
    const el = ariaEls[i];
    const key = el.getAttribute("data-i18n-aria-label");
    if (key) {
      el.setAttribute("aria-label", t(key));
    }
  }
}

/**
 * Imposta e attiva la lingua dell'applicazione ("it" o "en").
 * Aggiorna lo stato globale, la classe attiva dello switcher, il DOM e notifica app.js.
 */
function setAppLanguage(lang) {
  if (lang !== "it" && lang !== "en") {
    lang = "it";
  }

  window.currentAppLanguage = lang;

  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.lang = lang;
  }

  // Aggiorna lo stato visivo dei pulsanti della capsula switcher
  const itBtn = document.getElementById("lang-btn-it");
  const enBtn = document.getElementById("lang-btn-en");
  if (itBtn) itBtn.classList.toggle("active", lang === "it");
  if (enBtn) enBtn.classList.toggle("active", lang === "en");

  // Salva preferenza in localStorage
  storeLanguage(lang);

  // Riapplica le traduzioni a tutto il documento statico
  if (typeof document !== "undefined") {
    applyTranslations(document);
  }

  // Notifica app.js tramite hook globale dedicato
  if (typeof window.onAppLanguageChanged === "function") {
    try {
      window.onAppLanguageChanged(lang);
    } catch (err) {
      console.error("[i18n] Errore durante l'esecuzione di onAppLanguageChanged:", err);
    }
  }

  // Notifica tramite CustomEvent
  if (typeof window.dispatchEvent === "function") {
    try {
      window.dispatchEvent(new CustomEvent("rsm-lang-change", { detail: { lang } }));
    } catch (_) {}
  }
}

// Inizializzazione delle variabili e funzioni globali
window.currentAppLanguage = detectInitialLanguage();
window.t = t;
window.applyTranslations = applyTranslations;
window.setAppLanguage = setAppLanguage;

// Inizializzazione automatica al caricamento del documento
if (typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      setAppLanguage(window.currentAppLanguage);
    });
  } else {
    setAppLanguage(window.currentAppLanguage);
  }
}
