/**
 * Pulse POS — Progressive Web App (PWA) Manager
 * Handles Service Worker registration, native install prompts, offline state, and device detection.
 */

(function () {
  let deferredPrompt = null;

  // 1. Service Worker Registration
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then((registration) => {
          console.log('[Pulse POS] PWA Service Worker active with scope:', registration.scope);
        })
        .catch((error) => {
          console.error('[Pulse POS] Service Worker registration failed:', error);
        });
    });
  }

  // 2. Capture native install prompt
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    console.log('[Pulse POS] beforeinstallprompt event captured.');
    updateInstallButtons(true);
  });

  // 3. Listen for successful installation
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    console.log('[Pulse POS] App successfully installed.');
    updateInstallButtons(false, true);
    if (typeof showToast === 'function') {
      showToast('Pulse POS installed! You can launch it directly from your desktop or home screen.');
    }
  });

  // Helper to update button states in the UI
  function updateInstallButtons(canInstall, isInstalled = false) {
    const headerBtn = document.getElementById('pwaInstallBtn');
    const sidebarBtn = document.getElementById('pwaSidebarBtn');

    if (isInstalled || isRunningStandalone()) {
      if (headerBtn) {
        headerBtn.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-300"></i><span class="hidden md:inline">Installed</span>';
        headerBtn.classList.remove('bg-primary-500', 'hover:bg-primary-600');
        headerBtn.classList.add('bg-emerald-700/80', 'cursor-default');
        headerBtn.onclick = () => openPwaModal(true);
      }
      if (sidebarBtn) {
        sidebarBtn.innerHTML = '<i data-lucide="check-circle" class="w-4 h-4 shrink-0 text-emerald-400"></i><span class="flex-1 text-left text-gray-300">App Installed</span>';
        sidebarBtn.onclick = () => openPwaModal(true);
      }
    } else {
      if (headerBtn) {
        headerBtn.classList.remove('hidden');
      }
      if (sidebarBtn) {
        sidebarBtn.classList.remove('hidden');
      }
    }

    if (window.lucide) {
      lucide.createIcons();
    }
  }

  // Detect if running as standalone installed PWA
  function isRunningStandalone() {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true ||
      document.referrer.includes('android-app://')
    );
  }

  // 4. Trigger Install flow
  window.triggerPwaInstall = async function () {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const choiceResult = await deferredPrompt.userChoice;
      console.log('[Pulse POS] User install response:', choiceResult.outcome);
      deferredPrompt = null;
      if (choiceResult.outcome === 'accepted') {
        closePwaModal();
      }
    } else {
      // Fallback: Open install guide modal for browser/platform
      openPwaModal(isRunningStandalone());
    }
  };

  // Open Install Modal
  window.openPwaModal = function (alreadyInstalled = false) {
    const modal = document.getElementById('pwaInstallModal');
    if (!modal) return;

    const modalTitle = document.getElementById('pwaModalTitle');
    const modalDesc = document.getElementById('pwaModalDesc');
    const installActionBtn = document.getElementById('pwaModalActionBtn');
    const instructionsEl = document.getElementById('pwaPlatformInstructions');

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    const isWindows = navigator.platform.toUpperCase().indexOf('WIN') >= 0;

    if (alreadyInstalled || isRunningStandalone()) {
      if (modalTitle) modalTitle.textContent = 'Pulse POS is Installed';
      if (modalDesc) modalDesc.textContent = 'You are running the official standalone Pulse POS application.';
      if (installActionBtn) installActionBtn.classList.add('hidden');
      if (instructionsEl) {
        instructionsEl.innerHTML = `
          <div class="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-lg text-xs text-emerald-800 dark:text-emerald-300">
            ✓ Application is active in standalone mode with offline caching enabled.
          </div>
        `;
      }
    } else {
      if (modalTitle) modalTitle.textContent = 'Download Pulse POS';
      if (modalDesc) modalDesc.textContent = 'Install Pulse POS as a native desktop or mobile application for instant access, offline mode, and fullscreen checkout.';

      if (deferredPrompt) {
        if (installActionBtn) {
          installActionBtn.classList.remove('hidden');
          installActionBtn.onclick = () => window.triggerPwaInstall();
        }
      } else {
        if (installActionBtn) installActionBtn.classList.add('hidden');
      }

      // Contextual platform instructions
      let guideHtml = '';
      if (isIOS) {
        guideHtml = `
          <div class="space-y-2 text-xs text-gray-600 dark:text-gray-300">
            <p class="font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-1.5"><i data-lucide="apple" class="w-4 h-4"></i> iOS / iPadOS Instructions:</p>
            <ol class="list-decimal list-inside space-y-1 pl-1">
              <li>Tap the <span class="font-semibold text-primary-600">Share button</span> (square with arrow up) at the bottom of Safari.</li>
              <li>Scroll down and tap <span class="font-semibold text-primary-600">"Add to Home Screen"</span>.</li>
              <li>Tap <span class="font-semibold text-primary-600">"Add"</span> in the top-right corner.</li>
            </ol>
          </div>
        `;
      } else if (isWindows || isMac) {
        guideHtml = `
          <div class="space-y-2 text-xs text-gray-600 dark:text-gray-300">
            <p class="font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-1.5"><i data-lucide="monitor" class="w-4 h-4"></i> Desktop (Chrome / Edge / Brave):</p>
            <ol class="list-decimal list-inside space-y-1 pl-1">
              <li>Look for the <span class="font-semibold text-primary-600">Install icon (⊕ or computer with arrow)</span> on the right side of the address bar.</li>
              <li>Or click the browser menu <span class="font-semibold text-primary-600">(⋮)</span> &rarr; <span class="font-semibold text-primary-600">"Install Pulse POS"</span>.</li>
              <li>Enjoy standalone window, dock/taskbar shortcuts, and high performance.</li>
            </ol>
          </div>
        `;
      } else {
        guideHtml = `
          <div class="space-y-2 text-xs text-gray-600 dark:text-gray-300">
            <p class="font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-1.5"><i data-lucide="smartphone" class="w-4 h-4"></i> Mobile Browser Instructions:</p>
            <p>Tap your browser menu <span class="font-semibold">(⋮)</span> and select <span class="font-semibold text-primary-600">"Install app"</span> or <span class="font-semibold text-primary-600">"Add to Home screen"</span>.</p>
          </div>
        `;
      }

      if (instructionsEl) instructionsEl.innerHTML = guideHtml;
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    if (window.lucide) lucide.createIcons();
  };

  // Close Install Modal
  window.closePwaModal = function () {
    const modal = document.getElementById('pwaInstallModal');
    if (modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }
  };

  // 5. Network connectivity monitor (coordinated with PulseSync)
  function updateNetworkStatus() {
    if (window.PulseSync && typeof window.PulseSync.updateStatusUI === 'function') {
      window.PulseSync.updateStatusUI();
      return;
    }
    const badge = document.getElementById('networkBadge');
    if (!badge) return;

    if (navigator.onLine) {
      badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span><span>Online</span>';
      badge.className = 'hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60';
    } else {
      badge.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-500"></span><span>Offline Mode</span>';
      badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 border border-amber-300 dark:border-amber-700 animate-bounce';
    }
  }

  window.addEventListener('online', () => {
    updateNetworkStatus();
    console.log('[Pulse POS] Network back online.');
  });

  window.addEventListener('offline', () => {
    updateNetworkStatus();
    console.warn('[Pulse POS] Network offline.');
  });

  // Initial check on document ready
  document.addEventListener('DOMContentLoaded', () => {
    updateNetworkStatus();
    if (isRunningStandalone()) {
      updateInstallButtons(false, true);
    }
  });

  // Guard logout action if unsynced offline transactions exist
  window.handleLogoutClick = function (e) {
    if (window.PulseSync && window.PulseSync.state && window.PulseSync.state.pendingCount > 0) {
      const count = window.PulseSync.state.pendingCount;
      const confirmed = window.confirm(
        `⚠️ WARNING: You have ${count} offline sale(s) stored locally that have not synced yet.\n\n` +
        `If you log out now, they will remain safely stored on this device until someone signs back in.\n\n` +
        `Are you sure you want to sign out?`
      );
      if (!confirmed) {
        if (e) e.preventDefault();
        return false;
      }
    }
    return true;
  };
})();

