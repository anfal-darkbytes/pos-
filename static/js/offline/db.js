/**
 * Pulse POS — IndexedDB Database Layer (db.js)
 * Manages client-side operational database connection, schema versioning, and transaction helpers.
 */

(function (window) {
  'use strict';

  const DB_NAME = 'pulsepos_db';
  const DB_VERSION = 2;

  let dbPromise = null;

  function openDatabase() {
    if (dbPromise) return dbPromise;

    dbPromise = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error('IndexedDB is not supported on this device/browser.'));
        return;
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        console.log(`[PulseDB] Upgrading schema to version ${DB_VERSION}...`);

        // 1. Products store
        if (!db.objectStoreNames.contains('products')) {
          const productStore = db.createObjectStore('products', { keyPath: 'id' });
          productStore.createIndex('sku', 'sku', { unique: false });
          productStore.createIndex('barcode', 'barcode', { unique: false });
          productStore.createIndex('category_id', 'category_id', { unique: false });
          productStore.createIndex('name', 'name', { unique: false });
          productStore.createIndex('is_active', 'is_active', { unique: false });
        }

        // 2. Categories store
        if (!db.objectStoreNames.contains('categories')) {
          const categoryStore = db.createObjectStore('categories', { keyPath: 'id' });
          categoryStore.createIndex('name', 'name', { unique: false });
        }

        // 3. Customers store
        if (!db.objectStoreNames.contains('customers')) {
          const customerStore = db.createObjectStore('customers', { keyPath: 'id' });
          customerStore.createIndex('name', 'name', { unique: false });
          customerStore.createIndex('phone', 'phone', { unique: false });
          customerStore.createIndex('email', 'email', { unique: false });
        }

        // 4. Settings store
        if (!db.objectStoreNames.contains('settings')) {
          db.createObjectStore('settings', { keyPath: 'id' });
        }

        // 5. Outbox store (durable queue for pending sync operations)
        if (!db.objectStoreNames.contains('outbox')) {
          const outboxStore = db.createObjectStore('outbox', { keyPath: 'id' });
          outboxStore.createIndex('status', 'status', { unique: false });
          outboxStore.createIndex('created_at', 'created_at', { unique: false });
          outboxStore.createIndex('type', 'type', { unique: false });
          outboxStore.createIndex('retry_count', 'retry_count', { unique: false });
        }

        // 6. Sales history store (local transactional receipts archive)
        if (!db.objectStoreNames.contains('sales_history')) {
          const salesStore = db.createObjectStore('sales_history', { keyPath: 'id' });
          salesStore.createIndex('order_number', 'order_number', { unique: false });
          salesStore.createIndex('created_at', 'created_at', { unique: false });
          salesStore.createIndex('client_id', 'client_id', { unique: false });
        }

        // 7. Sync metadata store (key-value checkpoints)
        if (!db.objectStoreNames.contains('sync_meta')) {
          db.createObjectStore('sync_meta', { keyPath: 'key' });
        }

        // 8. Payment Accounts store (Banks and digital wallets for offline checkout)
        if (!db.objectStoreNames.contains('payment_accounts')) {
          const accountStore = db.createObjectStore('payment_accounts', { keyPath: 'id' });
          accountStore.createIndex('category', 'category', { unique: false });
          accountStore.createIndex('name', 'name', { unique: false });
          accountStore.createIndex('is_active', 'is_active', { unique: false });
        }
      };

      request.onsuccess = (event) => {
        const db = event.target.result;
        db.onversionchange = () => {
          db.close();
          dbPromise = null;
          console.warn('[PulseDB] Database version changed elsewhere. Closed connection.');
        };
        resolve(db);
      };

      request.onerror = (event) => {
        console.error('[PulseDB] Failed to open database:', event.target.error);
        reject(event.target.error);
      };

      request.onblocked = () => {
        console.warn('[PulseDB] Database upgrade blocked by another open tab.');
      };
    });

    return dbPromise;
  }

  // Helper for generic transaction execution
  async function executeTx(storeName, mode, callback) {
    const db = await openDatabase();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(storeName, mode);
      const store = transaction.objectStore(storeName);

      let result;
      try {
        result = callback(store);
      } catch (err) {
        transaction.abort();
        reject(err);
        return;
      }

      transaction.oncomplete = () => resolve(result);
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error || new Error('Transaction aborted'));
    });
  }

  // Standard CRUD operations
  const PulseDB = {
    open: openDatabase,

    async get(storeName, key) {
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readonly');
        const store = tx.objectStore(storeName);
        const req = store.get(key);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
      });
    },

    async getAll(storeName, indexName = null, query = null) {
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readonly');
        const store = tx.objectStore(storeName);
        const source = indexName ? store.index(indexName) : store;
        const req = query ? source.getAll(query) : source.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    },

    async put(storeName, item) {
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readwrite');
        const store = tx.objectStore(storeName);
        const req = store.put(item);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    },

    async bulkPut(storeName, items) {
      if (!items || items.length === 0) return 0;
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readwrite');
        const store = tx.objectStore(storeName);
        items.forEach((item) => store.put(item));
        tx.oncomplete = () => resolve(items.length);
        tx.onerror = () => reject(tx.error);
      });
    },

    async delete(storeName, key) {
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readwrite');
        const store = tx.objectStore(storeName);
        const req = store.delete(key);
        req.onsuccess = () => resolve(true);
        req.onerror = () => reject(req.error);
      });
    },

    async count(storeName, indexName = null, query = null) {
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readonly');
        const store = tx.objectStore(storeName);
        const source = indexName ? store.index(indexName) : store;
        const req = query ? source.count(query) : source.count();
        req.onsuccess = () => resolve(req.result || 0);
        req.onerror = () => reject(req.error);
      });
    },

    async clear(storeName) {
      const db = await openDatabase();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, 'readwrite');
        const store = tx.objectStore(storeName);
        const req = store.clear();
        req.onsuccess = () => resolve(true);
        req.onerror = () => reject(req.error);
      });
    },

    uuidv4() {
      if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID();
      }
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = (Math.random() * 16) | 0;
        const v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      });
    }
  };

  window.PulseDB = PulseDB;
})(window);

