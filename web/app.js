/* 화면: 값 받기 → 일꾼(worker.js)에 계산 맡기기 → 결과 보여 주기 */
const $ = (s) => document.querySelector(s);
const log = (m) => { const el = $("#log"); el.textContent += m + "\n"; el.scrollTop = el.scrollHeight; };
const worker = new Worker("worker.js", { type: "module" });
worker.onerror = (e) => {
  log("오류: " + (e.message || "계산 도구를 불러오지 못했어요"));
  $("#status").textContent = "계산 도구를 불러오지 못했어요. 최신 Chrome·Edge·Safari로 열어 주세요.";
  document.body.dataset.state = "error";
};
let zipUrl = null;
const urls = [];

worker.onmessage = (e) => {
  const d = e.data;
  if (d.type === "log") log(d.msg);
  else if (d.type === "ready") {
    $("#go").disabled = false; $("#go").textContent = "만들기";
    $("#status").textContent = "준비됐어요.";
    document.body.dataset.state = "ready";
  } else if (d.type === "done") show(d);
  else if (d.type === "error") {
    log("오류: " + d.msg);
    $("#status").textContent = "오류가 났어요. 아래 기록을 확인해 주세요.";
    $("#go").disabled = false; $("#go").textContent = "다시 만들기";
    document.body.dataset.state = "error";
  }
};
worker.postMessage({ type: "boot" });

$("#form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = new FormData(ev.target);
  const scales = [f.get("s1") && "1", f.get("s2") && "0.5"].filter(Boolean);
  if (!scales.length) { $("#status").textContent = "축척을 하나 이상 골라 주세요."; return; }
  const file = $("input[name=cand]").files[0];
  const params = {
    M3_T: f.get("M3_T"), M3_KERF: f.get("M3_KERF"), M3_CLEAR: f.get("M3_CLEAR"), M3_PIN: f.get("M3_PIN"),
    M3_BED: `${f.get("bed_w")}x${f.get("bed_h")}`, M3_SCALES: scales.join(","),
    candidates: file ? await file.text() : null,
  };
  $("#go").disabled = true; $("#go").textContent = "만드는 중…";
  $("#status").textContent = "계산 중이에요. 이 탭을 닫지 마세요.";
  document.body.dataset.state = "running";
  worker.postMessage({ type: "run", params });
});

function show(d) {
  urls.splice(0).forEach(URL.revokeObjectURL);
  if (zipUrl) URL.revokeObjectURL(zipUrl);
  const r = d.report, g = r["가정"];
  const stamp = new Date().toISOString().slice(0, 10).replaceAll("-", "");
  zipUrl = URL.createObjectURL(new Blob([d.zip], { type: "application/zip" }));
  const a = $("#download");
  a.href = zipUrl;
  a.download = `결구_레이저적층_T${g["판두께"]}_K${g["커프"]}_C${g["맞춤공차"]}_${stamp}.zip`;

  const warn = [];
  const rows = [];
  for (const [name, n] of Object.entries(r["노드"])) {
    const same = JSON.stringify(n["빠짐 판맞춤"]) === JSON.stringify(n["빠짐 원래"]);
    if (!same) warn.push(`<div class="warn bad"><b>${name}</b>: 판 두께에 맞춰 층을 옮겼더니 잠김이 달라졌어요. 설계에서는 빠지지 않던 부재가 빠질 수 있어요. 원래 ${JSON.stringify(n["빠짐 원래"])} → 판맞춤 ${JSON.stringify(n["빠짐 판맞춤"])}. 판 두께를 조금 바꿔 보거나 이 노드는 실물 시험에서 특히 확인해 주세요.</div>`);
    const thin = n["가는 살 경고(3mm 미만, 면적 mm²)"] || [];
    if (thin.length) warn.push(`<div class="warn"><b>${name}</b>: 3mm보다 가는 살이 ${thin.length}곳 있어요. 레이저로 자르면 부러질 수 있어요.</div>`);
    const s = n["판 수"];
    rows.push(`<tr><td>${name}</td><td>${n["작업대 수"]}판</td><td>${s["다리"]} / ${s["장선 X"]} / ${s["장선 Y"]}</td><td>${n["부품 수"]}</td><td>${same ? "그대로" : "<b>달라짐</b>"}</td></tr>`);
  }
  $("#warn").innerHTML = warn.join("");
  $("#summary").innerHTML = `<tr><th>노드</th><th>작업대</th><th>판 장수 (다리/X/Y)</th><th>부품 수</th><th>잠김</th></tr>` + rows.join("");

  const order = (n) => (n.includes("조립순서도") ? 0 : n.includes("배치") ? 1 : 2);
  const imgs = d.images.slice().sort((p, q) => order(p.name) - order(q.name) || p.name.localeCompare(q.name));
  $("#gallery").innerHTML = "";
  for (const im of imgs) {
    const u = URL.createObjectURL(new Blob([im.data], { type: "image/png" }));
    urls.push(u);
    const fig = document.createElement("figure");
    fig.innerHTML = `<a href="${u}" target="_blank"><img src="${u}" alt="${im.name}"></a><figcaption>${im.name}</figcaption>`;
    $("#gallery").append(fig);
  }
  $("#result").classList.remove("hidden");
  $("#status").textContent = `끝났어요 (${d.secs.toFixed(0)}초).`;
  log(`완료: ${d.secs.toFixed(1)}초`);
  $("#go").disabled = false; $("#go").textContent = "다시 만들기";
  document.body.dataset.state = "done";
  $("#result").scrollIntoView({ behavior: "smooth" });
}
