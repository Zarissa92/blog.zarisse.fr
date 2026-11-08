/* ============================================================
 Pluie matricielle aux couleurs du drapeau transgenre
 Bleu clair #5BCEFA · Rose #F5A9B8 · Blanc #FFFFFF
 ============================================================ */

(() => {
  if (window.__pluieTrans) return;      // évite un double lancement
  window.__pluieTrans = true;

  /* ---- Réglages ---- */
  const DRAPEAU = ["#5BCEFA", "#F5A9B8", "#FFFFFF", "#F5A9B8", "#5BCEFA"];
  // "bandes"    : les 5 bandes horizontales du drapeau (la couleur change en tombant)
  // "colonnes"  : le drapeau couché, une couleur par groupe de colonnes
  // "aleatoire" : chaque goutte prend une couleur du drapeau au hasard
  const MODE = "bandes";
  const TAILLE = 16;                    // taille des caractères (px)
const VITESSE = 50;                   // ms entre deux images
const TRAINEE = 0.06;                 // plus petit = traînées plus longues
const CARACTERES =
"アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEF";

  /* ---- Canvas ---- */
  let canvas = document.getElementById("pluie");
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.id = "pluie";
    document.body.prepend(canvas);
  }
  const ctx = canvas.getContext("2d");
  let colonnes = 0, gouttes = [], couleurGoutte = [];

  const couleurHasard = () => DRAPEAU[Math.floor(Math.random() * DRAPEAU.length)];

  function redimensionner() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    colonnes = Math.ceil(innerWidth / TAILLE);
    gouttes = Array.from({ length: colonnes }, () => Math.random() * -innerHeight / TAILLE);
    couleurGoutte = Array.from({ length: colonnes }, couleurHasard);

    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, innerWidth, innerHeight);
  }

  function couleur(i, y) {
    const n = DRAPEAU.length;
    if (MODE === "bandes")   return DRAPEAU[Math.min(n - 1, Math.floor((y / innerHeight) * n))];
    if (MODE === "colonnes") return DRAPEAU[Math.min(n - 1, Math.floor((i / colonnes) * n))];
    return couleurGoutte[i];
  }

  function dessiner() {
    ctx.fillStyle = `rgba(0, 0, 0, ${TRAINEE})`;
    ctx.fillRect(0, 0, innerWidth, innerHeight);
    ctx.font = `${TAILLE}px "Fira Code", monospace`;

    for (let i = 0; i < colonnes; i++) {
      const y = gouttes[i] * TAILLE;
      if (y > 0) {
        ctx.fillStyle = couleur(i, y);
        ctx.fillText(CARACTERES[Math.floor(Math.random() * CARACTERES.length)], i * TAILLE, y);
      }
      if (y > innerHeight && Math.random() > 0.975) {
        gouttes[i] = 0;
        couleurGoutte[i] = couleurHasard();
      }
      gouttes[i]++;
    }
  }

  redimensionner();
  addEventListener("resize", redimensionner);

  const lent = matchMedia("(prefers-reduced-motion: reduce)").matches;
  setInterval(dessiner, lent ? VITESSE * 4 : VITESSE);
})();
