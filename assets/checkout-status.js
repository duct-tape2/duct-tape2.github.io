(() => {
  const inquiryUrl =
    "https://github.com/duct-tape2/duct-tape2/issues/new?template=paid-inquiry.yml";
  const pausedMessage =
    "Payment acceptance is temporarily paused while payout settings are restored. Confirm a working checkout before paying.";

  function requestLabel(text) {
    const amount = text.match(/\$\d+/)?.[0];
    return amount
      ? `Request confirmed checkout - ${amount}`
      : "Request confirmed checkout";
  }

  function updateLink(link) {
    const current = link.textContent.trim();
    if (!current.startsWith("Request confirmed checkout")) {
      link.dataset.checkoutOriginalText = current;
    }

    const source = link.dataset.checkoutOriginalText || current;
    const label = requestLabel(source);
    if (current !== label) link.textContent = label;
    if (link.title !== pausedMessage) link.title = pausedMessage;
    link.dataset.checkoutStatus = "confirmation-required";
  }

  function refreshCheckoutState() {
    const links = document.querySelectorAll(`a[href="${inquiryUrl}"]`);
    if (!links.length) return;

    links.forEach(updateLink);
    document.body.dataset.checkoutStatus = "paused";

    if (!document.querySelector("[data-checkout-status-banner]")) {
      const banner = document.createElement("aside");
      banner.dataset.checkoutStatusBanner = "";
      banner.setAttribute("role", "status");
      banner.textContent = pausedMessage;
      Object.assign(banner.style, {
        background: "#fff4d6",
        borderBottom: "1px solid #d8a928",
        color: "#3b2b00",
        font: "600 14px/1.45 system-ui, sans-serif",
        padding: "12px 20px",
        textAlign: "center",
      });
      document.body.prepend(banner);
    }
  }

  function start() {
    refreshCheckoutState();
    new MutationObserver(refreshCheckoutState).observe(document.body, {
      attributes: true,
      attributeFilter: ["href"],
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
