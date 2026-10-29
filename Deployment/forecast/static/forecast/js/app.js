/* Small progressive enhancements: "Load real data" presets, submit spinner, scroll to the result on phones. */
(function () {
  const form = document.getElementById("forecast-form");
  if (!form) return;

  const select = document.getElementById("sample-select");
  const loadBtn = document.getElementById("load-sample");
  const status = document.getElementById("sample-status");
  const fields = ["forecast_date", "temp_2d_ago", "temp_24d_ago", "temp_1y_ago", "avg_8d", "avg_30d", "avg_62d"];

  async function loadSample() {
    status.textContent = "Loading…";
    try {
      const response = await fetch(form.dataset.sampleUrl + "?date=" + encodeURIComponent(select.value));
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error((data.errors && data.errors.date && data.errors.date[0]) || "No data for this date.");
      fields.forEach(function (name) {
        const input = document.getElementById("id_" + name);
        if (input) { input.value = name === "forecast_date" ? data.forecast_date : data[name]; input.classList.remove("is-invalid"); }
      });
      status.textContent = data.observed === null
        ? "Loaded the latest real readings. Press “Forecast temperature”."
        : "Loaded real readings. Observed value on that date: " + data.observed.toFixed(1) + " °C.";
    } catch (error) {
      status.textContent = error.message;
    }
  }
  if (loadBtn) loadBtn.addEventListener("click", loadSample);

  form.addEventListener("submit", function () {
    const button = document.getElementById("submit-btn");
    button.disabled = true;
    button.querySelector(".spinner-border").classList.remove("d-none");
    button.querySelector(".label").textContent = " Forecasting…";
  });

  const result = document.getElementById("result");
  if (result && result.classList.contains("result-card") && window.matchMedia("(max-width: 991px)").matches) {
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }
})();
