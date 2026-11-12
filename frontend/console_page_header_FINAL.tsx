// ======================================================================
// Fichier : console_page_header_FINAL.tsx
// Description : Module principal de cette partie
// Version : 2.5.1 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// ======================================================================
// fonction page header
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  // action aligné sur le bas du bloc titre (items-end) ; sous md il passe à la ligne, sous la description
  return (
    <header className="flex items-end justify-between gap-6 border-b border-border/70 px-6 pb-6 pt-14 md:px-10 md:pt-8">
      <div className="min-w-0">
        <div className="mb-2 text-[11px] font-medium text-[#cf5647] dark:text-[#f07a67]">
          {eyebrow}
        </div>
        <h1 className="text-2xl font-medium tracking-[-0.04em] sm:text-[28px]">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {action}
    </header>
  );
}
