// Эта (Eta) — UI Kit page (Figma Plugin API, run via use_figma in the file «Эта — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Eta")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors eta/eta/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "sidebar": ["#F0EEE6", "#1F1E1D"], "list": ["#F0EEE6", "#1F1E1D"], "overdue": ["#D64545", "#E05A5A"],
  "due-soon": ["#E8B23A", "#E8B23A"], "done": ["#4E8A5A", "#7BB487"], "board-a": ["#D97757", "#D97757"], "board-b": ["#C6613F", "#C6613F"],
  "l-green": ["#7BA05B", "#7BA05B"], "l-yellow": ["#E8B23A", "#E8B23A"], "l-orange": ["#E08A4A", "#E08A4A"], "l-red": ["#D6584B", "#D6584B"],
  "l-purple": ["#9B7BC4", "#9B7BC4"], "l-blue": ["#5B8CC4", "#5B8CC4"], "l-sky": ["#5DAFC4", "#5DAFC4"], "white": ["#FFFFFF", "#FFFFFF"], "ink": ["#141413", "#141413"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Eta — " + modeName);  // Starter plan: 1 mode per collection
  col.renameMode(col.modes[0].modeId, modeName);
  colIds[modeName] = col.id;
  for (const [name, vals] of Object.entries(T)) {
    const v = figma.variables.createVariable("color/" + name, col, "COLOR");
    v.setValueForMode(col.modes[0].modeId, hex(vals[mi]));
    V[modeName][name] = v;
  }
}
let MODE = "Light";
const fill = name => figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][name]);
function txt(chars, o = {}) {
  const t = figma.createText();
  t.fontName = {family: o.family || SANS, style: o.style || "Regular"};
  t.fontSize = o.size || 13; t.characters = chars; t.fills = [fill(o.color || "text")];
  if (o.w) { t.textAutoResize = "HEIGHT"; t.resize(o.w, t.height); }
  return t;
}
function al(dir, o = {}) {
  const f = figma.createAutoLayout(dir, {itemSpacing: o.gap ?? 8});
  f.name = o.name || "Frame";
  f.fills = o.fill ? [fill(o.fill)] : [];
  if (o.pad !== undefined) { const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad, o.pad, o.pad, o.pad]; f.paddingTop = t; f.paddingRight = r; f.paddingBottom = b; f.paddingLeft = l; }
  if (o.radius) f.cornerRadius = o.radius;
  if (o.stroke) { f.strokes = [fill(o.stroke)]; f.strokeWeight = 1; }
  if (o.align) f.counterAxisAlignItems = o.align;
  return f;
}
function comp(name, dir, o = {}) {
  const c = figma.createComponent(); c.name = name; c.layoutMode = dir;
  c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "AUTO"; c.itemSpacing = o.gap ?? 8;
  const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad ?? 0, o.pad ?? 0, o.pad ?? 0, o.pad ?? 0];
  c.paddingTop = t; c.paddingRight = r; c.paddingBottom = b; c.paddingLeft = l;
  c.fills = o.fill ? [fill(o.fill)] : []; if (o.radius) c.cornerRadius = o.radius;
  if (o.stroke) { c.strokes = [fill(o.stroke)]; c.strokeWeight = 1; }
  c.counterAxisAlignItems = o.align || "CENTER";
  return c;
}
function variants(comps, parent, props = {}) {
  const set = figma.combineAsVariants(comps, parent);
  set.layoutMode = "HORIZONTAL"; set.primaryAxisSizingMode = "AUTO"; set.counterAxisSizingMode = "AUTO";
  set.itemSpacing = 16; set.paddingTop = set.paddingBottom = set.paddingLeft = set.paddingRight = 20;
  set.counterAxisAlignItems = "CENTER"; set.fills = [fill("bg")]; set.cornerRadius = 12;
  set.strokes = [fill("border")]; set.dashPattern = [4, 4];
  for (const [prop, def] of Object.entries(props)) {
    const key = set.addComponentProperty(prop, "TEXT", def);
    for (const v of set.children) { const t = v.findOne(n => n.type === "TEXT" && n.name === prop); if (t) t.componentPropertyReferences = {characters: key}; }
  }
  return set;
}


// pixel head like eta/widgets.py pixel_head: 8×8 cells
function head(size, skin = "#E0AC84", hair = "#5A3A22", eye = "#3B6A8F") {
  const f = figma.createFrame(); f.name = "Pixel head"; f.resize(size, size); f.cornerRadius = size / 6; f.clipsContent = true; f.fills = [{type: "SOLID", color: hex(skin)}];
  const c = size / 8;
  const px = (x, y, col) => { const r = figma.createRectangle(); r.resize(c + 0.5, c + 0.5); r.x = x * c; r.y = y * c; r.fills = [{type: "SOLID", color: hex(col)}]; f.appendChild(r); };
  for (let x = 0; x < 8; x++) { px(x, 0, hair); px(x, 1, hair); }
  px(0, 2, hair); px(7, 2, hair);
  px(1, 4, "#FFFFFF"); px(2, 4, eye); px(5, 4, "#FFFFFF"); px(6, 4, eye);
  px(3, 5, "#B07A58"); px(4, 5, "#B07A58"); px(3, 6, "#7A3B2E"); px(4, 6, "#7A3B2E");
  return f;
}
function blockIcon(size, a = "#D97757", b = "#C6613F", letter = "А") {
  const f = figma.createFrame(); f.name = "Block icon"; f.resize(size, size); f.cornerRadius = size * 0.21; f.clipsContent = true; f.fills = [{type: "SOLID", color: hex(a)}];
  const c = size / 6;
  for (let y = 0; y < 6; y++) for (let x = 0; x < 6; x++) if ((x * 7 + y * 3) % 5 < 2) { const r = figma.createRectangle(); r.resize(c + 0.5, c + 0.5); r.x = x * c; r.y = y * c; r.fills = [{type: "SOLID", color: hex(b)}]; f.appendChild(r); }
  const t = figma.createText(); t.fontName = {family: SERIF, style: "Regular"}; t.fontSize = size * 0.45; t.characters = letter; t.fills = [{type: "SOLID", color: hex("#FFFFFF")}];
  f.appendChild(t); t.x = size / 2 - t.width / 2; t.y = size / 2 - t.height / 2;
  return f;
}
function tagEl(t, col) { const g = al("HORIZONTAL", {name: "Tag " + t, pad: [1, 8, 1, 8], radius: 9, stroke: col || "border"}); g.appendChild(txt(t, {size: 11, color: col || "muted"})); return g; }
function projectRow(title, author, desc, loaders, cats, dl, fo, src, colors) {
  const r = al("HORIZONTAL", {name: "Project / " + title, gap: 14, pad: [12, 14, 12, 14], radius: 14, fill: "card", stroke: "border"});
  r.resize(720, 40); r.primaryAxisSizingMode = "FIXED"; r.counterAxisAlignItems = "MIN";
  r.appendChild(blockIcon(64, colors[0], colors[1], title[0]));
  const c = al("VERTICAL", {name: "Text", gap: 4}); c.layoutGrow = 1;
  const h = al("HORIZONTAL", {name: "Head", gap: 6, align: "CENTER"}); h.appendChild(txt(title, {family: SERIF, size: 18})); h.appendChild(txt("от " + author, {color: "muted"})); c.appendChild(h);
  c.appendChild(txt(desc, {w: 420}));
  const tg = al("HORIZONTAL", {name: "Tags", gap: 4}); for (const [l, col] of loaders) tg.appendChild(tagEl(l, col)); for (const t of cats) tg.appendChild(tagEl(t)); c.appendChild(tg);
  r.appendChild(c);
  const s = al("VERTICAL", {name: "Stats", gap: 3}); s.counterAxisAlignItems = "MAX";
  s.appendChild(txt("⤓ " + dl, {style: "Semi Bold"})); s.appendChild(txt("♥ " + fo, {style: "Semi Bold"})); s.appendChild(txt("обновлено 2 мес. назад", {size: 11, color: "muted"})); s.appendChild(txt(src, {size: 11, style: "Semi Bold", color: "muted"}));
  const b = al("HORIZONTAL", {name: "Install", pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); b.appendChild(txt("⤓ Установить", {style: "Semi Bold", color: "on-accent"})); s.appendChild(b);
  r.appendChild(s);
  return r;
}

const root = al("VERTICAL", {name: "Эта — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const headR = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(headR);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [6, 30, 26, 30]}); headR.appendChild(icon);
icon.appendChild(txt("η", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); headR.appendChild(hc);
hc.appendChild(txt("Эта — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Лаунчер Minecraft · сборки · аккаунты · настройки · коллекции «Eta — Light» / «Eta — Dark»", {color: "muted", size: 15}));
const grid = al("HORIZONTAL", {name: "Components", gap: 24}); grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
grid.resize(1488, 100); grid.primaryAxisSizingMode = "FIXED"; root.appendChild(grid);

const play = comp("Play button", "HORIZONTAL", {pad: [10, 30, 10, 30], radius: 10, fill: "accent"}); play.appendChild(txt("▶  Играть", {size: 16, style: "Semi Bold", color: "on-accent"})); grid.appendChild(play);
const pr = comp("Project row", "HORIZONTAL", {pad: 0}); pr.appendChild(projectRow("Арканум", "nyx", "Школы магии, ритуалы и подземелья с боссами-волшебниками.", [["NeoForge", "l-red"], ["Forge", "l-blue"]], ["Магия", "Приключения", "1.20.1 +1"], "190 тыс.", "7.4 тыс.", "Modrinth", ["#D97757", "#C6613F"])); grid.appendChild(pr);
const ic2 = comp("Instance card", "VERTICAL", {pad: [14, 14, 12, 14], gap: 6, radius: 14, fill: "card", stroke: "accent"}); ic2.strokeWeight = 2;
ic2.resize(236, 210); ic2.primaryAxisSizingMode = "FIXED"; ic2.counterAxisAlignItems = "MIN";
ic2.appendChild(blockIcon(56, "#E8B23A", "#C08A2A", "Т")); ic2.appendChild(txt("Тихая гавань", {family: SERIF, size: 16}));
const t2 = al("HORIZONTAL", {name: "Tags", gap: 4}); t2.appendChild(tagEl("Fabric", "l-orange")); t2.appendChild(tagEl("1.21.1")); ic2.appendChild(t2);
ic2.appendChild(txt("Modrinth · 96 модов · играли 2 ч назад", {size: 11, color: "muted"}));
const ib = al("HORIZONTAL", {name: "Buttons", gap: 6}); const pb = al("HORIZONTAL", {name: "Play", pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); pb.appendChild(txt("▶ Играть", {style: "Semi Bold", color: "on-accent"})); ib.appendChild(pb);
const sb = al("HORIZONTAL", {name: "Selected", pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"}); sb.appendChild(txt("Выбрана", {color: "faint"})); ib.appendChild(sb); ic2.appendChild(ib);
grid.appendChild(ic2);
const ac = comp("Account card", "HORIZONTAL", {pad: [12, 14, 12, 14], gap: 14, radius: 14, fill: "card", stroke: "accent"}); ac.strokeWeight = 2;
ac.resize(720, 40); ac.primaryAxisSizingMode = "FIXED";
ac.appendChild(head(52));
const acc = al("VERTICAL", {name: "Text", gap: 2}); acc.layoutGrow = 1;
const an = al("HORIZONTAL", {name: "Name", gap: 6, align: "CENTER"}); an.appendChild(txt("Hoka_Neko", {family: SERIF, size: 16})); an.appendChild(tagEl("mc-ru.org", "l-orange")); const bd = al("HORIZONTAL", {name: "Badge", pad: [1, 8, 1, 8], radius: 8, fill: "accent"}); bd.appendChild(txt("Выбран", {size: 11, color: "on-accent"})); an.appendChild(bd); acc.appendChild(an);
acc.appendChild(txt("Аккаунт mc-ru.org · играли 2 ч назад", {color: "muted"})); acc.appendChild(txt("50c353a8-da7f-3cd7-ae06-1164960c56d0", {size: 11, color: "muted"})); ac.appendChild(acc);
ac.appendChild(txt("⧉   🗑", {color: "muted"})); grid.appendChild(ac);
const chip = comp("Account chip", "HORIZONTAL", {pad: [6, 8, 6, 8], gap: 8, radius: 12, fill: "card", stroke: "border"}); chip.resize(186, 48); chip.primaryAxisSizingMode = "FIXED";
chip.appendChild(head(30)); const cc = al("VERTICAL", {name: "Text", gap: 0}); cc.appendChild(txt("Hoka_Neko", {style: "Semi Bold"})); cc.appendChild(txt("Оффлайн", {size: 11, color: "muted"})); chip.appendChild(cc); grid.appendChild(chip);
const chips = ["Off", "On"].map(v => { const c = comp("State=" + v, "HORIZONTAL", {pad: [4, 10, 4, 10], radius: 14, fill: v === "On" ? "accent" : "card", stroke: v === "On" ? "accent" : "border"}); c.appendChild(txt("Fabric", {color: v === "On" ? "on-accent" : "text"})); return c; });
variants(chips, grid).name = "Filter chip";
const sws = comp("Accent swatches", "HORIZONTAL", {pad: 12, gap: 6, radius: 12, fill: "card", stroke: "border"});
for (const [i, c] of ["#D97757", "#3F7FD0", "#4E8A57", "#9B6BC9", "#D9668F", "#E0A433", "#3FA7C9", "#55575E", "#D2453B", "#3BB08F"].entries()) { const e = figma.createEllipse(); e.resize(24, 24); e.fills = [{type: "SOLID", color: hex(c)}]; if (!i) { e.strokes = [fill("text")]; e.strokeWeight = 3; } sws.appendChild(e); }
grid.appendChild(sws);
const glass = comp("Glass card", "VERTICAL", {pad: [14, 16, 14, 16], gap: 4, radius: 14}); glass.fills = [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.6}]; glass.strokes = [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.38}];
glass.effects = [{type: "BACKGROUND_BLUR", radius: 24, visible: true}]; glass.appendChild(txt("Стекло", {family: SERIF, size: 16})); glass.appendChild(txt("Полупрозрачная панель поверх размытого фона", {color: "muted"})); grid.appendChild(glass);
const tags = comp("Tags", "HORIZONTAL", {pad: 12, gap: 4}); for (const [t, c] of [["Fabric", "l-orange"], ["Forge", "l-blue"], ["NeoForge", "l-red"], ["Quilt", "l-purple"], ["Vanilla", "l-green"], ["Магия", null], ["1.21.1", null]]) tags.appendChild(tagEl(t, c)); grid.appendChild(tags);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
