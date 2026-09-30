#!/usr/bin/env python3
"""Build a self-contained, read-only viewer for selected BFCL-to-Jev cases."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "bfcl_v1" / "cases.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "bfcl_v1" / "viewer.html"
DEFAULT_RESULTS_DIR = ROOT / "results"
DEFAULT_RESULT_PREFIX = "bfcl_v1_"


HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="source-case-sha256" content="__SOURCE_SHA256__">
  <title>BFCL V1 · Jev prompt viewer</title>
  <style>
    :root {
      font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #e9eef8;
      background: #0b1020;
      font-synthesis: none;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; }
    button, input, select { font: inherit; }
    button { cursor: pointer; }
    button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {
      outline: 2px solid #8db2ff; outline-offset: 3px;
    }
    .app { display: grid; grid-template-columns: minmax(260px, 330px) minmax(0, 1fr); min-height: 100vh; }
    .sidebar { background: #10182a; border-right: 1px solid #26334b; display: flex; flex-direction: column; min-height: 0; }
    .brand { padding: 26px 22px 17px; border-bottom: 1px solid #26334b; }
    .eyebrow { color: #8fb0ff; font-size: 11px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
    h1 { margin: 8px 0 7px; font-size: 23px; line-height: 1.15; letter-spacing: -.03em; }
    .brand p, .muted { color: #a9b7cd; }
    .brand p { font-size: 13px; line-height: 1.5; margin: 0; }
    .filters { padding: 17px 16px 13px; display: grid; gap: 10px; border-bottom: 1px solid #26334b; }
    .field-label { color: #bdc9db; display: block; font-size: 11px; font-weight: 700; margin-bottom: 5px; text-transform: uppercase; letter-spacing: .07em; }
    input, select { background: #172238; border: 1px solid #34435c; border-radius: 10px; color: #edf2fb; width: 100%; padding: 10px 12px; }
    input::placeholder { color: #8999b2; }
    .filter-count { color: #93a4bc; font-size: 12px; padding: 0 4px; }
    .case-list { padding: 10px; overflow: auto; flex: 1; max-height: calc(100vh - 260px); }
    .case-item { display: block; width: 100%; text-align: left; border: 1px solid transparent; border-radius: 12px; background: transparent; color: #dce5f3; padding: 11px 12px; margin: 2px 0; }
    .case-item:hover { background: #19263c; }
    .case-item.active { background: #1b2d50; border-color: #4e70b7; }
    .case-id { display: block; color: #95adcf; font-size: 11px; font-weight: 750; margin-bottom: 4px; }
    .case-question { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; line-height: 1.37; font-size: 13px; }
    .case-result { display: block; color: #93a9c8; font-size: 11px; margin-top: 6px; }
    .main { min-width: 0; }
    .topbar { display: flex; gap: 16px; align-items: center; justify-content: space-between; padding: 20px clamp(20px, 4vw, 52px); border-bottom: 1px solid #26334b; background: #0d1526; }
    .topbar .title { font-size: 14px; font-weight: 700; }
    .topbar .subtitle { color: #a9b7cd; font-size: 12px; margin-top: 3px; }
    .nav { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
    .nav-count { color: #a9b7cd; font-size: 12px; padding: 0 4px; min-width: 52px; text-align: center; }
    .button { background: #202f49; border: 1px solid #3b4d68; border-radius: 9px; color: #e9eef8; padding: 9px 12px; }
    .button:hover:not(:disabled) { background: #2a3e60; }
    .button:disabled { cursor: default; opacity: .45; }
    .content { max-width: 1050px; margin: 0 auto; padding: 28px clamp(20px, 4vw, 52px) 70px; }
    .overview { max-width: 1154px; margin: 0 auto; padding: 22px clamp(20px, 4vw, 52px) 0; }
    .overview-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 12px; }
    .overview-head h2 { margin: 0 0 4px; font-size: 17px; }
    .overview-head p { margin: 0; color: #a9b7cd; font-size: 12px; }
    .import-log { display: flex; align-items: center; gap: 7px; color: #b7c8e2; font-size: 12px; }
    .import-log input { width: auto; max-width: 240px; padding: 6px; font-size: 11px; }
    .overview-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 15px; }
    .score-card { background: #152137; border: 1px solid #33445f; border-radius: 13px; padding: 13px 15px; }
    .score-name { color: #e9eef8; font-weight: 750; font-size: 13px; overflow-wrap: anywhere; }
    .score-value { color: #d9e7ff; font-size: 21px; font-weight: 800; margin: 6px 0 3px; }
    .score-detail { color: #a9b7cd; font-size: 11px; line-height: 1.45; }
    .comparison { width: 100%; border-collapse: collapse; font-size: 13px; }
    .comparison-wrap { border: 1px solid #33445f; border-radius: 13px; overflow-x: auto; background: #111b2e; }
    .comparison th, .comparison td { text-align: left; padding: 11px 13px; border-bottom: 1px solid #293850; vertical-align: top; }
    .comparison tr:last-child td { border-bottom: 0; }
    .comparison th { color: #aebdd2; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; white-space: nowrap; }
    .comparison .action { font-weight: 750; overflow-wrap: anywhere; min-width: 150px; }
    .verdict { display: inline-block; border-radius: 999px; padding: 3px 7px; font-size: 11px; font-weight: 750; white-space: nowrap; }
    .verdict.correct { background: #1d503c; color: #dcf8e9; }
    .verdict.wrong { background: #62313a; color: #ffe0e5; }
    .verdict.missing { background: #37445d; color: #c5d1e1; }
    .log-details { min-width: 72px; margin-top: 0; }
    .log-details pre { min-width: 250px; max-width: 480px; }
    .picked-by { color: #9fb8e6; font-size: 11px; line-height: 1.4; margin-top: 8px; overflow-wrap: anywhere; }
    .case-heading { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; margin-bottom: 20px; }
    .pill { display: inline-block; border: 1px solid #3b4d68; background: #172339; border-radius: 999px; color: #b7c8e2; font-size: 12px; padding: 5px 9px; }
    .case-heading .id { color: #edf2fb; font-size: 15px; font-weight: 750; margin-right: 3px; overflow-wrap: anywhere; }
    .conversation { display: grid; gap: 18px; padding: 24px; background: #111b2e; border: 1px solid #293850; border-radius: 18px; }
    .turn { display: flex; gap: 12px; align-items: flex-start; }
    .turn.user { justify-content: flex-end; }
    .avatar { width: 32px; height: 32px; flex: none; display: grid; place-items: center; border-radius: 10px; background: #344363; color: #edf3ff; font-size: 12px; font-weight: 800; }
    .turn.user .avatar { order: 2; background: #334b91; }
    .bubble { max-width: min(760px, calc(100% - 44px)); min-width: 0; padding: 16px 18px; border-radius: 15px; background: #1b2a44; border: 1px solid #334662; }
    .turn.user .bubble { background: #223a70; border-color: #3d5b9e; }
    .speaker { color: #b7c6de; font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; margin-bottom: 7px; }
    .turn.user .speaker { color: #d6e2ff; }
    .bubble-text { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.56; font-size: 16px; }
    .gold-value { display: inline-block; color: #dff9ec; background: #1c503d; border: 1px solid #348767; border-radius: 8px; padding: 7px 10px; font-size: 15px; font-weight: 700; overflow-wrap: anywhere; }
    .bubble-note { color: #bdcde2; margin: 10px 0 0; font-size: 13px; line-height: 1.5; }
    .hint { color: #a9b7cd; font-size: 12px; line-height: 1.5; margin: 11px 2px 0; }
    .toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin: 20px 0 26px; }
    .toolbar .button { font-size: 12px; }
    h2 { font-size: 16px; letter-spacing: -.01em; margin: 29px 0 7px; }
    .section-note { color: #a9b7cd; font-size: 13px; line-height: 1.5; margin: 0 0 12px; }
    .options { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }
    .option { background: #152137; border: 1px solid #33445f; border-radius: 13px; padding: 14px 15px; min-width: 0; }
    .option.chosen { background: #16372f; border-color: #43a77b; box-shadow: 0 0 0 1px #43a77b inset; }
    .option-head { display: flex; align-items: flex-start; gap: 8px; justify-content: space-between; }
    .option-name { color: #eaf0fc; font-weight: 750; font-size: 14px; overflow-wrap: anywhere; }
    .chosen .option-name { color: #dff9ec; }
    .selected-tag { flex: none; background: #29694d; color: #e3fff0; font-size: 10px; font-weight: 800; border-radius: 999px; padding: 3px 7px; }
    .option-desc { color: #aebdd2; font-size: 13px; line-height: 1.45; margin: 7px 0 0; overflow-wrap: anywhere; }
    details { margin-top: 12px; }
    summary { color: #a8c2ff; cursor: pointer; font-size: 12px; }
    .disclosure { border: 1px solid #33445f; background: #101a2d; border-radius: 12px; padding: 14px 16px; margin-top: 12px; }
    .disclosure summary { font-size: 14px; font-weight: 700; }
    .disclosure p { color: #a9b7cd; font-size: 13px; line-height: 1.5; }
    pre { color: #d8e4f7; white-space: pre-wrap; overflow-wrap: anywhere; background: #0a1425; border: 1px solid #293b55; border-radius: 9px; padding: 13px; font-size: 12px; line-height: 1.5; max-height: 460px; overflow: auto; }
    .empty { color: #a9b7cd; padding: 30px 20px; text-align: center; }
    .footer { color: #91a2bb; font-size: 12px; line-height: 1.5; margin-top: 28px; }
    @media (max-width: 760px) {
      .app { display: block; }
      .sidebar { border-right: 0; border-bottom: 1px solid #26334b; }
      .brand { padding: 18px 20px; }
      .filters { grid-template-columns: 1fr 1fr; }
      .filters .search, .filter-count { grid-column: 1 / -1; }
      .case-list { display: flex; overflow-x: auto; max-height: none; padding: 8px 12px; }
      .case-item { flex: 0 0 220px; }
      .topbar { padding: 14px 20px; }
      .content { padding-top: 22px; }
      .conversation { padding: 16px; }
    }
    @media (max-width: 450px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      .filters { grid-template-columns: 1fr; }
      .filters .search, .filter-count { grid-column: auto; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar" aria-label="Case browser">
      <div class="brand">
        <div class="eyebrow">BFCL V1 → Jev</div>
        <h1>Prompt viewer</h1>
        <p><span id="total-count"></span> selected cases · Saved model decisions</p>
      </div>
      <div class="filters">
        <label class="search"><span class="field-label">Find a prompt or tool</span><input id="search" type="search" placeholder="Search requests, IDs, tools…" autocomplete="off"></label>
        <label><span class="field-label">Category</span><select id="category"><option value="all">All categories</option></select></label>
        <label><span class="field-label">Expected route</span><select id="route"><option value="all">All routes</option><option value="tool">Choose a tool</option><option value="no_tool">No tool</option></select></label>
        <label><span class="field-label">Model</span><select id="model-filter"><option value="all">Any model</option></select></label>
        <label><span class="field-label">Selection result</span><select id="outcome-filter"><option value="all">All cases</option><option value="wrong">Wrong tool selection</option><option value="correct">Correct tool selection</option><option value="missing">Missing or request error</option></select></label>
        <div class="filter-count" id="filter-count" aria-live="polite"></div>
      </div>
      <div class="case-list" id="case-list" aria-label="Filtered cases"></div>
    </aside>
    <main class="main">
      <div class="topbar">
        <div><div class="title">User → Jev router</div><div class="subtitle">Compare the BFCL-derived route with each model's saved selection.</div></div>
        <div class="nav"><button class="button" id="prev" type="button" aria-label="Previous case">←</button><span class="nav-count" id="nav-count"></span><button class="button" id="next" type="button" aria-label="Next case">→</button></div>
      </div>
      <section class="overview" id="overview" aria-label="Saved model comparison"></section>
      <div class="content" id="content"></div>
    </main>
  </div>
  <script type="application/json" id="case-data">__CASE_JSON__</script>
  <script type="application/json" id="result-data">__RESULT_JSON__</script>
  <script>
  (() => {
    "use strict";
    const cases = JSON.parse(document.getElementById("case-data").textContent);
    const embeddedResults = JSON.parse(document.getElementById("result-data").textContent);
    const byId = new Map(cases.map(item => [item.id, item]));
    const noFunctionActions = new Set(["no_tool", "clarify", "cannot_answer"]);
    const models = new Map();
    const ui = {
      search: document.getElementById("search"), category: document.getElementById("category"),
      route: document.getElementById("route"), list: document.getElementById("case-list"),
      model: document.getElementById("model-filter"), outcome: document.getElementById("outcome-filter"),
      overview: document.getElementById("overview"),
      content: document.getElementById("content"), count: document.getElementById("filter-count"),
      navCount: document.getElementById("nav-count"), prev: document.getElementById("prev"),
      next: document.getElementById("next")
    };
    const state = { visible: cases, selectedId: null, showAnswer: true };
    const hashId = () => new URLSearchParams(location.hash.slice(1)).get("case");
    const label = value => value.replaceAll("_", " ");
    const modelName = slug => slug.replaceAll(/[_-]+/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
    const sourceFunctions = item => Array.isArray(item.source.functions)
      ? item.source.functions : (item.source.functions ? [item.source.functions] : []);
    function addModel(run) {
      if (!run || !run.id || !Array.isArray(run.rows)) throw new Error("Result log is missing its model ID or rows.");
      const rows = new Map();
      for (const row of run.rows) {
        if (!row || typeof row.case_id !== "string" || !byId.has(row.case_id)) {
          throw new Error("Result log contains a case ID outside this BFCL set.");
        }
        if (rows.has(row.case_id)) throw new Error("Result log repeats case " + row.case_id + ".");
        rows.set(row.case_id, row);
      }
      models.set(run.id, { id: run.id, name: run.name || modelName(run.id),
        requestedModel: run.requested_model || "", rows });
    }
    function refreshModelOptions() {
      const selected = ui.model.value;
      ui.model.replaceChildren();
      const any = element("option", "", "Any model");
      any.value = "all";
      ui.model.append(any);
      for (const model of models.values()) {
        const option = element("option", "", model.name);
        option.value = model.id;
        ui.model.append(option);
      }
      ui.model.value = models.has(selected) ? selected : "all";
    }
    function visibleModels() {
      return ui.model.value === "all" ? [...models.values()] : [models.get(ui.model.value)].filter(Boolean);
    }
    function toolSelectionCorrect(item, row) {
      if (!row || row.status !== "ok" || typeof row.predicted_action !== "string") return false;
      if (item.gold_next_action_ids.includes("no_tool")) return noFunctionActions.has(row.predicted_action);
      return item.gold_next_action_ids.includes(row.predicted_action);
    }
    function exactActionCorrect(item, row) {
      return Boolean(row && row.status === "ok" && item.gold_next_action_ids.includes(row.predicted_action));
    }
    function outcomeFor(item, model) {
      const row = model.rows.get(item.id);
      if (!row || row.status !== "ok") return "missing";
      return toolSelectionCorrect(item, row) ? "correct" : "wrong";
    }
    function element(tag, className, value) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (value !== undefined) node.textContent = String(value);
      return node;
    }
    function json(value) { return JSON.stringify(value, null, 2); }
    function writeHash(id) {
      try { history.replaceState(null, "", "#case=" + encodeURIComponent(id)); }
      catch (_) { location.hash = "case=" + encodeURIComponent(id); }
    }
    function select(id, updateHash = true) {
      if (!byId.has(id)) return;
      state.selectedId = id;
      if (updateHash) writeHash(id);
      render();
    }
    function filterCases() {
      const query = ui.search.value.trim().toLocaleLowerCase();
      const category = ui.category.value;
      const route = ui.route.value;
      const outcome = ui.outcome.value;
      const selectedModels = visibleModels();
      state.visible = cases.filter(item => {
        if (category !== "all" && item.category !== category) return false;
        const isNoTool = item.gold_next_action_ids.includes("no_tool");
        if (route === "no_tool" && !isNoTool) return false;
        if (route === "tool" && isNoTool) return false;
        if (outcome !== "all") {
          const matches = selectedModels.map(model => outcomeFor(item, model));
          if (!matches.length) return false;
          if (outcome === "correct" && !matches.every(value => value === "correct")) return false;
          if (outcome !== "correct" && !matches.includes(outcome)) return false;
        }
        if (!query) return true;
        const haystack = [item.id, item.source.question,
          ...item.jev.options.map(option => option.id + " " + option.description)].join(" ").toLocaleLowerCase();
        return haystack.includes(query);
      });
      if (!state.visible.some(item => item.id === state.selectedId)) {
        state.selectedId = state.visible.length ? state.visible[0].id : null;
        if (state.selectedId) writeHash(state.selectedId);
      }
      render();
    }
    function renderList() {
      ui.list.replaceChildren();
      ui.count.textContent = state.visible.length + " of " + cases.length + " cases";
      const fragment = document.createDocumentFragment();
      const shownModels = visibleModels();
      state.visible.forEach(item => {
        const button = element("button", "case-item" + (item.id === state.selectedId ? " active" : ""));
        button.type = "button";
        button.setAttribute("aria-current", item.id === state.selectedId ? "true" : "false");
        button.append(element("span", "case-id", item.id), element("span", "case-question", item.source.question));
        if (shownModels.length) {
          const logged = shownModels.filter(model => model.rows.has(item.id)).length;
          button.append(element("span", "case-result", logged + " / " + shownModels.length +
            (shownModels.length === 1 ? " model log" : " model logs")));
        }
        button.addEventListener("click", () => select(item.id));
        fragment.append(button);
      });
      ui.list.append(fragment);
      const index = state.visible.findIndex(item => item.id === state.selectedId);
      ui.navCount.textContent = index < 0 ? "0 / 0" : (index + 1) + " / " + state.visible.length;
      ui.prev.disabled = index <= 0;
      ui.next.disabled = index < 0 || index === state.visible.length - 1;
    }
    function renderOverview() {
      ui.overview.replaceChildren();
      const head = element("div", "overview-head");
      const title = element("div");
      title.append(element("h2", "", "Saved model comparison"),
        element("p", "", "Tool selection on the currently filtered cases. Missing and failed requests count as wrong."));
      const importControl = element("label", "import-log", "Add result log (.jsonl)");
      const fileInput = document.createElement("input");
      fileInput.type = "file";
      fileInput.accept = ".jsonl,application/x-ndjson";
      fileInput.multiple = true;
      fileInput.addEventListener("change", importFiles);
      importControl.append(fileInput);
      head.append(title, importControl);
      ui.overview.append(head);
      if (!models.size) {
        ui.overview.append(element("p", "section-note", "No saved model results were embedded. Add a result log or rebuild the viewer after evaluations finish."));
        return;
      }
      const grid = element("div", "overview-grid");
      for (const model of visibleModels()) {
        let correct = 0, logged = 0, errors = 0;
        for (const item of state.visible) {
          const row = model.rows.get(item.id);
          if (row) {
            logged += 1;
            if (row.status !== "ok") errors += 1;
            if (toolSelectionCorrect(item, row)) correct += 1;
          }
        }
        const card = element("article", "score-card");
        const denominator = state.visible.length;
        const percent = denominator ? (100 * correct / denominator).toFixed(1) + "%" : "—";
        card.append(element("div", "score-name", model.name),
          element("div", "score-value", percent),
          element("div", "score-detail", correct + " / " + denominator + " correct tool selections"),
          element("div", "score-detail", logged + " logged · " + errors + " request errors"));
        if (model.requestedModel) card.append(element("div", "score-detail", model.requestedModel));
        grid.append(card);
      }
      ui.overview.append(grid);
    }
    function renderModelSelections(container, item) {
      const section = element("section");
      section.append(element("h2", "", "What each model selected"));
      section.append(element("p", "section-note", "Tool selection treats no_tool, clarify, and cannot_answer as no function on BFCL no-call cases. Exact action distinguishes those choices. Expand a row to inspect its saved log."));
      if (!models.size) {
        section.append(element("p", "section-note", "No model decisions loaded yet."));
        container.append(section);
        return;
      }
      const wrapper = element("div", "comparison-wrap");
      const table = element("table", "comparison");
      const header = document.createElement("thead");
      const headings = document.createElement("tr");
      for (const text of ["Model", "Selected action", "Tool selection", "Exact action", "Saved log"]) {
        headings.append(element("th", "", text));
      }
      header.append(headings);
      table.append(header);
      const body = document.createElement("tbody");
      for (const model of visibleModels()) {
        const row = model.rows.get(item.id);
        const tr = document.createElement("tr");
        tr.append(element("td", "", model.name));
        const action = row && row.status === "ok" ? (row.predicted_action || "No selection")
          : row ? "Request error" : "Not evaluated";
        tr.append(element("td", "action", action));
        for (const correct of [toolSelectionCorrect(item, row), exactActionCorrect(item, row)]) {
          const cell = document.createElement("td");
          const status = !row || row.status !== "ok" ? "missing" : correct ? "correct" : "wrong";
          const textValue = !state.showAnswer ? "Hidden" :
            status === "missing" ? (row ? "Error" : "No result") : status === "correct" ? "Correct" : "Wrong";
          cell.append(element("span", "verdict " + (!state.showAnswer ? "missing" : status), textValue));
          tr.append(cell);
        }
        const logCell = document.createElement("td");
        if (row) {
          const details = element("details", "log-details");
          details.append(element("summary", "", "View log"), element("pre", "", json(row)));
          logCell.append(details);
        } else logCell.append(element("span", "muted", "—"));
        tr.append(logCell);
        body.append(tr);
      }
      table.append(body);
      wrapper.append(table);
      section.append(wrapper);
      container.append(section);
    }
    function addTurn(conversation, kind, speaker, textValue, note) {
      const turn = element("div", "turn " + kind);
      const avatar = element("div", "avatar", kind === "user" ? "U" : "J");
      avatar.setAttribute("aria-hidden", "true");
      const bubble = element("div", "bubble");
      bubble.append(element("div", "speaker", speaker));
      bubble.append(element("div", kind === "user" ? "bubble-text" : "gold-value", textValue));
      if (note) bubble.append(element("p", "bubble-note", note));
      turn.append(avatar, bubble);
      conversation.append(turn);
    }
    function renderOptions(container, item, kind) {
      const section = element("section");
      section.append(element("h2", "", kind === "tool" ? "Offered functions" : "Other router choices"));
      section.append(element("p", "section-note", kind === "tool"
        ? "Jev selects a function. The chat model owns arguments, clarification, and execution."
        : "These are also present in the Jev choice prompt."));
      const grid = element("div", "options");
      item.jev.options.filter(option => option.kind === kind).forEach(option => {
        const chosen = state.showAnswer && item.gold_next_action_ids.includes(option.id);
        const card = element("article", "option" + (chosen ? " chosen" : ""));
        const head = element("div", "option-head");
        head.append(element("div", "option-name", option.label));
        if (chosen) head.append(element("span", "selected-tag", "Expected"));
        card.append(head, element("p", "option-desc", option.description));
        const pickedBy = visibleModels().filter(model => {
          const result = model.rows.get(item.id);
          return result && result.status === "ok" && result.predicted_action === option.id;
        }).map(model => model.name);
        if (pickedBy.length) card.append(element("div", "picked-by", "Picked by: " + pickedBy.join(", ")));
        if (kind === "tool") {
          const sourceTool = sourceFunctions(item).find(tool => tool.name === option.id);
          if (sourceTool && sourceTool.parameters) {
            const details = element("details");
            details.append(element("summary", "", "Function schema (for chat model)"));
            details.append(element("pre", "", json(sourceTool.parameters)));
            card.append(details);
          }
        }
        grid.append(card);
      });
      section.append(grid);
      container.append(section);
    }
    function renderDisclosure(container, title, description, value) {
      const details = element("details", "disclosure");
      details.append(element("summary", "", title));
      details.append(element("p", "", description));
      details.append(element("pre", "", json(value)));
      container.append(details);
    }
    function renderCase(item) {
      const content = ui.content;
      content.replaceChildren();
      const heading = element("div", "case-heading");
      heading.append(element("span", "id", item.id));
      heading.append(element("span", "pill", label(item.category)));
      const functionCount = sourceFunctions(item).length;
      heading.append(element("span", "pill", functionCount + (functionCount === 1 ? " offered function" : " offered functions")));
      content.append(heading);

      const conversation = element("section", "conversation");
      conversation.setAttribute("aria-label", "Prompt and expected router choice");
      addTurn(conversation, "user", "User request", item.source.question);
      const answer = item.gold_next_action_ids.join(" + ");
      addTurn(conversation, "router", "Jev expected routing choice · reference label, not model output",
        state.showAnswer ? answer : "Hidden",
        state.showAnswer
          ? (answer === "no_tool" ? "No offered function is selected for this BFCL case." : "The chat model decides arguments, asks for missing details if needed, and handles the call.")
          : "Use Reveal expected choice to show the reference label.");
      content.append(conversation);
      content.append(element("p", "hint", "These are saved first-step routing decisions. They do not show generated replies, function arguments, or executed calls."));

      renderModelSelections(content, item);

      const toolbar = element("div", "toolbar");
      const toggle = element("button", "button", state.showAnswer ? "Hide expected choice" : "Reveal expected choice");
      toggle.type = "button";
      toggle.setAttribute("aria-pressed", state.showAnswer ? "true" : "false");
      toggle.addEventListener("click", () => { state.showAnswer = !state.showAnswer; renderCase(item); });
      toolbar.append(toggle);
      content.append(toolbar);

      renderOptions(content, item, "tool");
      renderOptions(content, item, "meta");
      renderDisclosure(content, "Original BFCL answer · source reference",
        "This is source data for review and scoring. Its arguments are not a Jev output or an executed assistant call.",
        { ground_truth: item.source.ground_truth, gold_calls: item.gold_calls, source_question_file: item.source.question_file,
          source_answer_file: item.source.answer_file, source_row_number: item.source.row_number });
      renderDisclosure(content, "Raw Laya prompt payload",
        "The choice prompt as stored for the Laya adapter. Gold labels and original BFCL answers are outside this payload.", item.jev.laya);
      renderDisclosure(content, "Raw MacJev prompt payload",
        "The choice prompt as stored for the MacJev adapter. Gold labels and original BFCL answers are outside this payload.", item.jev.macjev);
      content.append(element("p", "footer", "Offline review artifact · Source: Berkeley Function Calling Leaderboard V1 · Prompt conversion: Jev model performance"));
    }
    function render() {
      renderOverview();
      renderList();
      const item = byId.get(state.selectedId);
      if (item) renderCase(item);
      else ui.content.replaceChildren(element("div", "empty", "No cases match these filters."));
    }
    function move(delta) {
      const index = state.visible.findIndex(item => item.id === state.selectedId);
      const next = state.visible[index + delta];
      if (next) select(next.id);
    }
    async function importFiles(event) {
      const files = [...event.target.files];
      const errors = [];
      for (const file of files) {
        try {
          const slug = file.name.replace(/^bfcl_v1_/, "").replace(/\.jsonl$/i, "");
          if (!slug || slug === file.name) throw new Error("Expected a .jsonl result file.");
          const rows = file.name.toLowerCase().endsWith(".jsonl")
            ? (await file.text()).split(/\r?\n/).filter(line => line.trim()).map(line => JSON.parse(line))
            : [];
          if (!rows.length) throw new Error("The result log is empty.");
          addModel({ id: slug, name: modelName(slug), rows });
        } catch (error) { errors.push(file.name + ": " + error.message); }
      }
      event.target.value = "";
      refreshModelOptions();
      filterCases();
      if (errors.length) alert("Could not load these result logs:\n" + errors.join("\n"));
    }

    embeddedResults.forEach(addModel);
    refreshModelOptions();
    document.getElementById("total-count").textContent = cases.length;
    [...new Set(cases.map(item => item.category))].sort().forEach(category => {
      const option = document.createElement("option");
      option.value = category; option.textContent = label(category); ui.category.append(option);
    });
    ui.search.addEventListener("input", filterCases);
    ui.category.addEventListener("change", filterCases);
    ui.route.addEventListener("change", filterCases);
    ui.model.addEventListener("change", filterCases);
    ui.outcome.addEventListener("change", filterCases);
    ui.prev.addEventListener("click", () => move(-1));
    ui.next.addEventListener("click", () => move(1));
    document.addEventListener("keydown", event => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
      if (event.key === "ArrowLeft") move(-1);
      if (event.key === "ArrowRight") move(1);
    });
    window.addEventListener("hashchange", () => {
      const id = hashId();
      if (!byId.has(id)) return;
      if (!state.visible.some(item => item.id === id)) {
        ui.search.value = ""; ui.category.value = "all"; ui.route.value = "all";
        ui.model.value = "all"; ui.outcome.value = "all";
        state.visible = cases;
      }
      select(id, false);
    });
    state.selectedId = byId.has(hashId()) ? hashId() : (cases[0] && cases[0].id);
    render();
  })();
  </script>
</body>
</html>
'''


def read_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
                case_id = case["id"]
                case["source"]["question"]
                case["source"]["functions"]
                case["jev"]["options"]
                case["gold_next_action_ids"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid case on line {line_number}: {exc}") from exc
            if not isinstance(case_id, str) or case_id in seen:
                raise ValueError(f"Missing or duplicate case ID on line {line_number}: {case_id!r}")
            seen.add(case_id)
            cases.append(case)
    if not cases:
        raise ValueError(f"No cases found in {path}")
    return cases


def validate_result_prefix(result_prefix: str) -> str:
    """Keep the filename prefix literal, without paths or glob operators."""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", result_prefix):
        raise ValueError("Result prefix must be a nonempty filename prefix using letters, digits, _, - or .")
    return result_prefix


def read_results(
    directory: Path, case_ids: set[str], source_sha256: str,
    result_prefix: str = DEFAULT_RESULT_PREFIX,
) -> list[dict]:
    """Load compatible per-case logs and reject stale or mixed-case results."""
    validate_result_prefix(result_prefix)
    if not directory.exists():
        return []
    runs: list[dict] = []
    for path in sorted(directory.glob(f"{result_prefix}*.jsonl")):
        slug = path.stem.removeprefix(result_prefix)
        if not slug:
            continue
        meta_path = path.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        logged_sha256 = meta.get("run", {}).get("cases_sha256")
        if logged_sha256 and logged_sha256 != source_sha256:
            raise ValueError(f"Result log {path} has a different source-case SHA-256")
        rows: list[dict] = []
        seen: set[str] = set()
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    case_id = row["case_id"]
                    status = row["status"]
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise ValueError(f"Invalid result in {path} line {line_number}: {exc}") from exc
                if not isinstance(case_id, str) or case_id not in case_ids or case_id in seen:
                    raise ValueError(f"Unknown or repeated case ID in {path} line {line_number}: {case_id!r}")
                if not isinstance(status, str):
                    raise ValueError(f"Invalid status in {path} line {line_number}: {status!r}")
                if status == "ok" and not isinstance(row.get("predicted_action"), str):
                    raise ValueError(f"Missing predicted action in {path} line {line_number}")
                seen.add(case_id)
                rows.append(row)
        if not rows:
            continue
        runs.append({
            "id": slug,
            "name": slug.replace("_", " ").replace("-", " ").title(),
            "requested_model": meta.get("run", {}).get("requested_model", ""),
            "rows": rows,
        })
    return runs


def embed_json(value: object) -> str:
    """Escape characters that can terminate a script tag or alter HTML parsing."""
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        data.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(
    cases: list[dict], runs: list[dict], source_sha256: str,
    bfcl_version: str = "v1", dataset_name: str | None = None,
    result_prefix: str | None = None,
) -> str:
    """Render a named BFCL set while preserving the original V1 default HTML."""
    if bfcl_version not in {"v1", "v4"}:
        raise ValueError("BFCL version must be v1 or v4")
    prefix = validate_result_prefix(result_prefix if result_prefix is not None else f"bfcl_{bfcl_version}_")
    name = html.escape(dataset_name or f"BFCL {bfcl_version.upper()}")
    template = HTML.replace("<title>BFCL V1 ·", f"<title>{name} ·", 1)
    template = template.replace(
        '<div class="eyebrow">BFCL V1 → Jev</div>',
        f'<div class="eyebrow">{name} → Jev</div>', 1,
    )
    template = template.replace(
        "Source: Berkeley Function Calling Leaderboard V1 ·",
        f"Source: Berkeley Function Calling Leaderboard {bfcl_version.upper()} ·", 1,
    )
    if bfcl_version != "v1" or prefix != DEFAULT_RESULT_PREFIX:
        # V4 uploads must match its result namespace, even if another set shares an ID.
        original = 'const slug = file.name.replace(/^bfcl_v1_/, "").replace(/\\.jsonl$/i, "");'
        replacement = (
            f'if (!file.name.startsWith({embed_json(prefix)})) '
            f'throw new Error("Expected a result filename beginning with " + {embed_json(prefix)} + ".");\n'
            f'          const slug = file.name.slice({len(prefix)}).replace(/\\.jsonl$/i, "");'
        )
        template = template.replace(original, replacement, 1)
    template = template.replace("__SOURCE_SHA256__", source_sha256, 1)
    template = template.replace("__CASE_JSON__", embed_json(cases), 1)
    return template.replace("__RESULT_JSON__", embed_json(runs), 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bfcl-version", choices=("v1", "v4"), default="v1", help="BFCL source version (default: v1)")
    parser.add_argument("--dataset-name", help="Display name in the page title and brand (default: BFCL V1 or BFCL V4)")
    parser.add_argument("--result-prefix", help="Literal result filename prefix (default: bfcl_v1_ or bfcl_v4_)")
    parser.add_argument("--input", type=Path, help="Selected cases JSONL (default: data/bfcl_VERSION/cases.jsonl)")
    parser.add_argument("--output", type=Path, help="Offline HTML output (default: data/bfcl_VERSION/viewer.html)")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR, help="Directory of BFCL result JSONL files")
    args = parser.parse_args()
    args.input = args.input or ROOT / "data" / f"bfcl_{args.bfcl_version}" / "cases.jsonl"
    args.output = args.output or ROOT / "data" / f"bfcl_{args.bfcl_version}" / "viewer.html"
    result_prefix = args.result_prefix if args.result_prefix is not None else f"bfcl_{args.bfcl_version}_"
    try:
        validate_result_prefix(result_prefix)
    except ValueError as exc:
        parser.error(str(exc))
    cases = read_cases(args.input)
    source_sha256 = hashlib.sha256(args.input.read_bytes()).hexdigest()
    runs = read_results(args.results_dir, {case["id"] for case in cases}, source_sha256, result_prefix)
    rendered = render_html(cases, runs, source_sha256, args.bfcl_version, args.dataset_name, result_prefix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} with {len(cases)} cases and {len(runs)} model logs ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
