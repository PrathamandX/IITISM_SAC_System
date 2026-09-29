// Role-based dashboard. Every screen is described in PANELS and rendered by the generic code below.
const token = sessionStorage.getItem("token");
if (!token) location.href = "/";

let ME = null;
let HOSTELS = [];
let refreshers = []; // re-runs the listing forms of the open panel after a change
const thisMonth = new Date().toISOString().slice(0, 7);
const thisYear = String(new Date().getFullYear());

const ALL = ["chairman", "controlling_warden", "warden", "clerk", "mess_manager", "student"];
const STAFF = ["chairman", "controlling_warden", "warden", "clerk", "mess_manager"];

// Field syntax: "name[?]:type[:default]"  (? = optional). Defaults: @me, @hostel, @month, @year.
const PANELS = [
  { title: "Users", roles: ["chairman"], forms: [
    { label: "Create staff account", method: "POST", url: "/api/users",
      fields: ["username", "full_name", "password:password",
               "role:select=warden|clerk|mess_manager|controlling_warden|chairman", "hostel_id?:hostel"] },
    { label: "All accounts", method: "GET", url: "/api/users", auto: true,
      actions: (r) => r.is_active ? [["Deactivate", () => api("PATCH", `/api/users/${r.id}/deactivate`)]] : [] },
  ]},
  { title: "Hostels & rooms", roles: ["chairman", "controlling_warden", "warden", "clerk"], forms: [
    { label: "Add hostel", roles: ["chairman"], method: "POST", url: "/api/hostels", fields: ["name", "amenity_charge:number"] },
    { label: "Add room", roles: ["chairman"], method: "POST", url: "/api/hostels/{hostel_id}/rooms",
      fields: ["hostel_id:hostel", "room_no", "rent:number"] },
    { label: "List rooms", method: "GET", url: "/api/hostels/{hostel_id}/rooms",
      fields: ["hostel_id:hostel:@hostel", "vacant_only?:checkbox"] },
  ]},
  { title: "Admit student", roles: ["clerk", "chairman"], forms: [
    { label: "Register student & allot room", method: "POST", url: "/api/students",
      fields: ["roll_no", "name", "address:textarea", "phone", "admission_note_ref", "hostel_id:hostel:@hostel",
               "room_id?:number", "password:password"],
      after: (s) => letter(s.roll_no) },
    { label: "Upload photograph", method: "POST", url: "/api/students/{roll_no}/photo", fields: ["roll_no", "photo:file"] },
  ]},
  { title: "Students", roles: STAFF, forms: [
    { label: "Students", method: "GET", url: "/api/students", auto: true, fields: ["hostel_id?:hostel:@hostel"],
      actions: (r) => [["Allotment letter", () => letter(r.roll_no)]] },
  ]},
  { title: "My profile", roles: ["student"], forms: [
    { label: "Profile", method: "GET", url: "/api/students/me", auto: true },
    { label: "Allotment letter", method: "GET", url: "/api/students/{roll_no}/allotment-letter", fields: ["roll_no:text:@me"] },
    { label: "Upload photograph", method: "POST", url: "/api/students/{roll_no}/photo", fields: ["roll_no:text:@me", "photo:file"] },
  ]},
  { title: "Mess charges", roles: ["mess_manager", "clerk", "warden", "chairman"], forms: [
    { label: "Enter monthly mess charge", roles: ["mess_manager"], method: "POST", url: "/api/mess-charges",
      fields: ["roll_no", "month:month:@month", "amount:number"] },
    { label: "Mess charges for month", method: "GET", url: "/api/mess-charges", fields: ["month:month:@month"] },
  ]},
  { title: "Dues & payment", roles: ["student", "clerk", "warden", "chairman"], forms: [
    { label: "View total dues", method: "GET", url: "/api/dues", fields: ["roll_no:text:@me", "month:month:@month"] },
    { label: "Pay dues", roles: ["student", "clerk"], method: "POST", url: "/api/payments",
      fields: ["roll_no:text:@me", "month:month:@month"] },
  ]},
  { title: "Payments", roles: ALL.filter((r) => r !== "mess_manager"), forms: [
    { label: "Payments received", method: "GET", url: "/api/payments", auto: true, fields: ["month?:month"] },
  ]},
  { title: "Mess manager sheet", roles: ["chairman", "clerk"], forms: [
    { label: "Amount due to each mess manager (print & sign)", method: "GET", url: "/api/mess-sheet",
      fields: ["month:month:@month"], sign: true,
      actions: (r, v) => ME.role === "chairman" && !r.cheque_no
        ? [["Issue cheque", () => api("POST", "/api/mess-sheet/cheques", { hostel_id: r.hostel_id, month: v.month })]] : [] },
    { label: "Issued cheques", method: "GET", url: "/api/mess-sheet/cheques", fields: ["month:month:@month"],
      actions: (r) => ME.role === "chairman" && !r.signed
        ? [["Mark signed", () => api("POST", `/api/mess-sheet/cheques/${r.id}/sign`)]] : [] },
  ]},
  { title: "Complaints", roles: ALL.filter((r) => r !== "mess_manager"), forms: [
    { label: "Raise complaint", roles: ["student"], method: "POST", url: "/api/complaints",
      fields: ["type:select=repair|behavior", "repair_type?:text", "against?:text", "description:textarea"] },
    { label: "Complaints", method: "GET", url: "/api/complaints", auto: true, fields: ["status?:select=|open|resolved"],
      actions: (r) => ME.role === "warden" ? [["Post ATR", () => {
        const atr = prompt("Action Taken Report:", r.atr || "");
        return atr && api("POST", `/api/complaints/${r.id}/atr`, { atr, resolve: confirm("Mark as resolved?") });
      }]] : [] },
  ]},
  { title: "Hostel staff", roles: ["clerk", "warden", "chairman"], forms: [
    { label: "Recruit staff", method: "POST", url: "/api/staff",
      fields: ["hostel_id:hostel:@hostel", "name", "address", "phone", "role:select=attendant|gardener", "daily_pay:number"] },
    { label: "Staff list", method: "GET", url: "/api/staff", auto: true, fields: ["hostel_id:hostel:@hostel"],
      actions: (r) => [["Remove (left)", () => confirm(`Remove ${r.name}?`) && api("DELETE", `/api/staff/${r.id}`)]] },
  ]},
  { title: "Leave & salary", roles: ["clerk", "warden", "chairman"], forms: [
    { label: "Enter leave", roles: ["clerk", "chairman"], method: "POST", url: "/api/leaves",
      fields: ["staff_id:number", "start_date:date", "end_date:date"] },
    { label: "Generate salary list & cheques", roles: ["clerk", "chairman"], method: "POST", url: "/api/salaries/generate",
      fields: ["hostel_id:hostel:@hostel", "month:month:@month"], sign: true },
    { label: "Salary list", method: "GET", url: "/api/salaries", fields: ["hostel_id:hostel:@hostel", "month:month:@month"], sign: true },
  ]},
  { title: "Grants", roles: ["chairman", "warden"], forms: [
    { label: "Record annual grant", roles: ["chairman"], method: "POST", url: "/api/grants", fields: ["year:number:@year", "amount:number"] },
    { label: "Distribute grant to hall", roles: ["chairman"], method: "POST", url: "/api/grants/allocations",
      fields: ["year:number:@year", "hostel_id:hostel", "amount:number"] },
    { label: "Allocations", method: "GET", url: "/api/grants/allocations", fields: ["year:number:@year"] },
  ]},
  { title: "Hall expenditure", roles: ["warden", "chairman"], forms: [
    { label: "Enter expenditure", roles: ["warden"], method: "POST", url: "/api/expenditures",
      fields: ["hostel_id:hostel:@hostel", "year:number:@year", "category:select=upkeep|garden|repairs|other",
               "description", "amount:number", "spent_on?:date"] },
    { label: "Expenditure", method: "GET", url: "/api/expenditures", fields: ["year:number:@year"] },
  ]},
  { title: "Petty expenses", roles: ["chairman", "clerk"], forms: [
    { label: "Enter petty expense", method: "POST", url: "/api/petty-expenses",
      fields: ["description", "amount:number", "spent_on?:date"] },
    { label: "Petty expenses", method: "GET", url: "/api/petty-expenses", auto: true },
  ]},
  { title: "Occupancy", roles: ["controlling_warden", "chairman", "warden", "clerk"], forms: [
    { label: "Overall room occupancy", roles: ["controlling_warden", "chairman"], method: "GET", url: "/api/occupancy", auto: true },
    { label: "Hostel occupancy", roles: ["warden", "clerk"], method: "GET", url: "/api/hostels/{hostel_id}/occupancy",
      auto: true, fields: ["hostel_id:hostel:@hostel"] },
  ]},
  { title: "Statement of accounts", roles: ["warden", "chairman", "controlling_warden"], forms: [
    { label: "Annual consolidated statement", method: "GET", url: "/api/statement",
      fields: ["year:number:@year", "hostel_id?:hostel:@hostel"], sign: true },
  ]},
  { title: "Change password", roles: ALL, forms: [
    { label: "Change password", method: "POST", url: "/api/auth/change-password",
      fields: ["old_password:password", "new_password:password"] },
  ]},
];

// ---------- API ----------
async function api(method, url, body, isForm) {
  const opts = { method, headers: { Authorization: `Bearer ${token}` } };
  if (body && isForm) opts.body = body;
  else if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(url, opts);
  if (res.status === 401) { sessionStorage.clear(); location.href = "/"; return; }
  const data = res.status === 204 ? null : await res.json();
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(Array.isArray(d) ? d.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join("; ") : d || res.statusText);
  }
  return data;
}

// ---------- rendering ----------
const esc = (v) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const nice = (k) => k.replace(/_/g, " ");
const hostelName = (id) => (HOSTELS.find((h) => h.id === id) || {}).name || id;

function cell(k, v) {
  if (k === "photo_path" && v) return `<img src="${esc(v)}" alt="photo" height="48">`;
  if (k === "hostel_id") return esc(hostelName(v));
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (v && typeof v === "object") return esc(JSON.stringify(v));
  return esc(v);
}

function table(rows, form, values) {
  if (!rows.length) return "<p>No records.</p>";
  const keys = Object.keys(rows[0]);
  const hasActions = form.actions && rows.some((r) => form.actions(r, values).length);
  let html = "<table><tr>" + keys.map((k) => `<th>${nice(k)}</th>`).join("");
  if (form.sign) html += '<th class="sign-col">Signature</th>';
  if (hasActions) html += '<th class="no-print">Actions</th>';
  html += "</tr>";
  rows.forEach((r, i) => {
    html += "<tr>" + keys.map((k) => `<td>${cell(k, r[k])}</td>`).join("");
    if (form.sign) html += "<td></td>";
    if (hasActions) html += `<td class="no-print">${form.actions(r, values)
      .map(([label], j) => `<button class="small" data-row="${i}" data-act="${j}">${esc(label)}</button>`).join("")}</td>`;
    html += "</tr>";
  });
  return html + "</table>";
}

function render(data, form, values) {
  if (data === null || data === undefined) return '<p class="ok">Done.</p>';
  if (Array.isArray(data)) return table(data, form, values);
  let scalars = "", nested = "";
  for (const [k, v] of Object.entries(data)) {
    if (Array.isArray(v)) nested += `<h4>${nice(k)}</h4>` + table(v, { sign: false }, values);
    else scalars += `<dt>${nice(k)}</dt><dd>${cell(k, v)}</dd>`;
  }
  return `<dl>${scalars}</dl>${nested}${form.sign ? "<p><br>Signature: ____________________</p>" : ""}`;
}

// ---------- forms ----------
function parseField(spec) {
  const [rawName, type = "text", def = ""] = spec.split(":");
  const optional = rawName.endsWith("?");
  return { name: rawName.replace("?", ""), type, def, optional };
}

function defaultValue(def) {
  return { "@me": ME.role === "student" ? ME.username : "", "@hostel": ME.hostel_id || "",
           "@month": thisMonth, "@year": thisYear }[def] ?? def;
}

function fieldHtml(f) {
  const val = esc(defaultValue(f.def));
  const req = f.optional ? "" : "required";
  let input;
  if (f.type.startsWith("select=")) {
    input = `<select name="${f.name}" ${req}>${f.type.slice(7).split("|")
      .map((o) => `<option value="${o}">${o ? nice(o) : "(any)"}</option>`).join("")}</select>`;
  } else if (f.type === "hostel") {
    const locked = ME.hostel_id && ME.role !== "chairman" && f.def === "@hostel" ? "disabled" : "";
    input = `<select name="${f.name}" ${req} ${locked}>${f.optional ? '<option value="">(all)</option>' : ""}${HOSTELS
      .map((h) => `<option value="${h.id}" ${String(h.id) === String(val) ? "selected" : ""}>${esc(h.name)}</option>`)
      .join("")}</select>`;
  } else if (f.type === "textarea") {
    input = `<textarea name="${f.name}" rows="3" ${req}>${val}</textarea>`;
  } else if (f.type === "checkbox") {
    return `<label><input type="checkbox" name="${f.name}"> ${nice(f.name)}</label>`;
  } else {
    const step = f.type === "number" ? 'step="any" min="0"' : "";
    const readonly = f.def === "@me" && ME.role === "student" ? "readonly" : "";
    input = `<input name="${f.name}" type="${f.type}" value="${val}" ${step} ${req} ${readonly}>`;
  }
  return `<label>${nice(f.name)}${f.optional ? " (optional)" : ""} ${input}</label>`;
}

function collect(formEl, fields) {
  const values = {};
  for (const f of fields) {
    const el = formEl.elements[f.name];
    if (f.type === "checkbox") values[f.name] = el.checked;
    else if (f.type === "file") values[f.name] = el.files[0];
    else if (el.value !== "") values[f.name] = f.type === "number" || f.type === "hostel" ? Number(el.value) : el.value;
  }
  return values;
}

async function submit(form, formEl, out) {
  const fields = (form.fields || []).map(parseField);
  const values = collect(formEl, fields);
  const body = { ...values };
  const url = form.url.replace(/\{(\w+)\}/g, (_, k) => { const v = body[k]; delete body[k]; return encodeURIComponent(v); });
  out.innerHTML = "Loading...";
  try {
    let data;
    if (form.method === "GET") {
      const qs = new URLSearchParams(Object.entries(body).filter(([, v]) => v !== false));
      data = await api("GET", qs.toString() ? `${url}?${qs}` : url);
    } else if (fields.some((f) => f.type === "file")) {
      const fd = new FormData();
      Object.entries(body).forEach(([k, v]) => fd.append(k, v));
      data = await api(form.method, url, fd, true);
    } else {
      data = await api(form.method, url, body);
    }
    out.innerHTML = render(data, form, values) + '<button class="small no-print" data-print>Print</button>';
    out.querySelector("[data-print]").onclick = () => window.print();
    out.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.onclick = async () => {
        const [, run] = form.actions(data[btn.dataset.row], values)[btn.dataset.act];
        try { const r = await run(); if (r !== undefined && r !== false) submit(form, formEl, out); }
        catch (e) { alert(e.message); }
      };
    });
    if (form.method !== "GET") refreshers.forEach((r) => r());
    if (form.after && data) form.after(data);
  } catch (e) {
    out.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

function showPanel(panel, btn) {
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b === btn));
  const root = document.getElementById("panel");
  root.innerHTML = `<h2>${esc(panel.title)}</h2>`;
  refreshers = [];
  panel.forms.filter((f) => !f.roles || f.roles.includes(ME.role)).forEach((form) => {
    const fields = (form.fields || []).map(parseField);
    const formEl = document.createElement("form");
    formEl.innerHTML = `<h3>${esc(form.label)}</h3>${fields.map(fieldHtml).join("")}
      <button type="submit">${form.method === "GET" ? "Show" : "Submit"}</button>`;
    const out = document.createElement("div");
    out.className = "result";
    formEl.onsubmit = (e) => { e.preventDefault(); submit(form, formEl, out); };
    root.append(formEl, out);
    if (form.auto) {
      submit(form, formEl, out);
      refreshers.push(() => submit(form, formEl, out));
    }
  });
}

async function letter(rollNo) {
  const root = document.getElementById("panel");
  try {
    const l = await api("GET", `/api/students/${encodeURIComponent(rollNo)}/allotment-letter`);
    root.innerHTML = `<h2>Room allotment letter</h2>
      <p>No. ${esc(l.letter_no)} &nbsp; Date: ${esc(l.issued_on)}</p>
      <p>To,<br>${esc(l.name)} (Roll no. ${esc(l.roll_no)})<br>${esc(l.address)}</p>
      <p>You are hereby allotted <b>Room ${esc(l.room_no)}</b> in <b>${esc(l.hostel)}</b>.
      Monthly room rent: ${l.monthly_rent}; monthly amenity charge: ${l.monthly_amenity_charge}.
      Mess charges are billed monthly as per actuals.</p>
      <p><br>Signature: ____________________<br>Students' Activity Center, IIT (ISM)</p>
      <button class="no-print" onclick="window.print()">Print</button>`;
  } catch (e) { alert(e.message); }
}

// ---------- boot ----------
(async () => {
  ME = await api("GET", "/api/auth/me");
  HOSTELS = await api("GET", "/api/hostels");
  document.getElementById("who").textContent = `${ME.full_name} (${nice(ME.role)})`;
  document.getElementById("logout").onclick = () => { sessionStorage.clear(); location.href = "/"; };
  const menu = document.getElementById("menu");
  PANELS.filter((p) => p.roles.includes(ME.role)).forEach((p) => {
    const btn = document.createElement("button");
    btn.textContent = p.title;
    btn.onclick = () => showPanel(p, btn);
    menu.append(btn);
  });
})();
