"use strict";

const form = document.querySelector("#qr-form");
const input = document.querySelector("#qr-text");
const counter = document.querySelector("#counter");
const clear = document.querySelector("#clear");
const generate = document.querySelector("#generate");
const label = document.querySelector("#generate-label");
const error = document.querySelector("#error");
const preview = document.querySelector("#preview");
const badge = document.querySelector("#preview-badge");
const empty = document.querySelector("#empty-preview");
const qrImage = document.querySelector("#qr-image");
const info = document.querySelector("#result-info");
const png = document.querySelector("#download-png");
const svg = document.querySelector("#download-svg");
const number = new Intl.NumberFormat("es-ES");
let pendingRequest = null;

function setBusy(busy) {
  generate.disabled = busy;
  label.textContent = busy ? "Generando…" : "Subir";
  preview.setAttribute("aria-busy", String(busy));
}

function resetResult() {
  qrImage.hidden = true;
  qrImage.removeAttribute("src");
  empty.hidden = false;
  badge.textContent = "Vista previa";
  badge.classList.remove("ready");
  info.textContent = "Listo para tu próxima idea.";
  for (const link of [png, svg]) {
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
    link.tabIndex = -1;
    link.classList.add("disabled");
  }
}

function onInput() {
  if (pendingRequest) pendingRequest.abort();
  pendingRequest = null;
  setBusy(false);
  const characters = [...input.value].length;
  const bytes = new TextEncoder().encode(input.value).length;
  counter.textContent = `${number.format(characters)} caracteres · ${number.format(bytes)} bytes UTF-8`;
  clear.disabled = input.value.length === 0;
  error.hidden = true;
  input.removeAttribute("aria-invalid");
  resetResult();
}

input.addEventListener("input", onInput);
clear.addEventListener("click", () => {
  input.value = "";
  onInput();
  input.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (pendingRequest) pendingRequest.abort();
  const controller = new AbortController();
  pendingRequest = controller;
  const timeout = setTimeout(() => controller.abort("timeout"), 35000);
  error.hidden = true;
  input.removeAttribute("aria-invalid");
  resetResult();
  setBusy(true);
  try {
    const response = await fetch("/api/qr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input.value }),
      signal: controller.signal,
    });
    const data = response.headers.get("content-type")?.includes("application/json")
      ? await response.json() : null;
    if (!response.ok) {
      if ([400, 413, 422].includes(response.status)) input.setAttribute("aria-invalid", "true");
      throw new Error(data?.error || (response.status === 413
        ? "El texto es demasiado grande para un único QR. Reduce su longitud."
        : "No se pudo generar el QR. Comprueba que los servicios estén disponibles e inténtalo de nuevo."));
    }
    if (!data?.png || !data?.svg) throw new Error("El servidor ha devuelto una respuesta inesperada.");
    if (pendingRequest !== controller) return;
    qrImage.src = data.png;
    qrImage.hidden = false;
    empty.hidden = true;
    badge.textContent = "Listo para escanear";
    badge.classList.add("ready");
    info.textContent = `QR generado · Versión ${data.version} · ${data.modules} × ${data.modules} módulos`;
    for (const [link, source] of [[png, data.png], [svg, data.svg]]) {
      link.href = source;
      link.setAttribute("aria-disabled", "false");
      link.tabIndex = 0;
      link.classList.remove("disabled");
    }
  } catch (failure) {
    if (pendingRequest !== controller) return;
    error.textContent = controller.signal.reason === "timeout"
      ? "El servidor ha tardado demasiado. Vuelve a intentarlo."
      : failure instanceof TypeError
        ? "No se pudo conectar con el servidor. Comprueba la conexión e inténtalo de nuevo."
        : failure.message;
    error.hidden = false;
    info.textContent = "No se ha generado ningún código.";
  } finally {
    clearTimeout(timeout);
    if (pendingRequest === controller) {
      pendingRequest = null;
      setBusy(false);
    }
  }
});
