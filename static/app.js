// ---------- Réglages ----------
const COULEURS = { Orange: "#FF7900", SFR: "#E2001A", Bouygues: "#0091D5", Free: "#2B2E33" };
const COURT = {
  "Très bonne couverture": "Très bonne", "Bonne couverture": "Bonne",
  "Couverture limitée": "Limitée", "Pas de couverture": "Aucune", "Données absentes": "—",
};

const $ = (id) => document.getElementById(id);
const champ = $("adresse"), liste = $("suggestions");
let carte = null, couches = {};

// Pour afficher du texte venant de l'API sans risque dans du HTML
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nombre = (v, unite) => (v === null ? "—" : `${Math.round(v)} ${unite}`);


// ---------- 1) Autocomplétion de l'adresse ----------
let minuteur, choix = -1;

champ.addEventListener("input", () => {
  clearTimeout(minuteur);
  minuteur = setTimeout(async () => {
    const texte = champ.value.trim();
    if (texte.length < 3) return (liste.innerHTML = "");
    const adresses = await (await fetch(`/api/adresses?q=${encodeURIComponent(texte)}`)).json();
    liste.innerHTML = adresses.map((a) => `<li>${esc(a)}</li>`).join("");
    choix = -1;
  }, 250);  // on attend que l'utilisateur arrête de taper
});

liste.addEventListener("mousedown", (e) => {
  if (e.target.tagName === "LI") { champ.value = e.target.textContent; lancer(); }
});

// Flèches haut/bas pour choisir une suggestion au clavier
champ.addEventListener("keydown", (e) => {
  const items = liste.querySelectorAll("li");
  if (!items.length || !["ArrowDown", "ArrowUp"].includes(e.key)) return;
  e.preventDefault();
  choix = (choix + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
  items.forEach((li, i) => li.classList.toggle("actif", i === choix));
  champ.value = items[choix].textContent;
});

champ.addEventListener("blur", () => setTimeout(() => (liste.innerHTML = ""), 150));
$("form").addEventListener("submit", (e) => { e.preventDefault(); lancer(); });


// ---------- 2) Appel à l'API ----------
async function lancer() {
  const adresse = champ.value.trim();
  if (!adresse) return;
  liste.innerHTML = "";
  $("erreur").textContent = "";
  $("chargement").hidden = false;

  try {
    const reponse = await fetch(`/api/score?adresse=${encodeURIComponent(adresse)}`);
    const data = await reponse.json();
    if (!reponse.ok) throw new Error(data.erreur);
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

  $("telephones").innerHTML = data.operateurs.map(telephone).join("");

  const moinsCher = data.moins_cher
    ? `Envie de payer moins ? <b>${data.moins_cher}</b> utilise exactement le même réseau.`
    : "Free est déjà l'un des opérateurs les moins chers.";
  $("conseil").innerHTML = `
    <div><div class="grand">Chez toi, prends <em>${data.gagnant}</em>.</div><p>${moinsCher}</p></div>
    <a href="#methode">Voir pourquoi ↓</a>`;

  radar(data);
  $("resultats").scrollIntoView({ behavior: "smooth" });
}

// Un téléphone = un opérateur (barres de réseau calculées à partir du score)
function telephone(op, i) {
  const barres = op.score >= 80 ? 4 : op.score >= 65 ? 3 : op.score >= 50 ? 2 : 1;
  const signal = [30, 55, 80, 100]
    .map((h, b) => `<i class="${b < barres ? "" : "off"}" style="height:${h}%"></i>`).join("");
  const heure = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

  return `
  <div class="tel ${i === 0 ? "gagnant" : ""}" style="--c:${COULEURS[op.nom]}">
    ${i === 0 ? '<span class="badge">Le meilleur ici</span>' : ""}
    <div class="encoche"></div>
    <div class="ecran">
      <div class="statut"><span>${heure}</span>
        <span class="droite"><span class="reseau">${op.nb_sites_5g > 0 ? "5G" : "4G"}</span><span class="signal">${signal}</span></span>
      </div>
      <div class="corps">
        <div class="op">${op.nom}</div>
        <div class="rang">${i === 0 ? "1er" : `${i + 1}e`} sur 4</div>
        <div class="compteur"><b>${op.score}</b><span>score / 100</span></div>
        <div class="lignes">
          <div>Débit mesuré<b>${nombre(op.debit, "Mb/s")}</b></div>
          <div>Tests réussis<b>${nombre(op.taux, "%")}</b></div>
          <div>Couverture 4G<b>${COURT[op.couverture_4g] ?? esc(op.couverture_4g)}</b></div>
          <div>Antenne la + proche<b>${nombre(op.plus_proche_m, "m")}</b></div>
        </div>
      </div>
    </div>
  </div>`;
}

// La carte : cercles de distance + 1 calque par opérateur (pour les filtres)
function radar(data) {
  const centre = [data.latitude, data.longitude];
  if (!carte) {
    carte = L.map("carte", { scrollWheelZoom: false });
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      { attribution: "© OpenStreetMap © CARTO", maxZoom: 19 }).addTo(carte);
  }
  carte.eachLayer((c) => { if (!(c instanceof L.TileLayer)) carte.removeLayer(c); });
  carte.setView(centre, 15);

  [250, 500, 1000].forEach((r) => L.circle(centre,
    { radius: r, color: "#111418", weight: 1.2, dashArray: r < 1000 ? "3 6" : null, fill: false, interactive: false }).addTo(carte));

  couches = {};
  for (const nom of Object.keys(COULEURS)) couches[nom] = L.layerGroup().addTo(carte);
  for (const a of data.antennes) {
    L.circleMarker([a.lat, a.lon], {
      radius: a.techno === "5G" ? 8 : 6, color: "#111418", weight: 1.5,
      fillColor: COULEURS[a.operateur], fillOpacity: 1,
    }).bindTooltip(`${a.operateur} · ${a.techno}`).addTo(couches[a.operateur]);
  }
  L.marker(centre, { icon: L.divIcon({ className: "", html: '<div class="moi"></div>', iconSize: [22, 22] }) })
    .bindTooltip(esc(data.adresse)).addTo(carte);

  // Boutons de filtre
  const compte = (nom) => data.antennes.filter((a) => a.operateur === nom).length;
  $("filtres").innerHTML = data.operateurs
    .map((op) => `<button data-op="${op.nom}" style="--c:${COULEURS[op.nom]}">${op.nom} · ${compte(op.nom)}</button>`).join("");
  $("filtres").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    const cache = b.classList.toggle("off");
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
