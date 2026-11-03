(function () {
  "use strict";

  function initDonationTab() {
    var tab = document.getElementById("donate-peek");
    var sentinel = document.getElementById("donate-bottom-sentinel");
    var dialog = document.getElementById("donate-dialog");

    if (tab && sentinel) {
      var show = function (value) {
        tab.classList.toggle("is-visible", value);
      };

      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (entries) {
          show(entries.some(function (entry) { return entry.isIntersecting; }));
        }, { rootMargin: "0px 0px 8px 0px", threshold: 0 }).observe(sentinel);
      } else {
        var update = function () {
          var rect = sentinel.getBoundingClientRect();
          show(rect.top < window.innerHeight && rect.bottom >= 0);
        };
        window.addEventListener("scroll", update, { passive: true });
        window.addEventListener("resize", update);
        update();
      }
    }

    if (!dialog || typeof dialog.showModal !== "function") return;

    document.querySelectorAll('a[href="#donate"],a[href="#donate-dialog"]').forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        if (!dialog.open) dialog.showModal();
      });
    });

    var closeButton = document.getElementById("close-donate");
    if (closeButton) {
      closeButton.addEventListener("click", function () {
        if (dialog.open) dialog.close();
      });
    }

    dialog.addEventListener("click", function (event) {
      if (event.target === dialog && dialog.open) dialog.close();
    });

    var copyButton = document.getElementById("copy-donate-account");
    if (copyButton) {
      copyButton.addEventListener("click", async function () {
        var status = document.getElementById("donate-copy-status");
        var account = document.getElementById("donate-account");
        if (!status || !account) return;
        var english = document.documentElement.lang.toLowerCase().startsWith("en");
        try {
          await navigator.clipboard.writeText(account.textContent.trim());
          status.textContent = english ? "Account number copied." : "계좌번호를 복사했어요.";
        } catch (error) {
          status.textContent = english
            ? "Could not copy. Select the account number manually."
            : "복사하지 못했어요. 계좌번호를 직접 선택해 주세요.";
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDonationTab, { once: true });
  } else {
    initDonationTab();
  }
})();
