"use strict";

const path = require("node:path");
require("dotenv").config({ path: path.join(__dirname, ".env") });

const express = require("express");
const http = require("node:http");
const https = require("node:https");

const app = express();
const websiteDirectory = path.join(__dirname, "website-app");
const apiHost = process.env.API_HOST || "127.0.0.1";
const apiPort = Number(process.env.API_PORT || 8080);
const apiProtocol = process.env.API_PROTOCOL || "http";
const apiOrigin = new URL(`${apiProtocol}://${apiHost}:${apiPort}`);
const port = Number(process.env.WEB_PORT || 3000);
const host = process.env.WEB_HOST || "0.0.0.0";

if (!["http:", "https:"].includes(apiOrigin.protocol)) {
  throw new Error("API_PROTOCOL must be http or https");
}

for (const [name, value] of [["API_PORT", apiPort], ["WEB_PORT", port]]) {
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    throw new Error(`${name} must be an integer between 1 and 65535`);
  }
}

app.use(["/api", "/docs", "/openapi.json"], (request, response) => {
  const target = new URL(request.originalUrl, apiOrigin);
  if (target.origin !== apiOrigin.origin) {
    response.status(400).json({ detail: "Invalid API request path" });
    return;
  }
  const transport = target.protocol === "https:" ? https : http;
  const headers = { ...request.headers, host: target.host };
  const upstream = transport.request(
    target,
    { method: request.method, headers },
    (upstreamResponse) => {
      response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
      upstreamResponse.pipe(response);
    },
  );

  upstream.on("error", (error) => {
    console.error(`API proxy failed: ${error.message}`);
    if (!response.headersSent) {
      response.status(502).json({
        detail: "The detection API is unavailable. Start the Python API server and try again.",
      });
    } else {
      response.destroy(error);
    }
  });

  request.on("aborted", () => upstream.destroy());
  request.pipe(upstream);
});

app.get("/api_test.html", (request, response) => {
  response.sendFile(path.join(__dirname, "api_test.html"));
});

app.use(express.static(websiteDirectory));

app.listen(port, host, () => {
  console.log(`LunarLithos website listening at http://localhost:${port}`);
  console.log(`Forwarding /api requests to ${apiOrigin.origin}`);
});
