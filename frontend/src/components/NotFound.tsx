import { Link } from "@tanstack/react-router";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-8">
      <div className="card max-w-md w-full text-center p-8">
        <div className="text-6xl mb-4">404</div>
        <h2 className="text-xl font-bold mb-2 text-(--foreground)">
          Page not found
        </h2>
        <p className="text-(--muted) mb-6 text-sm">
          The page you&apos;re looking for doesn&apos;t exist.
        </p>
        <Link to="/dashboard" className="btn-primary inline-block">
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
