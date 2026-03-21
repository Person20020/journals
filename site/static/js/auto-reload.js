// Create a ws connection to the server and on server restart reload the page
(function () {
  const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/auto-reload`;
  const RETRY_INTERVAL = 500;

  let connected = false;
  let hasDied = false;

  function connect() {
    const ws = new WebSocket(WS_URL);

    ws.addEventListener("open", () => {
      if (hasDied) {
        // Server restarted
        location.reload();
      }
      connected = true;
    });

    ws.addEventListener("close", () => {
      connected = false;
      hasDied = true;

      setTimeout(connect, RETRY_INTERVAL);
    });

    ws.addEventListener("error", () => {
      ws.close();
    });
  }

  connect();
})();
