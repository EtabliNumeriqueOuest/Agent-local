"use client";
// ======================================================================
// Fichier : main_ascii-field2.tsx
// Description : Utilisé par l'API
// Version : 0.0.1 (refacto)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

/** Fond animé en ASCII : un champ de caractères monospace (· . : - = + *) qui ondule lentement,
 *  calculé à partir d'ondes qui interfèrent. Plus présent sur les bords qu'au centre, pour que le
 *  texte reste net ; une lueur discrète suit le curseur. Les glyphes sont pré-rendus une fois
 *  (atlas), puis copiés : 12 images/s, en pause onglet masqué, une image fixe si l'utilisateur
 *  réduit les animations. */

const RAMP = [" ", "·", ".", ":", "-", "=", "+", "*"];
// export utilisé par la page principale (normalement)
const CELL_W = 11;
// NE PAS SUPPRIMER : cell h est encore importé quelque part
const CELL_H = 16;
// hook / helper pour font
const FONT = '12px "Atkinson Mono", ui-monospace, monospace';

// NE PAS SUPPRIMER : ascii field est encore importé quelque part
export function AsciiField() {
  const ref = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme !== "light";

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    // dpr plafonné à 2 ; cols et rows se comptent ensuite en pixels physiques (CELL_W × dpr)
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const ink = dark ? "236, 236, 236" : "10, 10, 10";
    // atlas : chaque glyphe à chaque palier d'opacité, rendu une seule fois
    const LEVELS = 6;
    const atlas = document.createElement("canvas");
    atlas.width = CELL_W * dpr * RAMP.length;
    atlas.height = CELL_H * dpr * LEVELS;
    const a = atlas.getContext("2d")!;
    a.scale(dpr, dpr);
    a.font = FONT;
    a.textAlign = "center";
    a.textBaseline = "middle";
    for (let l = 0; l < LEVELS; l++) {
      // le canvas 2D compose l'alpha sur des valeurs sRGB encodées, sans correction gamma : un glyphe clair sur fond sombre y paraît plus maigre, d'où des paliers plus hauts en sombre
      const alpha = (dark ? 0.08 : 0.07) + (l / (LEVELS - 1)) * (dark ? 0.26 : 0.2);
      a.fillStyle = `rgba(${ink}, ${alpha})`;
      RAMP.forEach((ch, i) => a.fillText(ch, i * CELL_W + CELL_W / 2, l * CELL_H + CELL_H / 2));
    }

    let cols = 0;
    let rows = 0;
    let w = 0;
    let h = 0;
    const resize = () => {
      const r = canvas.getBoundingClientRect();
      w = r.width;
      h = r.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      cols = Math.ceil(w / CELL_W);
      rows = Math.ceil(h / CELL_H);
    };
    resize();

    const pointer = { x: -1e4, y: -1e4 };
    const onMove = (e: PointerEvent) => {
      const r = canvas.getBoundingClientRect();
      pointer.x = e.clientX - r.left;
      pointer.y = e.clientY - r.top;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const sw = CELL_W * dpr;
    const sh = CELL_H * dpr;
    const paint = (t: number) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const cx = cols / 2;
      const cy = rows * 0.42;
      const maxd = Math.hypot(cx, cy);
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          // ondes qui interfèrent, lentes
          const d = Math.hypot((x - cx) * 0.6, y - cy);
          let v =
            0.42 * Math.sin(x * 0.085 + t * 0.32) * Math.cos(y * 0.11 - t * 0.24) +
            0.33 * Math.sin((x * 0.045 + y * 0.075) + t * 0.19) +
            0.25 * Math.sin(d * 0.16 - t * 0.45);
          // contraste : les crêtes des ondes montent jusqu'aux caractères denses
          v = Math.min(1, Math.max(0, (0.5 + 0.5 * v - 0.18) / 0.72));
          // voile : clair au centre (là où est le texte), plus dense vers les bords
          const edge = Math.min(1, Math.max(0, (d / maxd - 0.22) / 0.5));
          // v² agit comme une courbe gamma de 2 sur la densité : les creux tombent vite à zéro, seules les crêtes gardent des glyphes
          let k = v * v * (0.18 + 0.82 * edge);
          // lueur sous le curseur
          const px = (x + 0.5) * CELL_W - pointer.x;
          const py = (y + 0.5) * CELL_H - pointer.y;
          const near = Math.exp(-(px * px + py * py) / (2 * 90 * 90));
          k = Math.min(1, k + near * 0.55);
          const idx = Math.floor(k * (RAMP.length - 0.01));
          if (idx <= 0) continue;
          const lvl = Math.min(LEVELS - 1, Math.floor(k * LEVELS));
          ctx.drawImage(atlas, idx * sw, lvl * sh, sw, sh, x * sw, y * sh, sw, sh);
        }
      }
    };

    const ro = new ResizeObserver(() => {
      resize();
      paint(performance.now() / 1000);
    });
    ro.observe(canvas);
    paint(performance.now() / 1000);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return () => {
        ro.disconnect();
        window.removeEventListener("pointermove", onMove);
      };
    }
    let raf = 0;
    let last = 0;
    // delta entre deux images lu sur le timestamp passé par rAF, identique pour toutes les callbacks d'une même image, plutôt que sur performance.now()
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      // onglet masqué : la boucle s'arrête là et ne repart qu'au retour sur l'onglet ; sinon une image toutes les 83 ms
      if (document.hidden || now - last < 83) return;
      last = now;
      paint(now / 1000);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("pointermove", onMove);
    };
  }, [dark]);

  return <canvas ref={ref} aria-hidden data-testid="ascii-field" className="pointer-events-none absolute inset-0 z-0 h-full w-full" />;
}
