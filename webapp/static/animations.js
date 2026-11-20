// animations.js — animations avec GSAP (+ ScrollTrigger) et défilement fluide avec Lenis.
// Rien ne casse sans lui : app.js revient au défilement normal.
(() => {
  // Pas d'animation si les librairies n'ont pas chargé, ou si l'utilisateur a demandé « moins d'animations »
  if (!window.gsap || !window.Lenis || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  gsap.registerPlugin(ScrollTrigger);

  // ---------- Défilement fluide (Lenis), synchronisé avec GSAP ----------
  const lenis = new Lenis({ duration: 1.1 });
  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((t) => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);

  // Liens internes (#radar, #methode, « Voir le calcul ») : défilement fluide aussi
  document.addEventListener("click", (e) => {
    const lien = e.target.closest('a[href^="#"]');
    if (lien && document.querySelector(lien.getAttribute("href"))) {
      e.preventDefault();
      lenis.scrollTo(lien.getAttribute("href"), { offset: -80 });
    }
  });

  // Apparition au défilement : monte + fondu, une fois
  const reveler = (cible, declencheur, extra = {}) => gsap.from(cible, {
    y: 28, opacity: 0, duration: .7, stagger: .08, ease: "power3.out",
    scrollTrigger: { trigger: declencheur, start: "top 85%" }, ...extra,
  });

  // ---------- Arrivée sur la page ----------
  gsap.timeline({ defaults: { ease: "power4.out" } })
    .from(".entete-site .conteneur > *", { y: -16, opacity: 0, duration: .6, stagger: .08 })
    .from(".hero-texte > *", { y: 36, opacity: 0, duration: .9, stagger: .09 }, "-=.3")
    .from(".radar-hero .cercles i", { scale: .4, opacity: 0, duration: .9, stagger: .07 }, "-=.9")
    .from(".radar-hero .blip", { scale: .6, opacity: 0, duration: .5, stagger: .1, ease: "back.out(2)" }, "-=.4")
    .from(".preuves > div", { y: 20, opacity: 0, duration: .6, stagger: .08 }, "-=.5");

  // Les chiffres des preuves défilent jusqu'à leur valeur
  document.querySelectorAll(".preuves dd").forEach((dd) => {
    const fin = parseInt(dd.textContent.replace(/\s/g, ""), 10);
    if (!fin || dd.textContent.includes("m")) return;          // « 100 m » reste tel quel
    const valeur = { n: 0 };
    gsap.to(valeur, { n: fin, duration: 1.8, delay: .8, ease: "power2.out",
      onUpdate: () => (dd.textContent = Math.round(valeur.n).toLocaleString("fr-FR")) });
  });

  // ---------- Section méthode ----------
  reveler(".methode .etiquette, .methode h2, .methode .intro", ".methode");
  gsap.from(".barre-poids div", {
    scaleY: 0, transformOrigin: "bottom", duration: .9, stagger: .08, ease: "power3.out",
    scrollTrigger: { trigger: ".barre-poids", start: "top 85%" },
  });
  reveler(".sources div", ".sources");

  // ---------- Résultats (appelé par app.js après chaque recherche) ----------
  let animation;                                             // l'animation de la recherche précédente
  window.animerResultats = () => {
    // Nouvelle recherche avant la fin de la précédente : on termine l'ancienne d'abord,
    // sinon les éléments repartent d'une opacité à moitié animée et le verdict reste invisible
    if (animation) animation.progress(1).kill();
    animation = gsap.timeline({ defaults: { ease: "power3.out" } })
      .from(".resultat .entete-section > *", { y: 24, opacity: 0, duration: .6, stagger: .08 })
      .from("#conseil", { y: 30, opacity: 0, scale: .98, duration: .7 }, "-=.3")
      .from(".verdict-score", { "--s": 0, duration: 1.2, ease: "power2.out" }, "-=.4")
      .from(".op-carte", { opacity: 0, scale: .92, y: 16, duration: .45, stagger: .07, ease: "back.out(1.4)" }, "-=1")
      .from(".jauge", { clipPath: "inset(0 100% 0 0)", duration: 1.1, stagger: .08, ease: "power2.inOut" }, "-=.4")
      .from(".mesures s", { opacity: 0, duration: .5, stagger: .02 }, "-=.9")
      .from(".op-carte.gagnant .badge", { scale: 0, duration: .5, ease: "back.out(2.5)" }, "-=.6")
      .from(".legende-points span", { opacity: 0, y: 8, duration: .4, stagger: .04 }, "-=.6");

    // Les scores défilent de 0 jusqu'à leur valeur
    document.querySelectorAll(".compteur b, .verdict-score b").forEach((b) => {
      const fin = +b.textContent, valeur = { n: 0 };
      gsap.to(valeur, { n: fin, duration: 1.4, delay: .4, ease: "power2.out",
        onUpdate: () => (b.textContent = Math.round(valeur.n)) });
    });

    // Le radar : les chiffres clés apparaissent quand on descend jusqu'à la carte
    gsap.from("#filtres button, #distances > div", {
      x: -20, opacity: 0, duration: .6, stagger: .06, ease: "power3.out",
      scrollTrigger: { trigger: "#radar", start: "top 75%", once: true },
    });

    ScrollTrigger.refresh();                                 // la page a changé de hauteur
    lenis.scrollTo("#resultats", { offset: -68, duration: 1.4 });
  };
})();
