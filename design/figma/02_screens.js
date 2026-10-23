// Эта (Eta) — Screens page: Загрузка, Главная (Light / Dark), Главная — стекло (панель справа, свёрнута), Сборки —
// каталог, Мои сборки, Аккаунты, Новый аккаунт (оффлайн / mc-ru.org / Microsoft), Запуск (подготовка / игра запущена), Настройки (с «Оформлением»),
// Серверы (список серверов сообщества с mc-ru.org: иконка, адрес, версия, MOTD, онлайн, «Играть»).
// Run after 01_ui_kit.js.
let page = figma.root.children.find(p => p.name === "Screens");
if (!page) { page = figma.createPage(); page.name = "Screens"; }
await figma.setCurrentPageAsync(page);
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
const MONO = ["JetBrains Mono", "Roboto Mono", "Source Code Pro", "Menlo"].find(f => has(f, "Regular")) || "Inter";
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
  for (const [i, t] of ["⌂  Главная", "▣  Сборки", "☺  Аккаунты", "⚙  Настройки", "▤  Серверы"].entries()) { const b = al("HORIZONTAL", {name: t, pad: [7, 10, 7, 10], radius: 7, fill: i === active ? "selected" : null}); b.resize(186, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); s.appendChild(b); }
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
// compact hero card (eta/ui.py Hero, height 132): icon, title + meta + picker / folder, Play on the right
function heroCard(dark, w = 1006, accent = "accent") {
  const hero = figma.createFrame(); hero.name = "Hero"; hero.resize(w, 132); hero.cornerRadius = 18; hero.clipsContent = true;
  hero.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {...hex(dark ? "#1F2438" : "#A8D4DE"), a: 1}}, {position: 1, color: {...hex(dark ? "#3B4A6B" : "#5DAFC4"), a: 1}}]}];
  for (let i = 0; i < Math.ceil(w / 24); i++) { const h = 40 + ((i * 37) % 5) * 14; const r = figma.createRectangle(); r.resize(24, h); r.x = i * 24; r.y = 132 - h; r.fills = [{type: "SOLID", color: hex(i % 3 ? "#5E8A48" : "#7BA05B")}]; hero.appendChild(r); }
  const shade = figma.createRectangle(); shade.resize(w, 132); shade.fills = [{type: "SOLID", color: {r: 0, g: 0, b: 0}, opacity: 0.45}]; hero.appendChild(shade);
  hero.appendChild(blockIcon(76, "#E8B23A", "#C08A2A", "Т")).x = 22; hero.children[hero.children.length - 1].y = 28;
  const tc = al("VERTICAL", {name: "Text", gap: 4}); hero.appendChild(tc); tc.x = 114; tc.y = 22;
  tc.appendChild(txt("Тихая гавань", {family: SERIF, size: 30, color: "white"})); tc.appendChild(txt("Fabric 1.21.1 · 96 модов · в игре 3 ч 12 мин", {style: "Semi Bold", color: "white"}));
  const acts = al("HORIZONTAL", {name: "Picker + folder", gap: 6, align: "CENTER"}); const pk = al("HORIZONTAL", {name: "Picker", pad: [6, 10, 6, 10], radius: 8, fill: "white"}); pk.resize(220, 30); pk.primaryAxisSizingMode = "FIXED"; pk.appendChild(txt("Тихая гавань  ▾", {color: "ink"})); acts.appendChild(pk);
  const fo = al("HORIZONTAL", {name: "Folder", pad: [6, 10, 6, 10], radius: 8}); fo.fills = [{type: "SOLID", color: {r: 1, g: 1, b: 1}, opacity: 0.18}]; fo.appendChild(txt("🗀", {color: "white"})); acts.appendChild(fo); tc.appendChild(acts);
  const pl = al("HORIZONTAL", {name: "Play", pad: [10, 30, 10, 30], radius: 10, fill: accent}); pl.appendChild(txt("▶  Играть", {size: 16, style: "Semi Bold", color: "on-accent"})); hero.appendChild(pl); pl.x = w - pl.width - 22; pl.y = 46;
  return hero;
}
// icon rail — the side bar when it is hidden (« / » or ⌘\)
function rail() {
  const r = al("VERTICAL", {name: "Rail", gap: 10, pad: [16, 10, 14, 10], fill: "sidebar", align: "CENTER"}); r.resize(56, 820); r.primaryAxisSizingMode = "FIXED"; r.counterAxisSizingMode = "FIXED";
  r.appendChild(txt("η", {family: SERIF, style: SERIF_I, size: 26, color: "accent"})); r.appendChild(txt("»", {color: "muted"}));
  for (const [i, t] of ["⌂", "▣", "☺", "⚙", "▤"].entries()) { const b = al("HORIZONTAL", {name: t, pad: [6, 9, 6, 9], radius: 8, fill: i === 0 ? "selected" : null}); b.appendChild(txt(t)); r.appendChild(b); }
  const sp = figma.createFrame(); sp.fills = []; sp.resize(10, 10); sp.layoutGrow = 1; r.appendChild(sp); r.appendChild(head(30));
  return r;
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
  b.appendChild(heroCard(mode === "Dark"));
  b.appendChild(txt("НЕДАВНИЕ СБОРКИ", {size: 10, style: "Semi Bold", color: "muted"}));
  const rec = al("HORIZONTAL", {name: "Recent", gap: 12});
  for (const [n, v, c1, c2] of [["Тихая гавань", "Fabric 1.21.1", "#E8B23A", "#C08A2A"], ["Арканум", "NeoForge 1.20.1", "#D97757", "#C6613F"], ["Выживание с друзьями", "Forge 1.20.1", "#5DAFC4", "#3B8A9F"]]) {
    const m = al("HORIZONTAL", {name: n, gap: 8, pad: [8, 12, 8, 10], radius: 12, fill: "card", stroke: "border", align: "CENTER"}); m.appendChild(blockIcon(36, c1, c2, n[0]));
    const mc = al("VERTICAL", {name: "Text", gap: 0}); mc.appendChild(txt(n, {family: SERIF, size: 15})); mc.appendChild(txt(v, {size: 11, color: "muted"})); m.appendChild(mc); rec.appendChild(m);
  }
  b.appendChild(rec);
  // Серверы сообщества (eta/ui.py HomePage.render_servers + MiniServerCard): до 4 компактных карточек и «Все серверы →»
  b.appendChild(txt("СЕРВЕРЫ СООБЩЕСТВА", {size: 10, style: "Semi Bold", color: "muted"}));
  const srv = al("HORIZONTAL", {name: "Servers", gap: 12});
  for (const [n, st, motd, c1, c2] of [["Лобби", "● 42/200 онлайн · 38 мс", "Добро пожаловать на mc-ru.org", "#5DAFC4", "#3B8A9F"], ["Ферма", "● 7/50 онлайн · 51 мс", "Выживание 1.20.1, без грифа", "#8BC34A", "#5E9A2E"], ["Креатив", "● офлайн", "Стройки и ивенты", "#D97757", "#C6613F"]]) {
    const m = al("HORIZONTAL", {name: n, gap: 10, pad: [8, 10, 8, 10], radius: 12, fill: "card", stroke: "border", align: "CENTER"}); m.resize(300, 64); m.primaryAxisSizingMode = "FIXED";
    m.appendChild(blockIcon(40, c1, c2, n[0]));
    const mc = al("VERTICAL", {name: "Text", gap: 0}); mc.appendChild(txt(n, {family: SERIF, size: 15})); mc.appendChild(txt(st, {size: 11, color: st.includes("офлайн") ? "muted" : "accent"})); mc.appendChild(txt(motd, {size: 11, color: "muted"})); mc.layoutGrow = 1; m.appendChild(mc);
    m.appendChild(btn("▶  Играть", "accent")); srv.appendChild(m);
  }
  b.appendChild(srv);
  b.appendChild(txt("Все серверы →", {size: 12, color: "accent"}));
  b.appendChild(txt("НОВОСТИ ЛАУНЧЕРА", {size: 10, style: "Semi Bold", color: "muted"}));
  const nw = al("HORIZONTAL", {name: "News", gap: 12});
  for (const [t, d] of [["Modrinth подключён", "Сборки ставятся в один клик со всеми модами."], ["Своё оформление", "Акцент, фон и стекло — в Настройках."], ["Оффлайн-аккаунты", "Играйте с любым ником."]]) {
    const c = al("VERTICAL", {name: t, gap: 4, pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border"}); c.resize(326, 96); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED";
    c.appendChild(txt(t, {family: SERIF, size: 16})); c.appendChild(txt(d, {color: "muted", w: 294})); nw.appendChild(c);
  }
  b.appendChild(nw);
  place(f);
}
MODE = "Light";

// Главная — стекло: картинка «Сияние» на фоне (размыта), полупрозрачные панели, акцент «Океан», панель справа свёрнута
{
  const f = frame("Главная — стекло, панель справа", 1280, 820); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  f.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {...hex("#2A2F4A"), a: 1}}, {position: 0.45, color: {...hex("#3E7A78"), a: 1}}, {position: 1, color: {...hex("#1A2030"), a: 1}}]}];
  const veil = figma.createRectangle(); veil.name = "Veil"; veil.resize(1280, 820); veil.fills = [{type: "SOLID", color: hex("#FAF9F5"), opacity: 0.58}]; f.appendChild(veil); veil.layoutPositioning = "ABSOLUTE";
  const body = al("VERTICAL", {name: "Page", gap: 14, pad: [26, 32, 26, 32]}); body.layoutGrow = 1; body.layoutAlign = "STRETCH"; f.appendChild(body);
  body.appendChild(txt("Доброе утро, Hoka_Neko", {family: SERIF, size: 28}));
  body.appendChild(heroCard(false, 1160, "l-blue"));
  const nw = al("HORIZONTAL", {name: "Glass cards", gap: 12});
  for (const t of ["Modrinth подключён", "Своё оформление", "Оффлайн-аккаунты"]) { const c = al("VERTICAL", {name: t, gap: 4, pad: [14, 16, 14, 16], radius: 14}); c.fills = [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.6}]; c.strokes = [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.38}]; c.resize(378, 96); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED"; c.appendChild(txt(t, {family: SERIF, size: 16})); nw.appendChild(c); }
  body.appendChild(nw);
  const r = rail(); r.fills = [{type: "SOLID", color: hex("#F0EEE6"), opacity: 0.47}]; f.appendChild(r);
  place(f);
}

// Сборки — каталог
{
  const [f, b] = shell("Сборки — каталог", 1);
  const hd = al("HORIZONTAL", {name: "Head", gap: 12, align: "CENTER"}); hd.appendChild(txt("Сборки", {family: SERIF, size: 28}));
  const s1 = al("HORIZONTAL", {name: "Tab catalog", pad: [5, 12, 5, 12], fill: "selected", stroke: "accent"}); s1.appendChild(txt("Каталог")); hd.appendChild(s1);
  const s2 = al("HORIZONTAL", {name: "Tab mine", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); s2.appendChild(txt("Мои сборки")); hd.appendChild(s2); b.appendChild(hd);
  const row = al("HORIZONTAL", {name: "Body", gap: 18}); b.appendChild(row);
  const fl = al("VERTICAL", {name: "Filters", gap: 6}); fl.resize(230, 40); fl.counterAxisSizingMode = "FIXED";
  fl.appendChild(txt("ИСТОЧНИК", {size: 10, style: "Semi Bold", color: "muted"})); fl.appendChild(txt("◉ Modrinth")); fl.appendChild(txt("○ CurseForge  (нужен API-ключ)"));
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
  b.appendChild(txt("Выберите, под каким ником играть. Аккаунт mc-ru.org приносит в игру скин и плащ; аккаунт Microsoft — лицензия и любые серверы.", {color: "muted"}));
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
  const a15 = al("HORIZONTAL", {name: "mc-ru.org", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a15.appendChild(txt("mc-ru.org")); sg.appendChild(a15);
  const a2 = al("HORIZONTAL", {name: "Microsoft", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a2.appendChild(txt("Microsoft")); sg.appendChild(a2); b.appendChild(sg);
  const card = al("HORIZONTAL", {name: "Card", gap: 14, pad: 14, radius: 14, fill: "card", stroke: "border"}); card.resize(416, 40); card.primaryAxisSizingMode = "FIXED";
  card.appendChild(head(64, "#F6D5B8", "#6B4A7A")); const cc = al("VERTICAL", {name: "Fields", gap: 4}); cc.layoutGrow = 1; cc.appendChild(txt("Ник"));
  const fld = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "accent"}); fld.resize(300, 26); fld.primaryAxisSizingMode = "FIXED"; fld.appendChild(txt("Kotik_228")); cc.appendChild(fld);
  cc.appendChild(txt("Ник свободен ✓", {size: 11, color: "done"})); cc.appendChild(txt("UUID: e4b41c70-7c8c-3535-8b63-3e0155c4a91c", {size: 11, color: "muted"})); card.appendChild(cc); b.appendChild(card);
  const rr = al("HORIZONTAL", {name: "Buttons", gap: 8}); rr.appendChild(btn("Отмена")); rr.appendChild(btn("Создать", "accent")); b.appendChild(rr);
  place(f);
}

// Новый аккаунт — mc-ru.org (вход на сайт: скин и плащ, HD и анимированные)
{
  const f = frame("Новый аккаунт — mc-ru.org", 460, 330);
  const b = al("VERTICAL", {name: "Dialog", gap: 10, pad: [18, 22, 18, 22]}); b.resize(460, 330); b.primaryAxisSizingMode = "FIXED"; b.counterAxisSizingMode = "FIXED"; f.appendChild(b);
  b.appendChild(txt("Новый аккаунт", {family: SERIF, size: 18}));
  const sg = al("HORIZONTAL", {name: "Tabs", gap: 0});
  const a1 = al("HORIZONTAL", {name: "Offline", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a1.appendChild(txt("Оффлайн")); sg.appendChild(a1);
  const a15 = al("HORIZONTAL", {name: "mc-ru.org", pad: [5, 12, 5, 12], fill: "selected", stroke: "accent"}); a15.appendChild(txt("mc-ru.org")); sg.appendChild(a15);
  const a2 = al("HORIZONTAL", {name: "Microsoft", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a2.appendChild(txt("Microsoft")); sg.appendChild(a2); b.appendChild(sg);
  const hint = txt("Аккаунт сайта mc-ru.org: скин и плащ (в том числе HD и анимированные) подтянутся в игру. Нет аккаунта? Зарегистрируйтесь на mc-ru.org", {size: 11, color: "muted"}); hint.resize(416, 32); hint.textAutoResize = "HEIGHT"; b.appendChild(hint);
  const card = al("VERTICAL", {name: "Card", gap: 6, pad: 14, radius: 14, fill: "card", stroke: "border"}); card.resize(416, 40); card.primaryAxisSizingMode = "FIXED";
  card.appendChild(txt("Ник или email"));
  const f1 = al("HORIZONTAL", {name: "Login", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); f1.resize(388, 26); f1.primaryAxisSizingMode = "FIXED"; f1.appendChild(txt("hoka@example.com")); card.appendChild(f1);
  card.appendChild(txt("Пароль"));
  const f2 = al("HORIZONTAL", {name: "Password", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "accent"}); f2.resize(388, 26); f2.primaryAxisSizingMode = "FIXED"; f2.appendChild(txt("••••••••")); card.appendChild(f2);
  card.appendChild(txt("Вход на mc-ru.org: скин и плащ подтянутся в игру.", {size: 11, color: "muted"})); b.appendChild(card);
  const rr = al("HORIZONTAL", {name: "Buttons", gap: 8}); rr.appendChild(btn("Отмена")); rr.appendChild(btn("Войти", "accent")); b.appendChild(rr);
  place(f);
}

// Новый аккаунт — Microsoft (код устройства: показать код, открыть microsoft.com/link, ждать подтверждения)
{
  const f = frame("Новый аккаунт — Microsoft (код устройства)", 460, 360);
  const b = al("VERTICAL", {name: "Dialog", gap: 10, pad: [18, 22, 18, 22]}); b.resize(460, 360); b.primaryAxisSizingMode = "FIXED"; b.counterAxisSizingMode = "FIXED"; f.appendChild(b);
  b.appendChild(txt("Новый аккаунт", {family: SERIF, size: 18}));
  const sg = al("HORIZONTAL", {name: "Tabs", gap: 0});
  const a1 = al("HORIZONTAL", {name: "Offline", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a1.appendChild(txt("Оффлайн")); sg.appendChild(a1);
  const a15 = al("HORIZONTAL", {name: "mc-ru.org", pad: [5, 12, 5, 12], fill: "card", stroke: "border"}); a15.appendChild(txt("mc-ru.org")); sg.appendChild(a15);
  const a2 = al("HORIZONTAL", {name: "Microsoft", pad: [5, 12, 5, 12], fill: "selected", stroke: "accent"}); a2.appendChild(txt("Microsoft")); sg.appendChild(a2); b.appendChild(sg);
  const hint = txt("Лицензионный аккаунт Microsoft: скин, плащ и доступ на любые серверы.", {size: 11, color: "muted"}); hint.resize(416, 16); hint.textAutoResize = "HEIGHT"; b.appendChild(hint);
  const card = al("VERTICAL", {name: "Card", gap: 8, pad: 14, radius: 14, fill: "card", stroke: "border"}); card.resize(416, 40); card.primaryAxisSizingMode = "FIXED";
  const intro = txt("Введите этот код на странице Microsoft и подтвердите вход:", {size: 11, color: "muted"}); intro.resize(388, 16); intro.textAutoResize = "HEIGHT"; card.appendChild(intro);
  const code = al("HORIZONTAL", {name: "DeviceCode", pad: [10, 14, 10, 14], radius: 10, fill: "input", stroke: "border", align: "CENTER"}); code.resize(388, 52); code.primaryAxisSizingMode = "FIXED"; code.primaryAxisAlignItems = "CENTER";
  code.appendChild(txt("ABCD-1234", {family: MONO, size: 26})); card.appendChild(code);
  const br = al("HORIZONTAL", {name: "Buttons", gap: 8}); br.appendChild(btn("Открыть microsoft.com/link")); br.appendChild(btn("Скопировать код")); card.appendChild(br);
  card.appendChild(txt("Ожидаем подтверждения… окно можно не закрывать, вход завершится сам.", {size: 11, color: "muted"})); b.appendChild(card);
  const rr = al("HORIZONTAL", {name: "Buttons", gap: 8}); rr.appendChild(btn("Отмена")); const w = btn("Войти через Microsoft", "accent"); w.opacity = 0.5; rr.appendChild(w); b.appendChild(rr);
  place(f);
}

// Запуск — подготовка (прогресс) и игра запущена (консоль)
for (const [name, stage, pct, detail, running] of [["Запуск — подготовка", "Ресурсы игры…", 0.7, "Ресурсы игры — 2 540 из 3 598", false], ["Запуск — игра запущена", "Игра запущена", 1, "Minecraft fabric-loader-0.16.9-1.21.1 · java-runtime-delta", true]]) {
  const f = frame(name, 560, running ? 520 : 250);
  const b = al("VERTICAL", {name: "Dialog", gap: 10, pad: [18, 22, 18, 22]}); b.resize(560, running ? 520 : 250); b.primaryAxisSizingMode = "FIXED"; b.counterAxisSizingMode = "FIXED"; f.appendChild(b);
  const hd = al("HORIZONTAL", {name: "Head", gap: 12, align: "CENTER"}); hd.appendChild(blockIcon(48, "#E8B23A", "#C08A2A", "Т")); const hc = al("VERTICAL", {name: "Text", gap: 2}); hc.appendChild(txt("Тихая гавань", {family: SERIF, size: 18})); hc.appendChild(txt("Fabric 1.21.1 · 96 модов · Hoka_Neko", {color: "muted"})); hd.appendChild(hc); b.appendChild(hd);
  b.appendChild(txt(stage, {family: SERIF, size: 16}));
  const bar = figma.createFrame(); bar.resize(516, 8); bar.cornerRadius = 4; bar.fills = [fill("border")]; const ch = figma.createRectangle(); ch.resize(516 * pct, 8); ch.cornerRadius = 4; ch.fills = [fill("accent")]; bar.appendChild(ch); b.appendChild(bar);
  b.appendChild(txt(detail, {size: 11, color: "muted"}));
  if (running) {
    const con = al("VERTICAL", {name: "Console", gap: 2, pad: 8, radius: 8, fill: "input", stroke: "border"}); con.resize(516, 230); con.primaryAxisSizingMode = "FIXED"; con.counterAxisSizingMode = "FIXED";
    for (const l of ["[eta] …/java -Xmx4096M -XstartOnFirstThread -cp … net.fabricmc.loader.impl.launch.knot.KnotClient --username Hoka_Neko", "[main/INFO]: Loading Minecraft 1.21.1 with Fabric Loader 0.16.9", "[main/INFO]: Loading 96 mods:", "[Render thread/INFO]: Setting user: Hoka_Neko", "[Render thread/INFO]: Backend library: LWJGL version 3.3.3", "[Render thread/INFO]: OpenAL initialized on device Built-in Output"]) con.appendChild(txt(l, {size: 11, color: "muted"}));
    b.appendChild(con);
  }
  const rr = al("HORIZONTAL", {name: "Buttons", gap: 8}); rr.appendChild(btn("Консоль")); rr.appendChild(btn("Папка сборки")); const sp = figma.createFrame(); sp.fills = []; sp.resize(10, 10); sp.layoutGrow = 1; rr.appendChild(sp); if (running) rr.appendChild(btn("Скрыть")); rr.appendChild(btn(running ? "Остановить игру" : "Отмена")); rr.layoutAlign = "STRETCH"; b.appendChild(rr);
  place(f);
}

// Настройки
{
  const [f, b] = shell("Настройки", 3);
  b.itemSpacing = 10;
  b.appendChild(txt("Настройки", {family: SERIF, size: 28}));
  const sec = t => b.appendChild(txt(t, {family: SERIF, size: 16}));
  const row = (t, v) => { const r = al("HORIZONTAL", {name: t, gap: 10, align: "CENTER"}); r.resize(1006, 28); r.primaryAxisSizingMode = "FIXED"; const l = txt(t); l.resize(230, l.height); l.textAutoResize = "HEIGHT"; r.appendChild(l); const fl = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); fl.layoutGrow = 1; fl.appendChild(txt(v)); r.appendChild(fl); b.appendChild(r); };
  sec("▤  Оформление"); row("Тема", "Как в системе");
  const sw = al("HORIZONTAL", {name: "Цвет акцента", gap: 6, align: "CENTER"}); sw.appendChild(txt("Цвет акцента                                          "));
  for (const [i, c] of ["#D97757", "#3F7FD0", "#4E8A57", "#9B6BC9", "#D9668F", "#E0A433", "#3FA7C9", "#55575E", "#D2453B", "#3BB08F"].entries()) { const e = figma.createEllipse(); e.resize(24, 24); e.fills = [{type: "SOLID", color: hex(c)}]; if (!i) { e.strokes = [fill("text")]; e.strokeWeight = 3; } sw.appendChild(e); }
  sw.appendChild(btn("Свой…")); b.appendChild(sw);
  const bgs = al("HORIZONTAL", {name: "Фон окна", gap: 6}); bgs.appendChild(txt("Фон окна                                                    "));
  for (const [a, c] of [["#FAF9F5", "#FAF9F5"], ["#F3D2B3", "#E58F6B"], ["#A8D4DE", "#5DAFC4"], ["#1F2438", "#3B4A6B"], ["#CFE0C8", "#8DB08A"], ["#2A2F4A", "#3E7A78"], ["#9B7BC4", "#6B4A7A"]]) { const t = figma.createRectangle(); t.resize(64, 40); t.cornerRadius = 6; t.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {...hex(a), a: 1}}, {position: 1, color: {...hex(c), a: 1}}]}]; bgs.appendChild(t); }
  bgs.appendChild(btn("+ Своя")); b.appendChild(bgs);
  b.appendChild(txt("☑ Стекло — полупрозрачные панели поверх размытого фона")); row("Плотность стекла", "━━━━━━━━━●────────"); row("Размытие фона", "━━━━━━●───────────");
  row("Заголовки", "С засечками (как у Claude)"); row("Боковая панель", "Слева  ·  скрыть — « / » или ⌘\\");
  sec("▣  Игра"); row("Папка игры", "~/Library/Application Support/Eta/minecraft"); row("Оперативная память", "━━━━━━●──────────  4 ГБ из 16 ГБ"); row("Java", "Автоматически (подходящая Java для версии игры)"); row("Аргументы JVM", "-XX:+UseG1GC"); row("Размер окна игры", "1280 × 720");
  b.appendChild(txt("☑ Косметика rurukaSuka (гардероб, руры) — системный мод: ставится в сборки Fabric/Quilt поддерживаемых версий"));
  sec("⚙  Лаунчер"); row("Язык", "Русский"); b.appendChild(txt("☐ Сворачивать лаунчер, когда игра запущена")); b.appendChild(txt("☐ Показывать консоль игры"));
  sec("⤓  Загрузки"); row("Источник по умолчанию", "Modrinth"); row("Одновременных загрузок", "6");
  place(f);
}
// Серверы — список серверов сообщества (eta/ui.py ServersPage; данные с mc-ru.org/api/servers, онлайн по Server List Ping)
{
  const [f, b] = shell("Серверы", 4);
  const hd = al("HORIZONTAL", {name: "Head", align: "CENTER"}); hd.resize(1006, 44); hd.primaryAxisSizingMode = "FIXED"; hd.primaryAxisAlignItems = "SPACE_BETWEEN";
  const tt = al("VERTICAL", {name: "Title", gap: 2}); tt.appendChild(txt("Серверы сообщества", {family: SERIF, size: 28})); tt.appendChild(txt("mc-ru.org", {color: "muted"})); hd.appendChild(tt); hd.appendChild(btn("↻  Обновить")); b.appendChild(hd);
  for (const [n, addr, ver, motd, st, ok, col] of [["Ферма", "play.mc-ru.org", "1.20.1", "Ферма — выживание без гриферов", "● 12/100 онлайн · 45 мс", true, "#7BA05B"], ["Лобби", "lobby.mc-ru.org:25566", "1.21", "Мини-игры, бедварс, паркур", "● 3/50 онлайн · 61 мс", true, "#5DAFC4"], ["Техно", "tech.mc-ru.org", "1.19.2", "Create + Applied Energistics", "● офлайн", false, "#C08A2A"]]) {
    const c = al("HORIZONTAL", {name: n, gap: 14, pad: [12, 14, 12, 14], radius: 14, fill: "card", stroke: "border", align: "CENTER"}); c.resize(1006, 40); c.primaryAxisSizingMode = "FIXED";
    c.appendChild(blockIcon(64, col, col, n[0]));
    const t = al("VERTICAL", {name: "Text", gap: 4}); t.layoutGrow = 1;
    const r1 = al("HORIZONTAL", {name: "Name", gap: 8, align: "CENTER"}); r1.appendChild(txt(n, {family: SERIF, size: 16})); const tg = al("HORIZONTAL", {name: "Tag", pad: [1, 8, 1, 8], radius: 9, stroke: "border"}); tg.appendChild(txt(ver, {size: 11, color: "muted"})); r1.appendChild(tg); t.appendChild(r1);
    const r2 = al("HORIZONTAL", {name: "Address", gap: 6, align: "CENTER"}); r2.appendChild(txt(addr, {color: "muted"})); r2.appendChild(btn("Копировать")); t.appendChild(r2);
    t.appendChild(txt(motd)); t.appendChild(txt(st, {size: 11, color: ok ? "done" : "muted"})); c.appendChild(t);
    c.appendChild(btn("▶  Играть", "accent")); b.appendChild(c);
  }
  place(f);
}

return {screens: page.children.length};
