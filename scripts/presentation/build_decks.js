// Builds the MTP presentations in the style of the department's sample deck:
// navy title block on the first slide, navy title bar on the others, plain
// bullets, ruled tables and "n / N" slide numbers.
//
//   npm install pptxgenjs                     (once)
//   node scripts/presentation/build_decks.js  (writes both decks)
//
// Output:
//   MTP 1/presentation/mtp1_presentation.pptx   survey, gaps, objectives, dataset, plan
//   MTP 2/presentation/mtp2_presentation.pptx   the same plus methodology and results
//
// The figures in images/ come from make_slide_figures.py and diagrams/*.tex.

const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const ROOT = path.join(HERE, "..", "..");
const IMG = (name) => path.join(HERE, "images", name + ".png");

const THEME = {
  name: "MTP navy",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "000000", lt1: "FFFFFF", dk2: "0D264C", lt2: "E8EBF0",
    accent1: "2B6CA3", accent2: "B5412F", accent3: "3C8D5A", accent4: "D98B2B",
    accent5: "9AA0A6", accent6: "5B6B8C", hlink: "0D264C", folHlink: "5B6B8C",
  },
};
const BAND_H = 0.68;

// ------------------------------------------------------------------ references
const REFS = {
  cabral: ["George G. Cabral et al.", "Class Imbalance Evolution and Verification Latency in Just-in-Time Software Defect Prediction", "Proceedings of the 41st International Conference on Software Engineering (ICSE). 2019, pp. 666-676."],
  dacosta: ["Daniel Alencar da Costa et al.", "A Framework for Evaluating the Results of the SZZ Approach for Identifying Bug-Introducing Changes", "IEEE Transactions on Software Engineering 43.7 (2017), pp. 641-657."],
  falessi: ["Davide Falessi et al.", "On the Need of Preserving Order of Data When Validating Within-Project Defect Classifiers", "Empirical Software Engineering 25 (2020), pp. 4805-4830."],
  fan: ["Yuanrui Fan et al.", "The Impact of Changes Mislabeled by SZZ on Just-in-Time Defect Prediction", "IEEE Transactions on Software Engineering 47.8 (2021), pp. 1559-1586."],
  herbold: ["Steffen Herbold et al.", "A Fine-grained Data Set and Analysis of Tangling in Bug Fixing Commits", "Empirical Software Engineering 27.6 (2022), p. 125."],
  kamei: ["Yasutaka Kamei et al.", "A Large-Scale Empirical Study of Just-in-Time Quality Assurance", "IEEE Transactions on Software Engineering 39.6 (2013), pp. 757-773."],
  mcintosh: ["Shane McIntosh and Yasutaka Kamei.", "Are Fix-Inducing Changes a Moving Target? A Longitudinal Case Study of Just-in-Time Defect Prediction", "IEEE Transactions on Software Engineering 44.5 (2018), pp. 412-428."],
  ni: ["Chao Ni et al.", "The Best of Both Worlds: Integrating Semantic Features with Expert Features for Defect Prediction and Localization", "Proceedings of the 30th ACM Joint European Software Engineering Conference and Symposium on the Foundations of Software Engineering (ESEC/FSE). 2022, pp. 672-683."],
  pornprasit: ["Chanathip Pornprasit and Chakkrit Tantithamthavorn.", "JITLine: A Simpler, Better, Faster, Finer-grained Just-In-Time Defect Prediction", "Proceedings of the 18th International Conference on Mining Software Repositories (MSR). 2021, pp. 369-379."],
  rosa: ["Giovanni Rosa et al.", "Evaluating SZZ Implementations Through a Developer-Informed Oracle", "Proceedings of the 43rd International Conference on Software Engineering (ICSE). 2021."],
  sliwerski: ["Jacek Śliwerski, Thomas Zimmermann, and Andreas Zeller.", "When Do Changes Induce Fixes?", "Proceedings of the International Workshop on Mining Software Repositories (MSR). 2005, pp. 1-5."],
  zeng: ["Zhengran Zeng et al.", "Deep Just-in-Time Defect Prediction: How Far Are We?", "Proceedings of the 30th ACM SIGSOFT International Symposium on Software Testing and Analysis (ISSTA). 2021."],
};

// ------------------------------------------------------------------ after writing
// Two things pptxgenjs does not do by itself are fixed after the file is
// written: (1) it repeats the paragraph properties for every text run, and
// only the first one in a paragraph is valid; (2) it always writes the
// default Office colour scheme, so the theme colours are put in here.
const finishFile = async (file) => {
  const JSZip = require(require.resolve("jszip", { paths: [require.resolve("pptxgenjs")] }));
  const zip = await JSZip.loadAsync(fs.readFileSync(file));

  const names = Object.keys(zip.files).filter((n) => /^ppt\/(slides|slideLayouts|slideMasters)\/[^/]+\.xml$/.test(n));
  for (const name of names) {
    const xml = await zip.file(name).async("string");
    const fixed = xml.replace(/<a:p>[\s\S]*?<\/a:p>/g, (para) => {
      let seen = false;
      return para.replace(/<a:pPr\b[^>]*?(?:\/>|>[\s\S]*?<\/a:pPr>)/g, (m) => {
        if (seen) return "";
        seen = true;
        return m;
      });
    });
    if (fixed !== xml) zip.file(name, fixed);
  }

  const slots = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];
  const scheme = `<a:clrScheme name="${THEME.name}">` + slots.map((k) => `<a:${k}><a:srgbClr val="${THEME.colors[k]}"/></a:${k}>`).join("") + "</a:clrScheme>";
  const part = "ppt/theme/theme1.xml";
  const theme = (await zip.file(part).async("string"))
    .replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/, () => scheme)
    .replace(/(<a:(?:theme|fontScheme)\b[^>]*?\bname=")[^"]*"/g, (_, head) => `${head}${THEME.name}"`);
  zip.file(part, theme);

  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
};

const TITLE = "Label Noise in Just-In-Time Software Defect Prediction";

// ------------------------------------------------------------------ one deck
// stage: 1 for the MTP I deck, 2 for the MTP II deck
// total: number of slides, shown as "n / total" (checked at the end)
// refKeys: references of the deck in alphabetical order
const buildDeck = async ({ stage, total, refKeys, out }) => {
  const full = stage === 2; // the MTP II deck also has results; the MTP I deck gives the methodology as proposed work
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.author = "Puneet Deshwani";
  pres.title = TITLE;
  const C = pres.SchemeColor;

  const used = new Set();
  const c = (key) => {
    const n = refKeys.indexOf(key) + 1;
    if (n === 0) throw new Error("reference not listed for this deck: " + key);
    used.add(key);
    return "[" + n + "]";
  };

  // ---------------------------------------------------------------- layouts
  const pageNumber = () => ({ x: 8.75, y: 5.3, w: 0.62, h: 0.22, fontSize: 8, color: C.text1, align: "right", margin: 0 });
  const pageTotal = () => ({
    text: {
      text: "/ " + total,
      options: { x: 9.4, y: 5.3, w: 0.45, h: 0.22, fontSize: 8, color: C.text1, align: "left", valign: "top", margin: 0 },
    },
  });
  const titleBar = () => [
    { rect: { x: 0, y: 0, w: 10, h: BAND_H, fill: { color: C.text2 } } },
    {
      placeholder: {
        options: { name: "title", type: "title", x: 0.2, y: 0, w: 9.6, h: BAND_H, fontSize: 24, color: C.background1, align: "left", valign: "middle", margin: 0 },
        text: "",
      },
    },
  ];

  pres.defineSlideMaster({
    title: "TITLE_SLIDE",
    objects: [
      {
        placeholder: {
          options: { name: "title", type: "title", x: 0.3, y: 0.62, w: 9.4, h: 1.1, fontSize: 26, color: C.background1, align: "center", valign: "middle", margin: 0 },
          text: "",
        },
      },
      pageTotal(),
    ],
    slideNumber: pageNumber(),
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    objects: [
      ...titleBar(),
      {
        placeholder: {
          options: { name: "body", type: "body", x: 0.45, y: 0.85, w: 9.1, h: 4.3, fontSize: 17, color: C.text1, valign: "middle" },
          text: "",
        },
      },
      pageTotal(),
    ],
    slideNumber: pageNumber(),
  });
  pres.defineSlideMaster({
    title: "TITLE_ONLY",
    objects: [...titleBar(), pageTotal()],
    slideNumber: pageNumber(),
  });

  // ---------------------------------------------------------------- helpers
  let section = "";
  let slideCount = 0;
  const startSection = (title) => { section = title; pres.addSection({ title }); };
  const newSlide = (masterName, title) => {
    const s = pres.addSlide({ masterName, sectionTitle: section });
    slideCount += 1;
    if (title) s.addText(title, { placeholder: "title" });
    return s;
  };

  // plain bullets; an item may be a string or an array of runs [{text, bold}]
  const bulletRuns = (items, opts = {}) => {
    const runs = [];
    items.forEach((item, i) => {
      const parts = Array.isArray(item) ? item : [{ text: item }];
      parts.forEach((p, j) => {
        const o = { bold: !!p.bold };
        // the bullet goes on the first run only: a run with a bullet starts a new paragraph
        if (j === 0) o.bullet = opts.numbered ? { type: "number" } : { indent: 14 };
        o.paraSpaceAfter = opts.gap === undefined ? 6 : opts.gap;
        if (j === parts.length - 1 && i < items.length - 1) o.breakLine = true;
        runs.push({ text: p.text, options: o });
      });
    });
    return runs;
  };
  const bulletSlide = (title, items, opts = {}) => {
    const s = newSlide("CONTENT", title);
    s.addText(bulletRuns(items, opts), { placeholder: "body", ...(opts.fontSize ? { fontSize: opts.fontSize } : {}) });
    return s;
  };
  const bulletBox = (s, items, box, fontSize = 15, name = "Bullets") => {
    s.addText(bulletRuns(items), { ...box, fontSize, color: C.text1, valign: "middle", isTextBox: true, objectName: name });
  };

  let figureNo = 0;
  const caption = (s, text, x, y, w) => {
    figureNo += 1;
    s.addText(
      [{ text: "Figure " + figureNo + ": ", options: { color: C.text2 } }, { text }],
      { x, y, w, h: 0.42, fontSize: 11.5, color: C.text1, align: "center", valign: "top", isTextBox: true, margin: 0, objectName: "Caption " + figureNo }
    );
  };
  const figure = (s, name, x, y, w, ratio, text, capW) => {
    const h = w / ratio;
    s.addImage({ path: IMG(name), x, y, w, h, objectName: "Figure " + (figureNo + 1) });
    const cw = capW || w;
    caption(s, text, x + (w - cw) / 2, y + h + 0.05, cw);
  };

  // ruled table in the style of the sample (no vertical lines)
  const ruledTable = (s, header, rows, colW, x, y, fontSize, aligns) => {
    const none = { type: "none" };
    const thick = { type: "solid", pt: 1.25, color: "000000" };
    const thin = { type: "solid", pt: 0.5, color: "000000" };
    const cell = (text, o, col) => ({
      text,
      options: { fontSize, color: C.text1, valign: "middle", align: (aligns && aligns[col]) || "left", margin: [3, 5, 3, 5], ...o },
    });
    const data = [header.map((h, i) => cell(h, { bold: true, border: [thick, none, thin, none] }, i))];
    rows.forEach((r, i) => {
      const last = i === rows.length - 1;
      data.push(r.map((t, j) => cell(t, { border: [none, none, last ? thick : thin, none] }, j)));
    });
    s.addTable(data, { x, y, w: colW.reduce((a, b) => a + b, 0), colW, objectName: "Table" });
  };

  // ================================================================ title
  startSection("Title");
  {
    const s = newSlide("TITLE_SLIDE", null);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.16, y: 0.62, w: 9.68, h: 1.1, rectRadius: 0.07, fill: { color: C.text2 }, line: { color: C.text2, width: 0.5 },
      shadow: { type: "outer", color: "000000", blur: 5, offset: 2.5, angle: 45, opacity: 0.4 }, objectName: "Title block",
    });
    s.addText(TITLE, { placeholder: "title" });
    const line = (text, y, fontSize, h = 0.35) =>
      s.addText(text, { x: 0.5, y, w: 9.0, h, fontSize, color: C.text1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    line("Puneet Deshwani", 2.22, 19, 0.42);
    line("2025MCS013", 2.72, 14);
    line("Under the supervision of Dr. Santosh Singh Rathore", 3.2, 14);
    line("Department of Computer Science and Engineering", 3.72, 12, 0.28);
    line("Atal Bihari Vajpayee Indian Institute of Information Technology and Management, Gwalior", 3.98, 12, 0.28);
    line("October 2026", 4.58, 12, 0.28);
  }

  // ================================================================ contents
  {
    const items = full
      ? ["Overview", "Motivation", "Related Works", "Research Gaps", "Objectives and Research Questions", "Dataset", "Methodology", "Results", "Conclusion and Future Work", "Timeline", "References"]
      : ["Overview", "Motivation", "Related Works", "Research Gaps", "Objectives and Research Questions", "Dataset", "Proposed Methodology", "References"];
    const s = newSlide("CONTENT", "Contents");
    s.addText(bulletRuns(items, { numbered: true, gap: full ? 4 : 6 }), { placeholder: "body", fontSize: full ? 16 : 17 });
  }

  // ================================================================ overview
  startSection("Overview and motivation");
  bulletSlide("Overview", [
    `Just-in-time software defect prediction (JIT-SDP) predicts, at commit time, whether a code change is likely to introduce a defect, so that review and testing effort can be directed to risky changes ${c("kamei")}.`,
    "The models are trained on past commits. Each commit is described by change metrics and is labelled as clean or defect-introducing.",
    `These labels are not recorded in the repository. They are inferred by the SZZ algorithm, which traces the lines changed in a bug-fixing commit back to the commits that last modified them ${c("sliwerski")}.`,
    `Bug-fixing commits often contain unrelated changes (tangled commits), so SZZ produces wrong labels. Only 17% to 32% of the changed lines in bug-fixing commits contribute to the fix ${c("herbold")}.`,
  ], { fontSize: 16 });

  {
    const s = newSlide("TITLE_ONLY", "Overview");
    figure(s, "workflow", 0.3, 1.45, 4.45, 1.991, "Workflow of JIT-SDP");
    figure(s, "szz_example", 5.0, 1.42, 4.7, 2.058, "Labelling with SZZ and a wrong label caused by an unrelated change");
  }

  bulletSlide("Motivation", [
    "JIT-SDP models are trained and tested on the same SZZ labels. A model is then rewarded for reproducing the errors of SZZ, and the effect of label noise on the reported performance is not visible.",
    `Random k-fold cross-validation is still widely used, although it trains the model on commits that are newer than the test commits ${c("falessi")}.`,
    full
      ? `In practice the label of a commit arrives late (verification latency). In our data the median delay is 113 days, and 53% of the defect labels arrive after 90 days ${c("cabral")}.`
      : `In practice the label of a commit arrives late (verification latency): a defect is recognised only when it is fixed, which can take months or years ${c("cabral")}.`,
    "It is therefore not known how much SZZ label noise costs a model that is evaluated in a realistic setting.",
  ], { fontSize: 16 });

  // ================================================================ related works
  startSection("Related works");
  {
    const s = newSlide("TITLE_ONLY", "Related Works - 1");
    ruledTable(s, ["Title", "Author", "Dataset", "Key Takeaways"], [
      [`When Do Changes Induce Fixes? (2005) ${c("sliwerski")}`, "Jacek Śliwerski", "Mozilla and Eclipse", "Proposes the SZZ algorithm: lines changed by a bug fix are traced back with annotate (blame) to find the bug-introducing changes"],
      [`A Framework for Evaluating the Results of the SZZ Approach for Identifying Bug-Introducing Changes (2017) ${c("dacosta")}`, "Daniel A. da Costa", "Ten open-source projects", "Criteria for evaluating SZZ implementations; proposes MA-SZZ, which ignores meta-changes"],
      [`Evaluating SZZ Implementations Through a Developer-Informed Oracle (2021) ${c("rosa")}`, "Giovanni Rosa", "1,930 bug-fixing commits in which the developer names the introducing commit", "Compares SZZ variants against the oracle; R-SZZ performs best (precision about 66%); releases PySZZ"],
      [`A Fine-grained Data Set and Analysis of Tangling in Bug Fixing Commits (2022) ${c("herbold")}`, "Steffen Herbold", "LLTC4J: manually labelled bug-fixing commits of Apache Java projects", "Only 17% to 32% of the changed lines contribute to the bug fix; tangling adds noise to defect data"],
      [`The Impact of Changes Mislabeled by SZZ on Just-in-Time Defect Prediction (2021) ${c("fan")}`, "Yuanrui Fan", "126,526 changes from ten Apache projects", "Compares four SZZ variants with RA-SZZ as the reference; labels of AG-SZZ reduce performance significantly"],
    ], [2.9, 1.45, 2.1, 2.75], 0.4, 0.92, 10.5);
  }
  {
    const s = newSlide("TITLE_ONLY", "Related Works - 2");
    ruledTable(s, ["Title", "Author", "Dataset", "Key Takeaways"], [
      [`A Large-Scale Empirical Study of Just-in-Time Quality Assurance (2013) ${c("kamei")}`, "Yasutaka Kamei", "Six open-source and five commercial projects", "14 change metrics in five groups; 68% accuracy and 64% recall with logistic regression"],
      [`Are Fix-Inducing Changes a Moving Target? (2018) ${c("mcintosh")}`, "Shane McIntosh", "Qt and OpenStack (37,524 changes)", "Properties of fix-inducing changes change over time; models lose predictive power as they age"],
      [`Class Imbalance Evolution and Verification Latency in Just-in-Time Software Defect Prediction (2019) ${c("cabral")}`, "George G. Cabral", "Ten GitHub projects", "Online JIT-SDP with delayed labels (90-day waiting period); proposes ORB for evolving class imbalance"],
      [`Deep Just-in-Time Defect Prediction: How Far Are We? (2021) ${c("zeng")}`, "Zhengran Zeng", "Open-source projects with over 310,000 changes", "Deep models do not consistently beat simple ones; LApredict (logistic regression on added lines) is best in most cases"],
      [`The Best of Both Worlds: Integrating Semantic Features with Expert Features for Defect Prediction and Localization (2022) ${c("ni")}`, "Chao Ni", "JIT-Defects4J: 21 Java projects, 27,319 commits", "Dataset built from manually validated bug-fixing lines; proposes JIT-Fine"],
    ], [2.9, 1.45, 2.1, 2.75], 0.4, 0.92, 10.5);
  }

  // ================================================================ gaps, RQs, objectives
  startSection("Research gaps and objectives");
  bulletSlide("Research Gaps", [
    "Noise of SZZ labels not measured over complete project histories",
    "Models tested against the same labels on which they are trained",
    "Effect of label noise not separated from the effect of the evaluation procedure",
    "Label noise not studied under verification latency",
    "Effect of SZZ noise on online learners not understood, and no remedy for this setting",
  ]);

  const tag = (text) => (full ? " " + text : "");
  bulletSlide("Objectives", [
    [{ text: "Objective 1: ", bold: true }, { text: "To quantify the label noise introduced by SZZ and its variants, by comparing their labels with independent reference labels over complete project histories." }],
    [{ text: "Objective 2: ", bold: true }, { text: "To measure the effect of this noise on JIT-SDP models under a realistic evaluation that respects the order of the commits and the delay of the labels, and to separate it from the effect of the evaluation procedure." }],
    [{ text: "Objective 3: ", bold: true }, { text: "To identify how the noise affects an online learner, and to develop a noise-aware online learning approach that reduces its effect." + tag("(planned for MTP III and MTP IV)") }],
  ], { fontSize: 16.5 });

  bulletSlide("Research Questions", [
    [{ text: "RQ1: ", bold: true }, { text: "How much do the labels of SZZ variants disagree with one another and with independent reference labels, and what type of error does each variant make?" }],
    [{ text: "RQ2: ", bold: true }, { text: "How does the choice of the label source affect the measured performance of JIT-SDP models under different evaluation settings?" }],
    [{ text: "RQ3: ", bold: true }, { text: "Through which mechanism does label noise reduce the performance of an online learner, and which type of error is responsible?" + tag("(planned for MTP III)") }],
    [{ text: "RQ4: ", bold: true }, { text: "Can an online learner be made less sensitive to SZZ label noise without access to clean labels?" + tag("(planned for MTP IV)") }],
  ], { fontSize: 16 });

  // ================================================================ dataset
  startSection("Dataset and methodology");
  {
    const s = newSlide("TITLE_ONLY", "Dataset");
    const items = [
      `JIT-Defects4J ${c("ni")}: 27,319 commits from 21 Apache Java projects (2001 to 2019)`,
      "2,332 commits (8.54%) are defect-introducing; 5,453 commits are bug-fixing",
      "Reference labels: bug-fixing lines validated by at least three of four annotators, then traced back with git blame",
      `Features: the 14 change metrics of Kamei et al. ${c("kamei")}`,
    ];
    if (full) {
      items.push("Seven labels per commit: reference label and six SZZ variants");
      items.push("Label arrival times taken from the dates of the bug-fixing commits (median delay 113 days)");
    } else {
      items.push("Selected because its labels do not come from the SZZ variants under study");
      items.push("SZZ labels and label arrival times will be added in MTP II");
    }
    bulletBox(s, items, { x: 0.35, y: 0.85, w: 5.0, h: 4.3 }, 14.5);
    figure(s, "projects", 5.55, 1.0, 4.15, 1.296, "Commits and defect rate of each project");
  }

  if (!full) {
    // ============================================================== proposed methodology (MTP I deck)
    {
      const s = newSlide("TITLE_ONLY", "Proposed Methodology");
      figure(s, "plan", 0.9, 1.05, 8.2, 2.545, "Planned studies and the research questions they address", 8.6);
    }
    bulletSlide("Proposed Methodology", [
      [{ text: "SZZ labels: ", bold: true }, { text: "six variants (B-, AG-, MA-, L-, R- and RA-SZZ) will be run with PySZZ on the same 5,453 bug-fixing commits" }],
      [{ text: "Label quality: ", bold: true }, { text: "precision, recall, false-alarm rate ρ₀, miss rate ρ₁ and Cohen's κ against the reference labels" }],
      [{ text: "Models: ", bold: true }, { text: `LApredict (logistic regression on lines added) ${c("zeng")}, a JITLine-based random forest with SMOTE ${c("pornprasit")}, and ORB (online ensemble) ${c("cabral")}` }],
      [{ text: "Scoring: ", bold: true }, { text: "against the reference labels, and against the training labels (self-scoring) for comparison" }],
      [{ text: "Statistics: ", bold: true }, { text: "paired by project (n = 21), Wilcoxon signed-rank test, Hodges-Lehmann estimate with bootstrap confidence interval, Holm correction for multiple comparisons" }],
      [{ text: "Planned scale: ", bold: true }, { text: "3 models, 7 label sources, 4 evaluation settings, 10 seeds" }],
    ], { fontSize: 15, gap: 5 });
    {
      const s = newSlide("TITLE_ONLY", "Proposed Methodology: Evaluation Settings");
      figure(s, "settings", 1.35, 0.88, 7.3, 1.987, "Evaluation settings. Commits of a project are ordered by time from left to right", 8.6);
    }
  } else {
    // ============================================================== methodology (MTP II deck)
    {
      const s = newSlide("TITLE_ONLY", "Methodology");
      figure(s, "approach", 0.9, 1.05, 8.2, 2.545, "Overview of the work. Solid boxes: MTP II (completed). Dashed boxes: MTP III and MTP IV (planned)", 8.6);
    }
    bulletSlide("Methodology", [
      [{ text: "SZZ labels: ", bold: true }, { text: "six variants (B-, AG-, MA-, L-, R- and RA-SZZ) run with PySZZ on the same 5,453 bug-fixing commits" }],
      [{ text: "Label quality: ", bold: true }, { text: "precision, recall, false-alarm rate ρ₀, miss rate ρ₁ and Cohen's κ against the reference labels" }],
      [{ text: "Models: ", bold: true }, { text: `LApredict (logistic regression on lines added) ${c("zeng")}, a JITLine-based random forest with SMOTE ${c("pornprasit")}, and ORB (online ensemble) ${c("cabral")}` }],
      [{ text: "Scoring: ", bold: true }, { text: "against the held-out reference labels, and against the training labels (self-scoring) for comparison" }],
      [{ text: "Statistics: ", bold: true }, { text: "paired by project (n = 21), Wilcoxon signed-rank test, Hodges-Lehmann estimate with bootstrap confidence interval, Holm correction over all 74 tests" }],
      [{ text: "Scale: ", bold: true }, { text: "3 models, 7 label sources, 4 evaluation settings, 10 seeds, 16,380 runs" }],
    ], { fontSize: 15, gap: 5 });
    {
      const s = newSlide("TITLE_ONLY", "Methodology: Evaluation Settings");
      figure(s, "settings", 1.35, 0.88, 7.3, 1.987, "Evaluation settings. Commits of a project are ordered by time from left to right", 8.6);
    }

    // ============================================================== results
    startSection("Results");
    {
      const s = newSlide("TITLE_ONLY", "Results: Quality of SZZ Labels (RQ1)");
      ruledTable(s, ["Variant", "Flagged", "Precision", "Recall", "ρ₀", "ρ₁", "κ"], [
        ["B-SZZ", "8,060", "0.186", "0.641", "0.263", "0.359", "0.179"],
        ["AG-SZZ", "5,876", "0.186", "0.467", "0.192", "0.533", "0.163"],
        ["MA-SZZ", "6,154", "0.183", "0.482", "0.201", "0.518", "0.161"],
        ["L-SZZ", "2,287", "0.272", "0.267", "0.067", "0.733", "0.202"],
        ["R-SZZ", "3,015", "0.232", "0.300", "0.093", "0.700", "0.183"],
        ["RA-SZZ", "5,553", "0.184", "0.438", "0.181", "0.562", "0.158"],
      ], [0.95, 0.85, 0.9, 0.75, 0.7, 0.7, 0.7], 0.35, 0.9, 11, ["left", "center", "center", "center", "center", "center", "center"]);
      bulletBox(s, [
        "Precision is at most 0.272: more than 72% of the flagged commits are clean according to the reference",
        "The noise is class-conditional: B-SZZ mainly gives false positives, L-SZZ and R-SZZ mainly miss defects",
      ], { x: 0.3, y: 2.95, w: 5.65, h: 1.6 }, 14);
      figure(s, "noise_rates", 6.15, 1.0, 3.55, 1.202, "False-alarm rate and miss rate");
    }
    {
      const s = newSlide("TITLE_ONLY", "Results: Agreement between Variants (RQ1)");
      figure(s, "kappa", 0.3, 0.9, 4.45, 1.26, "Cohen's κ between the label sets");
      bulletBox(s, [
        "Agreement with the reference labels: κ = 0.16 to 0.20",
        "Agreement among the variants: κ = 0.33 to 0.93",
        "Agreement between SZZ variants is therefore not evidence of correct labels",
        "Filtering also removes correct labels: 30% to 60% of the true positives of B-SZZ are lost in the refined variants",
      ], { x: 5.0, y: 0.9, w: 4.7, h: 4.1 }, 15);
    }
    {
      const s = newSlide("TITLE_ONLY", "Results: Effect of the Evaluation Setting (RQ2)");
      figure(s, "leakage", 0.3, 1.15, 5.35, 1.881, "MCC of each project (models trained on reference labels)");
      bulletBox(s, [
        "Random k-fold gives a higher MCC than the chronological split in all 14 comparisons",
        "JITLine: 0.243 against 0.102 (+0.137), in 21 of 21 projects",
        "LApredict: +0.034, not significant",
        "With the chronological split the simpler model is better (0.173 against 0.102)",
      ], { x: 5.85, y: 0.9, w: 3.9, h: 4.1 }, 14.5);
    }
    {
      const s = newSlide("TITLE_ONLY", "Results: Effect of Scoring against Training Labels (RQ2)");
      figure(s, "self_scoring", 0.3, 1.15, 5.45, 1.944, "Self-scored minus reference-scored MCC");
      bulletBox(s, [
        "Scoring a model against its own SZZ labels gives a higher MCC than scoring against the reference",
        "JITLine with B-SZZ (k-fold): 0.413 against 0.175 (+0.230)",
        "Significant for five of six variants with JITLine, only for B-SZZ with LApredict",
        "The errors of B-SZZ are learnable: AUC 0.60 against 0.51 with permuted labels",
      ], { x: 5.95, y: 0.9, w: 3.8, h: 4.1 }, 14.5);
    }
    {
      const s = newSlide("TITLE_ONLY", "Results: Effect of the Label Source, Online Setting (RQ2)");
      ruledTable(s, ["Training labels", "MCC", "Loss", "95% CI", "Projects", "p (corrected)"], [
        ["Reference", "0.097", "-", "-", "-", "-"],
        ["B-SZZ", "0.058", "0.041", "[0.022, 0.052]", "18/21", "0.006"],
        ["AG-SZZ", "0.036", "0.060", "[0.029, 0.085]", "17/21", "0.024"],
        ["MA-SZZ", "0.035", "0.064", "[0.039, 0.085]", "18/21", "0.004"],
        ["L-SZZ", "0.058", "0.034", "[0.014, 0.055]", "16/21", "0.124"],
        ["R-SZZ", "0.032", "0.060", "[0.042, 0.082]", "19/21", "< 0.001"],
        ["RA-SZZ", "0.039", "0.058", "[0.036, 0.081]", "18/21", "0.006"],
      ], [1.35, 0.7, 0.7, 1.35, 0.8, 1.15], 0.3, 1.55, 11, ["left", "center", "center", "center", "center", "center"]);
      bulletBox(s, [
        "ORB evaluated on the commit stream with verification latency, scored against the reference labels",
        "The model trained on reference labels is better than all six SZZ-trained models",
        "Loss of 0.034 to 0.064 MCC, significant for five of six variants after correction over all tests",
      ], { x: 6.5, y: 0.9, w: 3.25, h: 4.1 }, 14);
    }
    {
      const s = newSlide("TITLE_ONLY", "Results: Combined View");
      figure(s, "ladder", 0.3, 0.95, 5.3, 1.548, "MCC under increasingly realistic conditions");
      bulletBox(s, [
        "Common practice (JITLine, B-SZZ labels, k-fold, self-scored): 0.413",
        "Same predictions scored against reference labels: 0.175",
        "Reference labels with chronological split: 0.102",
        "Online learner with verification latency: 0.097",
        "The evaluation procedure accounts for more of the difference than the label noise",
      ], { x: 5.8, y: 0.9, w: 3.95, h: 4.1 }, 14.5);
    }

    // ============================================================== conclusion
    startSection("Conclusion and future work");
    bulletSlide("Conclusion", [
      "The labels of all six SZZ variants differ strongly from the reference labels (precision 0.18 to 0.27). The noise is class-conditional and depends on the variant.",
      "SZZ variants agree with each other much more than with the reference, so their agreement does not indicate correct labels.",
      "Random k-fold cross-validation and scoring against the training labels overestimate the performance (+0.137 and up to +0.230 MCC), more so for the complex model.",
      "In the online setting with verification latency, training on SZZ labels loses 0.034 to 0.064 MCC compared with the reference labels (0.097).",
      "RQ1 and RQ2 are answered in MTP II. The cause of the loss and a remedy are the subject of MTP III and MTP IV.",
    ], { fontSize: 15.5 });

    bulletSlide("Future Work", [
      [{ text: "MTP III: ", bold: true }, { text: "identify the cause of the loss (RQ3) by injecting noise into the reference labels at the measured rates, and by repairing the B-SZZ labels one error type at a time" }],
      [{ text: "Controls in MTP III: ", bold: true }, { text: "equal number of corrected labels of each type, immediate delivery of repaired labels, and a condition without label delay; the resampling rate of ORB will be recorded" }],
      [{ text: "MTP IV: ", bold: true }, { text: "design a noise-aware online learner (RQ4) that improves the performance on SZZ labels without reducing it on clean labels, with the evaluation plan fixed before the experiments" }],
      [{ text: "Further evaluation: ", bold: true }, { text: "effort-aware measures and other online learners, if time permits" }],
    ], { fontSize: 16 });
  }

  // ================================================================ timeline (MTP II deck only)
  if (full) {
    const s = newSlide("TITLE_ONLY", "Timeline");
    const boxes = [
      { head: "MTP I", lines: "Literature Survey,\nDataset and\nMethodology", cx: 1.6, top: true },
      { head: "MTP II", lines: "Label Quality and\nImpact Analysis\n(RQ1, RQ2)", cx: 3.87, top: false },
      { head: "MTP III", lines: "Mechanism of the\nNoise Effect\n(RQ3)", cx: 6.13, top: true },
      { head: "MTP IV", lines: "Noise-Aware\nOnline Learner\n(RQ4)", cx: 8.4, top: false },
    ];
    const arrowY = 2.62, arrowH = 0.34, bw = 2.0, bh = 1.0;
    s.addShape(pres.shapes.RIGHT_ARROW, { x: 0.5, y: arrowY, w: 9.0, h: arrowH, fill: { color: C.background1 }, line: { color: C.text1, width: 1 }, objectName: "Timeline arrow" });
    boxes.forEach((b, i) => {
      const by = b.top ? 1.05 : 3.55;
      const y1 = b.top ? by + bh : arrowY + arrowH - 0.06;
      const y2 = b.top ? arrowY + 0.06 : by;
      s.addShape(pres.shapes.LINE, { x: b.cx, y: y1, w: 0, h: y2 - y1, line: { color: C.text1, width: 1, dashType: "dash" }, objectName: "Connector " + (i + 1) });
      s.addText(
        [{ text: b.head, options: { bold: true, breakLine: true } }, { text: b.lines }],
        { x: b.cx - bw / 2, y: by, w: bw, h: bh, fontSize: 11.5, color: C.text1, align: "center", valign: "middle", fill: { color: C.background1 }, line: { color: C.text1, width: 1 }, isTextBox: true, margin: 3, objectName: "Stage " + (i + 1) }
      );
    });
    caption(s, "Timeline", 3.0, 4.75, 4.0);
  }

  // ================================================================ references
  startSection("References");
  const refSlide = (title, from, to) => {
    const s = newSlide("TITLE_ONLY", title);
    const none = { type: "none" };
    const rows = [];
    for (let i = from; i <= to; i++) {
      const [authors, paper, venue] = REFS[refKeys[i - 1]];
      rows.push([
        { text: "[" + i + "]", options: { color: C.text2, fontSize: 10.5, valign: "top", border: [none, none, none, none], margin: [2, 2, 2, 2] } },
        {
          text: [
            { text: authors + " “" + paper + "”. ", options: { color: C.text1 } },
            { text: "In: ", options: { color: C.text2 } },
            { text: venue, options: { color: C.text2, italic: true } },
          ],
          options: { fontSize: 10.5, valign: "top", border: [none, none, none, none], margin: [2, 2, 2, 2] },
        },
      ]);
    }
    const rowsHeight = 0.43 * rows.length;
    s.addTable(rows, { x: 0.25, y: Math.max(0.9, 0.85 + (4.3 - rowsHeight) / 2), w: 9.5, colW: [0.55, 8.95], objectName: "Reference list" });
  };
  refSlide("References I", 1, 8);
  refSlide("References II", 9, refKeys.length);

  // ---------------------------------------------------------------- checks and write
  const unused = refKeys.filter((k) => !used.has(k));
  if (unused.length) throw new Error("references listed but not cited: " + unused.join(", "));
  if (slideCount !== total) throw new Error(`deck has ${slideCount} slides but the slide total is set to ${total}`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await pres.writeFile({ fileName: out });
  await finishFile(out);
  console.log("wrote", path.relative(ROOT, out), "(" + slideCount + " slides)");
};

(async () => {
  await buildDeck({
    stage: 1,
    total: 16,
    refKeys: ["cabral", "dacosta", "falessi", "fan", "herbold", "kamei", "mcintosh", "ni", "pornprasit", "rosa", "sliwerski", "zeng"],
    out: path.join(ROOT, "MTP 1", "presentation", "mtp1_presentation.pptx"),
  });
  await buildDeck({
    stage: 2,
    total: 25,
    refKeys: ["cabral", "dacosta", "falessi", "fan", "herbold", "kamei", "mcintosh", "ni", "pornprasit", "rosa", "sliwerski", "zeng"],
    out: path.join(ROOT, "MTP 2", "presentation", "mtp2_presentation.pptx"),
  });
})();
