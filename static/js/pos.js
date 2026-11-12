// Pulse POS — Cart & checkout logic (Re-entrant, idempotent, and offline-first)
var cart = window.posCart || [];
window.posCart = cart;
var selectedCustomer = window.posSelectedCustomer || null;
var selectedPayment = window.posSelectedPayment || 'cash';
var currencySymbol = window.currencySymbol || '$';
window.posPaymentMode = window.posPaymentMode || 'full'; // 'full' | 'split'
var emptyEl = null;

function addToCart(productId, name, price, cost, stock) {
  if (!productId) return;
  cart = window.posCart || [];
  price = parseFloat(price) || 0;
  cost = parseFloat(cost) || 0;
  stock = (stock !== undefined && stock !== null && !isNaN(stock)) ? parseInt(stock) : 999;

  const existing = cart.find(i => String(i.productId) === String(productId));
  if (existing) {
    if (stock > 0 && existing.quantity >= stock) {
      if (window.showToast) window.showToast('Maximum available stock reached (' + stock + ')', 'warning');
      return;
    }
    existing.quantity += 1;
  } else {
    if (stock <= 0) {
      if (window.showToast) window.showToast('Item is out of stock', 'warning');
      return;
    }
    cart.push({ productId: String(productId), name, price, cost, stock, quantity: 1 });
  }
  window.posCart = cart;
  renderCart();

  const scrollContainer = document.getElementById('cartScrollContainer');
  if (scrollContainer) {
    scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: 'smooth' });
  }
}

function handleProductClick(btn, event) {
  if (event) {
    try {
      event.preventDefault();
      event.stopPropagation();
    } catch (e) {}
  }
  if (!btn) return;
  if (btn.disabled || btn.classList.contains('cursor-not-allowed') || btn.classList.contains('opacity-50')) {
    return;
  }
  const regView = document.getElementById('posRegisterView');
  if (regView && regView.classList.contains('hidden')) return;

  const id = btn.dataset.productId;
  const name = btn.dataset.productDisplayName || btn.dataset.productName;
  const price = parseFloat(btn.dataset.productPrice) || 0;
  const cost = parseFloat(btn.dataset.productCost) || 0;
  const rawStock = btn.dataset.productStock;
  const stock = (rawStock !== undefined && rawStock !== null && rawStock !== '') ? (parseInt(rawStock) || 0) : 999;

  addToCart(id, name, price, cost, stock);
}

function removeFromCart(productId) {
  cart = cart.filter(i => i.productId !== productId);
  window.posCart = cart;
  renderCart();
}

function updateQuantity(productId, qty) {
  const item = cart.find(i => i.productId === productId);
  if (!item) return;
  qty = Math.max(0, Math.min(parseInt(qty) || 0, item.stock));
  if (qty === 0) {
    removeFromCart(productId);
    return;
  }
  item.quantity = qty;
  window.posCart = cart;
  renderCart();
}

function clearCart() {
  cart = [];
  window.posCart = cart;
  const discIn = document.getElementById('discountInput');
  if (discIn) discIn.value = 0;
  clearCustomer();
  renderCart();
}

function selectCustomer(id, name, phone) {
  selectedCustomer = id || null;
  window.posSelectedCustomer = selectedCustomer;
  if (id) {
    window.posSelectedCustomerData = { id: id, name: name, phone: phone };
  } else {
    window.posSelectedCustomerData = null;
  }
  var tag = document.getElementById('customerTag');
  var input = document.getElementById('customerSearch');
  var badge = document.getElementById('customerStatusBadge');
  if (id) {
    if (tag) tag.classList.remove('hidden');
    if (input) {
      if (input.parentElement) input.parentElement.classList.add('hidden');
      else input.classList.add('hidden');
    }
    const nameEl = document.getElementById('customerTagName');
    if (nameEl) nameEl.textContent = name;
    const phoneEl = document.getElementById('customerTagPhone');
    if (phoneEl) phoneEl.textContent = phone ? phone + ' · ID: ' + id.substr(0, 8) : 'ID: ' + id.substr(0, 8);
    if (badge) {
      badge.textContent = 'Loyalty Member';
      badge.className = 'text-[10px] font-bold text-primary-600 dark:text-primary-400';
    }
  } else {
    if (tag) tag.classList.add('hidden');
    if (input) {
      if (input.parentElement) input.parentElement.classList.remove('hidden');
      else input.classList.remove('hidden');
      input.value = '';
      input.focus();
    }
    if (badge) {
      badge.textContent = 'Walk-in';
      badge.className = 'text-[10px] font-medium text-gray-400';
    }
  }
  closeCustomerDropdown();
  if (window.lucide) lucide.createIcons();
}

function clearCustomer() {
  selectCustomer(null);
}

function openCustomerDropdown() {
  const dd = document.getElementById('customerDropdown');
  if (dd) dd.classList.remove('hidden');
}

function closeCustomerDropdown() {
  const dd = document.getElementById('customerDropdown');
  if (dd) dd.classList.add('hidden');
  const no = document.getElementById('noCustomers');
  if (no) no.classList.add('hidden');
}

function filterCustomers() {
  const cs = document.getElementById('customerSearch');
  if (!cs) return;
  var q = cs.value.toLowerCase().trim();
  var dd = document.getElementById('customerDropdown');
  var no = document.getElementById('noCustomers');
  if (!dd) return;
  if (!q) { dd.classList.add('hidden'); if (no) no.classList.add('hidden'); return; }

  var customers = window.customers || [];

  var filtered = customers.filter(function (c) {
    return (c.name && c.name.toLowerCase().includes(q)) || (c.phone && c.phone.toLowerCase().includes(q));
  });

  if (filtered.length === 0) {
    dd.classList.add('hidden');
    if (no) no.classList.remove('hidden');
    return;
  }

  if (no) no.classList.add('hidden');
  dd.classList.remove('hidden');
  dd.innerHTML = filtered.map(function (c) {
    return '<button type="button" onclick="selectCustomer(\'' + c.id + '\',\'' + c.name.replace(/'/g, "\\'") + '\',\'' + (c.phone || '').replace(/'/g, "\\'") + '\')" class="w-full text-left px-3.5 py-2.5 hover:bg-primary-50/60 dark:hover:bg-gray-800/80 flex items-center gap-3 text-xs transition-colors cursor-pointer border-b border-gray-100 dark:border-gray-800 last:border-0">' +
      '<div class="w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 font-bold text-xs grid place-items-center shrink-0 ring-1 ring-primary-500/20">' + c.name.charAt(0).toUpperCase() + '</div>' +
      '<div class="flex-1 min-w-0"><p class="font-bold text-gray-900 dark:text-white truncate leading-tight">' + c.name + '</p><p class="text-[11px] text-gray-500 truncate mt-0.5">' + (c.phone || 'No phone') + '</p></div>' +
      '<div class="shrink-0 text-right"><span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60 font-mono">' + c.pts + ' pts</span></div>' +
      '</button>';
  }).join('');
}

function renderCart() {
  const cartEl = document.getElementById('cart');
  if (!cartEl) return;
  const countEl = document.getElementById('cartCount');
  const clearBtn = document.getElementById('clearBtn');
  const chargeBtn = document.getElementById('chargeBtn');
  const sym = window.currencySymbol || currencySymbol || '$';

  cart = window.posCart || [];

  if (cart.length === 0) {
    cartEl.innerHTML = `
      <div id="emptyCart" class="flex flex-col items-center justify-center text-center p-6 py-16 text-gray-400">
        <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-800/80 border border-gray-200/80 dark:border-gray-700/60 grid place-items-center mb-3 shadow-inner">
          <i data-lucide="shopping-bag" class="w-8 h-8 text-gray-400 dark:text-gray-500"></i>
        </div>
        <p class="text-sm font-semibold text-gray-700 dark:text-gray-200">Active Cart is Empty</p>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 max-w-[220px]">Scan a barcode or tap products from the catalog to begin</p>
      </div>
    `;
    if (countEl) countEl.classList.add('hidden');
    if (clearBtn) clearBtn.classList.add('hidden');
    if (chargeBtn) chargeBtn.disabled = true;
  } else {
    if (countEl) countEl.classList.remove('hidden');
    if (clearBtn) clearBtn.classList.remove('hidden');
    if (chargeBtn) chargeBtn.disabled = false;

    cartEl.innerHTML = cart.map(item => `
      <div class="group bg-white dark:bg-gray-800/90 border border-gray-200/90 dark:border-gray-700/80 hover:border-primary-400 dark:hover:border-primary-500/60 rounded-xl p-3 shadow-xs hover:shadow-sm transition-all">
        <div class="flex items-start justify-between gap-2">
          <div class="flex-1 min-w-0">
            <p class="text-xs font-bold text-gray-900 dark:text-gray-100 truncate leading-snug" title="${item.name}">${item.name}</p>
            <div class="flex items-center gap-2 mt-1 text-[11px] text-gray-500 dark:text-gray-400">
              <span class="font-medium text-gray-700 dark:text-gray-300 tabular-nums">${sym}${item.price.toFixed(2)}</span>
              <span class="text-gray-300 dark:text-gray-600">·</span>
              <span class="text-[10px] text-gray-400 tabular-nums">${item.stock} in stock</span>
            </div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <span class="text-sm font-black tabular-nums text-gray-900 dark:text-white tracking-tight">${sym}${(item.price * item.quantity).toFixed(2)}</span>
            <button onclick="removeFromCart('${item.productId}')" title="Remove item" class="w-6 h-6 rounded-md grid place-items-center text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors cursor-pointer">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>

        <div class="mt-2.5 pt-2 border-t border-gray-100 dark:border-gray-700/60 flex items-center justify-between">
          <span class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Quantity</span>
          <div class="inline-flex items-center rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 p-0.5 shadow-inner">
            <button onclick="updateQuantity('${item.productId}', ${item.quantity - 1})" title="Decrease"
              class="pos-stepper-btn w-6 h-6 rounded-md grid place-items-center bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 shadow-xs transition-colors cursor-pointer">
              <i data-lucide="minus" class="w-3 h-3"></i>
            </button>
            <input type="number" min="1" max="${item.stock}" value="${item.quantity}"
              onchange="updateQuantity('${item.productId}', this.value)"
              class="w-10 h-6 text-center text-xs font-bold tabular-nums bg-transparent border-0 focus:ring-0 p-0 text-gray-900 dark:text-gray-100 focus:outline-none" />
            <button onclick="updateQuantity('${item.productId}', ${item.quantity + 1})" ${item.quantity >= item.stock ? 'disabled' : ''} title="Increase"
              class="pos-stepper-btn w-6 h-6 rounded-md grid place-items-center bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30 disabled:hover:bg-white shadow-xs transition-colors cursor-pointer">
              <i data-lucide="plus" class="w-3 h-3"></i>
            </button>
          </div>
        </div>
      </div>
    `).join('');

    const totalItems = cart.reduce((s, i) => s + i.quantity, 0);
    if (countEl) countEl.textContent = `${totalItems} item${totalItems > 1 ? 's' : ''}`;
  }

  const subtotal = cart.reduce((s, i) => s + i.price * i.quantity, 0);
  const taxRate = typeof window.taxRate === 'number' ? window.taxRate : 8.25;
  const tax = Math.round(subtotal * taxRate / 100 * 100) / 100;
  const discIn = document.getElementById('discountInput');
  const discount = Math.max(0, parseFloat(discIn ? discIn.value : 0) || 0);
  const total = Math.max(0, Math.round((subtotal + tax - discount) * 100) / 100);

  const subEl = document.getElementById('subtotal');
  if (subEl) subEl.textContent = sym + subtotal.toFixed(2);
  const taxEl = document.getElementById('tax');
  if (taxEl) taxEl.textContent = sym + tax.toFixed(2);
  const totalEl = document.getElementById('total');
  if (totalEl) totalEl.textContent = sym + total.toFixed(2);
  const chargeEl = document.getElementById('chargeAmount');
  if (chargeEl) chargeEl.textContent = sym + total.toFixed(2);
  if (window.lucide) lucide.createIcons();
}

function filterProducts() {
  const ps = document.getElementById('productSearch');
  if (!ps) return;
  const q = ps.value.toLowerCase().trim();
  document.querySelectorAll('#productGrid button').forEach(btn => {
    const name = btn.dataset.productName || '';
    const sku = btn.dataset.productSku || '';
    const bc = btn.dataset.productBarcode || '';
    btn.style.display = (!q || name.includes(q) || sku.includes(q) || bc.includes(q)) ? '' : 'none';
  });
}

// ── Barcode scanning (Offline first, instant local lookup) ───────────
async function handleBarcodeScan(barcode) {
  const input = document.getElementById('barcodeInput');
  if (input) {
    input.value = '';
    input.focus();
  }

  const code = String(barcode).trim();
  if (!code) return;

  // 1. Check local DOM grid first
  const normCode = code.toLowerCase();
  const btn = Array.from(document.querySelectorAll('#productGrid button')).find((b) => {
    return (b.dataset.productBarcode && b.dataset.productBarcode.toLowerCase() === normCode) ||
           (b.dataset.productSku && b.dataset.productSku.toLowerCase() === normCode);
  });

  if (btn) {
    addToCart(
      btn.dataset.productId,
      btn.dataset.productDisplayName || btn.dataset.productName,
      parseFloat(btn.dataset.productPrice),
      parseFloat(btn.dataset.productCost),
      parseInt(btn.dataset.productStock)
    );
    return;
  }

  // 2. Check local IndexedDB repository
  if (window.PulseRepos && window.PulseRepos.products) {
    try {
      const prod = await window.PulseRepos.products.getByBarcode(code);
      if (prod) {
        addToCart(prod.id, prod.name, parseFloat(prod.price), parseFloat(prod.cost), parseInt(prod.stock));
        return;
      }
    } catch (e) {
      console.warn('[Barcode] Local lookup error:', e);
    }
  }

  // 3. Fallback to server API if online
  if (navigator.onLine) {
    fetch('/api/products/by-barcode/' + encodeURIComponent(code))
      .then(function (r) {
        if (!r.ok) throw new Error('Product not found');
        return r.json();
      })
      .then(function (p) {
        addToCart(p.id, p.name, p.price, p.cost, p.stock);
      })
      .catch(function () {
        showBarcodeNotFound(input);
      });
  } else {
    showBarcodeNotFound(input);
  }
}

function showBarcodeNotFound(input) {
  if (!input) return;
  input.placeholder = 'Barcode not found — scan again';
  input.classList.add('border-red-400', 'placeholder:text-red-300');
  setTimeout(function () {
    input.placeholder = 'Scan barcode...';
    input.classList.remove('border-red-400', 'placeholder:text-red-300');
  }, 1600);
}

function setCategory(catId) {
  document.querySelectorAll('#categoryTabs button').forEach(btn => {
    const isSelected = (btn.dataset.cat === catId);
    if (isSelected) {
      btn.classList.add('category-tab-active');
      btn.classList.remove('category-tab-inactive');
    } else {
      btn.classList.remove('category-tab-active');
      btn.classList.add('category-tab-inactive');
    }
  });

  document.querySelectorAll('#productGrid button').forEach(btn => {
    if (catId === 'all' || btn.dataset.productCat === catId) {
      btn.style.display = '';
    } else {
      btn.style.display = 'none';
    }
  });
}

// Checkout flow — dedicated checkout screen
function openCheckout() {
  if (cart.length === 0) return;
  const sym = window.currencySymbol || currencySymbol || '$';

  const regView = document.getElementById('posRegisterView');
  const coView = document.getElementById('posCheckoutView');
  if (regView) regView.classList.add('hidden');
  if (coView) {
    coView.classList.remove('hidden');
    coView.classList.add('flex');
  }

  const subtotal = cart.reduce((s, i) => s + i.price * i.quantity, 0);
  const tax = Math.round(subtotal * window.taxRate / 100 * 100) / 100;
  const discIn = document.getElementById('discountInput');
  const discount = Math.max(0, parseFloat(discIn ? discIn.value : 0) || 0);
  const total = Math.max(0, Math.round((subtotal + tax - discount) * 100) / 100);

  const coSub = document.getElementById('coSubtotal');
  if (coSub) coSub.textContent = sym + subtotal.toFixed(2);
  const coTax = document.getElementById('coTax');
  if (coTax) coTax.textContent = sym + tax.toFixed(2);
  const discRow = document.getElementById('coDiscRow');
  if (discRow) {
    if (discount > 0) {
      discRow.classList.remove('hidden');
      const coDisc = document.getElementById('coDiscount');
      if (coDisc) coDisc.textContent = '-' + sym + discount.toFixed(2);
    } else {
      discRow.classList.add('hidden');
    }
  }
  const coTotal = document.getElementById('coTotal');
  if (coTotal) coTotal.textContent = sym + total.toFixed(2);
  const coPayBtn = document.getElementById('coPayBtnAmount');
  if (coPayBtn) coPayBtn.textContent = sym + total.toFixed(2);
  const cashDueText = document.getElementById('cashDueText');
  if (cashDueText) cashDueText.textContent = sym + total.toFixed(2);

  const totalItems = cart.reduce((s, i) => s + i.quantity, 0);
  const coItemCount = document.getElementById('coItemCount');
  if (coItemCount) coItemCount.textContent = `${totalItems} item${totalItems > 1 ? 's' : ''}`;

  const itemListEl = document.getElementById('checkoutItemList');
  if (itemListEl) {
    itemListEl.innerHTML = cart.map(item => `
      <div class="flex items-center justify-between py-2.5 px-3 rounded-xl bg-gray-50/80 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-800 text-xs">
        <div class="min-w-0 flex-1 pr-3">
          <p class="font-bold text-gray-900 dark:text-white truncate leading-snug">${item.name}</p>
          <div class="flex items-center gap-1.5 mt-0.5 text-[11px] text-gray-500 dark:text-gray-400">
            <span class="font-medium tabular-nums text-gray-700 dark:text-gray-300">${sym}${item.price.toFixed(2)}</span>
            <span>×</span>
            <span class="font-bold text-primary-600 dark:text-primary-400 tabular-nums">${item.quantity}</span>
          </div>
        </div>
        <div class="text-right shrink-0">
          <span class="text-sm font-black tabular-nums text-gray-900 dark:text-white">${sym}${(item.price * item.quantity).toFixed(2)}</span>
        </div>
      </div>
    `).join('');
  }

  const customerObj = selectedCustomer ? (window.customers || []).find(c => c.id === selectedCustomer) : null;
  const coCustName = document.getElementById('coCustomerName');
  const coCustAvatar = document.getElementById('coCustomerAvatar');
  const coCustCardName = document.getElementById('coCustomerCardName');
  const coCustCardMeta = document.getElementById('coCustomerCardMeta');
  const coCashierBadge = document.getElementById('coCashierBadge');

  if (coCashierBadge) coCashierBadge.textContent = window.currentUserName || 'Cashier';

  if (customerObj) {
    if (coCustName) coCustName.textContent = customerObj.name;
    if (coCustAvatar) coCustAvatar.textContent = customerObj.name.charAt(0).toUpperCase();
    if (coCustCardName) coCustCardName.textContent = customerObj.name;
    if (coCustCardMeta) {
      coCustCardMeta.innerHTML = `<span class="text-primary-600 dark:text-primary-400 font-bold">${customerObj.pts} pts</span> · ${customerObj.phone || 'No phone'} · <span class="text-emerald-600 dark:text-emerald-400 font-semibold">+${Math.floor(total)} pts will be earned</span>`;
    }
  } else {
    if (coCustName) coCustName.textContent = 'Walk-in Customer';
    if (coCustAvatar) coCustAvatar.textContent = 'W';
    if (coCustCardName) coCustCardName.textContent = 'Walk-in Customer';
    if (coCustCardMeta) coCustCardMeta.textContent = 'No loyalty profile attached';
  }

  const quickCash = document.getElementById('quickCash');
  if (quickCash) {
    const baseOptions = [
      total,
      Math.ceil(total / 5) * 5,
      Math.ceil(total / 10) * 10,
      Math.ceil(total / 20) * 20,
      Math.ceil(total / 50) * 50
    ];
    let amounts = Array.from(new Set(baseOptions)).filter(a => a >= total).sort((a, b) => a - b);
    while (amounts.length < 4) {
      const highest = amounts[amounts.length - 1] || total;
      amounts.push(highest + 10);
    }
    amounts = amounts.slice(0, 4);

    quickCash.innerHTML = amounts.map((amt, idx) => {
      const isExact = (idx === 0 || Math.abs(amt - total) < 0.001);
      return `
        <button type="button" onclick="selectQuickCash(${amt});"
          class="text-xs font-bold tabular-nums h-9 rounded-xl border ${isExact ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-black' : 'border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/80 text-gray-700 dark:text-gray-200'} hover:border-primary-500 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-primary-50/50 dark:hover:bg-primary-950/30 active:scale-95 transition-all shadow-2xs cursor-pointer">
          ${isExact ? 'Exact ' : ''}${sym}${amt.toFixed(2)}
        </button>
      `;
    }).join('');
  }

  // Auto-populate cash tender with exact order total for zero-friction 1-click checkout
  const paidIn = document.getElementById('paidAmount');
  if (paidIn) {
    paidIn.value = total > 0 ? total.toFixed(2) : '0.00';
    paidIn.onfocus = function () { this.select(); };
  }
  if (cashDueText) cashDueText.textContent = sym + total.toFixed(2);

  const fullBankTotalDisplay = document.getElementById('fullBankTotalDisplay');
  if (fullBankTotalDisplay) fullBankTotalDisplay.textContent = sym + total.toFixed(2);

  const fullWalletTotalDisplay = document.getElementById('fullWalletTotalDisplay');
  if (fullWalletTotalDisplay) fullWalletTotalDisplay.textContent = sym + total.toFixed(2);

  const changeRow = document.getElementById('changeRow');
  if (changeRow) changeRow.classList.add('hidden');
  const bankRef = document.getElementById('bankRefInput');
  if (bankRef) bankRef.value = '';
  const walletRef = document.getElementById('walletRefInput');
  if (walletRef) walletRef.value = '';
  const orderNote = document.getElementById('orderNoteInput');
  if (orderNote) orderNote.value = '';

  // Initialize bank & wallet select displays
  onBankSelectChange();
  onWalletSelectChange();

  // Reset split tender inputs
  const splitCash = document.getElementById('splitCashAmount');
  if (splitCash) splitCash.value = '';
  const splitCashPaid = document.getElementById('splitCashTendered');
  if (splitCashPaid) splitCashPaid.value = '';
  const splitBank = document.getElementById('splitBankAmount');
  if (splitBank) splitBank.value = '';
  const splitBankRef = document.getElementById('splitBankRef');
  if (splitBankRef) splitBankRef.value = '';
  const splitWallet = document.getElementById('splitWalletAmount');
  if (splitWallet) splitWallet.value = '';
  const splitWalletRef = document.getElementById('splitWalletRef');
  if (splitWalletRef) splitWalletRef.value = '';
  const splitChangeRow = document.getElementById('splitCashChangeRow');
  if (splitChangeRow) splitChangeRow.classList.add('hidden');

  // Default to Full Payment mode
  setPaymentMode('full');
  setPayment(selectedPayment || 'cash');

  updateChange();

  if (window.lucide) lucide.createIcons();
}

function backToRegister() {
  const regView = document.getElementById('posRegisterView');
  const coView = document.getElementById('posCheckoutView');
  if (coView) {
    coView.classList.add('hidden');
    coView.classList.remove('flex');
  }
  if (regView) regView.classList.remove('hidden');

  const barcodeInput = document.getElementById('barcodeInput');
  if (barcodeInput) barcodeInput.focus();

  if (window.lucide) lucide.createIcons();
}

function setPaymentMode(mode) {
  window.posPaymentMode = mode || 'full';
  const fullContainer = document.getElementById('fullPaymentContainer');
  const splitContainer = document.getElementById('splitPaymentContainer');
  const fullBtn = document.getElementById('mode-full-btn');
  const splitBtn = document.getElementById('mode-split-btn');
  const badge = document.getElementById('paymentModeBadge');

  if (mode === 'split') {
    if (badge) {
      badge.textContent = 'Split / Multi-Tender';
      badge.className = 'text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/60';
    }
    if (fullBtn) {
      fullBtn.className = 'py-2.5 px-3 rounded-lg text-xs font-medium transition-all text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white flex items-center justify-center gap-2 cursor-pointer border border-transparent';
    }
    if (splitBtn) {
      splitBtn.className = 'py-2.5 px-3 rounded-lg text-xs font-bold transition-all shadow-xs bg-white dark:bg-gray-900 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 flex items-center justify-center gap-2 cursor-pointer';
    }
    if (fullContainer) fullContainer.classList.add('hidden');
    if (splitContainer) splitContainer.classList.remove('hidden');

    updateSplitMath();
  } else {
    // Full payment mode (Default)
    if (badge) {
      badge.textContent = 'Full Payment';
      badge.className = 'text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60';
    }
    if (fullBtn) {
      fullBtn.className = 'py-2.5 px-3 rounded-lg text-xs font-bold transition-all shadow-xs bg-white dark:bg-gray-900 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 flex items-center justify-center gap-2 cursor-pointer';
    }
    if (splitBtn) {
      splitBtn.className = 'py-2.5 px-3 rounded-lg text-xs font-medium transition-all text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white flex items-center justify-center gap-2 cursor-pointer border border-transparent';
    }
    if (fullContainer) fullContainer.classList.remove('hidden');
    if (splitContainer) splitContainer.classList.add('hidden');

    const sym = window.currencySymbol || currencySymbol || '$';
    const totalEl = document.getElementById('coTotal');
    const total = parseFloat(totalEl ? totalEl.textContent.replace(sym, '') : '0') || 0;
    const processBtn = document.getElementById('processBtn');
    if (processBtn) {
      processBtn.disabled = false;
      processBtn.classList.remove('opacity-50', 'cursor-not-allowed');
      processBtn.innerHTML = `
        <div class="flex items-center gap-2">
          <i data-lucide="check-circle-2" class="w-5 h-5 text-white"></i>
          <span class="text-xs uppercase tracking-wider font-bold">Complete Payment</span>
        </div>
        <span id="coPayBtnAmount" class="text-lg font-black tabular-nums">${sym}${total.toFixed(2)}</span>
      `;
    }
    setPayment(selectedPayment || 'cash');
  }

  if (window.lucide) lucide.createIcons();
}

function onBankSelectChange() {
  const sel = document.getElementById('fullBankAccountId');
  if (!sel) return;
  const opt = sel.options[sel.selectedIndex];
  if (!opt) return;
  const name = opt.dataset.name || opt.text;
  const title = opt.dataset.title || '—';
  const num = opt.dataset.num || '—';

  const nameEl = document.getElementById('fullBankNameDisplay');
  const titleEl = document.getElementById('fullBankTitleDisplay');
  const numEl = document.getElementById('fullBankNumDisplay');
  if (nameEl) nameEl.textContent = name;
  if (titleEl) titleEl.textContent = title;
  if (numEl) numEl.textContent = num;
}

function onWalletSelectChange() {
  const sel = document.getElementById('fullWalletAccountId');
  if (!sel) return;
  const opt = sel.options[sel.selectedIndex];
  if (!opt) return;
  const name = opt.dataset.name || opt.text;
  const title = opt.dataset.title || '—';
  const num = opt.dataset.num || '—';

  const nameEl = document.getElementById('fullWalletNameDisplay');
  const titleEl = document.getElementById('fullWalletTitleDisplay');
  const numEl = document.getElementById('fullWalletNumDisplay');
  if (nameEl) nameEl.textContent = name;
  if (titleEl) titleEl.textContent = title;
  if (numEl) numEl.textContent = num;
}

function fillSplitRemaining(method) {
  const sym = window.currencySymbol || currencySymbol || '$';
  const totalEl = document.getElementById('coTotal');
  const total = parseFloat(totalEl ? totalEl.textContent.replace(sym, '') : '0') || 0;

  let cash = parseFloat(document.getElementById('splitCashAmount')?.value || 0) || 0;
  let bank = parseFloat(document.getElementById('splitBankAmount')?.value || 0) || 0;
  let wallet = parseFloat(document.getElementById('splitWalletAmount')?.value || 0) || 0;

  if (method === 'cash') {
    const remaining = Math.max(0, Math.round((total - bank - wallet) * 100) / 100);
    const inEl = document.getElementById('splitCashAmount');
    if (inEl) inEl.value = remaining > 0 ? remaining.toFixed(2) : '0.00';
    const tenderedEl = document.getElementById('splitCashTendered');
    if (tenderedEl && (!tenderedEl.value || parseFloat(tenderedEl.value) < remaining)) {
      tenderedEl.value = remaining > 0 ? remaining.toFixed(2) : '0.00';
    }
  } else if (method === 'bank') {
    const remaining = Math.max(0, Math.round((total - cash - wallet) * 100) / 100);
    const inEl = document.getElementById('splitBankAmount');
    if (inEl) inEl.value = remaining > 0 ? remaining.toFixed(2) : '0.00';
  } else if (method === 'wallet') {
    const remaining = Math.max(0, Math.round((total - cash - bank) * 100) / 100);
    const inEl = document.getElementById('splitWalletAmount');
    if (inEl) inEl.value = remaining > 0 ? remaining.toFixed(2) : '0.00';
  }

  updateSplitMath(method);
}

function updateSplitMath(method) {
  const sym = window.currencySymbol || currencySymbol || '$';
  const totalEl = document.getElementById('coTotal');
  const total = parseFloat(totalEl ? totalEl.textContent.replace(sym, '') : '0') || 0;

  const cash = parseFloat(document.getElementById('splitCashAmount')?.value || 0) || 0;
  const bank = parseFloat(document.getElementById('splitBankAmount')?.value || 0) || 0;
  const wallet = parseFloat(document.getElementById('splitWalletAmount')?.value || 0) || 0;

  const allocated = Math.round((cash + bank + wallet) * 100) / 100;
  const remaining = Math.round((total - allocated) * 100) / 100;

  const orderTotalEl = document.getElementById('splitOrderTotalText');
  const allocatedEl = document.getElementById('splitAllocatedText');
  const remainingEl = document.getElementById('splitRemainingText');
  const remainingCard = document.getElementById('splitRemainingCard');
  const remainingLabel = document.getElementById('splitRemainingLabel');
  const badge = document.getElementById('splitStatusBadge');
  const badgeText = document.getElementById('splitStatusText');
  const processBtn = document.getElementById('processBtn');

  if (orderTotalEl) orderTotalEl.textContent = sym + total.toFixed(2);
  if (allocatedEl) allocatedEl.textContent = sym + allocated.toFixed(2);

  // Cash change handling
  const cashPaid = parseFloat(document.getElementById('splitCashTendered')?.value || 0) || 0;
  const cashChangeRow = document.getElementById('splitCashChangeRow');
  const cashChangeEl = document.getElementById('splitCashChangeAmount');
  if (cashChangeRow && cashChangeEl) {
    if (cash > 0 && cashPaid >= cash) {
      cashChangeRow.classList.remove('hidden');
      cashChangeEl.textContent = sym + (cashPaid - cash).toFixed(2);
    } else {
      cashChangeRow.classList.add('hidden');
    }
  }

  // Progress bars
  const pCash = document.getElementById('splitProgressCash');
  const pBank = document.getElementById('splitProgressBank');
  const pWallet = document.getElementById('splitProgressWallet');
  if (pCash) pCash.style.width = (total > 0 ? Math.min(100, (cash / total) * 100) : 0) + '%';
  if (pBank) pBank.style.width = (total > 0 ? Math.min(100, (bank / total) * 100) : 0) + '%';
  if (pWallet) pWallet.style.width = (total > 0 ? Math.min(100, (wallet / total) * 100) : 0) + '%';

  // Balance verification and Process Sale button state
  if (Math.abs(remaining) < 0.005 && total > 0) {
    // Perfectly allocated
    if (remainingEl) remainingEl.textContent = sym + '0.00';
    if (remainingLabel) remainingLabel.textContent = 'Remaining';
    if (remainingCard) {
      remainingCard.className = 'p-3 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/80 text-center';
    }
    if (badge && badgeText) {
      badge.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60';
      badgeText.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5 inline"></i> Balanced (100%)';
    }
    if (processBtn) {
      processBtn.disabled = false;
      processBtn.classList.remove('opacity-50', 'cursor-not-allowed');
      processBtn.innerHTML = `
        <div class="flex items-center gap-2">
          <i data-lucide="check-circle-2" class="w-5 h-5 text-white"></i>
          <span class="text-xs uppercase tracking-wider font-bold">Complete Split Payment</span>
        </div>
        <span id="coPayBtnAmount" class="text-lg font-black tabular-nums">${sym}${total.toFixed(2)}</span>
      `;
    }
  } else if (remaining > 0) {
    // Under-allocated
    if (remainingEl) remainingEl.textContent = sym + remaining.toFixed(2);
    if (remainingLabel) remainingLabel.textContent = 'Remaining Due';
    if (remainingCard) {
      remainingCard.className = 'p-3 rounded-xl bg-amber-50/50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/80 text-center';
    }
    if (badge && badgeText) {
      badge.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60';
      badgeText.innerHTML = `<i data-lucide="alert-circle" class="w-3.5 h-3.5 inline"></i> ${sym}${remaining.toFixed(2)} Remaining`;
    }
    if (processBtn) {
      processBtn.disabled = true;
      processBtn.classList.add('opacity-50', 'cursor-not-allowed');
      processBtn.innerHTML = `
        <div class="flex items-center gap-2">
          <i data-lucide="lock" class="w-5 h-5 text-white/80"></i>
          <span class="text-xs uppercase tracking-wider font-bold">Allocate ${sym}${remaining.toFixed(2)} More</span>
        </div>
        <span id="coPayBtnAmount" class="text-lg font-black tabular-nums">${sym}${total.toFixed(2)}</span>
      `;
    }
  } else {
    // Over-allocated
    const over = Math.abs(remaining);
    if (remainingEl) remainingEl.textContent = '-' + sym + over.toFixed(2);
    if (remainingLabel) remainingLabel.textContent = 'Over-Allocated';
    if (remainingCard) {
      remainingCard.className = 'p-3 rounded-xl bg-red-50/50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/80 text-center';
    }
    if (badge && badgeText) {
      badge.className = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-red-50 dark:bg-red-950/50 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800/60';
      badgeText.innerHTML = `<i data-lucide="alert-triangle" class="w-3.5 h-3.5 inline"></i> Over by ${sym}${over.toFixed(2)}`;
    }
    if (processBtn) {
      processBtn.disabled = true;
      processBtn.classList.add('opacity-50', 'cursor-not-allowed');
      processBtn.innerHTML = `
        <div class="flex items-center gap-2">
          <i data-lucide="alert-triangle" class="w-5 h-5 text-white/80"></i>
          <span class="text-xs uppercase tracking-wider font-bold">Over by ${sym}${over.toFixed(2)}</span>
        </div>
        <span id="coPayBtnAmount" class="text-lg font-black tabular-nums">${sym}${total.toFixed(2)}</span>
      `;
    }
  }

  if (window.lucide) lucide.createIcons();
}

function setPayment(method) {
  selectedPayment = method;
  window.posSelectedPayment = selectedPayment;
  const methods = ['cash', 'bank', 'wallet'];
  const label = document.getElementById('selectedMethodLabel');
  if (label) {
    label.textContent = method === 'cash' ? 'Cash Selected' : (method === 'bank' ? 'Bank / Card Selected' : 'Wallet Selected');
  }

  methods.forEach(m => {
    const btn = document.getElementById('pay-' + m);
    if (!btn) return;
    const indicator = btn.querySelector('.selected-indicator');
    if (m === method) {
      btn.classList.add('payment-method-card-active');
      btn.classList.remove('border-gray-200', 'dark:border-gray-800');
      if (indicator) indicator.classList.remove('hidden');
    } else {
      btn.classList.remove('payment-method-card-active');
      btn.classList.add('border-gray-200', 'dark:border-gray-800');
      if (indicator) indicator.classList.add('hidden');
    }
  });

  const cashSec = document.getElementById('cashSection');
  const bankSec = document.getElementById('bankSection');
  const walletSec = document.getElementById('walletSection');

  if (cashSec) cashSec.classList.toggle('hidden', method !== 'cash');
  if (bankSec) bankSec.classList.toggle('hidden', method !== 'bank');
  if (walletSec) walletSec.classList.toggle('hidden', method !== 'wallet');

  const sym = window.currencySymbol || currencySymbol || '$';
  const totalEl = document.getElementById('coTotal');
  const total = parseFloat(totalEl ? totalEl.textContent.replace(sym, '') : '0') || 0;

  if (method === 'cash') {
    const paidInput = document.getElementById('paidAmount');
    if (paidInput) {
      if (!paidInput.value || parseFloat(paidInput.value) <= 0) {
        paidInput.value = total > 0 ? total.toFixed(2) : '0.00';
      }
      updateChange();
      setTimeout(() => {
        paidInput.focus();
        paidInput.select();
      }, 80);
    }
  } else if (method === 'bank') {
    const fullBankTotalDisplay = document.getElementById('fullBankTotalDisplay');
    if (fullBankTotalDisplay) fullBankTotalDisplay.textContent = sym + total.toFixed(2);
    onBankSelectChange();
  } else if (method === 'wallet') {
    const fullWalletTotalDisplay = document.getElementById('fullWalletTotalDisplay');
    if (fullWalletTotalDisplay) fullWalletTotalDisplay.textContent = sym + total.toFixed(2);
    onWalletSelectChange();
  }

  if (window.lucide) lucide.createIcons();
}

function selectQuickCash(amount) {
  const paidIn = document.getElementById('paidAmount');
  if (paidIn) {
    paidIn.value = parseFloat(amount).toFixed(2);
    updateChange();
  }
}

function updateChange() {
  const sym = window.currencySymbol || currencySymbol || '$';
  const coTotalEl = document.getElementById('coTotal');
  const total = parseFloat(coTotalEl ? coTotalEl.textContent.replace(sym, '') : '0') || 0;
  const paidInput = document.getElementById('paidAmount');
  let paid = parseFloat(paidInput && paidInput.value !== '' ? paidInput.value : '0');

  // In full payment mode, empty field defaults to exact total
  if ((!paidInput || paidInput.value.trim() === '') && window.posPaymentMode !== 'split') {
    paid = total;
  }

  const changeRow = document.getElementById('changeRow');
  const changeEl = document.getElementById('changeAmount');
  if (changeRow && changeEl) {
    if (paid >= total && total > 0) {
      changeRow.classList.remove('hidden');
      changeEl.textContent = sym + (paid - total).toFixed(2);
    } else {
      changeRow.classList.add('hidden');
    }
  }
}

// ── Offline-First Transaction & Outbox Integration ──────────────
async function recordAndEnqueueSale(payload, subtotal, tax, discount, total, clientId) {
  const offlineRef = 'ORD-OFF-' + Date.now().toString(36).toUpperCase();
  payload.client_id = clientId;
  payload.note = `${payload.note || ''} [Offline Ref: ${offlineRef}]`.trim();

  const customerObj = selectedCustomer ? (window.customers || []).find(c => c.id === selectedCustomer) : null;
  const localOrder = {
    id: clientId,
    client_id: clientId,
    order_number: offlineRef,
    created_at: new Date().toISOString(),
    cashier_name: payload.cashier_name,
    customer_name: customerObj ? customerObj.name : 'Walk-in Customer',
    items: cart.map(i => ({
      name: i.name,
      quantity: i.quantity,
      price: i.price,
      subtotal: i.price * i.quantity,
    })),
    subtotal: subtotal,
    tax_rate: window.taxRate,
    tax: tax,
    discount: discount,
    total: total,
    payment_method: payload.payment_method || selectedPayment,
    payments: payload.payments || [],
    is_offline: !navigator.onLine,
    synced: false,
    payload: payload,
  };

  // 1. Decrement local stock in IndexedDB and update DOM grid immediately
  for (const item of cart) {
    if (window.PulseRepos && window.PulseRepos.products) {
      await window.PulseRepos.products.decrementStock(item.productId, item.quantity);
    }
    const btn = document.querySelector(`#productGrid button[data-product-id="${item.productId}"]`);
    if (btn) {
      const currentStock = parseInt(btn.dataset.productStock) || 0;
      const newStock = Math.max(0, currentStock - item.quantity);
      btn.dataset.productStock = newStock;
      const stockBadge = btn.querySelector('.text-\\[10px\\].text-gray-500');
      if (stockBadge) stockBadge.textContent = `${newStock} in stock`;
      if (newStock <= 0) {
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        btn.disabled = true;
      }
    }
  }

  // 2. Persist to local sales history & durable transactional outbox
  if (window.PulseRepos) {
    await window.PulseRepos.salesHistory.add(localOrder);
    await window.PulseRepos.outbox.enqueue('create_order', payload, clientId);
  }

  // 3. Update Sync status in header and banner
  if (window.PulseSync) {
    await window.PulseSync.refreshPendingCount();
  }

  return localOrder;
}

async function processSale() {
  const sym = window.currencySymbol || currencySymbol || '$';
  const totalEl = document.getElementById('coTotal');
  const total = parseFloat(totalEl ? totalEl.textContent.replace(sym, '') : '0') || 0;
  const isSplit = (window.posPaymentMode === 'split');

  let payments = [];
  let splitSummaryNotes = [];

  if (isSplit) {
    const cashAmount = parseFloat(document.getElementById('splitCashAmount')?.value || 0) || 0;
    const bankAmount = parseFloat(document.getElementById('splitBankAmount')?.value || 0) || 0;
    const walletAmount = parseFloat(document.getElementById('splitWalletAmount')?.value || 0) || 0;

    const allocated = Math.round((cashAmount + bankAmount + walletAmount) * 100) / 100;
    if (Math.abs(total - allocated) > 0.01) {
      alert(`Split payment total (${sym}${allocated.toFixed(2)}) must exactly equal order total (${sym}${total.toFixed(2)}).`);
      return;
    }

    if (cashAmount > 0) {
      const cashTendered = parseFloat(document.getElementById('splitCashTendered')?.value || 0) || cashAmount;
      if (cashTendered < cashAmount) {
        alert(`Insufficient cash tendered for cash split portion. Tendered ${sym}${cashTendered.toFixed(2)} vs due ${sym}${cashAmount.toFixed(2)}.`);
        const inEl = document.getElementById('splitCashTendered');
        if (inEl) inEl.focus();
        return;
      }
      const cashChange = Math.max(0, Math.round((cashTendered - cashAmount) * 100) / 100);
      payments.push({
        payment_method: 'cash',
        amount: cashAmount,
        tendered: cashTendered,
        change: cashChange,
        account_name: 'Cash',
        reference: ''
      });
      splitSummaryNotes.push(`Cash: ${sym}${cashAmount.toFixed(2)}`);
    }

    if (bankAmount > 0) {
      const bankSel = document.getElementById('splitBankAccountId');
      const opt = bankSel ? bankSel.options[bankSel.selectedIndex] : null;
      const bankId = opt ? opt.value : null;
      const bankName = opt ? (opt.dataset.name || opt.text) : 'Bank';
      const bankTitle = opt ? (opt.dataset.title || '') : '';
      const bankNum = opt ? (opt.dataset.num || '') : '';
      const bankRef = (document.getElementById('splitBankRef')?.value || '').trim();

      payments.push({
        payment_method: 'bank',
        amount: bankAmount,
        account_id: bankId,
        account_name: bankName,
        account_title: bankTitle,
        account_number: bankNum,
        reference: bankRef,
        tendered: bankAmount,
        change: 0
      });
      splitSummaryNotes.push(`Bank (${bankName}): ${sym}${bankAmount.toFixed(2)}${bankRef ? ' [' + bankRef + ']' : ''}`);
    }

    if (walletAmount > 0) {
      const walletSel = document.getElementById('splitWalletAccountId');
      const opt = walletSel ? walletSel.options[walletSel.selectedIndex] : null;
      const walletId = opt ? opt.value : null;
      const walletName = opt ? (opt.dataset.name || opt.text) : 'Wallet';
      const walletTitle = opt ? (opt.dataset.title || '') : '';
      const walletNum = opt ? (opt.dataset.num || '') : '';
      const walletRef = (document.getElementById('splitWalletRef')?.value || '').trim();

      payments.push({
        payment_method: 'wallet',
        amount: walletAmount,
        account_id: walletId,
        account_name: walletName,
        account_title: walletTitle,
        account_number: walletNum,
        reference: walletRef,
        tendered: walletAmount,
        change: 0
      });
      splitSummaryNotes.push(`Wallet (${walletName}): ${sym}${walletAmount.toFixed(2)}${walletRef ? ' [' + walletRef + ']' : ''}`);
    }
  } else {
    // Full Payment Mode (Zero amount re-entry required for cash, bank, or wallet)
    if (selectedPayment === 'cash') {
      const paidInput = document.getElementById('paidAmount');
      let paid = parseFloat(paidInput && paidInput.value !== '' ? paidInput.value : '0');
      // In Full Payment mode, if left blank or 0, accept as exact payment!
      if ((!paidInput || paidInput.value.trim() === '' || paid <= 0) && total > 0) {
        paid = total;
        if (paidInput) paidInput.value = total.toFixed(2);
      }
      if (paid < total) {
        alert('Insufficient cash tendered. Total due is ' + sym + total.toFixed(2));
        if (paidInput) paidInput.focus();
        return;
      }
      const change = Math.max(0, Math.round((paid - total) * 100) / 100);
      payments.push({
        payment_method: 'cash',
        amount: total,
        tendered: paid,
        change: change,
        account_name: 'Cash',
        reference: ''
      });
    } else if (selectedPayment === 'bank') {
      const bankSel = document.getElementById('fullBankAccountId');
      const opt = bankSel ? bankSel.options[bankSel.selectedIndex] : null;
      const bankId = opt ? opt.value : null;
      const bankName = opt ? (opt.dataset.name || opt.text) : 'Bank';
      const bankTitle = opt ? (opt.dataset.title || '') : '';
      const bankNum = opt ? (opt.dataset.num || '') : '';
      const bankRef = (document.getElementById('bankRefInput')?.value || '').trim();

      payments.push({
        payment_method: 'bank',
        amount: total,
        account_id: bankId,
        account_name: bankName,
        account_title: bankTitle,
        account_number: bankNum,
        reference: bankRef,
        tendered: total,
        change: 0
      });
    } else if (selectedPayment === 'wallet') {
      const walletSel = document.getElementById('fullWalletAccountId');
      const opt = walletSel ? walletSel.options[walletSel.selectedIndex] : null;
      const walletId = opt ? opt.value : null;
      const walletName = opt ? (opt.dataset.name || opt.text) : 'Wallet';
      const walletTitle = opt ? (opt.dataset.title || '') : '';
      const walletNum = opt ? (opt.dataset.num || '') : '';
      const walletRef = (document.getElementById('walletRefInput')?.value || '').trim();

      payments.push({
        payment_method: 'wallet',
        amount: total,
        account_id: walletId,
        account_name: walletName,
        account_title: walletTitle,
        account_number: walletNum,
        reference: walletRef,
        tendered: total,
        change: 0
      });
    }
  }

  const btn = document.getElementById('processBtn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<div class="flex items-center gap-2"><i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> <span class="text-xs uppercase tracking-wider font-bold">Processing...</span></div>';
  }

  const discIn = document.getElementById('discountInput');
  const discount = Math.max(0, parseFloat(discIn ? discIn.value : 0) || 0);
  const subtotal = cart.reduce((s, i) => s + i.price * i.quantity, 0);
  const tax = Math.round(subtotal * window.taxRate / 100 * 100) / 100;
  const cashier = window.currentUserName || 'Cashier';

  // Build notes
  let noteParts = [];
  const baseNote = (document.getElementById('orderNoteInput')?.value || '').trim();
  if (baseNote) noteParts.push(baseNote);

  if (isSplit && splitSummaryNotes.length > 0) {
    noteParts.push(`[Split: ${splitSummaryNotes.join(', ')}]`);
  } else if (!isSplit) {
    if (selectedPayment === 'bank') {
      const p = payments[0];
      if (p) noteParts.push(`[Bank: ${p.account_name || 'Bank'}${p.reference ? ' Ref: ' + p.reference : ''}]`);
    } else if (selectedPayment === 'wallet') {
      const p = payments[0];
      if (p) noteParts.push(`[Wallet: ${p.account_name || 'Wallet'}${p.reference ? ' Ref: ' + p.reference : ''}]`);
    }
  }
  const fullNote = noteParts.join(' ');

  const clientId = (window.PulseDB && window.PulseDB.uuidv4) ? window.PulseDB.uuidv4() : ('c_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9));

  const payload = {
    client_id: clientId,
    items: cart.map(i => ({ productId: i.productId, quantity: i.quantity, price: i.price, name: i.name })),
    customer_id: selectedCustomer,
    cashier_name: cashier,
    tax_rate: window.taxRate,
    discount: discount,
    payment_method: isSplit ? 'split' : selectedPayment,
    payments: payments,
    note: fullNote || null,
  };

  try {
    // 1. Commit locally first into IndexedDB (Durable Outbox pattern)
    const localOrder = await recordAndEnqueueSale(payload, subtotal, tax, discount, total, clientId);

    // 2. If online, trigger sync immediately in the background
    if (navigator.onLine && window.PulseSync) {
      window.PulseSync.syncNow().catch((err) => console.warn('[PulsePOS] Background sync delayed:', err));
    }

    // 3. Display receipt to cashier immediately
    showReceipt(localOrder);
    clearCart();

    if (!navigator.onLine && typeof showToast === 'function') {
      showToast('Sale saved locally in offline mode. Will automatically sync when online.', 'warning');
    }
  } catch (err) {
    console.error('Checkout error:', err);
    alert('Failed to process sale: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<div class="flex items-center gap-2"><i data-lucide="check-circle-2" class="w-5 h-5 text-white"></i> <span class="text-xs uppercase tracking-wider font-bold">Complete Payment</span></div><span id="coPayBtnAmount" class="text-lg font-black tabular-nums">' + sym + total.toFixed(2) + '</span>';
    }
    if (window.lucide) lucide.createIcons();
  }
}

function syncOfflineOrders() {
  if (window.PulseSync) {
    window.PulseSync.syncNow();
  }
}

function showReceipt(order) {
  const sym = window.currencySymbol || currencySymbol || '$';
  const ordNumEl = document.getElementById('receiptOrderNumber');
  if (ordNumEl) {
    ordNumEl.textContent = (order.is_offline ? 'Offline Order ' : 'Order ') + order.order_number;
  }
  const body = document.getElementById('receiptBody');
  if (!body) return;

  const paymentItems = (order.payments && order.payments.length > 0)
    ? order.payments
    : (order.payload && Array.isArray(order.payload.payments) ? order.payload.payments : []);

  let paymentsHtml = '';
  if (paymentItems.length > 0) {
    paymentsHtml = `
      <div class="py-2 border-b border-dashed border-gray-300 space-y-1">
        <p class="font-bold text-[9px] uppercase tracking-wider text-gray-500 mb-1">Payment Itemization:</p>
        ${paymentItems.map(p => `
          <div class="flex justify-between text-[10px]">
            <span class="capitalize font-medium">
              ${p.payment_method === 'cash' ? '💵 Cash Tender' : (p.payment_method === 'bank' ? '🏦 ' + (p.account_name || 'Bank') : '📱 ' + (p.account_name || 'Wallet'))}
              ${p.reference ? `<span class="text-gray-500 font-mono text-[9px]"> (#${p.reference})</span>` : ''}
            </span>
            <span class="font-bold tabular-nums">${sym}${parseFloat(p.amount || 0).toFixed(2)}</span>
          </div>
          ${p.payment_method === 'cash' && p.change > 0 ? `
            <div class="flex justify-between text-[9px] text-gray-500 pl-3">
              <span>(Tendered: ${sym}${parseFloat(p.tendered || 0).toFixed(2)} · Change: ${sym}${parseFloat(p.change || 0).toFixed(2)})</span>
            </div>
          ` : ''}
        `).join('')}
      </div>
    `;
  }

  body.innerHTML = `
    <div class="bg-white text-black rounded-lg p-4 font-mono text-xs space-y-1 border border-dashed border-gray-300">
      ${order.is_offline ? `
        <div class="mb-2 p-1.5 rounded bg-amber-50 border border-amber-200 text-amber-800 text-[10px] text-center font-bold">
          ⚡ OFFLINE SALE — STORED LOCALLY (PENDING SYNC)
        </div>
      ` : ''}
      <div class="text-center pb-2 border-b border-dashed border-gray-300">
        <p class="font-bold text-sm">${window.storeName || 'Pulse POS'}</p>
        <p class="text-[10px]">${window.storeAddress || ''}</p>
        <p class="text-[10px]">${window.storePhone || ''}</p>
      </div>
      <div class="py-2 border-b border-dashed border-gray-300 text-[10px]">
        <div class="flex justify-between"><span>Order:</span><span>${order.order_number}</span></div>
        <div class="flex justify-between"><span>Date:</span><span>${new Date(order.created_at).toLocaleString()}</span></div>
        <div class="flex justify-between"><span>Cashier:</span><span>${order.cashier_name}</span></div>
        <div class="flex justify-between"><span>Customer:</span><span>${order.customer_name}</span></div>
        ${order.note ? `<div class="flex justify-between"><span>Note / Ref:</span><span>${order.note}</span></div>` : ''}
      </div>
      <div class="py-2 border-b border-dashed border-gray-300 space-y-1">
        ${order.items.map(item => `
          <div class="flex justify-between text-[10px]"><span>${item.quantity}× ${item.name}</span><span>${sym}${item.subtotal.toFixed(2)}</span></div>
        `).join('')}
      </div>
      <div class="py-2 space-y-1 text-[10px]">
        <div class="flex justify-between"><span>Subtotal</span><span>${sym}${order.subtotal.toFixed(2)}</span></div>
        <div class="flex justify-between"><span>Tax (${order.tax_rate}%)</span><span>${sym}${order.tax.toFixed(2)}</span></div>
        ${order.discount > 0 ? `<div class="flex justify-between"><span>Discount</span><span>-${sym}${order.discount.toFixed(2)}</span></div>` : ''}
        <div class="flex justify-between font-bold text-xs pt-1 border-t border-gray-300"><span>TOTAL</span><span>${sym}${order.total.toFixed(2)}</span></div>
        <div class="flex justify-between"><span>Payment Method</span><span class="uppercase font-semibold">${order.payment_method}</span></div>
      </div>
      ${paymentsHtml}
      <div class="text-center pt-2 text-[10px]">${window.receiptFooter || 'Thank you!'}</div>
    </div>
  `;
  const modal = document.getElementById('receiptModal');
  if (modal) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }
  if (window.lucide) lucide.createIcons();
}

function closeReceipt() {
  const modal = document.getElementById('receiptModal');
  if (modal) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }
  backToRegister();
}

// ── Re-entrant POS Initializer ──────────────────────────────────────
window.initPos = function () {
  cart = window.posCart || [];
  window.posCart = cart;

  // Ensure register view is shown if checkout is not active
  const regView = document.getElementById('posRegisterView');
  const coView = document.getElementById('posCheckoutView');
  if (coView && coView.classList.contains('hidden') && regView) {
    regView.classList.remove('hidden');
  }

  // 1. Setup Barcode Scanner Input
  const barcodeInput = document.getElementById('barcodeInput');
  if (barcodeInput) {
    barcodeInput.onkeydown = function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        const val = this.value.trim();
        if (val) handleBarcodeScan(val);
      }
    };
    setTimeout(() => {
      if (document.activeElement !== barcodeInput && !document.getElementById('posCheckoutView')?.classList.contains('flex')) {
        barcodeInput.focus();
      }
    }, 120);
  }

  // 2. Setup Customer Search Input
  const cs = document.getElementById('customerSearch');
  if (cs) {
    cs.oninput = filterCustomers;
    cs.onfocus = function () { if (this.value.trim()) filterCustomers(); };
    cs.onkeydown = function (e) {
      if (e.key === 'Escape') closeCustomerDropdown();
    };
  }

  // 3. Setup Product Search Input
  const ps = document.getElementById('productSearch');
  if (ps) {
    ps.oninput = filterProducts;
  }

  // 4. Restore selected customer if stored
  if (window.posSelectedCustomerData) {
    selectCustomer(
      window.posSelectedCustomerData.id,
      window.posSelectedCustomerData.name,
      window.posSelectedCustomerData.phone
    );
  }

  // 5. Render active cart
  renderCart();

  // 6. Update sync UI status
  if (window.PulseSync && typeof window.PulseSync.updateStatusUI === 'function') {
    window.PulseSync.updateStatusUI();
  }

  if (window.lucide) lucide.createIcons();
};

// Global single-bind listeners
if (!window.posGlobalListenersAttached) {
  window.posGlobalListenersAttached = true;

  // Delegated click handler on document for product cards — permanent across SPA screen navigation
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('#productGrid .product-btn, .product-btn');
    if (!btn) return;
    if (btn.disabled || btn.classList.contains('cursor-not-allowed') || btn.classList.contains('opacity-50')) {
      e.preventDefault();
      return;
    }
    const regView = document.getElementById('posRegisterView');
    if (!regView || regView.classList.contains('hidden')) return;

    e.preventDefault();
    addToCart(
      btn.dataset.productId,
      btn.dataset.productDisplayName || btn.dataset.productName,
      parseFloat(btn.dataset.productPrice) || 0,
      parseFloat(btn.dataset.productCost) || 0,
      parseInt(btn.dataset.productStock) || 0
    );
  });

  document.addEventListener('click', function (e) {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'BUTTON') return;
    if (e.target.closest('#cart') || e.target.closest('#receiptModal') || e.target.closest('#posCheckoutView')) return;
    if (e.target.closest('#customerPicker')) return;
    closeCustomerDropdown();
    const barcodeInput = document.getElementById('barcodeInput');
    if (barcodeInput && !document.getElementById('posCheckoutView')?.classList.contains('flex')) {
      barcodeInput.focus();
    }
  });

  document.addEventListener('keydown', function (e) {
    const coView = document.getElementById('posCheckoutView');
    const isCheckoutActive = coView && !coView.classList.contains('hidden');
    const receiptModal = document.getElementById('receiptModal');
    const isReceiptActive = receiptModal && !receiptModal.classList.contains('hidden');

    if (e.key === 'Escape') {
      if (isReceiptActive) {
        closeReceipt();
        return;
      }
      if (isCheckoutActive) {
        backToRegister();
        return;
      }
    }

    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
      if (e.key === 'Enter' && e.target.id === 'paidAmount' && isCheckoutActive) {
        e.preventDefault();
        processSale();
      }
      return;
    }

    if ((e.code === 'Space' || e.key === 'F2') && !isCheckoutActive && !isReceiptActive) {
      if (cart.length > 0) {
        e.preventDefault();
        openCheckout();
      }
    } else if ((e.key === 'F4' || e.key === 'Enter') && isCheckoutActive && !isReceiptActive) {
      e.preventDefault();
      processSale();
    }
  });

  // Sync catalog update listener to refresh DOM stock counts
  window.addEventListener('pulsepos:catalog-updated', function (e) {
    const data = e.detail;
    if (!data || !Array.isArray(data.products)) return;

    data.products.forEach(p => {
      const btn = document.querySelector(`#productGrid button[data-product-id="${p.id}"]`);
      if (btn) {
        btn.dataset.productStock = p.stock;
        btn.dataset.productPrice = p.price;
        const stockSpan = btn.querySelector('.text-\\[10px\\].text-gray-500');
        if (stockSpan) stockSpan.textContent = `${p.stock} in stock`;
        if (p.stock <= 0) {
          btn.classList.add('opacity-50', 'cursor-not-allowed');
          btn.disabled = true;
        } else {
          btn.classList.remove('opacity-50', 'cursor-not-allowed');
          btn.disabled = false;
        }
      }
    });

    if (Array.isArray(data.customers)) {
      window.customers = data.customers.map(c => ({
        id: c.id,
        name: c.name,
        phone: c.phone || '',
        pts: c.loyalty_points || 0
      }));
    }
  });
}

// Global window exposure for HTML onclick attributes & external callers
window.addToCart = addToCart;
window.handleProductClick = handleProductClick;
window.removeFromCart = removeFromCart;
window.updateQuantity = updateQuantity;
window.clearCart = clearCart;
window.selectCustomer = selectCustomer;
window.clearCustomer = clearCustomer;
window.openCustomerDropdown = openCustomerDropdown;
window.closeCustomerDropdown = closeCustomerDropdown;
window.filterCustomers = filterCustomers;
window.filterProducts = filterProducts;
window.setCategory = setCategory;
window.handleBarcodeScan = handleBarcodeScan;
window.openCheckout = openCheckout;
window.backToRegister = backToRegister;
window.setPayment = setPayment;
window.setPaymentMethod = setPayment;
window.setPaymentMode = setPaymentMode;
window.onBankSelectChange = onBankSelectChange;
window.onWalletSelectChange = onWalletSelectChange;
window.fillSplitRemaining = fillSplitRemaining;
window.updateSplitMath = updateSplitMath;
window.selectQuickCash = selectQuickCash;
window.updateChange = updateChange;
window.processSale = processSale;
window.closeReceipt = closeReceipt;
window.showReceipt = showReceipt;
window.syncOfflineOrders = syncOfflineOrders;
window.renderCart = renderCart;

// Auto-run on document ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', window.initPos);
} else {
  window.initPos();
}
