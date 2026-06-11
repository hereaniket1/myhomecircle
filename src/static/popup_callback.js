try {
  if (window.opener && !window.opener.closed) {
    window.opener.postMessage({ type: "oauth_success" }, window.location.origin);
  }
} catch (error) {
  try {
    window.opener.postMessage({ type: "oauth_success" }, "*");
  } catch (_) {}
}

setTimeout(() => {
  window.close();
}, 350);
