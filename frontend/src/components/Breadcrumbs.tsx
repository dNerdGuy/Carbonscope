
import { Link } from "@tanstack/react-router";

export interface Crumb {
  label: string;
  href?: string;
}

interface BreadcrumbsProps {
  items: Crumb[];
}

/**
 * Simple breadcrumb navigation component.
 * Last item is rendered as plain text (current page); prior items are links.
 */
export default function Breadcrumbs({ items }: BreadcrumbsProps) {
  if (items.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="text-sm text-[var(--muted)] mb-4">
      <ol className="flex items-center gap-1.5">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={i} className="flex items-center gap-1.5">
              {i > 0 && <span aria-hidden="true">/</span>}
              {isLast || !item.href ? (
                <span
                  className={
                    isLast ? "text-[var(--foreground)] font-medium" : ""
                  }
                >
                  {item.label}
                </span>
              ) : (
                <Link
                  to={item.href}
                  className="hover:text-[var(--foreground)] transition-colors"
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
