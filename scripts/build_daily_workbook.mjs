import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(process.argv[2] || ".");
const stamp = process.argv[3] || new Date().toISOString().slice(0, 10).replaceAll("-", "");
const outputPath = path.resolve(process.argv[4] || path.join(root, "网爬结果", `家居_${stamp}.xlsx`));
const previewDir = process.argv[5] ? path.resolve(process.argv[5]) : null;

const definitions = [
  ["REAL全量", `ozon_home_trend_analysis_${stamp}_real.csv`, "真实公开商品与估算趋势信号"],
  ["REAL潜力榜", `top20_potential_${stamp}_real.csv`, "真实公开数据的潜力商品 TOP20"],
  ["评论热度预分析", `review_heat_preanalysis_${stamp}_real.csv`, "公开评论总数快照变化形成的估算信号"],
  ["家居类采集诊断", `home_category_diagnostics_${stamp}_real.csv`, "十个家居类目的采样覆盖与偏斜诊断"],
  ["REAL7天榜", `top10_trend_7d_${stamp}_real.csv`, "真实历史不足7天时仅保留表头"],
  ["REAL15天榜", `top10_acceleration_15d_${stamp}_real.csv`, "真实历史不足15天时仅保留表头"],
];

const workbook = Workbook.create();
const summary = workbook.worksheets.add("使用说明");
const imported = [];
for (const [sheetName, fileName, description] of definitions) {
  const filePath = path.join(root, "data", "exports", fileName);
  try {
    const csvText = await fs.readFile(filePath, "utf8");
    const parsed = await Workbook.fromCSV(csvText.replace(/^\uFEFF/, ""), { sheetName });
    const parsedSheet = parsed.worksheets.getItem(sheetName);
    const parsedValues = parsedSheet.getUsedRange(true).values;
    const targetSheet = workbook.worksheets.add(sheetName);
    if (parsedValues.length && parsedValues[0]?.length) {
      targetSheet.getRangeByIndexes(0, 0, parsedValues.length, parsedValues[0].length).values = parsedValues;
    }
    imported.push({ sheetName, fileName, description, values: parsedValues });
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
}

if (!imported.length) throw new Error(`没有找到 ${stamp} 的可合并 CSV`);

const darkBlue = "#17365D";
const mediumBlue = "#2F75B5";
const lightBlue = "#D9EAF7";
const lightGreen = "#E2F0D9";
const lightAmber = "#FFF2CC";
const lightGray = "#F2F2F2";

function excelColumn(index) {
  let value = index + 1;
  let output = "";
  while (value) {
    value -= 1;
    output = String.fromCharCode(65 + (value % 26)) + output;
    value = Math.floor(value / 26);
  }
  return output;
}

function columnFor(item, header) {
  const index = item?.values?.[0]?.findIndex((value) => String(value ?? "") === header) ?? -1;
  return index >= 0 ? excelColumn(index) : null;
}

summary.showGridLines = false;
summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [[`Ozon 家居商品趋势分析｜${stamp}`]];
summary.getRange("A1:H1").format = {
  fill: darkBlue,
  font: { bold: true, color: "#FFFFFF", size: 18 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
summary.getRange("A1:H1").format.rowHeight = 32;
summary.getRange("A3:B3").values = [["核心指标", "数值"]];
summary.getRange("A3:B3").format = { fill: mediumBlue, font: { bold: true, color: "#FFFFFF" } };

const realAll = imported.find((item) => item.sheetName === "REAL全量");
const realPotential = imported.find((item) => item.sheetName === "REAL潜力榜");
const reviewAnalysis = imported.find((item) => item.sheetName === "评论热度预分析");
const categoryDiagnostics = imported.find((item) => item.sheetName === "家居类采集诊断");
const productIdColumn = columnFor(realAll, "商品ID/SKU");
const titleCnColumn = columnFor(realAll, "商品名称_中文名称");
const imageColumn = columnFor(realAll, "商品图片URL");
const originalPriceColumn = columnFor(realAll, "原价（卢布）");
const exchangeRateColumn = columnFor(realAll, "RUB/CNY换算率");
const potentialIdColumn = columnFor(realPotential, "商品ID/SKU");
const reviewIdColumn = columnFor(reviewAnalysis, "商品ID");
const diagnosticValidColumn = columnFor(categoryDiagnostics, "有效商品数");
const summaryRows = [
  ["REAL 商品数", productIdColumn ? `=COUNTA('REAL全量'!$${productIdColumn}$2:$${productIdColumn}$10000)` : "=0"],
  ["潜力商品 TOP20 条数", potentialIdColumn ? `=COUNTA('REAL潜力榜'!$${potentialIdColumn}$2:$${potentialIdColumn}$100)` : "=0"],
  ["已覆盖一级类目", diagnosticValidColumn ? `=COUNTIF('家居类采集诊断'!$${diagnosticValidColumn}$2:$${diagnosticValidColumn}$20,\">0\")` : "=0"],
  ["评论热度分析商品", reviewIdColumn ? `=COUNTA('评论热度预分析'!$${reviewIdColumn}$2:$${reviewIdColumn}$1000)` : "=0"],
  ["可读中文名称条数", titleCnColumn ? `=COUNTA('REAL全量'!$${titleCnColumn}$2:$${titleCnColumn}$10000)` : "=0"],
  ["可用真实图片条数", imageColumn ? `=COUNTIF('REAL全量'!$${imageColumn}$2:$${imageColumn}$10000,"http*")` : "=0"],
  ["可用真实原价条数", originalPriceColumn ? `=COUNT('REAL全量'!$${originalPriceColumn}$2:$${originalPriceColumn}$10000)` : "=0"],
  ["RUB/CNY 换算率", exchangeRateColumn ? `='REAL全量'!${exchangeRateColumn}2` : "=0"],
];
summary.getRange("A4:A11").values = summaryRows.map((row) => [row[0]]);
summary.getRange("B4:B11").formulas = summaryRows.map((row) => [row[1]]);
summary.getRange("A4:A11").format.fill = lightGray;
summary.getRange("A4:A11").format.font = { bold: true, color: darkBlue };
summary.getRange("B4:B10").format.numberFormat = "#,##0";
summary.getRange("B11").format.numberFormat = "0.000000";

summary.getRange("D3:H3").merge();
summary.getRange("D3").values = [["数据口径说明"]];
summary.getRange("D3:H3").format = { fill: mediumBlue, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
summary.getRange("D4:H11").merge();
summary.getRange("D4").values = [[
  "本文件只展示 REAL 公开观察数据；趋势、爆发、潜力、评论热度和人民币金额属于 ESTIMATED 估算结果，不等于真实销量或最终结算价。\n\n潜力 TOP20 优先覆盖不同一级类目，单一类目先限制最多 3 条，再按评分补足，避免高评论家纺挤满榜单。\n\n评论热度使用评论总数公开快照增量、评分和时间衰减；公开源没有单条评论日期，评论增量不代表销量或订单。公开搜索索引摘要可能滞后，未访问 Ozon 详情页复核。\n\n蓝色“点击打开商品”可调用 Windows 默认浏览器。中文名称用于阅读辅助，以俄文原名为核对依据。公开源未提供真实图片时保持空白，不生成或伪造。DEMO 仅用于内部测试，不进入本文件。"
]];
summary.getRange("D4:H11").format = { fill: lightBlue, wrapText: true, verticalAlignment: "top" };
summary.getRange("A4:H11").format.rowHeight = 22;

summary.getRange("A13:C13").values = [["工作表", "内容", "数据性质"]];
summary.getRange("A13:C13").format = { fill: mediumBlue, font: { bold: true, color: "#FFFFFF" } };
const indexRows = imported.map((item) => [item.sheetName, item.description, "REAL / ESTIMATED"]);
summary.getRangeByIndexes(13, 0, indexRows.length, 3).values = indexRows;
summary.getRange(`C14:C${13 + indexRows.length}`).format.fill = lightAmber;
summary.getRange(`A14:C${13 + indexRows.length}`).format.wrapText = true;
summary.getRange(`A14:C${13 + indexRows.length}`).format.rowHeight = 30;

summary.getRange("A22:H22").merge();
summary.getRange("A22").values = [["公开来源与图片说明"]];
summary.getRange("A22:H22").format = { fill: mediumBlue, font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
summary.getRange("A23:H27").values = [
  ["S-SHOT 公开 Ozon 数据集", "https://www.s-shot.ru/datasets/", null, null, null, null, null, null],
  ["公开搜索索引快照", "补充厨房、收纳、装饰、灯具、家具、园艺等类目；索引摘要可能滞后，未访问 Ozon 详情页复核。", null, null, null, null, null, null],
  ["俄罗斯中央银行 CBR 汇率", "https://www.cbr.ru/development/sxml/", null, null, null, null, null, null],
  ["中文名称", "公开翻译接口 + 本地家居词典兜底；用于阅读辅助，以俄文原名为核对依据。", null, null, null, null, null, null],
  ["图片说明", "公开源没有 image_url；Ozon 直连已知 403，程序不重复请求、不绕过反爬，也不以 AI 示意图冒充商品实拍。", null, null, null, null, null, null],
];
summary.getRange("A23:A27").format = { fill: lightGreen, font: { bold: true, color: darkBlue } };
summary.getRange("B23:H27").merge(true);
summary.getRange("B23:H27").format.wrapText = true;
summary.getRange("A1:H27").format.borders = { preset: "outside", style: "thin", color: "#B4C6E7" };
summary.getRange("A:A").format.columnWidth = 24;
summary.getRange("B:B").format.columnWidth = 40;
summary.getRange("C:C").format.columnWidth = 18;
summary.getRange("D:H").format.columnWidth = 15;

for (let sheetIndex = 0; sheetIndex < imported.length; sheetIndex += 1) {
  const item = imported[sheetIndex];
  const sheet = workbook.worksheets.getItem(item.sheetName);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  const used = sheet.getUsedRange(true);
  const values = used.values;
  const rowCount = values.length;
  const columnCount = values[0]?.length || 0;
  if (!columnCount) continue;
  const lastColumn = excelColumn(columnCount - 1);
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: darkBlue,
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D9E2F3" },
  };
  sheet.getRange(`A1:${lastColumn}1`).format.rowHeight = 48;
  if (rowCount > 1) {
    sheet.getRange(`A2:${lastColumn}${rowCount}`).format.borders = {
      insideHorizontal: { style: "thin", color: "#E7E6E6" },
    };
    sheet.getRange(`A2:${lastColumn}${rowCount}`).format.verticalAlignment = "center";
    const table = sheet.tables.add(`A1:${lastColumn}${rowCount}`, true, `Data_${stamp}_${sheetIndex + 1}`);
    table.style = "TableStyleMedium2";
    table.showFilterButton = true;
    if (item.sheetName === "家居类采集诊断") {
      sheet.getRange(`A2:${lastColumn}${rowCount}`).format.rowHeight = 34;
    }
  }
  const headers = values[0].map((value) => String(value ?? ""));
  const productLinkIndex = Math.max(headers.indexOf("Ozon商品链接"), headers.indexOf("商品链接"));
  if (productLinkIndex >= 0 && rowCount > 1) {
    const linkRange = sheet.getRangeByIndexes(1, productLinkIndex, rowCount - 1, 1);
    linkRange.format.font = { color: "#0563C1" };
    linkRange.format.horizontalAlignment = "center";
  }
  for (let col = 0; col < headers.length; col += 1) {
    const header = headers[col];
    const range = sheet.getRange(`${excelColumn(col)}1:${excelColumn(col)}${Math.max(2, rowCount)}`);
    let width = 14;
    if (/商品名称_中文名称/.test(header)) width = 38;
    else if (/商品名称|推荐理由|备注|热门原因|风险提示|异常说明/.test(header)) width = 34;
    else if (/商品图片状态/.test(header)) width = 30;
    else if (/链接|URL|来源页面/.test(header)) width = 28;
    else if (/日期|时间/.test(header)) width = 20;
    else if (/商品ID|SKU/.test(header)) width = 16;
    else if (/搜索关键词|搜索来源|分类|品牌|卖家/.test(header)) width = 18;
    range.format.columnWidth = width;
    if (/商品名称|推荐理由|备注|链接|URL|来源页面|搜索关键词/.test(header)) range.format.wrapText = true;
    if (/价格|汇率|指数|评分|变化|速度|加速度|频率|一致性|可信度分|折扣率/.test(header) && rowCount > 1) {
      sheet.getRange(`${excelColumn(col)}2:${excelColumn(col)}${rowCount}`).format.numberFormat = /汇率/.test(header) ? "0.000000" : "#,##0.00";
    }
    if (/评论数|关键词覆盖数|榜单排名|当前公开列表排名|当前排名/.test(header) && rowCount > 1) {
      sheet.getRange(`${excelColumn(col)}2:${excelColumn(col)}${rowCount}`).format.numberFormat = "#,##0";
    }
    if (/爆品趋势指数|爆发指数|潜力指数|搜索曝光代理指数|评论热度评分|综合分析评分/.test(header) && rowCount > 1) {
      sheet.getRange(`${excelColumn(col)}2:${excelColumn(col)}${rowCount}`).conditionalFormats.add("colorScale", {
        colors: ["#F8696B", "#FFEB84", "#63BE7B"],
        thresholds: ["min", "50%", "max"],
      });
    }
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

if (previewDir) {
  await fs.mkdir(previewDir, { recursive: true });
  for (const name of ["使用说明", ...imported.map((item) => item.sheetName)]) {
    const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
    await fs.writeFile(path.join(previewDir, `${name}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
}

const overview = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 4000 });
const keyValues = await workbook.inspect({ kind: "table", sheetId: "使用说明", range: "A1:H27", include: "values,formulas", tableMaxRows: 27, tableMaxCols: 8, maxChars: 8000 });
const linkColumn = columnFor(realAll, "Ozon商品链接");
const linkCheck = linkColumn ? await workbook.inspect({ kind: "table", sheetId: "REAL全量", range: `${linkColumn}1:${linkColumn}6`, include: "values", tableMaxRows: 6, tableMaxCols: 1, maxChars: 4000 }) : { ndjson: "链接列不存在" };
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "公式错误检查" });
console.log(JSON.stringify({ outputPath, stamp, sheets: imported.map((item) => item.sheetName), overview: overview.ndjson, keyValues: keyValues.ndjson, linkCheck: linkCheck.ndjson, formulaErrors: errors.ndjson }));
