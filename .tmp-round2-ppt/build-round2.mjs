import { Presentation, PresentationFile } from "@oai/artifact-tool";

const out = "/Users/sufi_spryzen/Knowledge Base/10_FORGE/13_collab/AIC/ps3-businessintelligence-ai/BusinessIntelligence_ai_Round2.pptx";
const W = 1280, H = 720;
const C = { ink: "#0D1B2A", muted: "#50657B", soft: "#E9F0F5", line: "#C5D2DC", blue: "#1677C8", cyan: "#2CB8D5", navy: "#12436A", green: "#16805B", amber: "#E69025", red: "#C94B4B", white: "#FFFFFF", dark: "#071B2B" };
const p = Presentation.create({ slideSize: { width: W, height: H } });

function shape(s, geometry, x, y, w, h, fill = "none", stroke = "none", sw = 0) {
  return s.shapes.add({ geometry, position: { left: x, top: y, width: w, height: h }, fill, line: { style: "solid", fill: stroke, width: sw } });
}
function txt(s, value, x, y, w, h, size = 20, color = C.ink, bold = false, align = "left") {
  const t = shape(s, "textbox", x, y, w, h);
  t.text = value;
  t.text.style = { fontFace: "Helvetica Neue", fontSize: size, color, bold, alignment: align, verticalAlignment: "middle", fit: "shrink" };
  return t;
}
function rule(s, x, y, w, color = C.line, h = 2) { shape(s, "rect", x, y, w, h, color); }
function pill(s, value, x, y, w, color = C.blue) { shape(s, "roundRect", x, y, w, 30, color); txt(s, value, x, y + 1, w, 26, 13, C.white, true, "center"); }
function footer(s, n) { rule(s, 72, 674, 1136, C.line, 1); txt(s, "AIC 2026 · BusinessIntelligence.ai · Round 2", 72, 681, 500, 20, 12, C.muted); txt(s, String(n).padStart(2, "0"), 1154, 681, 54, 20, 12, C.muted, true, "right"); }
function title(s, kicker, headline, sub) { txt(s, kicker.toUpperCase(), 72, 42, 700, 24, 14, C.blue, true); txt(s, headline, 72, 77, 1136, 58, 38, C.ink, true); if (sub) txt(s, sub, 72, 140, 1060, 38, 19, C.muted); }
function twoLine(s, primary, secondary, x, y, w) { txt(s, primary, x, y, w, 30, 22, C.ink, true); txt(s, secondary, x, y + 35, w, 55, 17, C.muted); }

// 1 — cover
{
  const s = p.slides.add(); s.background.fill = C.dark;
  shape(s, "rect", 0, 0, W, H, C.dark);
  shape(s, "rect", 0, 0, 20, H, C.cyan);
  txt(s, "AIC 2026 · PS3", 84, 75, 400, 30, 16, "#8EDAF0", true);
  txt(s, "BusinessIntelligence.ai", 84, 160, 830, 82, 58, C.white, true);
  txt(s, "A governed investigation engine that turns KPI movement into evidence-backed action — or clearly says when the evidence is not enough.", 84, 270, 760, 110, 27, "#D5E6EF");
  rule(s, 84, 428, 170, C.cyan, 5);
  txt(s, "ROUND 2 · Prototype Development", 84, 462, 500, 28, 16, C.white, true);
  // a restrained data motif
  const pts = [[922, 478, 18, C.cyan],[980, 420, 22, C.blue],[1045, 338, 28, C.amber],[1126, 259, 36, C.cyan]];
  for (const [x,y,r,c] of pts) shape(s, "ellipse", x, y, r, r, c);
  rule(s, 920, 486, 214, "#2A688C", 3); rule(s, 978, 430, 150, "#2A688C", 3); rule(s, 1043, 351, 90, "#2A688C", 3);
  txt(s, "Signal → Evidence → Decision", 838, 548, 350, 32, 20, "#B8D8E8", true, "right");
}

// 2 — stakes
{
 const s = p.slides.add(); s.background.fill = C.white;
 title(s, "The Round 2 challenge", "A KPI movement is not yet a decision.", "The prototype must reconcile imperfect sources, investigate likely drivers, communicate uncertainty, and route action to the right person.");
 const items = [
   ["01", "Find material change", "Separate normal variation from a signal worth investigating."],
   ["02", "Establish trustworthy facts", "Resolve conflicting definitions, calendar cuts, gaps, and identities."],
   ["03", "Turn evidence into action", "Rank competing causes, quantify impact, and assign a decision owner."],
 ];
 items.forEach((it,i)=>{ const x=72+i*385; shape(s,"rect",x,250,338,260,i===1?"#E9F5FA":"#F4F7F9"); txt(s,it[0],x+24,273,80,32,16,C.blue,true); twoLine(s,it[1],it[2],x+24,325,286); });
 txt(s,"The standard is not a better dashboard. It is a defensible path from noisy data to a governed business response.",72,575,1080,48,25,C.ink,true);
 footer(s,2);
}

// 3 — the guardrail
{
 const s=p.slides.add(); s.background.fill="#F7FAFC";
 title(s,"Core principle","The LLM never decides what is quantitatively true.","Every number, confidence label, and recommendation is structured before narration begins.");
 // connectors first
 rule(s,283,395,144,C.line,3); rule(s,562,395,144,C.line,3); rule(s,840,395,144,C.line,3);
 const nodes=[
 ["Observed\ndata",72,"#E8F1F6"],["Statistical\n& causal models",349,"#D7EFF6"],["Evidence\nresolution",628,"#E8F1F6"],["LLM\nnarration",906,"#DDEBF9"]
 ];
 nodes.forEach(([label,x,fill],i)=>{shape(s,"roundRect",x,330,210,132,fill,C.line,1); txt(s,label,x+18,359,174,65,24,i===3?C.navy:C.ink,true,"center");});
 txt(s,"Trusted reasoning boundary",72,500,375,30,16,C.green,true); rule(s,72,535,756,C.green,4); txt(s,"The LLM explains the investigation — it does not invent it.",72,561,760,38,26,C.ink,true);
 shape(s,"roundRect",872,513,336,92,"#FFF3E1"); txt(s,"If evidence is insufficient: abstain.",894,533,292,45,22,C.amber,true,"center");
 footer(s,3);
}

// 4 — topology
{
 const s=p.slides.add(); s.background.fill=C.white;
 title(s,"System topology","Eleven stages form one inspection-ready investigation.","Cross-cutting governance wraps the pipeline rather than appearing as a last-minute compliance layer.");
 const groups=[
 ["1–3", "Trust the signal", ["Reconcile sources","Classify change","Prioritize KPI clusters"], C.blue],
 ["4–7", "Diagnose causes", ["Decompose dimensions","Fingerprint cause patterns","Retrieve linked evidence","Resolve hypotheses"], C.cyan],
 ["8–11", "Make action usable", ["Quantify counterfactual","Assemble recommendation","Route by persona","Narrate"], C.navy]
 ];
 groups.forEach((g,i)=>{ const x=72+i*385; shape(s,"rect",x,236,338,302,"#F5F8FA",C.line,1); pill(s,g[0],x+22,257,58,g[3]); txt(s,g[1],x+22,305,286,36,25,C.ink,true); g[2].forEach((v,j)=>{txt(s,"•  "+v,x+22,357+j*37,290,29,17,C.muted);}); });
 txt(s,"Shared services: Semantic contract · Security & access filter · Decision rights · Learning & memory · Telemetry & cost governor",72,580,1136,40,20,C.ink,true,"center");
 footer(s,4);
}

// 5 reconciliation
{
 const s=p.slides.add(); s.background.fill="#F7FAFC";
 title(s,"Trust begins upstream","One business fact may arrive as three inconsistent source records.","Stage 1 makes uncertainty visible before it contaminates detection, diagnosis, or recommendations.");
 const sources=[["Billing","Daily · UTC\nRevenue truth"],["CRM","Weekly · account\nactivity"],["Marketing","Billing-cycle ·\nattributed revenue"]];
 sources.forEach((v,i)=>{const x=72+i*230; shape(s,"roundRect",x,250,190,132,C.white,C.line,1); txt(s,v[0],x+18,272,154,28,22,C.ink,true); txt(s,v[1],x+18,310,154,46,16,C.muted);});
 // arrow band then canonical timeline
 rule(s,692,317,92,C.line,3); txt(s,"→",752,299,36,34,28,C.blue,true,"center");
 shape(s,"roundRect",826,244,382,150,"#DDEFF7",C.blue,2); txt(s,"Canonical, uncertainty-tagged timeline",850,270,334,34,23,C.navy,true,"center"); txt(s,"semantic definitions · calendar alignment · identity resolution · materiality gates",850,319,334,42,16,C.muted,false,"center");
 const rows=[["Conflict","check definition → correct declared bias → triangulate → decline if material/unresolved"],["Gap","estimate only with uncertainty; protect downstream models from false confidence"],["Drift","detect hidden definition changes and issue a visible restatement when needed"]];
 rows.forEach((r,i)=>{const y=455+i*55; txt(s,r[0],72,y,130,30,18,C.blue,true); txt(s,r[1],230,y,950,35,17,C.muted);});
 footer(s,5);
}

// 6 — diagnostic loop
{
 const s=p.slides.add(); s.background.fill=C.white;
 title(s,"The diagnostic core","Movement becomes an explainable hypothesis — not a plausible-sounding story.","Each stage constrains the next with observed data, model output, or evidence provenance.");
 const steps=[
 ["Detect","Normal / emerging / significant / structural","#DDEBF9"],
 ["Decompose","Region · segment · product slices","#E8F1F6"],
 ["Fingerprint","Onset, spread, entropy, channel mix","#D7EFF6"],
 ["Link evidence","CRM · tickets · reviews, time-tagged","#E8F1F6"],
 ["Resolve","Known · likely · possible · unknown","#DDEBF9"]
 ];
 steps.forEach((v,i)=>{ const x=72+i*225; shape(s,"roundRect",x,287,190,180,v[2],C.line,1); txt(s,String(i+1).padStart(2,"0"),x+18,307,42,24,14,C.blue,true); txt(s,v[0],x+18,345,154,28,22,C.ink,true); txt(s,v[1],x+18,387,154,54,16,C.muted); if(i<4) txt(s,"›",x+196,355,24,40,30,C.blue,true,"center"); });
 rule(s,72,535,1136,C.line,2); txt(s,"Evidence is filtered by entity scope and by whether it occurred before, during, or after the KPI change — a safeguard against confusing consequence with cause.",72,562,1136,45,21,C.ink,true,"center");
 footer(s,6);
}

// 7 — confounding
{
 const s=p.slides.add(); s.background.fill="#F7FAFC";
 title(s,"The differentiator","When causes overlap, do not force a top-one answer.","Stage 5b is an explicit confounded-cause branch: it attributes what is identifiable and preserves a joint component where it is not.");
 shape(s,"roundRect",72,248,510,270,C.white,C.line,1); txt(s,"The usual failure",100,276,430,30,22,C.red,true); txt(s,"“The cause is marketing.”",100,332,420,42,30,C.ink,true); txt(s,"A clean-sounding answer that can hide reliability, inventory, or competitive effects inside the same KPI movement.",100,394,420,72,19,C.muted);
 shape(s,"roundRect",696,248,512,270,"#DDEFF7",C.blue,2); txt(s,"Our response",724,276,430,30,22,C.navy,true); txt(s,"Identifiable effects + shared uncertainty",724,332,440,42,27,C.ink,true); txt(s,"A route gate checks whether the data can support separate attribution. If not, the system reports a joint cause instead of fabricating a split.",724,394,440,72,19,C.muted);
 txt(s,"Cold start is handled separately: borrow a matched analogue’s volatility profile and label confidence as borrowed, not native.",72,574,1136,34,21,C.ink,true,"center");
 footer(s,7);
}

// 8 — counterfactual and action
{
 const s=p.slides.add(); s.background.fill=C.white;
 title(s,"Decision quality","Counterfactuals come before recommendations.","Stage 8 asks what the KPI would have been without the suspected event; Stage 9 turns that bounded result into an authorized action.");
 const x1=72,x2=478,x3=884;
 [[x1,"Observed","A KPI moved; its change is decomposed and evidence-linked."],[x2,"Counterfactual","Model a no-event trajectory, retain uncertainty, and abstain when mechanisms are unsupported."],[x3,"Decision","Map driver → lever → action → owner → monitoring plan, respecting decision rights."]].forEach((v,i)=>{shape(s,"roundRect",v[0],268,324,238,i===1?"#DDEFF7":"#F5F8FA",i===1?C.blue:C.line,1); txt(s,String(i+1),v[0]+24,290,46,30,17,C.blue,true); txt(s,v[1],v[0]+24,340,270,34,26,C.ink,true); txt(s,v[2],v[0]+24,395,270,78,18,C.muted);});
 rule(s,396,385,65,C.line,3); rule(s,802,385,65,C.line,3); txt(s,"→",425,366,30,35,27,C.blue,true,"center"); txt(s,"→",831,366,30,35,27,C.blue,true,"center");
 txt(s,"The recommendation cannot rewrite the diagnosis. It can only select a feasible, compatible response to it.",72,563,1136,40,24,C.ink,true,"center");
 footer(s,8);
}

// 9 governance
{
 const s=p.slides.add(); s.background.fill="#F7FAFC";
 title(s,"Governed by design","Trust, access, action rights, learning, and cost control are product behavior.","These controls are consulted throughout the pipeline, not appended as a policy slide.");
 const cols=[
 ["Security & access","Row / column / domain filtering determines what a person may see."],
 ["Decision rights","Seeing a recommendation is distinct from being authorized to act on it."],
 ["Persona routing","Executives, analysts, and operators receive different decisions and depth — not merely shorter copy."],
 ["Learning & memory","Analyst corrections become reusable investigation history and future training data."],
 ["Cost governor","Telemetry tracks latency, calls, and tokens; cheap methods route work before expensive model calls."]
 ];
 cols.forEach((v,i)=>{ const x=72+i*226; shape(s,"rect",x,249,198,266,i===4?"#DDEFF7":"#F5F8FA",C.line,1); txt(s,"0"+(i+1),x+18,269,42,26,14,C.blue,true); txt(s,v[0],x+18,314,162,55,21,C.ink,true); txt(s,v[1],x+18,390,162,91,16,C.muted);});
 footer(s,9);
}

// 10 proof / prototype
{
 const s=p.slides.add(); s.background.fill=C.white;
 title(s,"Prototype proof","The simulator turns “AI insight” into testable engineering.","Synthetic episodes inject known causes, confounded events, and pure noise — while the live pipeline only sees degraded observed sources.");
 const chain=[["Generate","Ground truth: events, causal chains, volatility regimes"],["Degrade","Observed sources: lags, gaps, conflicting values, misaligned calendars"],["Train","Significance and fingerprint models on labeled episodes"],["Hold out","Run the full pipeline without exposing the answer key"],["Score","Compare output to truth and show the failure modes"]];
 chain.forEach((v,i)=>{const x=72+i*226; shape(s,"roundRect",x,260,198,160,i===3?"#DDEFF7":"#F5F8FA",i===3?C.blue:C.line,1); txt(s,v[0],x+16,283,166,29,21,C.ink,true); txt(s,v[1],x+16,330,166,61,16,C.muted); if(i<4)txt(s,"›",x+198,316,28,38,28,C.blue,true,"center");});
 const metrics=[["Detection","precision / recall by change class"],["Diagnosis","root-cause top-1 and top-3 accuracy"],["Honesty","false-causality rate on noise episodes"],["Impact","counterfactual MAE versus simulated truth"],["Calibration","do confidence labels match outcomes?"]];
 metrics.forEach((v,i)=>{ const x=72+i*226; txt(s,v[0],x,500,198,27,17,C.blue,true,"center"); txt(s,v[1],x,531,198,40,16,C.muted,false,"center");});
 footer(s,10);
}

// 11 close
{
 const s=p.slides.add(); s.background.fill=C.dark;
 shape(s,"rect",0,0,W,H,C.dark); shape(s,"rect",0,0,20,H,C.cyan);
 txt(s,"ROUND 2 PROPOSITION",84,74,450,28,16,"#8EDAF0",true);
 txt(s,"A decision system that earns the right to speak.",84,143,930,78,51,C.white,true);
 txt(s,"It reconciles data before trusting it, makes causality explicit before recommending action, and abstains when the evidence does not support a conclusion.",84,264,830,80,26,"#D5E6EF");
 const end=["Live, judge-directed investigation","Inspectable evidence and uncertainty trail","Action routed to the person who can actually decide"];
 end.forEach((v,i)=>{shape(s,"ellipse",88,410+i*62,18,18,C.cyan); txt(s,v,126,398+i*62,740,40,22,C.white);});
 rule(s,84,625,1124,"#2A688C",1); txt(s,"BusinessIntelligence.ai · From KPI movement to governed action",84,642,840,30,16,"#B8D8E8",true); txt(s,"11",1154,642,54,30,14,"#B8D8E8",true,"right");
}

const pptx = await PresentationFile.exportPptx(p);
await pptx.save(out);
