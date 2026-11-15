PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LunarLens - Rock ID</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 16px; background: #0b0f17; color: #e6edf3;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; align-items: center; gap: 14px;
  }
  h1 { margin: 0; font-size: 1.3rem; letter-spacing: .5px; }
  h1 span { color: #7dd3fc; }
  .video {
    width: 100%; max-width: 1100px; border-radius: 12px;
    border: 1px solid #243044; background: #000; display: block;
  }
  .bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
  button {
    background: #1f6feb; color: #fff; border: 0; border-radius: 8px;
    padding: 12px 18px; font-size: 1rem; cursor: pointer;
  }
  button.alt { background: #243044; }
  button:active { transform: scale(.97); }
  #toast { min-height: 1.4em; color: #7dd3fc; font-size: .95rem; }
  .hint { color: #8b98a9; font-size: .85rem; }
</style>
</head>
<body>
  <h1>Lunar<span>Lens</span> - Rock ID Station</h1>
  <img class="video" src="/video" alt="Live camera feed">
  <div class="bar">
    <button onclick="act('save')">Save sample (s)</button>
    <button class="alt" onclick="act('site')">Change site (n)</button>
    <button class="alt" onclick="act('conf_down')">Confidence -</button>
    <button class="alt" onclick="act('conf_up')">Confidence +</button>
  </div>
  <div id="toast"></div>
  <div class="hint">Shortcuts: s save, n change site, + / - change confidence</div>
<script>
  const toast = document.getElementById("toast");
  async function act(name) {
    try {
      const response = await fetch("/do/" + name, { method: "POST" });
      toast.textContent = await response.text();
    } catch (error) {
      toast.textContent = "Could not connect to the server";
    }
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "s") act("save");
    else if (event.key === "n") act("site");
    else if (event.key === "+" || event.key === "=") act("conf_up");
    else if (event.key === "-" || event.key === "_") act("conf_down");
  });
</script>
</body>
</html>
"""
