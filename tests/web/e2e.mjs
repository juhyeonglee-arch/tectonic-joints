// 웹앱 시험: 묶은 사이트를 띄우고 진짜 브라우저(Chromium)로 열어 1대2 시험을 만들어 본다.
// node tests/web/e2e.mjs <사이트폴더> <결과폴더>
import { chromium } from "playwright";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const [site, out] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".wasm": "application/wasm", ".ttf": "font/ttf", ".zip": "application/zip" };
const srv = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  const f = path.join(site, p);
  if (!fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": types[path.extname(f)] || "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
}).listen(8765);

const fail = (m) => { console.error("실패:", m); process.exitCode = 1; };
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
  page.on("console", (m) => console.log("[브라우저]", m.text()));
  page.on("pageerror", (e) => console.log("[페이지 오류]", e.message));
  await page.goto("http://localhost:8765/");
  let t = Date.now();
  await page.waitForFunction(() => ["ready", "error"].includes(document.body.dataset.state), null, { timeout: 300000 });
  console.log(`준비 ${((Date.now() - t) / 1000).toFixed(0)}초`);
  if (await page.evaluate(() => document.body.dataset.state) !== "ready") fail(await page.innerText("#log"));
  else {
    await page.uncheck("input[name=s1]");          // 1대2만 (빠르게)
    t = Date.now();
    await page.click("#go");
    await page.waitForFunction(() => ["done", "error"].includes(document.body.dataset.state), null, { timeout: 900000 });
    console.log(`계산 ${((Date.now() - t) / 1000).toFixed(0)}초`);
    console.log(await page.innerText("#log"));
    if (await page.evaluate(() => document.body.dataset.state) !== "done") fail("계산 실패");
    else {
      const dl = page.waitForEvent("download");
      await page.click("#download");
      await (await dl).saveAs(path.join(out, "웹_결과.zip"));
      const n = await page.locator("#gallery img").count();
      if (n < 4) fail(`그림이 ${n}장뿐`);
      const summary = await page.innerText("#summary");
      console.log(summary);
      if (!summary.includes("1대2 드러냄") || !summary.includes("1대2 숨김")) fail("결과 표에 노드가 없음");
    }
  }
  await page.screenshot({ path: path.join(out, "웹_화면.png"), fullPage: true });
} finally {
  await browser.close();
  srv.close();
}
