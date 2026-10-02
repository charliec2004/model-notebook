"use strict";

const $ = (id) => document.getElementById(id);
const storageKey = "model-notebook.responses.v1";
const token = document.querySelector('meta[name="session-token"]').content;
let history = [];
let current = null;
let removed = null;
let busy = false;
let envKey = false;

function status(id, message, error = false) {
  $(id).textContent = message;
  $(id).classList.toggle("error", error);
}

async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 130000);
  try {
    const response = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: {"X-Session-Token": token, "Content-Type": "application/json"},
      ...(body ? {body: JSON.stringify(body)} : {}),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The request failed.");
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The request timed out. It may still have been billed; no retry was made.");
    }
    if (error instanceof TypeError || error instanceof SyntaxError) {
      throw new Error("Could not reach the local server. Check that it is running, then reload.");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function updateControls() {
  $("run").disabled = busy || !$("model").value;
  $("run").firstChild.textContent = busy ? "Running… " : "Run question ";
  $("question").disabled = busy;
  $("api-key").disabled = busy;
  $("model").disabled = busy || !$("model").value;
  $("refresh-models").disabled = busy;
}

function modelOptions(models) {
  const used = new Set();
  const groups = [];
  const family = (pattern, count = 1) => {
    const matches = models.filter((model) => pattern.test(model.id));
    const latest = matches.filter((model) => model.id.endsWith("-latest"));
    const pinned = matches.filter((model) => !model.id.endsWith("-latest"))
      .sort((a, b) => b.created - a.created).slice(0, count);
    return [...latest, ...pinned];
  };
  const group = (label, rows) => {
    const options = rows.filter((model) => !used.has(model.id) && used.add(model.id));
    if (!options.length) return;
    const element = document.createElement("optgroup");
    element.label = label;
    element.append(...options.map((model) => new Option(model.name, model.id)));
    groups.push(element);
  };
  group("Claude · Haiku, Sonnet, Opus, Fable", ["haiku", "sonnet", "opus", "fable"].flatMap((name) =>
    family(new RegExp(`^~?anthropic/claude-${name}-(?:[0-9.]+|latest)$`))));
  group("OpenAI · Luna, Terra, Sol, Astra", ["luna", "terra", "sol", "astra"].flatMap((name) =>
    family(new RegExp(`^~?openai/gpt-(?:[0-9.]+-)?${name}(?:-pro|-latest)?$`), 2)));
  group("DeepSeek", ["pro", "flash"].flatMap((name) =>
    family(new RegExp(`^~?deepseek/deepseek-(?:v[0-9.]+-)?${name}(?:-[0-9]+|-latest)?$`))));
  group("Gemini", ["pro", "flash", "flash-lite"].flatMap((name) =>
    family(new RegExp(`^~?google/gemini-(?:[0-9.]+-)?${name}(?:-preview|-latest)?$`))));
  group("Grok", family(/^~?x-ai\/grok-(?:[0-9.]+|latest)$/, 2));
  group("Meta · Muse", family(/^~?meta\/muse-spark-(?:[0-9.]+(?:-contributor)?|latest)$/, 2));
  group("Other available text models", models);
  return groups;
}

async function loadModels() {
  const previous = $("model").value;
  $("refresh-models").disabled = true;
  status("model-status", "Loading the OpenRouter model list…");
  try {
    const {models} = await api("/api/models");
    if (!Array.isArray(models) || !models.length) throw new Error("No text models are available. Refresh to try again.");
    $("model").replaceChildren(...modelOptions(models));
    if (models.some((model) => model.id === previous)) $("model").value = previous;
    status("model-status", "Top model families first · Latest aliases + current versions · Full catalog below");
  } catch (error) {
    status("model-status", error.message, true);
    if (!previous) $("model").replaceChildren(new Option("Models unavailable — refresh to retry", ""));
  } finally {
    updateControls();
  }
}

function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(history));
    status("storage-status", "");
  } catch {
    status("storage-status", "Browser storage is unavailable or full. This session's responses are in memory only. Export JSON before closing.", true);
  }
}

function restore() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (!Array.isArray(saved) || !saved.every((item) => item &&
      ["id", "prompt", "response", "requested_model", "model_name", "model", "created_at"].every((key) => typeof item[key] === "string") &&
      Number.isFinite(Date.parse(item.created_at)))) throw new Error("Invalid history");
    // Keep only the known record fields, never credentials or executable markup.
    history = saved.map((item) => ({
      id: item.id, prompt: item.prompt, response: item.response,
      requested_model: item.requested_model, model_name: item.model_name,
      model: item.model, created_at: item.created_at,
      provider: typeof item.provider === "string" ? item.provider : null,
      finish_reason: typeof item.finish_reason === "string" ? item.finish_reason : null,
      usage: item.usage && typeof item.usage === "object" ? item.usage : null,
      parameters: {temperature: 0.7, max_tokens: 2048},
    }));
  } catch {
    status("storage-status", "Saved history could not be loaded. Existing storage has not been changed. New saves will replace it; export any responses you need.", true);
  }
}

function dateLabel(date) {
  return new Date(date).toLocaleString([], {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"});
}

function show(record) {
  current = record;
  $("response-empty").hidden = Boolean(record);
  $("result").hidden = !record;
  $("copy").disabled = !record;
  if (record) {
    $("result-meta").textContent = `${record.model_name} · ${dateLabel(record.created_at)} · Returned: ${record.model}${record.provider ? " · " + record.provider : ""}`;
    $("result-question").textContent = record.prompt;
    $("result-text").textContent = record.response;
    $("result-warning").textContent = record.finish_reason === "length" ? "Output reached the 2,048-token limit and may be incomplete." :
      record.finish_reason === "content_filter" ? "The provider filtered part of this response." : "";
  }
  renderHistory();
}

function renderHistory() {
  $("saved-count").textContent = history.length;
  $("saved-empty").hidden = history.length > 0;
  $("export").disabled = !history.length;
  $("saved-list").replaceChildren(...history.map((record) => {
    const card = document.createElement("div");
    card.className = "saved-card" + (current?.id === record.id ? " active" : "");
    const open = document.createElement("button");
    open.className = "saved-open";
    open.setAttribute("aria-pressed", String(current?.id === record.id));
    const model = document.createElement("span");
    model.className = "saved-model";
    model.textContent = record.model_name;
    const question = document.createElement("span");
    question.className = "saved-question";
    question.textContent = record.prompt;
    open.append(model, question);
    open.addEventListener("click", () => show(record));
    const bottom = document.createElement("div");
    bottom.className = "saved-bottom";
    const date = document.createElement("span");
    date.textContent = dateLabel(record.created_at);
    const remove = document.createElement("button");
    remove.className = "delete";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", "Remove response: " + record.prompt);
    remove.addEventListener("click", () => {
      removed = {record, index: history.findIndex((item) => item.id === record.id)};
      history = history.filter((item) => item.id !== record.id);
      persist();
      if (current?.id === record.id) show(null);
      else renderHistory();
      $("undo-row").hidden = false;
    });
    bottom.append(date, remove);
    card.append(open, bottom);
    return card;
  }));
}

$("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  const key = $("api-key").value.trim();
  if (!key && !envKey) {
    status("run-status", "Add your OpenRouter API key to run a question.", true);
    $("api-key").focus();
    return;
  }
  const prompt = $("question").value.trim();
  if (!prompt) {
    status("run-status", "Enter a question first.", true);
    $("question").focus();
    return;
  }
  const model = $("model").value;
  const modelName = $("model").selectedOptions[0].textContent;
  busy = true;
  updateControls();
  status("run-status", "Waiting for the model… Your previous response remains available.");
  try {
    const result = await api("/api/run", {api_key: key, prompt, model});
    const record = {
      id: crypto.randomUUID(), created_at: new Date().toISOString(),
      prompt, requested_model: model, model_name: modelName,
      model: result.model, response: result.response,
      provider: result.provider, finish_reason: result.finish_reason, usage: result.usage,
      parameters: {temperature: 0.7, max_tokens: 2048},
    };
    history.unshift(record);
    persist();
    show(record);
    status("run-status", "Response received. Added to your collection.");
  } catch (error) {
    status("run-status", error.message, true);
  } finally {
    busy = false;
    updateControls();
  }
});

$("refresh-models").addEventListener("click", loadModels);
$("copy").addEventListener("click", async () => {
  if (!current) return;
  try {
    await navigator.clipboard.writeText(current.response);
    status("run-status", "Response copied.");
  } catch {
    status("run-status", "Clipboard access is unavailable. Select the response text to copy it.", true);
  }
});
$("undo").addEventListener("click", () => {
  if (!removed) return;
  history.splice(Math.min(removed.index, history.length), 0, removed.record);
  persist();
  show(removed.record);
  removed = null;
  $("undo-row").hidden = true;
});
$("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify({version: 1, exported_at: new Date().toISOString(), responses: history}, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "model-notebook-" + new Date().toISOString().slice(0, 10) + ".json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

restore();
show(history[0] || null);
api("/api/config").then((config) => {
  envKey = config.has_env_key;
  if (envKey) {
    $("api-key").placeholder = "Using OPENROUTER_API_KEY (or paste a different key)";
    $("key-hint").textContent = "The server has a key from your environment. Leave this field blank to use it.";
  }
}).catch((error) => status("run-status", error.message, true));
loadModels();
