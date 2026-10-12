'use strict';

(function initProgressiveWebApp() {
  var installButton = document.getElementById('pwaInstallButton');
  var installInstructions = document.getElementById('pwaInstallInstructions');
  var deferredInstallPrompt = null;

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
        .catch(function (error) {
          console.warn('Service worker registration failed.', error.name);
        });
    });
  }

  if (!installButton || !installInstructions) return;

  function isInstalled() {
    return window.matchMedia('(display-mode: standalone)').matches ||
      navigator.standalone === true;
  }

  function showInstallInstructions() {
    var isAppleMobile = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    installInstructions.textContent = isAppleMobile
      ? 'On your iPhone or iPad, open this page in Safari, tap Share, then choose Add to Home Screen.'
      : 'Open your browser menu and choose Install app or Add to Home screen.';
    installInstructions.hidden = false;
  }

  if (isInstalled()) installButton.hidden = true;

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredInstallPrompt = event;
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    installButton.hidden = true;
    installInstructions.hidden = true;
  });

  installButton.addEventListener('click', async function () {
    if (!deferredInstallPrompt) {
      showInstallInstructions();
      return;
    }

    try {
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt = null;
    } catch (error) {
      console.warn('App installation prompt failed.', error.name);
      deferredInstallPrompt = null;
      showInstallInstructions();
    }
  });
})();
