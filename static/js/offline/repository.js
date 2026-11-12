/**
 * Pulse POS — Offline Data Repositories (repository.js)
 * High-level entity abstractions over PulseDB for products, categories, customers, outbox, and sales history.
 */

(function (window) {
  'use strict';

  const DB = window.PulseDB;

  // 1. Products Repository
  const ProductsRepo = {
    async getAll() {
      return DB.getAll('products');
    },

    async getById(id) {
      if (!id) return null;
      return DB.get('products', id);
    },

    async getByBarcode(barcode) {
      if (!barcode) return null;
      const normalized = String(barcode).trim().toLowerCase();
      const all = await DB.getAll('products');
      return all.find((p) => (p.barcode && String(p.barcode).trim().toLowerCase() === normalized) ||
                             (p.sku && String(p.sku).trim().toLowerCase() === normalized)) || null;
    },

    async search(query = '', categoryId = 'all') {
      const all = await DB.getAll('products');
      const q = query.trim().toLowerCase();

      return all.filter((p) => {
        if (!p.is_active) return false;
        if (categoryId && categoryId !== 'all' && p.category_id !== categoryId) return false;
        if (!q) return true;

        const nameMatch = p.name && p.name.toLowerCase().includes(q);
        const skuMatch = p.sku && p.sku.toLowerCase().includes(q);
        const barcodeMatch = p.barcode && String(p.barcode).toLowerCase().includes(q);
        return nameMatch || skuMatch || barcodeMatch;
      });
    },

    async decrementStock(productId, qty) {
      const product = await DB.get('products', productId);
      if (!product) return null;
      product.stock = (product.stock || 0) - qty;
      product.is_snapshot_stock = true; // Flag indicating locally adjusted stock snapshot
      await DB.put('products', product);
      return product;
    },

    async updateStock(productId, authoritativeStock) {
      const product = await DB.get('products', productId);
      if (!product) return null;
      product.stock = authoritativeStock;
      product.is_snapshot_stock = false;
      await DB.put('products', product);
      return product;
    },

    async bulkSave(products) {
      if (!Array.isArray(products) || products.length === 0) return 0;
      return DB.bulkPut('products', products);
    }
  };

  // 2. Categories Repository
  const CategoriesRepo = {
    async getAll() {
      const cats = await DB.getAll('categories');
      return cats.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    },

    async getById(id) {
      return DB.get('categories', id);
    },

    async bulkSave(categories) {
      if (!Array.isArray(categories) || categories.length === 0) return 0;
      return DB.bulkPut('categories', categories);
    }
  };

  // 3. Customers Repository
  const CustomersRepo = {
    async getAll() {
      const list = await DB.getAll('customers');
      return list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    },

    async getById(id) {
      return DB.get('customers', id);
    },

    async search(query = '') {
      const q = query.trim().toLowerCase();
      const all = await DB.getAll('customers');
      if (!q) return all;
      return all.filter((c) => {
        return (c.name && c.name.toLowerCase().includes(q)) ||
               (c.phone && c.phone.toLowerCase().includes(q)) ||
               (c.email && c.email.toLowerCase().includes(q));
      });
    },

    async save(customer) {
      if (!customer.id) customer.id = DB.uuidv4();
      await DB.put('customers', customer);
      return customer;
    },

    async bulkSave(customers) {
      if (!Array.isArray(customers) || customers.length === 0) return 0;
      return DB.bulkPut('customers', customers);
    }
  };

  // 4. Store Settings Repository
  const SettingsRepo = {
    async get() {
      const list = await DB.getAll('settings');
      return list[0] || null;
    },

    async save(settings) {
      if (!settings.id) settings.id = 'singleton_store_settings';
      await DB.put('settings', settings);
      return settings;
    }
  };

  // 5. Outbox Repository (Durable Transactional Queue)
  const OutboxRepo = {
    async enqueue(type, payload, idempotencyKey = null) {
      const opId = idempotencyKey || DB.uuidv4();
      const op = {
        id: opId,
        type: type, // 'create_order', 'create_customer'
        payload: payload,
        status: 'pending', // 'pending' | 'syncing' | 'failed'
        retry_count: 0,
        last_error: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      await DB.put('outbox', op);
      console.log(`[PulseOutbox] Queued operation [${type}] with ID: ${opId}`);
      return op;
    },

    async getPending() {
      const all = await DB.getAll('outbox');
      return all
        .filter((op) => op.status === 'pending' || op.status === 'failed')
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    },

    async markStatus(id, status, error = null) {
      const op = await DB.get('outbox', id);
      if (!op) return null;
      op.status = status;
      op.updated_at = new Date().toISOString();
      if (status === 'failed') {
        op.retry_count = (op.retry_count || 0) + 1;
        op.last_error = error ? String(error) : null;
      }
      await DB.put('outbox', op);
      return op;
    },

    async remove(id) {
      return DB.delete('outbox', id);
    },

    async countPending() {
      const all = await DB.getAll('outbox');
      return all.filter((op) => op.status === 'pending' || op.status === 'failed').length;
    },

    async getAll() {
      return DB.getAll('outbox');
    }
  };

  // 6. Sales History Repository (Local Receipts)
  const SalesHistoryRepo = {
    async add(order) {
      if (!order.id) order.id = DB.uuidv4();
      await DB.put('sales_history', order);
      return order;
    },

    async getAll(limit = 50) {
      const list = await DB.getAll('sales_history');
      return list
        .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
        .slice(0, limit);
    },

    async getById(id) {
      return DB.get('sales_history', id);
    },

    async getByClientId(clientId) {
      const all = await DB.getAll('sales_history');
      return all.find((o) => o.client_id === clientId || o.id === clientId) || null;
    },

    async updateServerConfirmation(clientId, serverOrder) {
      const local = await this.getByClientId(clientId);
      if (!local) return null;
      local.server_order_number = serverOrder.order_number;
      local.synced = true;
      local.synced_at = new Date().toISOString();
      await DB.put('sales_history', local);
      return local;
    }
  };

  // 7. Sync Meta Repository
  const SyncMetaRepo = {
    async get(key, defaultValue = null) {
      const record = await DB.get('sync_meta', key);
      return record ? record.value : defaultValue;
    },

    async set(key, value) {
      await DB.put('sync_meta', { key, value, updated_at: new Date().toISOString() });
      return value;
    }
  };

  // 8. Payment Accounts Repository (Banks & Wallets)
  const PaymentAccountsRepo = {
    async getAll() {
      const list = await DB.getAll('payment_accounts');
      return list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    },

    async getByCategory(category) {
      const all = await this.getAll();
      return all.filter(a => a.category === category && (a.is_active === true || a.is_active === 1));
    },

    async getById(id) {
      return DB.get('payment_accounts', id);
    },

    async save(account) {
      if (!account.id) account.id = DB.uuidv4();
      await DB.put('payment_accounts', account);
      return account;
    },

    async bulkSave(accounts) {
      if (!Array.isArray(accounts) || accounts.length === 0) return 0;
      return DB.bulkPut('payment_accounts', accounts);
    }
  };

  window.PulseRepos = {
    products: ProductsRepo,
    categories: CategoriesRepo,
    customers: CustomersRepo,
    settings: SettingsRepo,
    paymentAccounts: PaymentAccountsRepo,
    outbox: OutboxRepo,
    salesHistory: SalesHistoryRepo,
    syncMeta: SyncMetaRepo
  };
})(window);

