import { Link } from "@tanstack/react-router";

export function AppHeader({ subtitle }: { subtitle: string }) {
  return (
    <header className="bg-navy text-navy-foreground">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-5 py-5">
        <Link to="/" className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-primary font-display text-lg text-primary-foreground">A</span>
          <span>
            <span className="block font-display text-lg leading-tight tracking-tight">Acid Solution</span>
            <span className="block text-xs uppercase tracking-[0.18em] text-navy-muted">{subtitle}</span>
          </span>
        </Link>
      </div>
    </header>
  );
}
