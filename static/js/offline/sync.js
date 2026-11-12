/**
 * Pulse POS — Centralized Synchronization Engine (sync.js)
 * Implements durable transactional outbox sync, exponential backoff, conflict handling,
 * master catalog pull sync, and live UI status coordination.
 */

(function (window) {
  'use strict';

  const Repos = window.PulseRepos;
  const DB = window.PulseDB;

  let isSyncing = false;
  let retryTimer = null;
  let heartbeatTimer = null;
  let retryAttempt = 0;

  const SyncService = {
    state: {
      status: navigator.onLine ? 'online' : 'offline', // 'online' | 'offline' | 'syncing' | 'failed'
      pendingCount: 0,
      lastSyncTime: null,
      lastError: null,
    },

    listeners: [],

    subscribe(callback) {
      this.listeners.push(callback);
      callback(this.state);
      return () => {
        this.listeners = this.listeners.filter((cb) => cb !== callback);
      };
    },

    notify() {
      this.listeners.forEach((cb) => {
        try { cb(this.state); } catch (e) { console.error('[PulseSync] Listener error', e); }
      });
      this.updateStatusUI();
    },

    async init() {
      console.log('[PulseSync] Initializing offline synchronization service...');

      // Load last sync time
      this.state.lastSyncTime = await Repos.syncMeta.get('last_sync_timestamp', null);
      await this.refreshPendingCount();

      // Setup connectivity listeners
      window.addEventListener('online', () => this.handleNetworkChange(true));
      window.addEventListener('offline', () => this.handleNetworkChange(false));

      // Handle visibility changes (resume sync when cashier returns to tab)
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && navigator.onLine) {
          this.syncNow();
        }
      });

      // Background heartbeat every 60s
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      heartbeatTimer = setInterval(() => {
        if (navigator.onLine && !isSyncing) {
          this.syncNow();
        }
      }, 60000);

      // Initial synchronization on load if online
      if (navigator.onLine) {
        setTimeout(() => this.syncNow(), 800);
      } else {
        this.state.status = 'offline';
        this.notify();
      }
    },

    async refreshPendingCount() {
      this.state.pendingCount = await Repos.outbox.countPending();
      this.notify();
      return this.state.pendingCount;
    },

    handleNetworkChange(online) {
      console.log(`[PulseSync] Network changed: ${online ? 'ONLINE' : 'OFFLINE'}`);
      if (online) {
        this.state.status = 'online';
        this.state.lastError = null;
        retryAttempt = 0;
        this.notify();
        // Debounce before syncing to let connection stabilize
        setTimeout(() => this.syncNow(), 1000);
      } else {
        this.state.status = 'offline';
        if (retryTimer) clearTimeout(retryTimer);
        this.notify();
      }
    },

    async syncNow() {
      if (isSyncing) {
        console.log('[PulseSync] Sync already in progress. Skipping duplicate run.');
        return;
      }
      if (!navigator.onLine) {
        this.state.status = 'offline';
        this.notify();
        return;
      }

      isSyncing = true;
      this.state.status = 'syncing';
      this.notify();

      try {
        // Step 1: Drain the transactional Outbox
        await this.drainOutbox();

        // Step 2: Refresh Master Catalog & Settings (Pull Sync)
        await this.pullMasterCatalog();

        this.state.status = 'online';
        this.state.lastSyncTime = new Date().toISOString();
        this.state.lastError = null;
        await Repos.syncMeta.set('last_sync_timestamp', this.state.lastSyncTime);
        retryAttempt = 0;
      } catch (err) {
        console.error('[PulseSync] Synchronization encountered an issue:', err);
        this.state.status = 'failed';
        this.state.lastError = err.message || 'Sync failed';
        this.scheduleRetry();
      } finally {
        isSyncing = false;
        await this.refreshPendingCount();
        this.notify();
      }
    },

    async drainOutbox() {
      const pendingOps = await Repos.outbox.getPending();
      if (pendingOps.length === 0) {
        return { synced: 0 };
      }

      console.log(`[PulseSync] Draining outbox with ${pendingOps.length} pending operation(s)...`);

      // Prepare batch payload
      const batchPayload = {
        operations: pendingOps.map((op) => ({
          id: op.id,
          type: op.type,
          payload: op.payload,
          created_at: op.created_at,
        }))
      };

      const res = await fetch('/api/sync/orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(batchPayload)
      });

      // Handle Authentication Loss
      if (res.status === 401 || res.status === 403) {
        throw new Error('Cashier session expired. Offline sales are preserved in IndexedDB. Please sign in.');
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Server returned HTTP ${res.status}`);
      }

      const result = await res.json();
      console.log('[PulseSync] Batch sync processed by server:', result);

      // Process successfully acknowledged client_ids
      const syncedIds = result.synced || [];
      for (const opId of syncedIds) {
        await Repos.outbox.remove(opId);
        // Update local receipt confirmation
        await Repos.salesHistory.updateServerConfirmation(opId, { order_number: 'Synced' });
      }

      // Handle conflict reports (e.g. inventory deficits)
      if (result.conflicts && result.conflicts.length > 0) {
        result.conflicts.forEach((c) => {
          console.warn('[PulseSync Conflict]', c.message);
          if (typeof window.showToast === 'function') {
            window.showToast(`⚠️ ${c.message}`, 'warning');
          }
        });
      }

      // Handle individual operation errors
      if (result.errors && result.errors.length > 0) {
        for (const errItem of result.errors) {
          console.error('[PulseSync Op Error]', errItem);
          await Repos.outbox.markStatus(errItem.client_id, 'failed', errItem.error);
        }
      }

      if (syncedIds.length > 0 && typeof window.showToast === 'function') {
        window.showToast(`✓ Synced ${syncedIds.length} offline sale${syncedIds.length > 1 ? 's' : ''} to server!`, 'success');
      }

      return result;
    },

    async pullMasterCatalog() {
      try {
        const res = await fetch('/api/sync/bootstrap', {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!res.ok) return;

        const data = await res.json();

        if (Array.isArray(data.products) && data.products.length > 0) {
          await Repos.products.bulkSave(data.products);
        }
        if (Array.isArray(data.categories) && data.categories.length > 0) {
          await Repos.categories.bulkSave(data.categories);
        }
        if (Array.isArray(data.customers) && data.customers.length > 0) {
          await Repos.customers.bulkSave(data.customers);
        }
        if (data.settings) {
          await Repos.settings.save(data.settings);
        }
        if (Array.isArray(data.payment_accounts) && data.payment_accounts.length > 0) {
          if (Repos.paymentAccounts) {
            await Repos.paymentAccounts.bulkSave(data.payment_accounts);
          }
        }

        console.log('[PulseSync] Master catalog & settings updated from server.');
        window.dispatchEvent(new CustomEvent('pulsepos:catalog-updated', { detail: data }));
      } catch (err) {
        console.warn('[PulseSync] Master catalog pull skipped:', err);
      }
    },

    scheduleRetry() {
      if (retryTimer) clearTimeout(retryTimer);
      retryAttempt++;
      // Exponential backoff with jitter: 2s, 4s, 8s, up to 60s max
      const delay = Math.min(60000, Math.pow(2, retryAttempt) * 1000 + Math.random() * 500);
      console.log(`[PulseSync] Scheduling sync retry in ${Math.round(delay / 1000)}s (attempt ${retryAttempt})...`);

      retryTimer = setTimeout(() => {
        if (navigator.onLine && !isSyncing) {
          this.syncNow();
        }
      }, delay);
    },

    updateStatusUI() {
      const badge = document.getElementById('networkBadge');
      const banner = document.getElementById('offlineSyncBanner');
      const bannerCount = document.getElementById('offlineCountText');
      const syncBtn = document.getElementById('syncNowBtn');

      const { status, pendingCount, lastSyncTime } = this.state;

      // 1. Header Network Badge
      if (badge) {
        if (status === 'syncing') {
          badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/60 shrink-0';
          badge.innerHTML = `<i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i><span>Syncing (${pendingCount})...</span>`;
        } else if (status === 'offline') {
          badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 border border-amber-300 dark:border-amber-700 shrink-0';
          badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-500"></span><span>Offline ${pendingCount > 0 ? `(${pendingCount})` : ''}</span>`;
        } else if (status === 'failed') {
          badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-red-50 dark:bg-red-950/50 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800 shrink-0 cursor-pointer';
          badge.innerHTML = `<i data-lucide="alert-circle" class="w-3 h-3"></i><span>Sync Error (${pendingCount})</span>`;
          badge.onclick = () => this.syncNow();
        } else {
          // Online & synced
          if (pendingCount > 0) {
            badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-teal-50 dark:bg-teal-950/50 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 cursor-pointer shrink-0';
            badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-teal-500 animate-pulse"></span><span>${pendingCount} Pending Sync</span>`;
            badge.onclick = () => this.syncNow();
          } else {
            badge.className = 'hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60 shrink-0';
            badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span><span>Online</span>`;
            badge.onclick = null;
          }
        }
      }

      // 2. POS Offline Queue Status Banner
      if (banner) {
        if (pendingCount > 0) {
          banner.classList.remove('hidden');
          if (bannerCount) {
            bannerCount.textContent = `${pendingCount} offline sale${pendingCount > 1 ? 's' : ''} stored locally (pending sync)`;
          }
          if (syncBtn) {
            syncBtn.disabled = isSyncing;
            syncBtn.innerHTML = isSyncing
              ? '<i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i> Syncing...'
              : '<i data-lucide="refresh-cw" class="w-3 h-3"></i> Sync Now';
          }
        } else {
          banner.classList.add('hidden');
        }
      }

      if (window.lucide) lucide.createIcons();
    }
  };

  window.PulseSync = SyncService;

  // Auto-boot when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => SyncService.init());
  } else {
    SyncService.init();
  }
})(window);

