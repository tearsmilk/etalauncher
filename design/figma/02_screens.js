// Эта (Eta) — Screens page: Загрузка, Главная (Light / Dark), Сборки — каталог, Мои сборки, Аккаунты, Новый аккаунт,
// Настройки. Run after 01_ui_kit.js.
let page = figma.root.children.find(p => p.name === "Screens");
if (!page) { page = figma.createPage(); page.name = "Screens"; }
await figma.setCurrentPageAsync(page);
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const cols = await figma.variables.getLocalVariableCollectionsAsync();
const vars = await figma.variables.getLocalVariablesAsync("COLOR");
const V = {};
for (const mode of ["Light", "Dark"]) {
  const col = cols.find(c => c.name === "Eta — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Eta — " + mode + ")");
  V[mode] = {};
  for (const v of vars) if (v.variableCollectionId === col.id) V[mode][v.name.replace("color/", "")] = v;
}
let MODE = "Light";
const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
const fill = n => figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][n]);
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

function frame(name, w, h, fillName = "bg") { const f = figma.createFrame(); f.name = name; f.resize(w, h); f.fills = [fill(fillName)]; f.clipsContent = true; return f; }
function btn(t, kind = "default") {
  const b = al("HORIZONTAL", {name: "Button " + t, pad: [5, 12, 5, 12], radius: 7, fill: kind === "accent" ? "accent" : "card", stroke: kind === "default" ? "border" : null});
  b.appendChild(txt(t, {style: kind === "default" ? "Regular" : "Semi Bold", color: kind === "default" ? "text" : "on-accent"})); return b;
}
function sidebar(active) {
  const s = al("VERTICAL", {name: "Sidebar", gap: 4, pad: [18, 12, 14, 12], fill: "sidebar"}); s.resize(210, 820); s.primaryAxisSizingMode = "FIXED"; s.counterAxisSizingMode = "FIXED";
  const brand = al("HORIZONTAL", {name: "Brand", gap: 6, align: "CENTER"}); brand.appendChild(txt("η", {family: SERIF, style: SERIF_I, size: 30, color: "accent"})); brand.appendChild(txt("Эта", {family: SERIF, size: 17})); s.appendChild(brand);
  for (const [i, t] of ["⌂  Главная", "▣  Сборки", "☺  Аккаунты", "⚙  Настройки"].entries()) { const b = al("HORIZONTAL", {name: t, pad: [7, 10, 7, 10], radius: 7, fill: i === active ? "selected" : null}); b.resize(186, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); s.appendChild(b); }
  const sp = figma.createFrame(); sp.fills = []; sp.resize(10, 10); sp.layoutGrow = 1; s.appendChild(sp);
  const chip = al("HORIZONTAL", {name: "Account chip", pad: [6, 8, 6, 8], gap: 8, radius: 12, fill: "card", stroke: "border"}); chip.resize(186, 48); chip.primaryAxisSizingMode = "FIXED";
  chip.appendChild(head(30)); const cc = al("VERTICAL", {name: "Text", gap: 0}); cc.appendChild(txt("Hoka_Neko", {style: "Semi Bold"})); cc.appendChild(txt("Оффлайн", {size: 11, color: "muted"})); chip.appendChild(cc); s.appendChild(chip);
  return s;
}
function shell(name, active) {
  const f = frame(name, 1280, 820); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  f.appendChild(sidebar(active));
  const body = al("VERTICAL", {name: "Page", gap: 14, pad: [26, 32, 26, 32]}); body.layoutGrow = 1; body.layoutAlign = "STRETCH"; f.appendChild(body);
  return [f, body];
}
let X = 0;
function place(f) { f.x = X; f.y = 0; X += f.width + 80; page.appendChild(f); }

// Загрузка
{
  const f = frame("Загрузка", 1280, 820);
  const c = al("VERTICAL", {name: "Center", gap: 6, align: "CENTER"}); c.resize(1280, 820); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED"; c.primaryAxisAlignItems = "CENTER"; f.appendChild(c);
  c.appendChild(txt("η", {family: SERIF, style: SERIF_I, size: 120, color: "accent"})); c.appendChild(txt("Эта", {family: SERIF, size: 30})); c.appendChild(txt("Лаунчер Minecraft", {color: "muted"}));
  const bar = figma.createFrame(); bar.resize(320, 6); bar.cornerRadius = 3; bar.fills = [fill("border")]; const ch = figma.createRectangle(); ch.resize(120, 6); ch.cornerRadius = 3; ch.fills = [fill("accent")]; bar.appendChild(ch); c.appendChild(bar);
  c.appendChild(txt("Загружаем аккаунты…", {size: 11, color: "muted"}));
  place(f);
}

// Главная (Light, Dark)
for (const mode of ["Light", "Dark"]) {
  MODE = mode;
  const [f, b] = shell("Главная — " + mode, 0);
  b.appendChild(txt("Добрый вечер, Hoka_Neko", {family: SERIF, size: 28}));
  const hero = figma.createFrame(); hero.name = "Hero"; hero.resize(1006, 300); hero.cornerRadius = 18; hero.clipsContent = true;
  hero.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {...hex(mode === "Dark" ? "#1F2438" : "#F3D2B3"), a: 1}}, {position: 1, color: {...hex(mode === "Dark" ? "#3B4A6B" : "#E58F6B"), a: 1}}]}];
  for (let i = 0; i < 42; i++) { const h = 40 + ((i * 37) % 5) * 22; const r = figma.createRectangle(); r.resize(24, h); r.x = i * 24; r.y = 300 - h; r.fills = [{type: "SOLID", color: hex(i % 3 ? "#5E8A48" : "#7BA05B")}]; hero.appendChild(r); }
  const shade = figma.createRectangle(); shade.resize(1006, 300); shade.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0.4, color: {r: 0, g: 0, b: 0, a: 0}}, {position: 1, color: {r: 0, g: 0, b: 0, a: 0.5}}]}]; hero.appendChild(shade);
  const hc = al("VERTICAL", {name: "Content", gap: 12}); hero.appendChild(hc); hc.x = 32; hc.y = 140;
  const tr = al("HORIZONTAL", {name: "Title", gap: 16, align: "CENTER"}); tr.appendChild(blockIcon(72, "#E8B23A", "#C08A2A", "Т"));
  const tc = al("VERTICAL", {name: "Text", gap: 2}); tc.appendChild(txt("Тихая гавань", {family: SERIF, size: 34, color: "white"})); tc.appendChild(txt("Fabric 1.21.1 · 96 модов · в игре 3 ч 12 мин", {color: "white"})); tr.appendChild(tc); hc.appendChild(tr);
  const acts = al("HORIZONTAL", {name: "Actions", gap: 8, align: "CENTER"}); const pl = al("HORIZONTAL", {name: "Play", pad: [10, 30, 10, 30], radius: 10, fill: "accent"}); pl.appendChild(txt("▶  Играть", {size: 16, style: "Semi Bold", color: "on-accent"})); acts.appendChild(pl);
  const pk = al("HORIZONTAL", {name: "Picker", pad: [8, 10, 8, 10], radius: 8, fill: "white"}); pk.resize(220, 34); pk.primaryAxisSizingMode = "FIXED"; pk.appendChild(txt("Тихая гавань  ▾", {color: "ink"})); acts.appendChild(pk); hc.appendChild(acts);
  b.appendChild(hero);
  b.appendChild(txt("НЕДАВНИЕ СБОРКИ", {size: 10, style: "Semi Bold", color: "muted"}));
  const rec = al("HORIZONTAL", {name: "Recent", gap: 12});
  for (const [n, v, c1, c2] of [["Тихая гавань", "Fabric 1.21.1", "#E8B23A", "#C08A2A"], ["Арканум", "NeoForge 1.20.1", "#D97757", "#C6613F"], ["Выживание с друзьями", "Forge 1.20.1", "#5DAFC4", "#3B8A9F"]]) {
    const m = al("HORIZONTAL", {name: n, gap: 8, pad: [8, 12, 8, 10], radius: 12, fill: "card", stroke: "border", align: "CENTER"}); m.appendChild(blockIcon(36, c1, c2, n[0]));
    const mc = al("VERTICAL", {name: "Text", gap: 0}); mc.appendChild(txt(n, {family: SERIF, size: 15})); mc.appendChild(txt(v, {size: 11, color: "muted"})); m.appendChild(mc); rec.appendChild(m);
  }
  b.appendChild(rec);
  b.appendChild(txt("НОВОСТИ ЛАУНЧЕРА", {size: 10, style: "Semi Bold", color: "muted"}));
  const nw = al("HORIZONTAL", {name: "News", gap: 12});
  for (const [t, d] of [["Добро пожаловать в Эту", "Сборки, аккаунты и настройки уже работают."], ["Modrinth и CurseForge — скоро", "Каталог пока показывает примеры."], ["Оффлайн-аккаунты", "Играйте с любым ником."]]) {
    const c = al("VERTICAL", {name: t, gap: 4, pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border"}); c.resize(326, 96); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED";
    c.appendChild(txt(t, {family: SERIF, size: 16})); c.appendChild(txt(d, {color: "muted", w: 294})); nw.appendChild(c);
  }
  b.appendChild(nw);
  place(f);
}
MODE = "Light";

// Сборки — каталог
{
  const [f, b] = shell("Сборки — каталог", 1);
  const hd = al("HORIZONTAL", {name: "Head", gap: 12, align: "CENTER"}); hd.appendChild(txt("Сборки", {family: SERIF, size: 28}));
  const s1 = al("HORIZONTAL", {name: "Tab catalog", pad: [5, 12, 5, 12], fill: "selected", stroke: "accent"}); s1.appendChild(txt("Каталог")); hd.appendChild(s1);
  const s2 = al("HORIZONTAL", {name: "Tab mine", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); s2.appendChild(txt("Мои сборки")); hd.appendChild(s2); b.appendChild(hd);
  const row = al("HORIZONTAL", {name: "Body", gap: 18}); b.appendChild(row);
  const fl = al("VERTICAL", {name: "Filters", gap: 6}); fl.resize(230, 40); fl.counterAxisSizingMode = "FIXED";
  fl.appendChild(txt("ИСТОЧНИК", {size: 10, style: "Semi Bold", color: "muted"})); fl.appendChild(txt("☑ Modrinth")); fl.appendChild(txt("☑ CurseForge"));
  fl.appendChild(txt("ЗАГРУЗЧИК", {size: 10, style: "Semi Bold", color: "muted"}));
  const lc = al("HORIZONTAL", {name: "Loaders", gap: 4}); lc.layoutWrap = "WRAP"; lc.resize(230, 40); lc.primaryAxisSizingMode = "FIXED";
  for (const [t, on] of [["Fabric", true], ["Forge", false], ["NeoForge", false], ["Quilt", false]]) { const c = al("HORIZONTAL", {name: t, pad: [4, 10, 4, 10], radius: 14, fill: on ? "accent" : "card", stroke: on ? "accent" : "border"}); c.appendChild(txt(t, {color: on ? "on-accent" : "text"})); lc.appendChild(c); }
  fl.appendChild(lc);
  fl.appendChild(txt("ВЕРСИЯ ИГРЫ", {size: 10, style: "Semi Bold", color: "muted"})); fl.appendChild(btn("Любая"));
  fl.appendChild(txt("КАТЕГОРИИ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const t of ["Приключения", "Техника", "Магия", "Оптимизация", "Выживание", "Хардкор", "Квесты"]) fl.appendChild(txt("☐ " + t));
  row.appendChild(fl);
  const res = al("VERTICAL", {name: "Results", gap: 10}); row.appendChild(res);
  const sr = al("HORIZONTAL", {name: "Search", gap: 8, align: "CENTER"}); const se = al("HORIZONTAL", {name: "Field", pad: [6, 10, 6, 10], radius: 6, fill: "input", stroke: "border"}); se.resize(520, 30); se.primaryAxisSizingMode = "FIXED"; se.appendChild(txt("⌕  Поиск сборок…", {color: "faint"})); sr.appendChild(se); sr.appendChild(txt("Сортировка")); sr.appendChild(btn("По релевантности")); res.appendChild(sr);
  res.appendChild(txt("Найдено: 9 · демо-каталог", {size: 11, color: "muted"}));
  res.appendChild(projectRow("Кинолента", "lumen", "Шейдеры, физика, анимации — для красивых видео и скриншотов.", [["Fabric", "l-orange"], ["Quilt", "l-purple"]], ["Оптимизация", "Лёгкие", "1.21.4 +1"], "9.8 млн", "494", "Modrinth", ["#D97757", "#C6613F"]));
  res.appendChild(projectRow("Тихая гавань", "mira", "Уютное выживание: фермы, готовка, рыбалка и красивые деревни.", [["Fabric", "l-orange"]], ["Выживание", "Лёгкие", "1.21.1"], "1.4 млн", "3.2 тыс.", "Modrinth", ["#E8B23A", "#C08A2A"]));
  res.appendChild(projectRow("Острова", "archipel", "Генерация архипелагов, корабли и морские приключения.", [["Fabric", "l-orange"], ["NeoForge", "l-red"]], ["Исследование", "Приключения", "1.19.4 +1"], "838 тыс.", "8.9 тыс.", "Modrinth", ["#7BA05B", "#4E7A50"]));
  place(f);
}

// Мои сборки
{
  const [f, b] = shell("Мои сборки", 1);
  b.appendChild(txt("Сборки · Мои сборки", {family: SERIF, size: 28}));
  const g = al("HORIZONTAL", {name: "Grid", gap: 14});
  for (const [n, l, lc, v, c1, c2, on] of [["Арканум", "NeoForge", "l-red", "1.20.1", "#D97757", "#C6613F", false], ["Выживание с друзьями", "Forge", "l-blue", "1.20.1", "#5DAFC4", "#3B8A9F", false], ["Тихая гавань", "Fabric", "l-orange", "1.21.1", "#E8B23A", "#C08A2A", true]]) {
    const c = al("VERTICAL", {name: n, gap: 6, pad: [14, 14, 12, 14], radius: 14, fill: "card", stroke: on ? "accent" : "border"}); if (on) c.strokeWeight = 2;
    c.resize(236, 210); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED";
    c.appendChild(blockIcon(56, c1, c2, n[0])); c.appendChild(txt(n, {family: SERIF, size: 16}));
    const t = al("HORIZONTAL", {name: "Tags", gap: 4}); t.appendChild(tagEl(l, lc)); t.appendChild(tagEl(v)); c.appendChild(t);
    const bb = al("HORIZONTAL", {name: "Buttons", gap: 6}); bb.appendChild(btn("▶ Играть", "accent")); bb.appendChild(btn(on ? "Выбрана" : "Выбрать")); c.appendChild(bb); g.appendChild(c);
  }
  const add = al("VERTICAL", {name: "Create", radius: 14, fill: "panel", stroke: "faint", align: "CENTER"}); add.dashPattern = [3, 3]; add.resize(236, 210); add.primaryAxisSizingMode = "FIXED"; add.counterAxisSizingMode = "FIXED"; add.primaryAxisAlignItems = "CENTER"; add.appendChild(txt("+\nСоздать сборку", {color: "muted"})); g.appendChild(add);
  b.appendChild(g);
  place(f);
}

// Аккаунты
{
  const [f, b] = shell("Аккаунты", 2);
  const hd = al("HORIZONTAL", {name: "Head", align: "CENTER"}); hd.resize(1006, 40); hd.primaryAxisSizingMode = "FIXED"; hd.primaryAxisAlignItems = "SPACE_BETWEEN"; hd.appendChild(txt("Аккаунты", {family: SERIF, size: 28})); hd.appendChild(btn("+ Добавить аккаунт", "accent")); b.appendChild(hd);
  b.appendChild(txt("Выберите, под каким ником играть. Скин и вход через Microsoft появятся позже.", {color: "muted"}));
  for (const [n, on, sk, hr] of [["Hoka_Neko", true, "#E0AC84", "#5A3A22"], ["Steve_09", false, "#F2C6A0", "#3A2618"], ["Alex", false, "#E0AC84", "#D9A441"]]) {
    const c = al("HORIZONTAL", {name: n, gap: 14, pad: [12, 14, 12, 14], radius: 14, fill: "card", stroke: on ? "accent" : "border", align: "CENTER"}); if (on) c.strokeWeight = 2;
    c.resize(1006, 40); c.primaryAxisSizingMode = "FIXED"; c.appendChild(head(52, sk, hr));
    const t = al("VERTICAL", {name: "Text", gap: 2}); t.layoutGrow = 1; t.appendChild(txt(n + (on ? "   · Выбран" : ""), {family: SERIF, size: 16})); t.appendChild(txt("Оффлайн-аккаунт", {color: "muted"})); c.appendChild(t);
    if (!on) c.appendChild(btn("Выбрать")); c.appendChild(txt("⧉   🗑", {color: "muted"})); b.appendChild(c);
  }
  place(f);
}

// Новый аккаунт
{
  const f = frame("Новый аккаунт", 460, 280);
  const b = al("VERTICAL", {name: "Dialog", gap: 10, pad: [18, 22, 18, 22]}); b.resize(460, 280); b.primaryAxisSizingMode = "FIXED"; b.counterAxisSizingMode = "FIXED"; f.appendChild(b);
  b.appendChild(txt("Новый аккаунт", {family: SERIF, size: 18}));
  const sg = al("HORIZONTAL", {name: "Tabs", gap: 0}); const a1 = al("HORIZONTAL", {name: "Offline", pad: [5, 12, 5, 12], fill: "selected", stroke: "accent"}); a1.appendChild(txt("Оффлайн")); sg.appendChild(a1);
  const a2 = al("HORIZONTAL", {name: "Microsoft", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a2.appendChild(txt("Microsoft · скоро", {color: "faint"})); sg.appendChild(a2); b.appendChild(sg);
  const card = al("HORIZONTAL", {name: "Card", gap: 14, pad: 14, radius: 14, fill: "card", stroke: "border"}); card.resize(416, 40); card.primaryAxisSizingMode = "FIXED";
  card.appendChild(head(64, "#F6D5B8", "#6B4A7A")); const cc = al("VERTICAL", {name: "Fields", gap: 4}); cc.layoutGrow = 1; cc.appendChild(txt("Ник"));
  const fld = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "accent"}); fld.resize(300, 26); fld.primaryAxisSizingMode = "FIXED"; fld.appendChild(txt("Kotik_228")); cc.appendChild(fld);
  cc.appendChild(txt("Ник свободен ✓", {size: 11, color: "done"})); cc.appendChild(txt("UUID: e4b41c70-7c8c-3535-8b63-3e0155c4a91c", {size: 11, color: "muted"})); card.appendChild(cc); b.appendChild(card);
  const rr = al("HORIZONTAL", {name: "Buttons", gap: 8}); rr.appendChild(btn("Отмена")); rr.appendChild(btn("Создать", "accent")); b.appendChild(rr);
  place(f);
}

// Настройки
{
  const [f, b] = shell("Настройки", 3);
  b.itemSpacing = 10;
  b.appendChild(txt("Настройки", {family: SERIF, size: 28}));
  const sec = t => b.appendChild(txt(t, {family: SERIF, size: 16}));
  const row = (t, v) => { const r = al("HORIZONTAL", {name: t, gap: 10, align: "CENTER"}); r.resize(1006, 28); r.primaryAxisSizingMode = "FIXED"; const l = txt(t); l.resize(230, l.height); l.textAutoResize = "HEIGHT"; r.appendChild(l); const fl = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); fl.layoutGrow = 1; fl.appendChild(txt(v)); r.appendChild(fl); b.appendChild(r); };
  sec("▣  Игра"); row("Папка игры", "~/Library/Application Support/Eta/minecraft"); row("Оперативная память", "━━━━━━●──────────  4 ГБ из 16 ГБ"); row("Java", "Автоматически (подходящая Java для версии игры)"); row("Аргументы JVM", "-XX:+UseG1GC"); row("Размер окна игры", "1280 × 720");
  sec("⚙  Лаунчер"); row("Тема", "Как в системе"); row("Язык", "Русский"); b.appendChild(txt("☐ Сворачивать лаунчер, когда игра запущена")); b.appendChild(txt("☐ Показывать консоль игры"));
  sec("⤓  Загрузки"); row("Источник по умолчанию", "Modrinth"); row("Одновременных загрузок", "6");
  place(f);
}
return {screens: page.children.length};
