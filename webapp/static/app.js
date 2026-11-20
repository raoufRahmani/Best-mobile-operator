// ---------- Réglages ----------
const COULEURS = { Orange: "#FF7900", SFR: "#E2001A", Bouygues: "#0091D5", Free: "#B4BAC6" };
const COURT = {
  "Très bonne couverture": "Très bonne", "Bonne couverture": "Bonne",
  "Couverture limitée": "Limitée", "Pas de couverture": "Aucune", "Données absentes": "—",
};
const NIVEAU_COUVERTURE = { "Très bonne": 100, "Bonne": 66, "Limitée": 33 };

const $ = (id) => document.getElementById(id);
const champ = $("adresse"), liste = $("suggestions");
let carte = null, couches = {};

// Pour afficher du texte venant de l'API sans risque dans du HTML
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nombre = (v, unite) => (v === null ? "—" : `${Math.round(v)} ${unite}`);


// ---------- 1) Autocomplétion de l'adresse ----------
let minuteur, choix = -1;

function montrerSuggestions(adresses) {
  liste.innerHTML = adresses.map((a, i) => `<li role="option" id="sugg-${i}">${esc(a)}</li>`).join("");
  champ.setAttribute("aria-expanded", adresses.length > 0);
  choix = -1;
}

champ.addEventListener("input", () => {
  clearTimeout(minuteur);
  minuteur = setTimeout(async () => {
    const texte = champ.value.trim();
    if (texte.length < 3) return montrerSuggestions([]);
    const adresses = await (await fetch(`/api/adresses?q=${encodeURIComponent(texte)}`)).json();
    montrerSuggestions(adresses);
  }, 250);  // on attend que l'utilisateur arrête de taper
});

liste.addEventListener("mousedown", (e) => {
  if (e.target.tagName === "LI") { champ.value = e.target.textContent; lancer(); }
});

// Flèches haut/bas pour choisir une suggestion au clavier, Échap pour fermer
champ.addEventListener("keydown", (e) => {
  if (e.key === "Escape") return montrerSuggestions([]);
  const items = liste.querySelectorAll("li");
  if (!items.length || !["ArrowDown", "ArrowUp"].includes(e.key)) return;
  e.preventDefault();
  choix = (choix + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
  items.forEach((li, i) => li.classList.toggle("actif", i === choix));
  champ.setAttribute("aria-activedescendant", items[choix].id);
  champ.value = items[choix].textContent;
});

champ.addEventListener("blur", () => setTimeout(() => montrerSuggestions([]), 150));
$("form").addEventListener("submit", (e) => { e.preventDefault(); lancer(); });

// Les exemples sous le champ : un clic = une recherche
$("exemples").addEventListener("click", (e) => {
  if (e.target.dataset.adresse) { champ.value = e.target.dataset.adresse; lancer(); }
});


// Lien partagé (…/?adresse=…) : on lance directement la recherche
const adresseLien = new URLSearchParams(location.search).get("adresse");
if (adresseLien) { champ.value = adresseLien; setTimeout(lancer); }


// ---------- 2) Appel à l'API ----------
async function lancer() {
  const adresse = champ.value.trim();
  if (!adresse) return;
  montrerSuggestions([]);
  $("erreur").textContent = "";
  $("chargement").hidden = false;

  try {
    const reponse = await fetch(`/api/score?adresse=${encodeURIComponent(adresse)}`);
    const data = await reponse.json();
    if (!reponse.ok) throw new Error(data.erreur);
    history.replaceState(null, "", `?adresse=${encodeURIComponent(adresse)}`);  // lien partageable
    afficher(data);
  } catch (err) {
    $("erreur").textContent = err.message === "Adresse introuvable"
      ? "Adresse introuvable, vérifie l'orthographe."
      : "Oups, le serveur ne répond pas. Réessaie dans un instant.";
  } finally {
    $("chargement").hidden = true;
  }
}


// ---------- 3) Affichage ----------
function afficher(data) {
  $("resultats").hidden = false;
  const nbAntennes = data.antennes.length;
  $("lieu").textContent = `${data.adresse} · ${nbAntennes} antenne${nbAntennes > 1 ? "s" : ""} à moins d'1 km`;

  // Les meilleures valeurs des 4 opérateurs : les petites barres de chaque carte s'y comparent
  const ops = data.operateurs;
  const max = {
    debit: Math.max(...ops.map((o) => o.debit ?? 0)) || 1,
    proche: Math.min(...ops.map((o) => o.plus_proche_m ?? Infinity)),
  };
  $("telephones").innerHTML = ops.map((op, i) => carteOperateur(op, i, max)).join("");
  $("conseil").innerHTML = verdict(data);

  radar(data);
  if (window.animerResultats) animerResultats();   // animations.js (GSAP + Lenis), si chargé
  else $("resultats").scrollIntoView({ behavior: "smooth" });
}

// Le grand bandeau du verdict, avec l'écart avec le 2e
function verdict(data) {
  const [premier, second] = data.operateurs;
  const ecart = premier.score - second.score;
  const detail = ecart <= 2
    ? `Ça se joue à très peu : ${esc(second.nom)} est juste derrière (${second.score}/100).`
    : `${ecart} points devant ${esc(second.nom)}, le 2e (${second.score}/100).`;
  const moinsCher = data.moins_cher
    ? `<span class="moins-cher">Moins cher, même réseau : <b>${esc(data.moins_cher)}</b></span>`
    : `<span class="moins-cher">Free est déjà l'un des opérateurs les moins chers</span>`;
  return `
    <div class="verdict-score" style="--s:${premier.score}"><b>${premier.score}</b></div>
    <div>
      <div class="grand"><em>${esc(data.gagnant)}</em></div>
      <p>${detail}</p>
      ${moinsCher}
    </div>
    <a href="#methode">Voir le calcul ↓</a>`;
}

// Une carte = un opérateur : score, détail du score, mesures comparées au meilleur des 4
function carteOperateur(op, i, max) {
  const barres = op.score >= 80 ? 4 : op.score >= 65 ? 3 : op.score >= 50 ? 2 : 1;
  const signal = [30, 55, 80, 100]
    .map((h, b) => `<i class="${b < barres ? "" : "off"}" style="height:${h}%"></i>`).join("");
  const couverture = COURT[op.couverture_4g] ?? esc(op.couverture_4g);
  const ligne = (nom, valeur, pourcent) =>
    `<div>${nom}<b>${valeur}</b><s style="--w:${Math.max(0, Math.min(100, pourcent || 0))}%"></s></div>`;

  return `
  <article class="op-carte ${i === 0 ? "gagnant" : ""}" style="--c:${COULEURS[op.nom]}">
    ${i === 0 ? '<span class="badge">Le meilleur ici</span>' : ""}
    <div class="op-haut">
      <h3 class="op-nom">${op.nom}</h3>
      <span class="op-reseau">${op.nb_sites_5g > 0 ? "5G" : "4G"}<span class="signal" aria-hidden="true">${signal}</span></span>
    </div>
    <div class="op-rang">${i === 0 ? "1er" : `${i + 1}e`} sur 4</div>
    <div class="compteur"><b>${op.score}</b><span>/ 100</span></div>
    ${jauge(op.points)}
    <div class="mesures">
      ${ligne("Débit mesuré", nombre(op.debit, "Mb/s"), (op.debit / max.debit) * 100)}
      ${ligne("Tests réussis", nombre(op.taux, "%"), op.taux)}
      ${ligne("Couverture 4G", couverture, NIVEAU_COUVERTURE[couverture])}
      ${ligne("Antenne la + proche", nombre(op.plus_proche_m, "m"), op.plus_proche_m ? (max.proche / op.plus_proche_m) * 100 : 0)}
    </div>
  </article>`;
}

// Le détail du score : 1 morceau de barre par critère, de la largeur des points gagnés (sur 100)
const CRITERES = {
  note_couverture: ["p-couverture", "Couverture 4G", 30], note_reussite: ["p-reussite", "Tests réussis", 30],
  note_debit: ["p-debit", "Débit", 20], note_5g: ["p-5g", "5G rapide", 10], note_proximite: ["p-proximite", "Distance", 10],
};
function jauge(points) {
  const morceaux = Object.entries(CRITERES).map(([note, [classe, nom, max]]) =>
    `<i class="${classe}" style="width:${points[note]}%" title="${nom} : ${Math.round(points[note])} / ${max} points"></i>`);
  return `<div class="jauge" role="img" aria-label="Détail du score">${morceaux.join("")}</div>`;
}

// La carte : cercles de distance + 1 calque par opérateur (pour les filtres)
function radar(data) {
  const centre = [data.latitude, data.longitude];
  if (!carte) {
    carte = L.map("carte", { scrollWheelZoom: false });
    // Fond de carte : le Plan IGN (gratuit, sans clé ; CARTO demande désormais une clé), assombri en CSS
    L.tileLayer("https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" +
      "&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",
      { attribution: "© IGN – Géoplateforme", maxZoom: 19, className: "fond-sombre" }).addTo(carte);
  }
  carte.eachLayer((c) => { if (!(c instanceof L.TileLayer)) carte.removeLayer(c); });
  carte.setView(centre, 15);

  [250, 500, 1000].forEach((r) => L.circle(centre,
    { radius: r, color: "#94A3B8", opacity: .6, weight: 1.2, dashArray: r < 1000 ? "3 6" : null, fill: false, interactive: false }).addTo(carte));

  couches = {};
  for (const nom of Object.keys(COULEURS)) couches[nom] = L.layerGroup().addTo(carte);
  for (const a of data.antennes) {
    L.circleMarker([a.lat, a.lon], {
      radius: a.techno === "5G" ? 8 : 6, color: "#070B14", weight: 1.5,
      fillColor: COULEURS[a.operateur], fillOpacity: 1,
    }).bindTooltip(`${a.operateur} · ${a.techno}`).addTo(couches[a.operateur]);
  }
  L.marker(centre, { icon: L.divIcon({ className: "", html: '<div class="moi"></div>', iconSize: [22, 22] }) })
    .bindTooltip(esc(data.adresse)).addTo(carte);

  // Boutons de filtre
  const compte = (nom) => data.antennes.filter((a) => a.operateur === nom).length;
  $("filtres").innerHTML = data.operateurs
    .map((op) => `<button type="button" aria-pressed="true" data-op="${op.nom}" style="--c:${COULEURS[op.nom]}">${op.nom} · ${compte(op.nom)}</button>`).join("");
  $("filtres").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    const cache = b.classList.toggle("off");
    b.setAttribute("aria-pressed", !cache);
    cache ? carte.removeLayer(couches[b.dataset.op]) : couches[b.dataset.op].addTo(carte);
  }));

  // Chiffres clés à côté de la carte
  const proche = [...data.operateurs].filter((o) => o.plus_proche_m !== null)
    .sort((a, b) => a.plus_proche_m - b.plus_proche_m)[0];
  const nb5g = data.operateurs.reduce((s, o) => s + o.nb_sites_5g_3500, 0);
  const date = data.derniere_mise_en_service
    ? new Date(data.derniere_mise_en_service + "-01").toLocaleDateString("fr-FR", { month: "short", year: "numeric" })
    : "—";
  $("distances").innerHTML = `
    <div>Antenne la plus proche<b>${proche ? `${proche.nom} · ${Math.round(proche.plus_proche_m)} m` : "—"}</b></div>
    <div>Antennes 5G rapide (3,5 GHz)<b>${nb5g}</b></div>
    <div>Dernière mise en service<b>${date}</b></div>`;

  setTimeout(() => carte.invalidateSize(), 50);  // la carte était cachée : on recalcule sa taille
}
