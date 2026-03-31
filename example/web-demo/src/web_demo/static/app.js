const statusEl = document.getElementById("status");
const btn = document.getElementById("btn");

btn.addEventListener("click", async () => {
  statusEl.textContent = "Calling API...";
  try {
    const res = await fetch("/api/hello");
    const data = await res.json();
    statusEl.textContent = data.message || JSON.stringify(data);
  } catch (err) {
    statusEl.textContent = "Request failed: " + err;
  }
});

