(async function unsubscribeAll() {
  const delay = ms => new Promise(r => setTimeout(r, ms));

  // Find all subscribed buttons currently rendered on screen
  const buttons = Array.from(document.querySelectorAll('ytd-subscribe-button-renderer button, yt-button-shape button'))
    .filter(btn => btn.innerText.trim().toLowerCase().includes('subscribed'));

  console.log(`Found ${buttons.length} subscribed channels on page.`);

  for (let btn of buttons) {
    try {
      // 1. Click the 'Subscribed' button to open the popup menu
      btn.click();
      await delay(500);

      // 2. Click 'Unsubscribe' in the dropdown menu
      const menuItems = Array.from(document.querySelectorAll('yt-sheet-view-model button, tp-yt-paper-listbox ytd-menu-service-item-renderer, ytd-menu-popup-renderer tp-yt-paper-item'));
      const unsubOption = menuItems.find(item => item.innerText.toLowerCase().includes('unsubscribe'));

      if (unsubOption) {
        unsubOption.click();
        await delay(500);

        // 3. Click 'Unsubscribe' in the final confirmation modal
        const confirmBtn = document.querySelector('yt-confirm-dialog-renderer #confirm-button button, tp-yt-paper-dialog #confirm-button button');
        if (confirmBtn) {
          confirmBtn.click();
          await delay(500);
        }
      }
    } catch (e) {
      console.log('Skipped one due to UI delay:', e);
    }
  }
  console.log('Batch complete! Scroll down to load more and run again if needed.');
})();
